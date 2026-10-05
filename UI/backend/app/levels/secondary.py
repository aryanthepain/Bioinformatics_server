"""Secondary structure: JPred 4, ProtBert-BFD-SS3 and experimental PDB structures.

Ported from the team notebook "SecondaryStructure.ipynb" (the function
analyze_secondary_structure). The seven steps keep their order, logic,
parameters, thresholds and helper-function names:

  1  JPred 4 single-sequence prediction (jpredapi), read from the .jnet file
  2  ProtBert-BFD-SS3 prediction per residue (Rostlab/prot_bert_bfd_ss3)
  3  consensus: the state both predictors agree on, "U" (uncertain) elsewhere
  4  secondary-structure profile of the consensus
  5  RCSB PDB sequence search (identity >= 30%, E-value <= 0.1, top 10)
  6  PDBe secondary structure of every hit, globally aligned onto the query
     and compared with the consensus
  7  final report: profile, agreement, helix and strand regions, PDB table

ONE CORRECTION (please tell the notebook's author): when the RCSB search finds
no structure, it answers HTTP 204 with an empty body, and the notebook's
rcsb_response.json() then crashed the whole analysis. This port treats that
answer as "no hits", which the notebook already reports as "No experimental
references found." Sequences that do have hits are not affected.

Plumbing changes only:
  * results are returned instead of printed or plotted (the three plots
    become residue-map tracks);
  * jpredapi checks the job once per call and this module does the waiting
    (every jpred_poll_seconds, at most jpred_max_wait, as in the notebook), so
    the wait stops as soon as the user presses Cancel; jpredapi's own web
    requests have no timeout, so its calls are time-limited as well;
  * the ProtBert model is loaded once and then reused (the notebook meant to
    do this, but its globals() check never saw the model, which was a local
    variable, so it reloaded the model on every call);
  * files live in a private temporary folder instead of /content;
  * the PDB comparison is sorted exactly like the notebook's pandas
    sort_values (including the order of ties), without needing pandas.

Additions used only for display (they never change a result):
  * each predictor's own helix/strand/coil profile, and JPred's confidence
    bands (High >= 7, Medium >= 4, Low below 4), from the notebook's
    exploratory cells;
  * the helix/strand/coil percentages of each experimental structure, as in
    the notebook's experimental summary table;
  * the structure of the best PDB match drawn along the query, as in the
    notebook's "Predicted vs Experimental" plot.
"""

import importlib.util
import inspect
import logging
import re
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import requests

from ..config import HTTP_TIMEOUT_SECONDS, JPRED_MAX_LENGTH, JPRED_TIMEOUT_SECONDS
from ..jobs import AnalysisCancelled, LevelSkipped, StageContext
from ..schemas import (
    EvidenceItem,
    Headline,
    LegendItem,
    LevelResult,
    Link,
    Metric,
    Note,
    Segment,
    Table,
    TableColumn,
    Tone,
    Track,
)

logger = logging.getLogger(__name__)

# Change this whenever the logic below changes, so cached results are not reused.
CACHE_VERSION = "secondary-1"

# The notebook's defaults for analyze_secondary_structure(). The app sends no
# protein names to JPred, so every job uses the notebook's default name.
PROTEIN_NAME = "Unknown_Protein"
MAX_PDB_HITS = 10
JPRED_POLL_SECONDS = 20
# jpred_max_wait (900 s in the notebook) is JPRED_TIMEOUT_SECONDS in app/config.py.

PROTBERT_MODEL_NAME = "Rostlab/prot_bert_bfd_ss3"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
JPRED_RESULTS_PAGE = "http://www.compbio.dundee.ac.uk/jpred4/results/{job_id}/{job_id}.results.html"

T = TypeVar("T")


# --- Setup checks and small helpers ---------------------------------------------------


_REQUIRED_LIBRARIES = (
    ("jpredapi", "jpredapi"),
    ("torch", "PyTorch"),
    ("transformers", "Transformers"),
    ("Bio", "Biopython"),
)


def missing_setup() -> list[str]:
    """Libraries that still need installing before the module can run (empty = ready)."""
    return [label for module, label in _REQUIRED_LIBRARIES if importlib.util.find_spec(module) is None]


def _jpredapi() -> Any:
    try:
        import jpredapi
    except ImportError as error:
        raise RuntimeError("jpredapi is not installed. Run `uv sync` in UI/backend, then restart the backend.") from error
    return jpredapi


def _ml_libraries() -> tuple[Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "PyTorch and Transformers are not installed. Run `uv sync` in UI/backend, then restart the backend."
        ) from error
    return torch, AutoTokenizer, AutoModelForTokenClassification


def _pairwise_aligner() -> Any:
    try:
        from Bio.Align import PairwiseAligner
    except ImportError as error:
        raise RuntimeError("Biopython is not installed. Run `uv sync` in UI/backend.") from error
    return PairwiseAligner


def _brief(text: str, limit: int = 200) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _bounded(call: Callable[[], T], ctx: StageContext, deadline: float, what: str) -> T:
    """Run a blocking call in a helper thread, so Cancel and a time limit still work.

    jpredapi sends its web requests without a timeout. If JPred stops answering,
    the helper thread is abandoned instead of holding up the whole analysis.
    """
    outcome: dict[str, Any] = {}

    def target() -> None:
        try:
            outcome["value"] = call()
        except BaseException as error:  # handed back to the caller below
            outcome["error"] = error

    worker = threading.Thread(target=target, name="secondary-jpred", daemon=True)
    worker.start()
    while True:
        worker.join(timeout=0.5)
        if not worker.is_alive():
            break
        ctx.check_cancelled()
        if time.monotonic() > deadline:
            raise TimeoutError(f"{what} did not answer in time.")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def _single_check_options(jpredapi: Any) -> dict[str, int]:
    """Options that make jpredapi.status() look at the job once and return.

    By default it re-checks up to 10 times, 60 s apart, inside a single call;
    the notebook's loop already waits jpred_poll_seconds between calls. Older
    jpredapi versions without these options are called exactly as in the notebook.
    """
    try:
        parameters = inspect.signature(jpredapi.status).parameters
    except (TypeError, ValueError):
        return {}
    if "max_attempts" in parameters and "wait_interval" in parameters:
        return {"max_attempts": 1, "wait_interval": 1}
    return {}


