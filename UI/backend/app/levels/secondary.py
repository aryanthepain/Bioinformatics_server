"""Secondary structure: the team's final notebook "SecondaryStructureFinal.ipynb".

Five single-sequence predictors, all running locally, and their majority consensus:

  S4PRED          GRU network (first checkpoint; S4PRED_FULL_ENSEMBLE = False)
  ESM-2 SS3       ESM-2 (8M) fine-tuned for 3-state secondary structure
  PSIPRED-single  PSIPRED 4 without a sequence profile (built from source)
  GOR IV          the GOR IV C code (gor4 package)
  Chou-Fasman     simplified propensity windows

  consensus: the state predicted by more than half of the methods that ran
  (and at least 3 of them), "U" (uncertain) elsewhere; the "neural consensus"
  does the same for S4PRED, ESM-2 SS3 and PSIPRED-single only. Then the
  profile, the regions and the pairwise agreement between the methods.

  optional (notebook cell 5, RUN_PDB_REFERENCES): the consensus compared with the
  secondary structure of up to 3 experimentally solved PDB structures (RCSB
  sequence search, PDBe annotation, global alignment).

Here it runs in two phases:
  1. analyze(): the five predictors (the notebook's analyze_secondary_structure).
     The result is shown straight away.
  2. refine(): the PDB comparison (compare_pdb_references). The notebook leaves it off
     by default; the app runs it in the background, because the final prediction uses
     it as a consistency check. The result and the prediction are updated when it
     finishes; if the lookup fails, the predictors' result stays.

The notebook's functions keep their names, parameters, thresholds and logic.
Plumbing changes only:
  * the assets folder (the notebook's ASSETS) comes from configuration; it is made
    by scripts/setup_secondary.py, the notebook's set-up cell;
  * the libraries are imported on first use, so the app starts without them;
    @torch.inference_mode() is applied inside the two neural predict functions;
  * the models are loaded once per process (the notebook's lru_cache) under a lock,
    so the start-up preload (app/warmup.py) and an analysis cannot load them twice;
    importing and loading also take turns with the other levels (app/mllock.py), because
    Transformers fails when two threads import it at the same moment;
  * progress messages, and Cancel is honoured between the predictors;
  * the notebook's pandas tables are returned as JSON instead of displayed or exported,
    and its plot becomes residue-map tracks;
  * the RCSB search and PDBe requests may take up to 60 seconds instead of the notebook's 6
    (PDB_TIMEOUT_SECONDS): they run in the background, and RCSB often needs longer.
Left out: the repeat (warm) benchmark of cell 4 and the run-all timer of cell 7
(scripts/check_secondary.py reports both timings), and the CSV export of cell 6.
"""

import functools
import importlib.util
import logging
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

import requests

from ..config import SECONDARY_DATA_DIR
from ..jobs import LevelSkipped, StageContext
from ..mllock import ML_LOCK
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
CACHE_VERSION = "secondary-2"
NOTEBOOK = "SecondaryStructureFinal.ipynb"

# =====================================================================================
# Notebook cell 0 - settings (the downloads themselves are in scripts/setup_secondary.py)
# =====================================================================================

ASSETS = SECONDARY_DATA_DIR
ESM_ID = "AmelieSchreiber/esm2_t6_8M_UR50D-finetuned-secondary-structure"
ESM_REVISION = "24b37e9d0341861d4c0e675ee771990d5a519b90"
S4PRED_FULL_ENSEMBLE = False  # True downloads the entire 413 MB archive.

# Notebook cell 1 - the run's switches
PROTEIN_NAME = "Unknown_Protein"  # analyze_secondary_structure's default name
RUN_PDB_REFERENCES = True  # False in the notebook; the app runs it as the background step (see above)
MAX_PDB_HITS = 3  # compare_pdb_references' default
# The notebook gives each RCSB / PDBe request 6 seconds. RCSB's sequence search often needs
# longer (it timed out for 3 of the app's 5 examples), and here the comparison runs in the
# background after the result is shown, so a slow answer delays nothing: 60 seconds.
PDB_TIMEOUT_SECONDS = 60
# RCSB runs each sequence search as a job and answers "500 ... did not complete ticketId ...
# within 30000 ms" when the job takes longer than 30 s (busy servers, longer sequences). The job
# keeps running at RCSB, and asking again with the same sequence returns its result as soon as it
# is done (scripts/diagnose_rcsb.py showed one finishing after about 90 s). So a busy RCSB or PDBe
# (no answer in time, a server error) is asked again after these waits - about 10 minutes in all,
# in the background - before the lookup counts as unavailable; a result whose lookup stayed
# unavailable tries again the next time it is opened.
PDB_RETRY_WAITS = (15, 30, 60, 90, 120, 120)

# The notebook's cell-2 imports, filled in by _import_libraries() on first use.
np: Any = None
pd: Any = None
torch: Any = None
PairwiseAligner: Any = None
GOR4: Any = None
AutoModelForTokenClassification: Any = None
AutoTokenizer: Any = None
DEVICE: Any = None
_IMPORT_LOCK = threading.Lock()
_LOAD_LOCK = threading.RLock()  # model loading: one thread at a time (analysis or start-up preload)

_LIBRARIES = (
    ("numpy", "NumPy"),
    ("pandas", "pandas"),
    ("torch", "PyTorch"),
    ("transformers", "Transformers"),
    ("gor4", "gor4 (GOR IV)"),
    ("Bio", "Biopython"),
)