# --- 1. JPred ---------------------------------------------------------------------------


def run_jpred(
    sequence: str,
    protein_name: str,
    workdir: Path,
    ctx: StageContext,
    jpred_poll_seconds: float,
    jpred_max_wait: float,
) -> tuple[str, list[str], list[int]]:
    """Submit the sequence to JPred, wait for the .jnet file and parse it.

    Returns (JPred job ID, per-residue states, per-residue confidence 0-9).
    """
    jpredapi = _jpredapi()
    ctx.report("Submitting the sequence to JPred…")

    # JPred only accepts letters, numbers and "_"
    jpred_name = re.sub(r"[^A-Za-z0-9_]", "_", protein_name)

    fasta_path = workdir / "jpred_pipeline_input.fasta"

    with open(fasta_path, "w", encoding="utf-8") as f:
        f.write(f">{jpred_name}\n")

        for i in range(0, len(sequence), 80):
            f.write(sequence[i:i + 80] + "\n")

    try:
        jpred_response = _bounded(
            lambda: jpredapi.submit(
                mode="single",
                user_format="fasta",
                file=str(fasta_path),
                name=jpred_name,
                silent=True,
            ),
            ctx,
            time.monotonic() + HTTP_TIMEOUT_SECONDS,
            "JPred",
        )
    except requests.RequestException as error:
        raise RuntimeError(f"Could not reach JPred ({error.__class__.__name__}). Check the internet connection.") from error

    if jpred_response.status_code != 202:
        raise RuntimeError(f"JPred submission failed (HTTP {jpred_response.status_code}): {_brief(jpred_response.text)}")

    location = jpred_response.headers.get("Location", "")

    # Look for jp_XXXX in either the Location header
    # or the response text.
    match = re.search(r"(jp_[A-Za-z0-9]+)", location + " " + jpred_response.text)

    if not match:
        raise RuntimeError(
            f"Could not extract the JPred job ID (Location: {location!r}; response: {_brief(jpred_response.text)})."
        )

    jpred_job_id = match.group(1)

    jpred_root = workdir / f"jpred_{jpred_job_id}"
    jpred_root.mkdir(parents=True, exist_ok=True)

    check_options = _single_check_options(jpredapi)
    jnet_file: Path | None = None
    start_time = time.monotonic()
    deadline = start_time + jpred_max_wait

    while time.monotonic() - start_time < jpred_max_wait:
        try:
            _bounded(
                lambda: jpredapi.status(
                    jobid=jpred_job_id,
                    results_dir_path=str(jpred_root),
                    extract=True,
                    silent=True,
                    **check_options,
                ),
                ctx,
                deadline,
                "JPred",
            )
        except AnalysisCancelled:
            raise
        except Exception as error:  # as in the notebook: ignore it and check again
            logger.debug("JPred status check for %s did not succeed: %s", jpred_job_id, error)

        candidate = jpred_root / jpred_job_id / f"{jpred_job_id}.jnet"

        if candidate.exists():
            jnet_file = candidate
            break

        elapsed = time.monotonic() - start_time
        ctx.report(f"JPred is predicting (job {jpred_job_id}) · {_clock(elapsed)} elapsed")
        ctx.sleep(jpred_poll_seconds)

    if jnet_file is None:
        raise TimeoutError(f"JPred did not finish within {jpred_max_wait:.0f} seconds (job {jpred_job_id}).")

    jnet_text = jnet_file.read_text(encoding="utf-8", errors="ignore")

    pred_match = re.search(r"jnetpred:(.*)", jnet_text)
    conf_match = re.search(r"JNETCONF:(.*)", jnet_text)

    if pred_match is None or conf_match is None:
        raise RuntimeError("Could not parse JPred .jnet output.")

    jpred_raw = pred_match.group(1).strip().rstrip(",")
    jpred_conf_raw = conf_match.group(1).strip().rstrip(",")

    jpred_ss = jpred_raw.split(",")
    jpred_conf = [int(x) for x in jpred_conf_raw.split(",")]

    # JPred uses "-" for non-helix/non-strand.
    # We represent this as C = coil.
    jpred_ss = ["C" if x == "-" else x for x in jpred_ss]

    if len(jpred_ss) != len(sequence):
        raise RuntimeError(f"JPred prediction length mismatch: {len(jpred_ss)} vs {len(sequence)}")

    if len(jpred_conf) != len(sequence):
        raise RuntimeError(f"JPred confidence length mismatch: {len(jpred_conf)} vs {len(sequence)}")

    return jpred_job_id, jpred_ss, jpred_conf


# --- 2. ProtBert-BFD-SS3 ------------------------------------------------------------------


class _ProtBert:
    """The ProtBert tokenizer and model, loaded once for the whole server."""

    def __init__(self) -> None:
        model_name = PROTBERT_MODEL_NAME
        torch, AutoTokenizer, AutoModelForTokenClassification = _ml_libraries()
        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()


_protbert: _ProtBert | None = None
_protbert_lock = threading.Lock()


def run_protbert(sequence: str, ctx: StageContext) -> tuple[list[str], list[float], str]:
    """Per-residue ProtBert states and confidences (the highest softmax probability).

    Returns (states, confidences, device name).
    """
    global _protbert
    with _protbert_lock:
        if _protbert is None:
            ctx.report("Loading ProtBert-BFD-SS3 (first analysis only; the first download is about 1.7 GB)…")
            _protbert = _ProtBert()

        ctx.report("Predicting with ProtBert-BFD-SS3…")
        torch = _protbert.torch
        tokenizer = _protbert.tokenizer
        model = _protbert.model
        device = _protbert.device

        sequence_input = " ".join(list(sequence))

        inputs = tokenizer(sequence_input, return_tensors="pt", add_special_tokens=True)

        inputs = {key: value.to(device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        probabilities = torch.softmax(outputs.logits, dim=-1)

        predicted_ids = torch.argmax(outputs.logits, dim=-1)[0]

        token_confidence = torch.max(probabilities, dim=-1).values[0]

        labels = model.config.id2label

        # Remove [CLS] and [SEP]
        protbert_ss = [labels[int(x)] for x in predicted_ids[1:-1]]

        protbert_conf = [float(x) for x in token_confidence[1:-1]]

    if len(protbert_ss) != len(sequence):
        raise RuntimeError(f"ProtBert prediction length mismatch: {len(protbert_ss)} vs {len(sequence)}")

    return protbert_ss, protbert_conf, str(device)


# --- 3. Consensus and 4. profile ------------------------------------------------------------


def build_consensus(
    jpred_ss: list[str],
    jpred_conf: list[int],
    protbert_ss: list[str],
    protbert_conf: list[float],
) -> tuple[list[str], list[float | None]]:
    """The shared state where JPred and ProtBert agree, "U" where they do not."""
    consensus: list[str] = []
    consensus_confidence: list[float | None] = []

    for jpred_state, jpred_c, protbert_state, protbert_c in zip(jpred_ss, jpred_conf, protbert_ss, protbert_conf):
        if jpred_state == protbert_state:
            consensus.append(jpred_state)

            # Normalize JPred confidence 0-9
            jpred_probability = jpred_c / 9.0

            consensus_confidence.append((jpred_probability + protbert_c) / 2)

        else:
            consensus.append("U")
            consensus_confidence.append(None)

    return consensus, consensus_confidence


def predictor_agreement_percent(jpred_ss: list[str], protbert_ss: list[str]) -> float:
    """Share of residues where JPred and ProtBert predict the same state, in percent.

    Same arithmetic as the notebook's (JPred == ProtBert).mean() * 100.
    """
    predictor_agreement = [jpred == protbert for jpred, protbert in zip(jpred_ss, protbert_ss)]
    return sum(predictor_agreement) / len(predictor_agreement) * 100


def calculate_profile(consensus: list[str], total: int) -> dict[str, Any]:
    """Counts and percentages of H, E, C and U in the consensus (total = sequence length)."""
    helix_count = consensus.count("H")
    strand_count = consensus.count("E")
    coil_count = consensus.count("C")
    uncertain_count = consensus.count("U")

    return {
        "length": total,
        "alpha_helix_count": int(helix_count),
        "beta_strand_count": int(strand_count),
        "coil_count": int(coil_count),
        "uncertain_count": int(uncertain_count),
        "alpha_helix_percent": helix_count / total * 100,
        "beta_strand_percent": strand_count / total * 100,
        "coil_percent": coil_count / total * 100,
        "uncertain_percent": uncertain_count / total * 100,
    }


# --- 5. RCSB PDB search ------------------------------------------------------------------------


def search_rcsb(sequence: str, max_pdb_hits: int) -> list[dict[str, Any]]:
    """PDB polymer entities similar to the query (best first, as RCSB ranks them)."""
    rcsb_url = RCSB_SEARCH_URL

    rcsb_query = {
        "query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "target": "pdb_protein_sequence",
                "value": sequence,
                "identity_cutoff": 0.30,
                "evalue_cutoff": 0.1,
            },
        },
        "return_type": "polymer_entity",
        "request_options": {
            "results_verbosity": "verbose",
            "paginate": {
                "start": 0,
                "rows": max_pdb_hits,
            },
        },
    }

    rcsb_response = requests.post(
        rcsb_url,
        json=rcsb_query,
        headers={"Content-Type": "application/json"},
        timeout=HTTP_TIMEOUT_SECONDS,
    )

    rcsb_response.raise_for_status()

    # The correction: HTTP 204 (empty body) is RCSB's answer when nothing matches.
    if rcsb_response.status_code == 204 or not rcsb_response.content:
        rcsb_data: dict[str, Any] = {}
    else:
        rcsb_data = rcsb_response.json()

    rcsb_rows: list[dict[str, Any]] = []

    for hit in rcsb_data.get("result_set", []):
        pdb_entity = hit["identifier"]

        parts = pdb_entity.split("_")

        if len(parts) != 2:
            continue

        rcsb_rows.append(
            {
                "PDB_entity": pdb_entity,
                "RCSB_score": hit.get("score"),
                "PDB_ID": parts[0],
                "Entity_ID": parts[1],
            }
        )

    return rcsb_rows


# --- 6. PDB + PDBe + alignment ----------------------------------------------------------------


def get_pdb_sequence(pdb_entity: str) -> str:
    url = "https://www.rcsb.org/" "fasta/entity/" f"{pdb_entity}/download"

    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)

    response.raise_for_status()

    lines = response.text.splitlines()

    return "".join(line.strip() for line in lines if not line.startswith(">"))