def _hf_snapshot() -> Path:
    """Where huggingface_hub keeps the pinned ESM-2 SS3 checkpoint inside ASSETS/hf."""
    return ASSETS / "hf" / f"models--{ESM_ID.replace('/', '--')}" / "snapshots" / ESM_REVISION


def _asset_files() -> list[tuple[Path, str]]:
    weights = [f"weights_{i}.pt" for i in range(1, 6)] if S4PRED_FULL_ENSEMBLE else ["weights_1.pt"]
    return (
        [(ASSETS / "s4pred" / "network.py", "S4PRED code")]
        + [(ASSETS / "s4pred" / "weights" / name, f"S4PRED {name}") for name in weights]
        + [(ASSETS / "psipred" / "src" / name, f"PSIPRED {name} (built)") for name in ("seq2mtx", "psipred", "psipass2")]
        + [(ASSETS / "psipred" / "data" / name, f"PSIPRED {name}")
           for name in ("weights.dat", "weights.dat2", "weights.dat3", "weights_p2.dat")]
        + [(_hf_snapshot() / "model.safetensors", "ESM-2 SS3 checkpoint")]
    )


def missing_setup() -> list[str]:
    """Libraries and downloaded files still missing (empty = ready)."""
    missing = [label for module, label in _LIBRARIES if importlib.util.find_spec(module) is None]
    missing += [label for path, label in _asset_files() if not path.is_file()]
    return missing


def _import_libraries() -> None:
    """Notebook cell 2's imports and device set-up."""
    global np, pd, torch, PairwiseAligner, GOR4, AutoModelForTokenClassification, AutoTokenizer, DEVICE
    with _IMPORT_LOCK, ML_LOCK:  # ML_LOCK: the levels' threads import the ML libraries in turn (app/mllock.py)
        if DEVICE is not None:
            return
        import numpy as _np
        import pandas as _pd
        import torch as _torch
        from Bio.Align import PairwiseAligner as _PairwiseAligner
        from gor4 import GOR4 as _GOR4
        from transformers import AutoModelForTokenClassification as _AutoModel
        from transformers import AutoTokenizer as _AutoTokenizer

        np, pd, torch = _np, _pd, _torch
        PairwiseAligner, GOR4 = _PairwiseAligner, _GOR4
        AutoModelForTokenClassification, AutoTokenizer = _AutoModel, _AutoTokenizer
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        DEVICE = device


# =====================================================================================
# Notebook cell 2 - the five predictors
# =====================================================================================

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
STATES = "HEC"


def normalize_sequence(raw):
    lines = raw.strip().splitlines()
    if lines and lines[0].startswith(">"):
        lines = lines[1:]
    sequence = "".join("".join(lines).split()).upper()
    if set(sequence) - set(AMINO_ACIDS):
        raise ValueError("Use one sequence containing only the 20 standard amino acids.")
    if not 25 <= len(sequence) <= 1000:
        raise ValueError("This five-method notebook supports 25–1,000 residues per query.")
    return sequence