def get_pdbe_secondary_structure(pdb_id: str, entity_id: str) -> Any:
    url = (
        "https://www.ebi.ac.uk/"
        "pdbe/api/pdb/entry/"
        "secondary_structure/"
        f"{pdb_id.lower()}/"
        f"{entity_id}"
    )

    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)

    if response.status_code != 200:
        return None

    return response.json()


def convert_pdbe_to_ss(pdbe_json: Any) -> tuple[str, str]:
    entry_key = next(iter(pdbe_json))

    entry = pdbe_json[entry_key]

    length = entry["length"]

    # Anything not explicitly annotated as
    # helix or strand is represented as coil.
    ss = ["C"] * length

    for structure in entry.get("data", []):
        if structure["name"] == "Helix":
            ss_type = "H"

        elif structure["name"] == "Strand":
            ss_type = "E"

        else:
            continue

        for region in structure.get("residues", []):
            start = region["startIndex"]
            end = region["endIndex"]

            for i in range(start, end + 1):
                if 1 <= i <= length:
                    ss[i - 1] = ss_type

    return entry["sequence"], "".join(ss)


def map_experimental_ss(query_aligned: str, target_aligned: str, target_ss: str) -> str:
    mapped = []
    target_position = 0

    for q, t in zip(query_aligned, target_aligned):
        if t != "-":
            ss_value = target_ss[target_position]

            target_position += 1

        else:
            ss_value = "-"

        if q != "-":
            mapped.append(ss_value)

    return "".join(mapped)


def _sort_like_pandas(rows: list[dict[str, Any]], column: str) -> list[dict[str, Any]]:
    """Rows in the order of pandas' sort_values(by=column, ascending=False, na_position="last").

    This is pandas' own procedure (nargsort with numpy's quicksort), so rows
    with equal values come out in the same order as in the notebook.
    """
    import numpy as np  # installed with Biopython

    values = np.array([np.nan if row[column] is None else float(row[column]) for row in rows], dtype=float)
    mask = np.isnan(values)
    idx = np.arange(len(values))
    non_nans = values[~mask][::-1]
    non_nan_idx = idx[~mask][::-1]
    indexer = non_nan_idx[non_nans.argsort(kind="quicksort")][::-1]
    indexer = np.concatenate([indexer, np.nonzero(mask)[0]])
    return [rows[int(i)] for i in indexer]


def compare_with_experimental(
    sequence: str,
    consensus: list[str],
    rcsb_rows: list[dict[str, Any]],
    ctx: StageContext,
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    """Map each hit's PDBe secondary structure onto the query and compare it with the consensus.

    Returns (aligner, experimental profiles, comparison rows sorted by
    agreement, entities that could not be compared).
    """
    PairwiseAligner = _pairwise_aligner()
    aligner = PairwiseAligner()
    aligner.mode = "global"

    experimental_profiles: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []  # display only: the notebook printed these

    for number, row in enumerate(rcsb_rows, start=1):
        pdb_entity = row["PDB_entity"]
        pdb_id = row["PDB_ID"]
        entity_id = row["Entity_ID"]

        ctx.report(f"Comparing with experimental structures · {number} of {len(rcsb_rows)} ({pdb_entity})")

        try:
            pdb_sequence = get_pdb_sequence(pdb_entity)

            pdbe_json = get_pdbe_secondary_structure(pdb_id, entity_id)

            if pdbe_json is None:
                skipped.append({"PDB_entity": pdb_entity, "reason": "PDBe returned no secondary-structure data."})
                continue

            experimental_sequence, experimental_ss = convert_pdbe_to_ss(pdbe_json)

            alignment = aligner.align(sequence, pdb_sequence)[0]

            query_aligned = str(alignment[0])

            target_aligned = str(alignment[1])

            mapped_experimental_ss = map_experimental_ss(query_aligned, target_aligned, experimental_ss)

            # ---------------------------------------------
            # Calculate aligned sequence identity
            # ---------------------------------------------

            identity_matches = 0
            identity_total = 0

            for q, t in zip(query_aligned, target_aligned):
                if q != "-" and t != "-":
                    identity_total += 1

                    if q == t:
                        identity_matches += 1

            sequence_identity = identity_matches / identity_total * 100 if identity_total > 0 else None

            # ---------------------------------------------
            # Compare predicted SS vs experimental SS
            # ---------------------------------------------

            comparable = 0
            matches = 0

            n = min(len(consensus), len(mapped_experimental_ss))

            for i in range(n):
                predicted = consensus[i]
                experimental = mapped_experimental_ss[i]

                if predicted == "U" or experimental == "-":
                    continue

                comparable += 1

                if predicted == experimental:
                    matches += 1

            ss_agreement = matches / comparable * 100 if comparable > 0 else None

            # Count observed elements
            experimental_helix_count = experimental_ss.count("H")

            experimental_strand_count = experimental_ss.count("E")

            experimental_coil_count = experimental_ss.count("C")

            experimental_profiles.append(
                {
                    "PDB_entity": pdb_entity,
                    "PDB_ID": pdb_id,
                    "Entity_ID": entity_id,
                    "sequence": experimental_sequence,
                    "secondary_structure": experimental_ss,
                }
            )

            comparison_rows.append(
                {
                    "PDB_entity": pdb_entity,
                    "Sequence_Identity_%": sequence_identity,
                    "Comparable_Residues": comparable,
                    "SS_Agreement_%": ss_agreement,
                    "Experimental_Helix_Residues": experimental_helix_count,
                    "Experimental_Strand_Residues": experimental_strand_count,
                    "Experimental_Coil_Residues": experimental_coil_count,
                }
            )

        except Exception as e:
            logger.info("Skipping %s: %s", pdb_entity, e)
            skipped.append({"PDB_entity": pdb_entity, "reason": _brief(str(e) or e.__class__.__name__)})

    if comparison_rows:
        comparison_rows = _sort_like_pandas(comparison_rows, "SS_Agreement_%")

    return aligner, experimental_profiles, comparison_rows, skipped


# --- 7. Final report -------------------------------------------------------------------------


def get_regions(ss: list[str] | str, target: str) -> list[tuple[int, int]]:
    regions = []
    start = None

    for i, value in enumerate(ss, start=1):
        if value == target:
            if start is None:
                start = i

        elif start is not None:
            regions.append((start, i - 1))

            start = None

    if start is not None:
        regions.append((start, len(ss)))

    return regions


def map_top_experimental(
    sequence: str,
    consensus: list[str],
    comparison_rows: list[dict[str, Any]],
    experimental_profiles: list[dict[str, Any]],
    aligner: Any,
) -> dict[str, str] | None:
    """The best PDB match's structure along the query (the notebook's third plot)."""
    if not comparison_rows:
        return None

    top_pdb = comparison_rows[0]["PDB_entity"]

    top_experimental = next((x for x in experimental_profiles if x["PDB_entity"] == top_pdb), None)

    if top_experimental is None:
        return None

    experimental_ss = top_experimental["secondary_structure"]

    pdb_sequence = top_experimental["sequence"]

    alignment = aligner.align(sequence, pdb_sequence)[0]

    query_aligned = str(alignment[0])

    target_aligned = str(alignment[1])

    mapped_experimental_ss = map_experimental_ss(query_aligned, target_aligned, experimental_ss)

    n = min(len(consensus), len(mapped_experimental_ss))

    return {"PDB_entity": top_pdb, "mapped_secondary_structure": mapped_experimental_ss[:n]}


def confidence_level(x: int) -> str:
    """JPred confidence bands from the notebook's exploratory cells."""
    if x >= 7:
        return "High"
    elif x >= 4:
        return "Medium"
    else:
        return "Low"


# --- The notebook's pipeline -------------------------------------------------------------------


def analyze_secondary_structure(
    sequence: str,
    ctx: StageContext,
    protein_name: str = PROTEIN_NAME,
    max_pdb_hits: int = MAX_PDB_HITS,
    jpred_poll_seconds: float = JPRED_POLL_SECONDS,
    jpred_max_wait: float = JPRED_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run the notebook's seven steps and return everything (JSON-safe, no DataFrames)."""

    # ============================================================
    # 0. CLEAN + VALIDATE INPUT
    # ============================================================

    sequence = "".join(sequence.split()).upper()

    valid_aas = set("ACDEFGHIKLMNPQRSTVWY")
    invalid = set(sequence) - valid_aas

    if invalid:
        raise ValueError(f"Invalid amino acids found: {invalid}")

    if len(sequence) < 25:
        raise ValueError("Protein sequence must contain at least 25 residues.")

    # ============================================================
    # 1. JPRED
    # ============================================================

    with tempfile.TemporaryDirectory(prefix="pfp-secondary-", ignore_cleanup_errors=True) as directory:
        jpred_job_id, jpred_ss, jpred_conf = run_jpred(
            sequence, protein_name, Path(directory), ctx, jpred_poll_seconds, jpred_max_wait
        )

    # ============================================================
    # 2. PROTBERT-BFD-SS3
    # ============================================================

    protbert_ss, protbert_conf, device = run_protbert(sequence, ctx)

    # ============================================================
    # 3. CONSENSUS
    # ============================================================

    ctx.report("Building the JPred / ProtBert consensus…")
    consensus, consensus_confidence = build_consensus(jpred_ss, jpred_conf, protbert_ss, protbert_conf)

    agreement_percentage = predictor_agreement_percent(jpred_ss, protbert_ss)

    # ============================================================
    # 4. SECONDARY STRUCTURE PROFILE
    # ============================================================

    total = len(sequence)
    profile = calculate_profile(consensus, total)

    # ============================================================
    # 5. RCSB PDB SEARCH
    # ============================================================

    ctx.report("Searching the RCSB PDB for experimentally solved structures…")
    try:
        rcsb_rows = search_rcsb(sequence, max_pdb_hits)
    except requests.RequestException as error:
        raise RuntimeError(f"The RCSB PDB search failed ({_brief(str(error) or error.__class__.__name__)}).") from error

    # ============================================================
    # 6. PDB + PDBe + ALIGNMENT
    # ============================================================

    aligner, experimental_profiles, comparison_rows, skipped = compare_with_experimental(
        sequence, consensus, rcsb_rows, ctx
    )

    # ============================================================
    # 7. FINAL REPORT (the plots become residue-map tracks)
    # ============================================================

    helix_regions = get_regions(consensus, "H")
    strand_regions = get_regions(consensus, "E")

    try:
        top_experimental_mapping = map_top_experimental(
            sequence, consensus, comparison_rows, experimental_profiles, aligner
        )
    except Exception as error:  # display only; never fails the analysis
        logger.warning("Could not map the best PDB match onto the query: %s", error)
        top_experimental_mapping = None

    return {
        "protein_name": protein_name,
        "sequence": sequence,
        "length": total,
        "jpred_job_id": jpred_job_id,
        "secondary_structure": "".join(consensus),
        "secondary_structure_table": {
            "JPred": jpred_ss,
            "JPred_Confidence": jpred_conf,
            "ProtBert": protbert_ss,
            "ProtBert_Confidence": protbert_conf,
            "Consensus": consensus,
            "Consensus_Confidence": consensus_confidence,
        },
        "profile": profile,
        "predictor_agreement_percent": agreement_percentage,
        "rcsb_hits": rcsb_rows,
        "experimental_profiles": experimental_profiles,
        "experimental_comparison": comparison_rows,
        # Additions for the interface:
        "skipped_pdb_entities": skipped,
        "helix_regions": helix_regions,
        "strand_regions": strand_regions,
        "top_experimental_mapping": top_experimental_mapping,
        "protbert_device": device,
    }


# --- Translating the results for the interface -----------------------------------------------

_STATE_TONES: dict[str, Tone] = {
    "H": "helix",
    "E": "strand",
    "C": "coil",
    "U": "uncertain",
    "-": "neutral",
}

_SS_LEGEND = [
    LegendItem(label="Helix", tone="helix"),
    LegendItem(label="Strand", tone="strand"),
    LegendItem(label="Coil", tone="coil"),
]

# The notebook's JPred confidence bands, coloured like other confidence tracks.
_CONFIDENCE_TONES: dict[str, Tone] = {
    "High": "confidence-very-high",
    "Medium": "confidence-low",
    "Low": "confidence-very-low",
}

_CONFIDENCE_LEGEND = [
    LegendItem(label="High (7–9)", tone="confidence-very-high"),
    LegendItem(label="Medium (4–6)", tone="confidence-low"),
    LegendItem(label="Low (0–3)", tone="confidence-very-low"),
]


def _runs(tones: list[Tone]) -> list[tuple[Tone, int, int]]:
    """Collapse one tone per residue into (tone, start, end) runs, 1-based."""
    runs: list[tuple[Tone, int, int]] = []
    for index, tone in enumerate(tones, start=1):
        if runs and runs[-1][0] == tone:
            runs[-1] = (tone, runs[-1][1], index)
        else:
            runs.append((tone, index, index))
    return runs


def _states_track(
    key: str,
    label: str,
    caption: str,
    tones: list[Tone],
    legend: list[LegendItem],
    overview: bool,
) -> Track:
    return Track(
        key=key,
        label=label,
        caption=caption,
        style="states",
        segments=[Segment(start=start, end=end, tone=tone) for tone, start, end in _runs(tones)],
        legend=legend,
        overview=overview,
    )


def _state_tones(states: list[str] | str) -> list[Tone]:
    return [_STATE_TONES.get(state, "neutral") for state in states]


def _shares(states: list[str]) -> str:
    """One predictor's own profile, as printed in the notebook's exploratory cells."""
    total = len(states)
    helix, strand, coil = (states.count(state) / total * 100 for state in ("H", "E", "C"))
    return f"{helix:.2f}% helix · {strand:.2f}% strand · {coil:.2f}% coil"


def _percent(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}%"


def _split_entity(pdb_entity: str) -> tuple[str, str]:
    pdb_id, _, entity_id = pdb_entity.partition("_")
    return pdb_id.upper(), entity_id


def _with_share(count: int, total: int) -> str:
    """'107 (75.4%)', as in the notebook's experimental summary table."""
    return f"{count} ({100 * count / total:.1f}%)" if total > 0 else str(count)


def _to_level_result(results: dict[str, Any]) -> LevelResult:
    length = int(results["length"])
    profile = results["profile"]
    table = results["secondary_structure_table"]
    jpred_ss: list[str] = table["JPred"]
    jpred_conf: list[int] = table["JPred_Confidence"]
    protbert_ss: list[str] = table["ProtBert"]
    protbert_conf: list[float] = table["ProtBert_Confidence"]
    consensus: list[str] = table["Consensus"]
    consensus_confidence: list[float | None] = table["Consensus_Confidence"]
    agreement = float(results["predictor_agreement_percent"])
    job_id = str(results["jpred_job_id"])
    rcsb_rows: list[dict[str, Any]] = results["rcsb_hits"]
    comparison: list[dict[str, Any]] = results["experimental_comparison"]
    skipped: list[dict[str, str]] = results["skipped_pdb_entities"]
    helix_regions: list[tuple[int, int]] = results["helix_regions"]
    strand_regions: list[tuple[int, int]] = results["strand_regions"]
    lengths = {item["PDB_entity"]: len(item["secondary_structure"]) for item in results["experimental_profiles"]}
    best = comparison[0] if comparison else None
    best_agreement = best["SS_Agreement_%"] if best is not None else None
    agreeing = sum(1 for jpred, protbert in zip(jpred_ss, protbert_ss) if jpred == protbert)

    # --- Summary sentence
    summary = (
        f"Consensus of JPred and ProtBert: {profile['alpha_helix_percent']:.2f}% α-helix, "
        f"{profile['beta_strand_percent']:.2f}% β-strand and {profile['coil_percent']:.2f}% coil; "
        f"the two predictors disagree on {profile['uncertain_percent']:.2f}% of residues."
    )
    if best is not None and best_agreement is not None:
        pdb_id, entity_id = _split_entity(best["PDB_entity"])
        summary += (
            f" The best-matching experimental structure, PDB {pdb_id} (entity {entity_id}), agrees with the "
            f"consensus at {best_agreement:.1f}% of {best['Comparable_Residues']} comparable residues."
        )
    elif not rcsb_rows:
        summary += " No experimental references found in the RCSB PDB."
    else:
        summary += " None of the experimental structures found could be compared."

    # --- Key figures and grouped properties
    metrics = [
        Metric(
            label="α-helix",
            value=f"{profile['alpha_helix_percent']:.2f}%",
            hint=f"{profile['alpha_helix_count']} of {length} residues (consensus H).",
        ),
        Metric(
            label="β-strand",
            value=f"{profile['beta_strand_percent']:.2f}%",
            hint=f"{profile['beta_strand_count']} of {length} residues (consensus E).",
        ),
        Metric(
            label="Coil",
            value=f"{profile['coil_percent']:.2f}%",
            hint=f"{profile['coil_count']} of {length} residues (consensus C).",
        ),
        Metric(
            label="Uncertain",
            value=f"{profile['uncertain_percent']:.2f}%",
            hint=f"{profile['uncertain_count']} of {length} residues where JPred and ProtBert disagree (U).",
        ),
    ]

    counts = "Consensus profile · residues"
    metrics += [
        Metric(label="α-helix (H)", value=str(profile["alpha_helix_count"]), group=counts),
        Metric(label="β-strand (E)", value=str(profile["beta_strand_count"]), group=counts),
        Metric(label="Coil (C)", value=str(profile["coil_count"]), group=counts),
        Metric(label="Uncertain (U)", value=str(profile["uncertain_count"]), group=counts),
        Metric(label="Protein length", value=str(length), group=counts),
    ]

    predictors = "Individual predictors"
    metrics += [
        Metric(label="JPred 4", value=_shares(jpred_ss), group=predictors),
        Metric(label="ProtBert-BFD-SS3", value=_shares(protbert_ss), group=predictors),
        Metric(
            label="Mean ProtBert confidence",
            value=f"{sum(protbert_conf) / len(protbert_conf):.3f}",
            hint="Average probability ProtBert gave to its predicted state.",
            group=predictors,
        ),
    ]
    agreed_confidence = [value for value in consensus_confidence if value is not None]
    if agreed_confidence:
        metrics.append(
            Metric(
                label="Mean consensus confidence",
                value=f"{sum(agreed_confidence) / len(agreed_confidence):.3f}",
                hint="(JPred confidence ÷ 9 + ProtBert probability) ÷ 2, averaged over the residues where both agree.",
                group=predictors,
            )
        )
    metrics += [
        Metric(label="JPred job", value=job_id, group=predictors),
        Metric(label="ProtBert model", value=PROTBERT_MODEL_NAME, group=predictors),
        Metric(label="Device", value=str(results.get("protbert_device", "")) or "—", group=predictors),
    ]

    levels = [confidence_level(value) for value in jpred_conf]
    confidence_group = "JPred confidence (0–9)"
    metrics += [
        Metric(label="High (7–9)", value=f"{levels.count('High')} residues", group=confidence_group),
        Metric(label="Medium (4–6)", value=f"{levels.count('Medium')} residues", group=confidence_group),
        Metric(label="Low (0–3)", value=f"{levels.count('Low')} residues", group=confidence_group),
    ]

    experimental_group = "Experimental comparison · RCSB PDB / PDBe"
    metrics += [
        Metric(label="PDB entities found", value=str(len(rcsb_rows)), group=experimental_group),
        Metric(label="Structures compared", value=str(len(comparison)), group=experimental_group),
        Metric(
            label="Best SS agreement",
            value=f"{best_agreement:.1f}% ({best['PDB_entity']})" if best is not None and best_agreement is not None else "—",
            group=experimental_group,
        ),
        Metric(
            label="Search cut-offs",
            value=f"identity ≥ 30%, E-value ≤ 0.1, top {MAX_PDB_HITS}",
            group=experimental_group,
        ),
    ]

    # --- Evidence
    evidence = [
        EvidenceItem(
            polarity="neutral",
            text=f"JPred and ProtBert agree on {agreement:.2f}% of residues ({agreeing} of {length}).",
        )
    ]
    if best is not None and best_agreement is not None:
        evidence.append(
            EvidenceItem(
                polarity="positive",
                text=(
                    f"{len(comparison)} experimentally solved PDB {'entity was' if len(comparison) == 1 else 'entities were'} "
                    f"compared; the best, {best['PDB_entity']}, matches the consensus at {best_agreement:.1f}% of "
                    f"{best['Comparable_Residues']} comparable residues."
                ),
            )
        )
    elif not rcsb_rows:
        evidence.append(
            EvidenceItem(
                polarity="negative",
                text="No experimental references found (RCSB PDB search: identity ≥ 30%, E-value ≤ 0.1).",
            )
        )
    else:
        evidence.append(
            EvidenceItem(
                polarity="negative",
                text=f"None of the {len(rcsb_rows)} PDB entities found could be compared with the prediction.",
            )
        )
    if profile["uncertain_count"] > 0:
        evidence.append(
            EvidenceItem(
                polarity="neutral",
                text=(
                    f"{profile['uncertain_count']} residues ({profile['uncertain_percent']:.2f}%) are uncertain because "
                    "the predictors disagree; they are left out of the experimental comparison."
                ),
            )
        )

    # --- Notes
    notes = [
        Note(
            kind="observation",
            title="How the consensus is built",
            text=(
                "Each residue takes the state that JPred and ProtBert both predict (H helix, E strand, C coil); "
                "where they disagree it is marked U (uncertain) and left out of the comparison with experimental "
                "structures. In the PDBe data, residues not annotated as helix or strand count as coil."
            ),
        )
    ]
    if skipped:
        listed = "; ".join(f"{item['PDB_entity']}: {item['reason']}" for item in skipped)
        notes.append(Note(kind="caution", title="PDB entities not compared", text=_brief(listed, 400)))

    # --- Tracks: the consensus on the combined map; the rest in this section
    tracks = [
        _states_track(
            "secondary-structure",
            "Secondary structure",
            "Consensus · JPred ∩ ProtBert",
            _state_tones(consensus),
            [*_SS_LEGEND, LegendItem(label="Predictors disagree", tone="uncertain")],
            overview=True,
        )
    ]
    mapping = results.get("top_experimental_mapping")
    if mapping:
        mapped = str(mapping["mapped_secondary_structure"])[:length].ljust(length, "-")
        pdb_id, entity_id = _split_entity(str(mapping["PDB_entity"]))
        legend = list(_SS_LEGEND)
        if "-" in mapped:
            legend.append(LegendItem(label="Not aligned", tone="neutral"))
        tracks.append(
            _states_track(
                "experimental",
                f"PDB {pdb_id}",
                f"Experimental · entity {entity_id} (PDBe)",
                _state_tones(mapped),
                legend,
                overview=False,
            )
        )
    jpred_legend = list(_SS_LEGEND)
    if any(state not in ("H", "E", "C") for state in jpred_ss):
        jpred_legend.append(LegendItem(label="Other", tone="neutral"))
    tracks += [
        _states_track("jpred", "JPred 4", "Secondary · prediction", _state_tones(jpred_ss), jpred_legend, overview=False),
        _states_track(
            "protbert",
            "ProtBert-BFD-SS3",
            "Secondary · prediction",
            _state_tones(protbert_ss),
            list(_SS_LEGEND),
            overview=False,
        ),
        _states_track(
            "jpred-confidence",
            "JPred confidence",
            "Secondary · JPred 0–9",
            [_CONFIDENCE_TONES[level] for level in levels],
            list(_CONFIDENCE_LEGEND),
            overview=False,
        ),
    ]

    # --- Tables
    tables = [
        Table(
            key="experimental-structures",
            title="Experimentally solved structures",
            caption=(
                f"RCSB PDB sequence search (identity ≥ 30%, E-value ≤ 0.1, top {MAX_PDB_HITS}); PDBe secondary "
                "structure aligned to the query. Helix, strand and coil count the residues of the whole PDB entity."
            ),
            columns=[
                TableColumn(key="entity", label="PDB entity", mono=True),
                TableColumn(key="identity", label="Identity", align="right"),
                TableColumn(key="comparable", label="Comparable residues", align="right"),
                TableColumn(key="agreement", label="SS agreement", align="right"),
                TableColumn(key="helix", label="Helix", align="right"),
                TableColumn(key="strand", label="Strand", align="right"),
                TableColumn(key="coil", label="Coil", align="right"),
            ],
            rows=[
                {
                    "entity": str(row["PDB_entity"]),
                    "identity": _percent(row["Sequence_Identity_%"]),
                    "comparable": str(row["Comparable_Residues"]),
                    "agreement": _percent(row["SS_Agreement_%"]),
                    "helix": _with_share(row["Experimental_Helix_Residues"], lengths.get(row["PDB_entity"], 0)),
                    "strand": _with_share(row["Experimental_Strand_Residues"], lengths.get(row["PDB_entity"], 0)),
                    "coil": _with_share(row["Experimental_Coil_Residues"], lengths.get(row["PDB_entity"], 0)),
                }
                for row in comparison
            ],
        ),
        Table(
            key="predicted-regions",
            title="Predicted regions",
            caption="Consensus α-helix and β-strand regions, as in the notebook's final report",
            columns=[
                TableColumn(key="element", label="Element"),
                TableColumn(key="residues", label="Residues", align="right", mono=True),
                TableColumn(key="length", label="Length", align="right"),
            ],
            rows=[
                {"element": element, "residues": f"{start}–{end}", "length": str(end - start + 1)}
                for element, regions in (("α-helix", helix_regions), ("β-strand", strand_regions))
                for start, end in regions
            ],
        ),
    ]

    # --- Links
    links = [Link(label=f"JPred results ({job_id})", url=JPRED_RESULTS_PAGE.format(job_id=job_id))]
    seen: set[str] = set()
    for row in comparison:
        pdb_id, _ = _split_entity(str(row["PDB_entity"]))
        if pdb_id and pdb_id not in seen:
            seen.add(pdb_id)
            links.append(Link(label=f"PDB {pdb_id}", url=f"https://www.rcsb.org/structure/{pdb_id}"))

    # --- Raw output: the notebook's return value, JSON-safe (one entry per residue, residue 1 first)
    raw = {
        "jpred_job_id": job_id,
        "length": length,
        "secondary_structure": results["secondary_structure"],
        "secondary_structure_table": {
            "AA": results["sequence"],
            "JPred": "".join(jpred_ss),
            "JPred_Confidence": list(jpred_conf),
            "ProtBert": "".join(protbert_ss),
            "ProtBert_Confidence": [round(value, 6) for value in protbert_conf],
            "Consensus": "".join(consensus),
            "Consensus_Confidence": [None if value is None else round(value, 6) for value in consensus_confidence],
        },
        "profile": profile,
        "predictor_agreement_percent": agreement,
        "predicted_regions": {
            "alpha_helix": [list(region) for region in helix_regions],
            "beta_strand": [list(region) for region in strand_regions],
        },
        "rcsb_hits": rcsb_rows,
        "experimental_comparison": comparison,
        "experimental_profiles": results["experimental_profiles"],
        "skipped_pdb_entities": skipped,
    }

    return LevelResult(
        source="live",
        headline=Headline(value=f"{agreement:.2f}%", label="JPred / ProtBert agreement"),
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )


# --- The entry point used by the app -----------------------------------------------------------


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Run the notebook's pipeline and return the result for the interface."""
    length = len(sequence)
    if length > JPRED_MAX_LENGTH:
        raise LevelSkipped(
            f"JPred accepts at most {JPRED_MAX_LENGTH} residues, so secondary structure "
            f"was not predicted for this {length:,}-residue sequence."
        )
    missing = missing_setup()
    if missing:
        raise LevelSkipped(
            "Secondary-structure analysis is not set up yet (missing: "
            + ", ".join(missing)
            + "). Run `uv sync` in UI/backend, then restart the backend."
        )
    results = analyze_secondary_structure(sequence, ctx)
    return _to_level_result(results)