@functools.lru_cache(maxsize=1)
def load_s4pred():
    location = ASSETS / "s4pred"
    spec = importlib.util.spec_from_file_location("secondary_s4pred_network", location / "network.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if S4PRED_FULL_ENSEMBLE:
        model = module.S4PRED()
        submodels = [getattr(model, f"model_{index}") for index in range(1, 6)]
    else:
        model = module.GRUnet()
        submodels = [model]
    for index, submodel in enumerate(submodels, start=1):
        path = location / "weights" / f"weights_{index}.pt"
        submodel.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    return model.eval().to(DEVICE)


def predict_s4pred(sequence, model):
    with torch.inference_mode():
        alphabet = "ARNDCQEGHILKMFPSTWYV"  # Official S4PRED residue-index order.
        tokens = torch.tensor([[alphabet.index(aa) for aa in sequence]], device=DEVICE)
        scores = model(tokens).softmax(dim=-1).cpu().numpy()
        return decode_scores(scores, "CHE")


@functools.lru_cache(maxsize=1)
def load_esm():
    snapshot = {
        "revision": ESM_REVISION,
        "cache_dir": str(ASSETS / "hf"),
        "local_files_only": True,
    }
    tokenizer = AutoTokenizer.from_pretrained(ESM_ID, **snapshot)
    model = AutoModelForTokenClassification.from_pretrained(
        ESM_ID, use_safetensors=True, **snapshot
    ).eval().to(DEVICE)
    return tokenizer, model


def predict_esm(sequence, resources):
    with torch.inference_mode():
        tokenizer, model = resources
        encoded = tokenizer(sequence, return_tensors="pt", return_special_tokens_mask=True)
        mask = encoded.pop("special_tokens_mask")[0].eq(0).to(DEVICE)
        logits = model(**encoded.to(DEVICE)).logits[0, mask]
        return decode_scores(logits.softmax(dim=-1).cpu().numpy(), "CHE")  # Model card label order.


def decode_scores(scores, labels):
    best = scores.argmax(axis=1)
    return "".join(labels[i] for i in best), scores.max(axis=1)


def parse_ss2(text, sequence):
    rows = [line.split() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    if ([int(row[0]) for row in rows] != list(range(1, len(sequence) + 1))
            or "".join(row[1] for row in rows) != sequence):
        raise ValueError("PSIPRED positions or residues differ from the query.")
    states = "".join(row[2] for row in rows)
    scores = [float(row[3 + "CHE".index(row[2])]) for row in rows]
    return states, scores


def predict_psipred(sequence, _):
    location = ASSETS / "psipred"
    binary, weights = location / "src", location / "data"
    with TemporaryDirectory(prefix="secondary-psipred-") as scratch:
        work = Path(scratch)
        fasta = work / "query.fasta"
        fasta.write_text(">query\n" + "\n".join(sequence[i:i+60] for i in range(0, len(sequence), 60)) + "\n")
        matrix, first, second = (work / name for name in ("query.mtx", "query.ss", "query.ss2"))
        with matrix.open("w") as output:
            subprocess.run([binary / "seq2mtx", fasta], stdout=output, check=True, timeout=30, cwd=work)
        with first.open("w") as output:
            subprocess.run([binary / "psipred", matrix, *(weights / name for name in
                           ("weights.dat", "weights.dat2", "weights.dat3"))],
                           stdout=output, check=True, timeout=30, cwd=work)
        subprocess.run([binary / "psipass2", weights / "weights_p2.dat",
                        "1", "1.0", "1.0", second, first],
                       stdout=subprocess.DEVNULL, check=True, timeout=30, cwd=work)
        return parse_ss2(second.read_text(), sequence)


@functools.lru_cache(maxsize=1)
def load_gor():
    return GOR4()


def predict_gor(sequence, model):
    result = model.predict(sequence)
    states = result["predictions"]
    scores = [row[STATES.index(state)] for row, state in zip(result["probabilities"], states)]
    return states, scores


# Published relative alpha and beta propensities, indexed by AMINO_ACIDS.
HELIX_PROPENSITY = dict(zip(AMINO_ACIDS, (
    1.42, .70, 1.01, 1.51, 1.13, .57, 1.00, 1.08, 1.16, 1.21,
    1.45, .67, .57, 1.11, .98, .77, .83, 1.06, 1.08, .69,
)))
STRAND_PROPENSITY = dict(zip(AMINO_ACIDS, (
    .83, 1.19, .54, .37, 1.38, .75, .87, 1.60, .74, 1.30,
    1.05, .89, .55, 1.10, .93, .75, 1.19, 1.70, 1.37, 1.47,
)))


def predict_propensity(sequence, _):
    # Simplified Chou–Fasman-style nucleation windows. Vote strength is local
    # mean propensity. Residues outside qualifying windows default to coil.
    tracks = []
    for table, width, minimum in ((HELIX_PROPENSITY, 6, 4), (STRAND_PROPENSITY, 5, 3)):
        values = [table[aa] for aa in sequence]
        support = np.zeros(len(sequence))
        for start in range(len(sequence) - width + 1):
            end = start + width
            window = values[start:end]
            mean = sum(window) / width
            if sum(value > 1 for value in window) >= minimum and mean > 1:
                support[start:end] = np.maximum(support[start:end], mean)
        tracks.append(support)
    return "".join("H" if h > e else "E" if e > h else "C"
                   for h, e in zip(*tracks)), None


PREDICTORS = {
    "S4PRED": (load_s4pred, predict_s4pred),
    "ESM-2 SS3": (load_esm, predict_esm),
    "PSIPRED-single": (None, predict_psipred),
    "GOR IV": (load_gor, predict_gor),
    "Chou–Fasman": (None, predict_propensity),
}


def load_models() -> None:
    """Load the three models now (the start-up preload, app/warmup.py)."""
    _import_libraries()
    with _LOAD_LOCK, ML_LOCK:
        for loader, _ in PREDICTORS.values():
            if loader is not None:
                loader()


# =====================================================================================
# Notebook cell 3 - consensus and report
# =====================================================================================

def consensus_track(votes, length):
    if not votes:
        return np.full(length, "U"), np.zeros(length, dtype=int)
    matrix = np.array([list(track) for track in votes.values()])
    counts = np.stack([(matrix == state).sum(axis=0) for state in STATES])
    support = counts.max(axis=0)
    winners = np.array(list(STATES))[counts.argmax(axis=0)]
    majority = (support > len(votes) / 2) & (len(votes) >= 3)
    return np.where(majority, winners, "U"), support


def analyze_secondary_structure(sequence, protein_name="Unknown_Protein", ctx: StageContext | None = None):
    started = perf_counter()
    sequence = normalize_sequence(sequence)
    residues = pd.DataFrame({"Position": range(1, len(sequence) + 1), "AA": list(sequence)})
    tracks, timings = {}, []
    for name, (loader, predict) in PREDICTORS.items():
        if ctx is not None:
            ctx.report(f"Predicting with {name}…")
        tick = perf_counter()
        try:
            with _LOAD_LOCK, ML_LOCK:
                resources = loader() if loader else None
            load_seconds = perf_counter() - tick
            tick = perf_counter()
            track, scores = predict(sequence, resources)
            if len(track) != len(sequence) or set(track) - set(STATES):
                raise ValueError("Invalid secondary structure track.")
            if scores is not None:
                scores = np.asarray(scores, dtype=float)
                if scores.shape != (len(sequence),) or not np.isfinite(scores).all():
                    raise ValueError("Invalid per-residue scores.")
                residues[f"{name}_Score"] = scores
            tracks[name] = track
            residues[name] = list(track)
            timings.append((name, load_seconds, perf_counter() - tick, "OK"))
        except (OSError, RuntimeError, ValueError, ImportError, subprocess.SubprocessError) as error:
            timings.append((name, None, None, f"{type(error).__name__}: {error}"))
    if ctx is not None:
        ctx.check_cancelled()

    residues["Consensus"], residues["Votes_for_top_call"] = consensus_track(tracks, len(sequence))
    residues["Models_available"] = len(tracks)
    core = {name: tracks[name] for name in list(PREDICTORS)[:3] if name in tracks}
    residues["Neural_consensus"], _ = consensus_track(core, len(sequence))
    calls = residues["Consensus"].to_numpy()
    changes = np.r_[0, np.flatnonzero(calls[1:] != calls[:-1]) + 1, len(calls)]
    regions = pd.DataFrame([
        (calls[start], start + 1, end, end - start)
        for start, end in zip(changes[:-1], changes[1:])
    ], columns=["State", "Start", "End", "Length"])
    counts = residues["Consensus"].value_counts().reindex(list("HECU"), fill_value=0)
    profile = pd.DataFrame({"Residues": counts, "Percent": counts * 100 / len(sequence)})
    agreement = pd.DataFrame(
        [[100 * (residues[left] == residues[right]).mean() for right in tracks] for left in tracks],
        index=list(tracks), columns=list(tracks),
    )
    return {
        "protein_name": protein_name, "sequence": sequence, "length": len(sequence),
        "secondary_structure": "".join(calls), "secondary_structure_table": residues,
        "profile": profile, "regions": regions, "pairwise_agreement_percent": agreement,
        "predictors_used": list(tracks),
        "timings": pd.DataFrame(timings, columns=["Predictor", "Load_s", "Predict_s", "Status"]),
        "elapsed_seconds": perf_counter() - started,
    }


# =====================================================================================
# Notebook cell 5 - comparison with experimental PDB structures (optional)
# =====================================================================================

def compare_pdb_references(report, max_hits=3):
    started = perf_counter()
    sequence = report["sequence"]
    consensus = report["secondary_structure"]
    query = {
        "query": {"type": "terminal", "service": "sequence", "parameters": {
            "target": "pdb_protein_sequence", "value": sequence,
            "identity_cutoff": .30, "evalue_cutoff": .1,
        }},
        "return_type": "polymer_entity",
        "request_options": {
            "results_content_type": ["experimental"],
            "paginate": {"start": 0, "rows": max_hits},
        },
    }
    response = requests.post("https://search.rcsb.org/rcsbsearch/v2/query", json=query, timeout=PDB_TIMEOUT_SECONDS)
    response.raise_for_status()
    hits = [] if response.status_code == 204 else response.json().get("result_set", [])

    def compare(hit):
        entity = hit["identifier"]
        pdb, entity_id = entity.split("_", 1)
        try:
            url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/secondary_structure/{pdb.lower()}/{entity_id}"
            reply = requests.get(url, timeout=PDB_TIMEOUT_SECONDS)
            reply.raise_for_status()
            annotation = next(iter(reply.json().values()))
            target = annotation["sequence"]
            if len(target) != annotation["length"]:
                raise ValueError("PDBe sequence and annotation lengths differ.")
            states = np.full(len(target), "?", dtype="<U1")
            for feature in annotation.get("data", []):
                state = {"Helix": "H", "Strand": "E"}.get(feature["name"])
                if state:
                    for region in feature["residues"]:
                        first, last = region["startIndex"], region["endIndex"]
                        if not 1 <= first <= last <= len(target):
                            raise ValueError("PDBe annotation index is out of bounds.")
                        states[first - 1:last] = state
            aligner = PairwiseAligner(mode="global", match_score=2, mismatch_score=-1,
                                      open_gap_score=-5, extend_gap_score=-.5)
            alignment = aligner.align(sequence, target)[0]
            positions = alignment.indices
            paired = (positions >= 0).all(axis=0)
            query_indices, target_indices = positions[:, paired]
            mapped = np.full(len(sequence), "?", dtype="<U1")
            mapped[query_indices] = states[target_indices]
            votes = np.array(list(consensus))
            comparable = (mapped != "?") & (votes != "U")
            return {
                "PDB_entity": entity, "Aligned_query_pct": 100 * paired.sum() / len(sequence),
                "Aligned_identity_pct": 100 * (np.array(list(sequence))[query_indices]
                                              == np.array(list(target))[target_indices]).mean()
                                        if paired.any() else None,
                "Comparable_residues": int(comparable.sum()),
                "SS_agreement_pct": 100 * (votes[comparable] == mapped[comparable]).mean()
                                    if comparable.any() else None,
                "Mapped_H_E_track": "".join(mapped), "Status": "OK",
            }
        except (requests.RequestException, ValueError, KeyError, StopIteration) as error:
            return {"PDB_entity": entity, "Status": str(error)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        table = pd.DataFrame(pool.map(compare, hits))
    return table, perf_counter() - started


# =====================================================================================
# The notebook's tables as JSON (the result's raw output)
# =====================================================================================

def _plain(value: Any) -> Any:
    """A JSON-safe copy: numpy numbers become Python numbers, NaN becomes None."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and value != value:
        return None
    return value


def _report_to_raw(report: dict[str, Any]) -> dict[str, Any]:
    table = report["secondary_structure_table"]
    used = list(report["predictors_used"])
    profile = report["profile"]
    agreement = report["pairwise_agreement_percent"]
    return _plain({
        "notebook": NOTEBOOK,
        "protein_name": report["protein_name"],
        "sequence": report["sequence"],
        "length": report["length"],
        "secondary_structure": report["secondary_structure"],
        "neural_consensus": "".join(table["Neural_consensus"].tolist()),
        "votes_for_top_call": [int(value) for value in table["Votes_for_top_call"].tolist()],
        "models_available": len(used),
        "predictors_used": used,
        "predictions": {name: "".join(table[name].tolist()) for name in used},
        "scores": {
            name: [round(float(value), 6) for value in table[f"{name}_Score"].tolist()]
            for name in used if f"{name}_Score" in table.columns
        },
        "profile": {
            state: {"residues": int(profile.loc[state, "Residues"]), "percent": float(profile.loc[state, "Percent"])}
            for state in "HECU"
        },
        "regions": [
            {"State": str(row.State), "Start": int(row.Start), "End": int(row.End), "Length": int(row.Length)}
            for row in report["regions"].itertuples(index=False)
        ],
        "pairwise_agreement_percent": {
            left: {right: float(agreement.loc[left, right]) for right in used} for left in used
        },
        "timings": [
            {"Predictor": row.Predictor, "Load_s": row.Load_s, "Predict_s": row.Predict_s, "Status": row.Status}
            for row in report["timings"].itertuples(index=False)
        ],
        "elapsed_seconds": report["elapsed_seconds"],
        "device": str(DEVICE),
        "pdb_references": {"status": "pending" if RUN_PDB_REFERENCES else "off", "max_hits": MAX_PDB_HITS, "rows": []},
    })


def _pdb_to_raw(table: Any, seconds: float) -> dict[str, Any]:
    columns = ["PDB_entity", "Aligned_query_pct", "Aligned_identity_pct", "Comparable_residues",
               "SS_agreement_pct", "Mapped_H_E_track", "Status"]
    rows = []
    for record in table.to_dict("records"):
        row = {column: record.get(column) for column in columns}
        rows.append(row)
    rows = _plain(rows)
    for row in rows:  # pandas fills the columns an error row lacks with NaN
        if row.get("Comparable_residues") is not None:
            row["Comparable_residues"] = int(row["Comparable_residues"])
    return {"status": "success", "max_hits": MAX_PDB_HITS, "rows": rows, "seconds": round(seconds, 3)}


def best_reference(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The reference shown first: at least 20 comparable residues, then the highest agreement
    (the same choice as the final prediction's secondary check, app/verdict.py)."""
    usable = [row for row in rows if row.get("Status") == "OK" and row.get("SS_agreement_pct") is not None
              and row.get("Comparable_residues") is not None]
    if not usable:
        return None
    return max(usable, key=lambda row: (row["Comparable_residues"] >= 20, row["SS_agreement_pct"]))


# =====================================================================================
# Translating the results for the interface
# =====================================================================================

_STATE_TONES: dict[str, Tone] = {"H": "helix", "E": "strand", "C": "coil", "U": "uncertain", "?": "neutral"}
_SS_LEGEND = [
    LegendItem(label="Helix", tone="helix"),
    LegendItem(label="Strand", tone="strand"),
    LegendItem(label="Coil", tone="coil"),
]
_TRACK_KEYS = {
    "S4PRED": "s4pred",
    "ESM-2 SS3": "esm2-ss3",
    "PSIPRED-single": "psipred",
    "GOR IV": "gor4",
    "Chou–Fasman": "chou-fasman",
}
_CAPTIONS = {
    "S4PRED": "GRU network, single sequence",
    "ESM-2 SS3": "fine-tuned ESM-2 (8M)",
    "PSIPRED-single": "PSIPRED 4, no profile",
    "GOR IV": "information theory",
    "Chou–Fasman": "propensity windows",
}


def _runs(tones: list[Tone]) -> list[tuple[Tone, int, int]]:
    """Collapse one tone per residue into (tone, start, end) runs, 1-based."""
    runs: list[tuple[Tone, int, int]] = []
    for index, tone in enumerate(tones, start=1):
        if runs and runs[-1][0] == tone:
            runs[-1] = (tone, runs[-1][1], index)
        else:
            runs.append((tone, index, index))
    return runs


def _states_track(key: str, label: str, caption: str, states: str, legend: list[LegendItem], overview: bool) -> Track:
    tones = [_STATE_TONES.get(state, "neutral") for state in states]
    return Track(
        key=key, label=label, caption=caption, style="states",
        segments=[Segment(start=start, end=end, tone=tone) for tone, start, end in _runs(tones)],
        legend=legend, overview=overview,
    )


def _shares(states: str) -> str:
    total = len(states)
    helix, strand, coil = (states.count(state) / total * 100 for state in ("H", "E", "C"))
    return f"{helix:.1f}% helix · {strand:.1f}% strand · {coil:.1f}% coil"


def _pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}%"


def _secs(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} s"


def _split_entity(pdb_entity: str) -> tuple[str, str]:
    pdb_id, _, entity_id = pdb_entity.partition("_")
    return pdb_id.upper(), entity_id


def build_level_result(raw: dict[str, Any]) -> LevelResult:
    length = int(raw["length"])
    profile = raw["profile"]
    used: list[str] = raw["predictors_used"]
    predictions: dict[str, str] = raw["predictions"]
    consensus: str = raw["secondary_structure"]
    agreement: dict[str, dict[str, float]] = raw["pairwise_agreement_percent"]
    pdb = raw.get("pdb_references") or {"status": "off", "rows": []}
    rows: list[dict[str, Any]] = pdb.get("rows") or []
    compared = [row for row in rows if row.get("Status") == "OK"]
    best = best_reference(rows)
    pct = {state: profile[state]["percent"] for state in "HECU"}
    count = {state: profile[state]["residues"] for state in "HECU"}
    failed = [row for row in raw["timings"] if row["Status"] != "OK"]
    neural = [name for name in list(PREDICTORS)[:3] if name in used]

    # --- Summary
    summary = (
        f"Majority consensus of {len(used)} of 5 predictors: {pct['H']:.1f}% α-helix, {pct['E']:.1f}% β-strand and "
        f"{pct['C']:.1f}% coil; {pct['U']:.1f}% of residues have no majority (uncertain)."
    )
    if pdb["status"] == "pending":
        summary += " The comparison with experimental PDB structures is running."
    elif pdb["status"] == "unavailable":
        summary += " The comparison with experimental PDB structures was unavailable."
    elif pdb["status"] == "success" and best is not None:
        pdb_id, entity_id = _split_entity(str(best["PDB_entity"]))
        summary += (
            f" The best experimental reference, PDB {pdb_id} (entity {entity_id}), agrees with the consensus at "
            f"{best['SS_agreement_pct']:.1f}% of {best['Comparable_residues']} comparable helix/strand residues."
        )
    elif pdb["status"] == "success" and not rows:
        summary += " No experimental PDB hits."
    elif pdb["status"] == "success":
        summary += " None of the experimental PDB structures found could be compared."
    if len(used) < 5:
        summary += f" Partial result: {', '.join(row['Predictor'] for row in failed)} did not run."

    # --- Key figures and grouped properties
    metrics = [
        Metric(label="α-helix", value=f"{pct['H']:.1f}%", hint=f"{count['H']} of {length} residues (consensus H)."),
        Metric(label="β-strand", value=f"{pct['E']:.1f}%", hint=f"{count['E']} of {length} residues (consensus E)."),
        Metric(label="Coil", value=f"{pct['C']:.1f}%", hint=f"{count['C']} of {length} residues (consensus C)."),
        Metric(label="Uncertain", value=f"{pct['U']:.1f}%",
               hint=f"{count['U']} of {length} residues where no state has a majority of the predictors (U)."),
    ]
    profile_group = "Consensus profile · residues"
    metrics += [
        Metric(label="α-helix (H)", value=str(count["H"]), group=profile_group),
        Metric(label="β-strand (E)", value=str(count["E"]), group=profile_group),
        Metric(label="Coil (C)", value=str(count["C"]), group=profile_group),
        Metric(label="Uncertain (U)", value=str(count["U"]), group=profile_group),
        Metric(label="Protein length", value=str(length), group=profile_group),
    ]
    predictor_group = "Individual predictors"
    metrics.append(Metric(label="Methods used", value=f"{len(used)}/5", group=predictor_group))
    for name in PREDICTORS:
        metrics.append(Metric(
            label=name,
            value=_shares(predictions[name]) if name in predictions else "did not run",
            group=predictor_group,
        ))
    metrics.append(Metric(label="Device", value=str(raw.get("device") or "—"), group=predictor_group))
    experimental_group = "Experimental references · RCSB PDB / PDBe"
    status_text = {
        "pending": "running", "success": "done", "unavailable": "unavailable", "off": "off",
    }.get(pdb["status"], str(pdb["status"]))
    metrics += [
        Metric(label="PDB lookup", value=status_text, group=experimental_group),
        Metric(label="PDB entities found", value=str(len(rows)) if pdb["status"] == "success" else "—",
               group=experimental_group),
        Metric(label="Structures compared", value=str(len(compared)) if pdb["status"] == "success" else "—",
               group=experimental_group),
        Metric(
            label="Best SS agreement",
            value=f"{best['SS_agreement_pct']:.1f}% ({best['PDB_entity']})" if best is not None else "—",
            group=experimental_group,
        ),
        Metric(label="Search cut-offs", value=f"identity ≥ 30%, E-value ≤ 0.1, top {pdb.get('max_hits', MAX_PDB_HITS)}",
               group=experimental_group),
    ]

    # --- Evidence
    evidence = [EvidenceItem(
        polarity="neutral" if len(used) >= 3 else "negative",
        text=(f"{len(used)} of 5 methods ran; each residue takes the state predicted by a majority of them "
              f"({len(used) // 2 + 1} or more)." if len(used) >= 3 else
              f"Only {len(used)} of 5 methods ran, so no residue has a consensus (at least 3 are needed)."),
    )]
    if len(neural) >= 2:
        pairs = [agreement[a][b] for i, a in enumerate(neural) for b in neural[i + 1:]]
        evidence.append(EvidenceItem(
            polarity="neutral",
            text=(f"The neural predictors ({', '.join(neural)}) agree pairwise on {min(pairs):.1f}–{max(pairs):.1f}% "
                  "of residues."),
        ))
    if best is not None:
        pdb_id, entity_id = _split_entity(str(best["PDB_entity"]))
        evidence.append(EvidenceItem(
            polarity="positive",
            text=(f"{len(compared)} experimentally solved PDB {'entity was' if len(compared) == 1 else 'entities were'} "
                  f"compared; the best, {best['PDB_entity']}, matches the consensus at {best['SS_agreement_pct']:.1f}% "
                  f"of {best['Comparable_residues']} comparable helix/strand residues."),
        ))
    elif pdb["status"] == "success" and not rows:
        evidence.append(EvidenceItem(
            polarity="negative",
            text="No experimental PDB hits (RCSB sequence search: identity ≥ 30%, E-value ≤ 0.1).",
        ))
    elif pdb["status"] == "success":
        evidence.append(EvidenceItem(
            polarity="negative",
            text=f"None of the {len(rows)} PDB entities found could be compared with the prediction.",
        ))
    if count["U"] > 0:
        evidence.append(EvidenceItem(
            polarity="neutral",
            text=(f"{count['U']} residues ({pct['U']:.1f}%) are uncertain because no state has a majority; they are "
                  "left out of the experimental comparison."),
        ))

    # --- Notes
    notes = [Note(
        kind="observation",
        title="How the consensus is built",
        text=("Each residue takes the state (H helix, E strand, C coil) that more than half of the methods that ran "
              "predict, provided at least 3 ran; otherwise it is U (uncertain). The neural consensus does the same "
              "with S4PRED, ESM-2 SS3 and PSIPRED-single only. Chou–Fasman uses simplified nucleation windows: "
              "residues outside a qualifying window are coil. In the PDB comparison only residues that PDBe "
              "annotates as helix or strand, and that are not uncertain, are compared."),
    )]
    if failed:
        notes.append(Note(
            kind="caution",
            title="Partial result",
            text=("Check the predictor status before interpreting the consensus: "
                  + "; ".join(f"{row['Predictor']}: {row['Status']}" for row in failed))[:600],
        ))
    if pdb["status"] == "unavailable":
        tries = int(pdb.get("attempts") or 1)
        notes.append(Note(
            kind="caution",
            title="PDB lookup unavailable",
            text=(f"{str(pdb.get('error') or '')[:300].rstrip('.')}"
                  + (f" (tried {tries} times)." if tries > 1 else ".")
                  + " The RCSB PDB search service did not answer properly, so the consensus could not be compared "
                    "with experimental structures; this is tried again the next time this sequence is analysed."),
        ))
    skipped = [row for row in rows if row.get("Status") != "OK"]
    if skipped:
        notes.append(Note(
            kind="caution",
            title="PDB entities not compared",
            text="; ".join(f"{row['PDB_entity']}: {row['Status']}" for row in skipped)[:400],
        ))

    # --- Tracks: the consensus on the combined map; the rest in this section
    tracks = [_states_track(
        "secondary-structure", "Secondary structure", f"Consensus · majority of {len(used)} predictors",
        consensus, [*_SS_LEGEND, LegendItem(label="No majority", tone="uncertain")], overview=True,
    )]
    if best is not None and best.get("Mapped_H_E_track"):
        pdb_id, entity_id = _split_entity(str(best["PDB_entity"]))
        mapped = str(best["Mapped_H_E_track"])[:length].ljust(length, "?")
        tracks.append(_states_track(
            "experimental", f"PDB {pdb_id}", f"Experimental · entity {entity_id} (PDBe helix/strand)", mapped,
            [LegendItem(label="Helix", tone="helix"), LegendItem(label="Strand", tone="strand"),
             LegendItem(label="Not annotated or not aligned", tone="neutral")],
            overview=False,
        ))
    tracks.append(_states_track(
        "neural-consensus", "Neural consensus", "S4PRED · ESM-2 SS3 · PSIPRED-single", raw["neural_consensus"],
        [*_SS_LEGEND, LegendItem(label="No majority", tone="uncertain")], overview=False,
    ))
    for name in PREDICTORS:
        if name in predictions:
            tracks.append(_states_track(
                _TRACK_KEYS[name], name, f"Secondary · {_CAPTIONS[name]}", predictions[name], list(_SS_LEGEND),
                overview=False,
            ))

    # --- Tables
    state_name = {"H": "α-helix", "E": "β-strand", "C": "coil", "U": "uncertain"}
    tables = [Table(
        key="consensus-regions",
        title="Consensus regions",
        caption="Runs of the same consensus state along the sequence, as in the notebook's regions table",
        columns=[
            TableColumn(key="state", label="State"),
            TableColumn(key="residues", label="Residues", align="right", mono=True),
            TableColumn(key="length", label="Length", align="right"),
        ],
        rows=[
            {"state": f"{state_name.get(row['State'], row['State'])} ({row['State']})",
             "residues": f"{row['Start']}–{row['End']}", "length": str(row["Length"])}
            for row in raw["regions"]
        ],
    )]
    if pdb["status"] == "success":
        tables.append(Table(
            key="pdb-references",
            title="Experimental PDB references",
            caption=(f"RCSB PDB sequence search (identity ≥ 30%, E-value ≤ 0.1, top {pdb.get('max_hits', MAX_PDB_HITS)}); "
                     "PDBe helix/strand annotation aligned to the query. Agreement counts the comparable residues: "
                     "annotated helix or strand in PDBe and not uncertain in the consensus"),
            columns=[
                TableColumn(key="entity", label="PDB entity", mono=True),
                TableColumn(key="aligned", label="Query aligned", align="right"),
                TableColumn(key="identity", label="Identity (aligned)", align="right"),
                TableColumn(key="comparable", label="Comparable residues", align="right"),
                TableColumn(key="agreement", label="SS agreement", align="right"),
                TableColumn(key="status", label="Status"),
            ],
            rows=[
                {
                    "entity": str(row["PDB_entity"]),
                    "aligned": _pct(row.get("Aligned_query_pct")),
                    "identity": _pct(row.get("Aligned_identity_pct")),
                    "comparable": "—" if row.get("Comparable_residues") is None else str(row["Comparable_residues"]),
                    "agreement": _pct(row.get("SS_agreement_pct")),
                    "status": str(row.get("Status")),
                }
                for row in rows
            ],
        ))
    tables.append(Table(
        key="pairwise-agreement",
        title="Pairwise agreement between predictors",
        caption="Percentage of residues on which two predictors give the same state",
        columns=[TableColumn(key="predictor", label="Predictor")]
        + [TableColumn(key=_TRACK_KEYS[name], label=name, align="right", mono=True) for name in used],
        rows=[
            {"predictor": left, **{_TRACK_KEYS[right]: f"{agreement[left][right]:.1f}" for right in used}}
            for left in used
        ],
    ))
    tables.append(Table(
        key="predictor-timings",
        title="Predictors",
        caption="Each method's status, and the seconds it took to load (first analysis only) and to predict",
        columns=[
            TableColumn(key="predictor", label="Predictor"),
            TableColumn(key="load", label="Load", align="right"),
            TableColumn(key="predict", label="Predict", align="right"),
            TableColumn(key="status", label="Status"),
        ],
        rows=[
            {"predictor": row["Predictor"], "load": _secs(row["Load_s"]), "predict": _secs(row["Predict_s"]),
             "status": str(row["Status"])}
            for row in raw["timings"]
        ],
    ))

    # --- Links
    links: list[Link] = []
    seen: set[str] = set()
    for row in compared:
        pdb_id, _ = _split_entity(str(row["PDB_entity"]))
        if pdb_id and pdb_id not in seen:
            seen.add(pdb_id)
            links.append(Link(label=f"PDB {pdb_id}", url=f"https://www.rcsb.org/structure/{pdb_id}"))

    return LevelResult(
        source="live",
        headline=Headline(value=f"{100 - pct['U']:.1f}%", label="residues with a majority call"),
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )


# =====================================================================================
# The entry points used by the app
# =====================================================================================

def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Phase 1: the five predictors (notebook cell 4's analyze_secondary_structure)."""
    missing = missing_setup()
    if missing:
        raise LevelSkipped(
            "Secondary-structure analysis is not set up yet (missing: " + ", ".join(missing)
            + "). Run `uv sync` and then `uv run python scripts/setup_secondary.py` in UI/backend, "
            "then restart the backend."
        )
    try:
        sequence = normalize_sequence(sequence)
    except ValueError as error:
        raise LevelSkipped(str(error)) from None
    ctx.report("Loading the secondary-structure libraries…")
    _import_libraries()
    report = analyze_secondary_structure(sequence, PROTEIN_NAME, ctx)
    return build_level_result(_report_to_raw(report))


def needs_refinement(result: LevelResult) -> bool:
    """True while the PDB comparison has not succeeded for this result: it has not run, the RCSB
    search was unavailable, or structures were found but none could be compared because PDBe did
    not answer properly (a time-out or a server error). Such a result tries again when it is next
    opened."""
    if not RUN_PDB_REFERENCES or result.source != "live" or not isinstance(result.raw, dict):
        return False
    pdb = result.raw.get("pdb_references")
    if not isinstance(pdb, dict):
        return False
    if pdb.get("status") in ("pending", "unavailable"):
        return True
    rows = pdb.get("rows") or []
    return (pdb.get("status") == "success" and bool(rows)
            and not any(row.get("Status") == "OK" for row in rows)
            and any(_is_transient(str(row.get("Status"))) for row in rows))


_TRANSIENT_TEXT = re.compile(
    r"\b(429|5\d\d) (Client|Server) Error|timed out|Connection (aborted|reset|refused)|Max retries exceeded"
    r"|RemoteDisconnected|Temporary failure|Failed to establish",
    re.IGNORECASE,
)


def _error_text(error: requests.RequestException) -> str:
    """The error, plus what the server said with it (RCSB explains its errors in the answer's body)."""
    text = str(error)
    response = getattr(error, "response", None)
    body = " ".join(str(getattr(response, "text", "") or "").split())[:200] if response is not None else ""
    return f"{text} | server said: {body}" if body else text


def _is_transient(error: BaseException | str) -> bool:
    """A failure worth retrying: no answer in time, a dropped connection, or a server error (5xx, 429)."""
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return error.response.status_code >= 500 or error.response.status_code == 429
    return bool(_TRANSIENT_TEXT.search(str(error)))


def refine(sequence: str, result: LevelResult, ctx: StageContext) -> LevelResult:
    """Phase 2: notebook cell 5 (compare_pdb_references) for the consensus of `result`.

    Plumbing: a busy RCSB or PDBe (no answer in time, a server error) is asked again,
    up to len(PDB_RETRY_WAITS) more times, before the lookup counts as unavailable.
    """
    raw = dict(result.raw or {})
    _import_libraries()
    report = {"sequence": raw["sequence"], "secondary_structure": raw["secondary_structure"]}
    attempts = len(PDB_RETRY_WAITS) + 1
    for attempt in range(1, attempts + 1):
        ctx.report("Searching the RCSB PDB for experimentally solved structures…"
                   + (f" (attempt {attempt} of {attempts})" if attempt > 1 else ""))
        try:
            table, seconds = compare_pdb_references(report, max_hits=MAX_PDB_HITS)
        except requests.RequestException as error:  # the notebook: "PDB lookup unavailable"
            raw["pdb_references"] = {
                "status": "unavailable", "max_hits": MAX_PDB_HITS, "rows": [], "attempts": attempt,
                "error": _error_text(error),
            }
            if not _is_transient(error) or attempt == attempts:
                break
        else:
            raw["pdb_references"] = {**_pdb_to_raw(table, seconds), "attempts": attempt}
            busy = [row for row in raw["pdb_references"]["rows"] if row["Status"] != "OK" and _is_transient(row["Status"])]
            if not busy or attempt == attempts:
                break
        wait = PDB_RETRY_WAITS[attempt - 1]
        ctx.report(f"RCSB's sequence search is still running or busy; asking again in {wait} s "
                   f"(attempt {attempt + 1} of {attempts})…")
        ctx.sleep(wait)
    ctx.check_cancelled()
    return build_level_result(raw)
