"""Tertiary structure: Swiss-Model, Foldseek, ProtParam and wet-lab advice.

Ported from the team notebook
"Mapping_protein_function_from_tertiary_structure.ipynb". The four steps keep
their names, order, logic, thresholds and texts:

  Step 1A  fold_sequence()            Swiss-Model AutoModel builds a 3D model
  Step 1B  identify_structure()       Foldseek searches pdb100 and afdb50
  Step 2   analyze_properties()       ProtParam profile and model geometry
  Step 3   generate_wet_lab_report()  solubility, purification, assay design

Changes are plumbing only:
  * results are returned instead of printed;
  * every web request has a timeout, every polling loop has a time limit,
    a brief network hiccup is retried, and waiting stops as soon as the user
    presses Cancel;
  * the model download is checked before it is used;
  * the Swiss-Model token comes from backend/.env instead of the code;
  * the model file lives in a private temporary folder that is always removed.

Two read-only additions come from the same model file, for the residue map:
which residues were modelled, and their local quality estimates (the
B-factor column).
"""

import gzip
import logging
import re
import tempfile
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from ..config import (
    FOLDSEEK_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    SWISSMODEL_TIMEOUT_SECONDS,
    SWISSMODEL_TOKEN,
)
from ..jobs import LevelSkipped, StageContext
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
CACHE_VERSION = "tertiary-1"

SWISSMODEL_SUBMIT_URL = "https://swissmodel.expasy.org/automodel"
SWISSMODEL_SUMMARY_URL = "https://swissmodel.expasy.org/project/{project_id}/models/summary/"
SWISSMODEL_POLL_SECONDS = 20  # as in the notebook

FOLDSEEK_SUBMIT_URL = "https://search.foldseek.com/api/ticket"
FOLDSEEK_STATUS_URL = "https://search.foldseek.com/api/ticket/{ticket_id}"
FOLDSEEK_RESULT_URL = "https://search.foldseek.com/api/result/{ticket_id}/0"
FOLDSEEK_POLL_SECONDS = 2  # as in the notebook
FOLDSEEK_DATABASES = ("pdb100", "afdb50")

MAX_CONSECUTIVE_NETWORK_ERRORS = 3
MINUS = "\u2212"


# --- Small helpers -------------------------------------------------------------


def _brief(text: str, limit: int = 200) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _biopython() -> tuple[Any, Any, Any]:
    try:
        from Bio.PDB import PDBParser
        from Bio.SeqUtils import seq1
        from Bio.SeqUtils.ProtParam import ProteinAnalysis
    except ImportError as error:
        raise RuntimeError(
            "Biopython is not installed. Run `uv sync` in UI/backend, then restart the backend."
        ) from error
    return ProteinAnalysis, PDBParser, seq1


def _get_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    """GET a URL and return (status code, parsed JSON or None)."""
    response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return response.status_code, payload


# --- Step 1A: 1D to 3D folding (Swiss-Model) ------------------------------------


def fold_sequence(sequence: str, sm_token: str, ctx: StageContext, workdir: Path) -> tuple[str, Path, str]:
    """Submit the sequence to Swiss-Model, wait for the model, and download it.

    Returns (project ID, path of the saved PDB file, PDB text).
    """
    ctx.report("Submitting the sequence to Swiss-Model…")
    sm_submit_url = SWISSMODEL_SUBMIT_URL
    headers = {"Authorization": f"Token {sm_token}", "Content-Type": "application/json"}
    payload = {"target_sequences": [sequence], "project_title": "Tertiary_Pipeline"}

    response = requests.post(sm_submit_url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    if response.status_code not in [200, 201, 202]:
        raise RuntimeError(
            f"Swiss-Model submission failed (HTTP {response.status_code}): {_brief(response.text)}"
        )

    project_id = response.json().get("project_id")
    if not project_id:
        raise RuntimeError("Swiss-Model accepted the job but returned no project ID.")

    status_url = SWISSMODEL_SUMMARY_URL.format(project_id=project_id)
    started = time.monotonic()
    network_errors = 0

    while True:
        ctx.check_cancelled()
        elapsed = time.monotonic() - started
        if elapsed > SWISSMODEL_TIMEOUT_SECONDS:
            raise RuntimeError(
                f"Swiss-Model did not finish within {SWISSMODEL_TIMEOUT_SECONDS / 60:.0f} minutes "
                f"(project {project_id})."
            )

        try:
            status_code, data = _get_json(status_url, headers=headers)
            network_errors = 0
        except requests.RequestException as error:
            network_errors += 1
            if network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                raise RuntimeError(f"Lost contact with Swiss-Model ({error.__class__.__name__}).") from error
            ctx.report("Connection to Swiss-Model interrupted, retrying…")
            ctx.sleep(SWISSMODEL_POLL_SECONDS)
            continue

        if status_code == 200 and isinstance(data, dict):
            if data.get("status") == "COMPLETED":
                models = data.get("models", [])
                if not models:
                    raise RuntimeError("Swiss-Model finished but returned no models.")

                pdb_url = models[0].get("coordinates_url")
                if not pdb_url:
                    raise RuntimeError("Swiss-Model returned a model without a coordinates URL.")
                ctx.report("Downloading the Swiss-Model model…")
                pdb_response = requests.get(pdb_url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
                if pdb_response.status_code != 200:
                    raise RuntimeError(f"Could not download the model (HTTP {pdb_response.status_code}).")
                try:
                    pdb_data = gzip.decompress(pdb_response.content).decode("utf-8")
                except Exception:
                    pdb_data = pdb_response.text

                pdb_path = workdir / f"predicted_{project_id}.pdb"
                pdb_path.write_text(pdb_data, encoding="utf-8")
                return str(project_id), pdb_path, pdb_data
            if data.get("status") in ["FAILED", "ERROR"]:
                raise RuntimeError("Swiss-Model job failed.")
            ctx.report(f"Swiss-Model is building the model · {_clock(elapsed)} elapsed (usually 5–15 minutes)")
        elif status_code == 202:
            ctx.report(f"Swiss-Model is still calculating · {_clock(elapsed)} elapsed (usually 5–15 minutes)")
        else:
            logger.warning("Swiss-Model status check returned HTTP %s", status_code)

        ctx.sleep(SWISSMODEL_POLL_SECONDS)


# --- Step 1B: 3D identification (Foldseek) --------------------------------------


def identify_structure(pdb_filename: str, pdb_data: str, ctx: StageContext) -> dict[str, dict[str, Any]]:
    """Search the model against pdb100 and afdb50; return the top hit per database."""
    ctx.report("Searching the PDB and AlphaFold DB with Foldseek…")
    fs_submit_url = FOLDSEEK_SUBMIT_URL
    files = {"q": (pdb_filename, pdb_data)}
    data = [("mode", "3diaa"), ("database[]", "pdb100"), ("database[]", "afdb50")]

    res = requests.post(fs_submit_url, files=files, data=data, timeout=HTTP_TIMEOUT_SECONDS)
    if res.status_code != 200:
        raise RuntimeError(f"Foldseek submission rejected (HTTP {res.status_code}): {_brief(res.text)}")

    ticket_id = res.json().get("id")
    if not ticket_id:
        raise RuntimeError("Foldseek accepted the search but returned no ticket ID.")
    status_url = FOLDSEEK_STATUS_URL.format(ticket_id=ticket_id)
    started = time.monotonic()
    network_errors = 0

    while True:
        ctx.check_cancelled()
        elapsed = time.monotonic() - started
        if elapsed > FOLDSEEK_TIMEOUT_SECONDS:
            raise RuntimeError(f"Foldseek did not finish within {FOLDSEEK_TIMEOUT_SECONDS / 60:.0f} minutes.")

        try:
            _, status_res = _get_json(status_url)
            network_errors = 0
        except requests.RequestException as error:
            network_errors += 1
            if network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                raise RuntimeError(f"Lost contact with Foldseek ({error.__class__.__name__}).") from error
            ctx.report("Connection to Foldseek interrupted, retrying…")
            ctx.sleep(FOLDSEEK_POLL_SECONDS)
            continue

        status = status_res.get("status") if isinstance(status_res, dict) else None
        if status == "COMPLETE":
            break
        elif status in ["ERROR", "FAILED"]:
            raise RuntimeError("Foldseek rejected the Swiss-Model output.")

        ctx.report(f"Foldseek is searching · {_clock(elapsed)} elapsed")
        ctx.sleep(FOLDSEEK_POLL_SECONDS)

    result_url = FOLDSEEK_RESULT_URL.format(ticket_id=ticket_id)
    _, raw_results = _get_json(result_url)

    top_hits: dict[str, dict[str, Any]] = {}

    if isinstance(raw_results, dict) and "results" in raw_results:
        raw_results = raw_results["results"]
    if not isinstance(raw_results, list):
        raw_results = [raw_results]

    for db_block in raw_results:
        if isinstance(db_block, dict) and "alignments" in db_block:
            db_name = db_block.get("target", db_block.get("db", "Unknown_DB"))
            alignments_array = db_block["alignments"]

            if isinstance(alignments_array, list) and len(alignments_array) > 0:
                query_hits = alignments_array[0]

                if isinstance(query_hits, list) and len(query_hits) > 0:
                    top_hit = query_hits[0]
                    top_hits[str(db_name)] = top_hit

    return top_hits


# --- Step 2: physicochemical and structural profile ------------------------------


@dataclass(frozen=True)
class ModelProfile:
    mol_weight: float
    pI: float
    gravy: float
    instability: float
    atom_count: int
    spans: tuple[float, float, float]
    # Read-only additions for the residue map (first chain, standard residues only):
    residue_numbers: list[int] = field(default_factory=list)
    residue_quality: dict[int, float] = field(default_factory=dict)
    residue_letters: dict[int, str] = field(default_factory=dict)


def analyze_properties(sequence: str, pdb_filename: str) -> ModelProfile:
    """ProtParam profile of the sequence, plus atom count and size of the model."""
    ProteinAnalysis, PDBParser, seq1 = _biopython()

    analysis = ProteinAnalysis(sequence)
    mol_weight = analysis.molecular_weight()
    pI = analysis.isoelectric_point()
    gravy = analysis.gravy()
    instability = analysis.instability_index()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = PDBParser()
        structure = parser.get_structure("Predicted", pdb_filename)

    atoms = [atom for atom in structure.get_atoms()]
    coords = [atom.get_coord() for atom in atoms]

    if coords:
        x_span = max(c[0] for c in coords) - min(c[0] for c in coords)
        y_span = max(c[1] for c in coords) - min(c[1] for c in coords)
        z_span = max(c[2] for c in coords) - min(c[2] for c in coords)
    else:
        x_span = y_span = z_span = 0.0

    # Additions: per-residue data from the first chain of the first model.
    residue_numbers: list[int] = []
    residue_quality: dict[int, float] = {}
    residue_letters: dict[int, str] = {}
    first_model = next(iter(structure), None)
    first_chain = next(iter(first_model), None) if first_model is not None else None
    if first_chain is not None:
        for residue in first_chain:
            hetero_flag, number, _insertion = residue.get_id()
            if hetero_flag != " ":
                continue  # ligands and water
            residue_atoms = list(residue.get_atoms())
            if not residue_atoms:
                continue
            number = int(number)
            residue_numbers.append(number)
            residue_quality[number] = sum(float(atom.get_bfactor()) for atom in residue_atoms) / len(residue_atoms)
            residue_letters[number] = str(seq1(residue.get_resname()))

    return ModelProfile(
        mol_weight=float(mol_weight),
        pI=float(pI),
        gravy=float(gravy),
        instability=float(instability),
        atom_count=len(atoms),
        spans=(float(x_span), float(y_span), float(z_span)),
        residue_numbers=residue_numbers,
        residue_quality=residue_quality,
        residue_letters=residue_letters,
    )


# --- Step 3: wet-lab recommendations ---------------------------------------------


def generate_wet_lab_report(props: dict[str, float], foldseek_hits: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    """The notebook's three recommendations, as (title, text) pairs. Rules and texts unchanged."""
    report: list[tuple[str, str]] = []

    if props["gravy"] < 0:
        report.append(
            (
                "Solubility",
                "Protein is hydrophilic. Standard cytosolic extraction buffers (e.g., Tris/PBS) "
                "without harsh detergents are recommended.",
            )
        )
    else:
        report.append(
            (
                "Solubility",
                "Protein is highly hydrophobic. Consider adding mild detergents (e.g., Triton X-100 "
                "or CHAPS) during lysis.",
            )
        )

    if props["pI"] < 7.4:
        report.append(
            (
                "Purification",
                "At physiological pH (7.4), this protein will be negatively charged. "
                "Use an Anion Exchange column.",
            )
        )
    else:
        report.append(
            (
                "Purification",
                "At physiological pH (7.4), this protein will be positively charged. "
                "Use a Cation Exchange column.",
            )
        )

    if foldseek_hits:
        top_target = list(foldseek_hits.values())[0].get("target", "Unknown")
        report.append(
            (
                "Assay design",
                f"Tertiary structure matches '{top_target}'. Review literature on this specific "
                "structural fold for known binding partners or enzyme activity assays.",
            )
        )
    else:
        report.append(
            ("Assay design", "No exact tertiary structural matches found. Protein fold may be novel.")
        )

    return report


# --- Translating the results for the interface ----------------------------------------

_PDB_ID = re.compile(r"^([0-9][A-Za-z0-9]{3})(?:[-_.]|$)")
_AFDB_ID = re.compile(r"^AF-([A-Za-z0-9]+)-F\d+")

_QUALITY_BANDS: list[tuple[float, Tone, str]] = [
    (0.8, "confidence-very-high", "QMEAN ≥ 0.8"),
    (0.6, "confidence-high", "0.6–0.8"),
    (0.4, "confidence-low", "0.4–0.6"),
    (float("-inf"), "confidence-very-low", "< 0.4"),
]

_KEPT_HIT_FIELDS = (
    "target",
    "eval",
    "prob",
    "seqId",
    "alnLength",
    "qStartPos",
    "qEndPos",
    "dbStartPos",
    "dbEndPos",
    "taxName",
    "taxId",
)


@dataclass(frozen=True)
class _Match:
    database: str
    target: str
    identifier: str
    description: str
    evalue: float | None
    probability: float | None
    identity: float | None
    start: int | None
    end: int | None
    link: Link | None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # rejects NaN


def _format_evalue(value: float | None) -> str:
    if value is None:
        return "—"
    if value == 0:
        return "0"
    if 1e-3 <= abs(value) < 1e3:
        return f"{value:.3g}"
    mantissa, exponent = f"{value:.1e}".split("e")
    exponent_value = int(exponent)
    return f"{mantissa}e{MINUS if exponent_value < 0 else ''}{abs(exponent_value)}"


def _signed(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace("-", MINUS)


def _parse_match(database: str, hit: dict[str, Any], profile: ModelProfile, numbering_ok: bool) -> _Match:
    target = str(hit.get("target", "Unknown"))
    token, _, description = target.partition(" ")
    identifier, link = token, None

    afdb = _AFDB_ID.match(token)
    pdb = _PDB_ID.match(token)
    if afdb:
        identifier = afdb.group(1)
        link = Link(label=f"AlphaFold DB {identifier}", url=f"https://alphafold.ebi.ac.uk/entry/{identifier}")
    elif pdb and database.lower().startswith("pdb"):
        pdb_id = pdb.group(1).upper()
        chain = token.rsplit("_", 1)[1] if "_" in token else ""
        identifier = f"{pdb_id} chain {chain}" if chain else pdb_id
        link = Link(label=f"PDB {pdb_id}", url=f"https://www.rcsb.org/structure/{pdb_id}")

    identity = _number(hit.get("seqId"))
    if identity is not None and identity <= 1:
        identity *= 100  # Foldseek may report identity as a fraction

    # Foldseek counts positions along the model's own residues (1-based);
    # convert them to positions in the submitted sequence.
    start = end = None
    q_start, q_end = _number(hit.get("qStartPos")), _number(hit.get("qEndPos"))
    numbers = profile.residue_numbers
    if numbering_ok and q_start is not None and q_end is not None:
        first, last = int(q_start), int(q_end)
        if 1 <= first <= last <= len(numbers):
            start, end = numbers[first - 1], numbers[last - 1]

    return _Match(
        database=database,
        target=target,
        identifier=identifier,
        description=description.strip(),
        evalue=_number(hit.get("eval")),
        probability=_number(hit.get("prob")),
        identity=identity,
        start=start,
        end=end,
        link=link,
    )


def _numbering_matches(sequence: str, profile: ModelProfile) -> bool:
    """True if the model's residue numbers line up with the submitted sequence."""
    letters = profile.residue_letters
    if not letters:
        return False
    agree = sum(1 for number, letter in letters.items() if 1 <= number <= len(sequence) and sequence[number - 1] == letter)
    return agree >= 0.9 * len(letters)


def _band(value: float) -> tuple[Tone, str]:
    for threshold, tone, label in _QUALITY_BANDS:
        if value >= threshold:
            return tone, label
    return _QUALITY_BANDS[-1][1], _QUALITY_BANDS[-1][2]


def _runs(tones: list[Tone]) -> list[tuple[Tone, int, int]]:
    """Collapse one tone per residue into (tone, start, end) runs, 1-based."""
    runs: list[tuple[Tone, int, int]] = []
    for index, tone in enumerate(tones, start=1):
        if runs and runs[-1][0] == tone:
            runs[-1] = (tone, runs[-1][1], index)
        else:
            runs.append((tone, index, index))
    return runs


def _quality_track(length: int, profile: ModelProfile) -> tuple[Track, list[float]] | None:
    """Local model quality along the chain, if the B-factors hold 0–1 quality estimates."""
    quality = {number: value for number, value in profile.residue_quality.items() if 1 <= number <= length}
    values = list(quality.values())
    if not values or min(values) < 0 or max(values) > 1 or max(values) - min(values) < 1e-6:
        return None

    tones: list[Tone] = [_band(quality[number])[0] if number in quality else "neutral" for number in range(1, length + 1)]
    legend = [LegendItem(label=label, tone=tone) for _, tone, label in _QUALITY_BANDS]
    if len(quality) < length:
        legend.append(LegendItem(label="Not modelled", tone="neutral"))
    track = Track(
        key="model-quality",
        label="Model quality",
        caption="Tertiary · local QMEAN",
        style="states",
        segments=[Segment(start=start, end=end, tone=tone) for tone, start, end in _runs(tones)],
        legend=legend,
    )
    return track, values


def _coverage_track(length: int, profile: ModelProfile) -> Track | None:
    """Which residues the model covers (used when quality estimates are unavailable)."""
    modelled = sorted({number for number in profile.residue_numbers if 1 <= number <= length})
    if not modelled:
        return None
    segments: list[Segment] = []
    for number in modelled:
        if segments and segments[-1].end + 1 == number:
            segments[-1] = Segment(start=segments[-1].start, end=number, tone="accent", label="Modelled")
        else:
            segments.append(Segment(start=number, end=number, tone="accent", label="Modelled"))
    return Track(
        key="model-coverage",
        label="Modelled region",
        caption="Tertiary · Swiss-Model",
        style="blocks",
        segments=segments,
    )


def _to_level_result(
    sequence: str,
    project_id: str,
    hits: dict[str, dict[str, Any]],
    profile: ModelProfile,
    report: list[tuple[str, str]],
) -> LevelResult:
    length = len(sequence)
    numbering_ok = _numbering_matches(sequence, profile)
    matches = [_parse_match(database, hit, profile, numbering_ok) for database, hit in hits.items()]
    scored = [match for match in matches if match.evalue is not None]
    best = min(scored, key=lambda match: match.evalue or 0.0) if scored else (matches[0] if matches else None)

    x_span, y_span, z_span = profile.spans
    dimensions = f"{x_span:.1f} × {y_span:.1f} × {z_span:.1f} Å"
    modelled = (
        sum(1 for number in profile.residue_numbers if 1 <= number <= length)
        if numbering_ok
        else len(profile.residue_numbers)
    )

    # Headline and summary
    if best is not None:
        headline = Headline(value=_format_evalue(best.evalue), label="best structural-match E-value")
        described = f"{best.identifier} ({best.description})" if best.description else best.identifier
        summary = (
            f"The predicted fold matches {described} in the {best.database} database, "
            f"with an E-value of {_format_evalue(best.evalue)}."
        )
    else:
        headline = Headline(value="No match", label="Foldseek structural search")
        summary = "Swiss-Model built a 3D model, but Foldseek found no significant structural match; the fold may be novel."

    # Tracks: one overview track (quality, or coverage as a fallback), then match regions.
    tracks: list[Track] = []
    quality_values: list[float] = []
    if numbering_ok:
        quality = _quality_track(length, profile)
        if quality is not None:
            tracks.append(quality[0])
            quality_values = quality[1]
        else:
            coverage = _coverage_track(length, profile)
            if coverage is not None:
                tracks.append(coverage)
    for match in matches:
        if match.start is not None and match.end is not None:
            tracks.append(
                Track(
                    key=f"match-{match.database}",
                    label=f"{match.database} match",
                    caption=f"Foldseek · {match.database}",
                    style="blocks",
                    segments=[
                        Segment(
                            start=match.start,
                            end=match.end,
                            tone="accent" if match is best else "ink",
                            label=match.identifier,
                        )
                    ],
                    overview=False,
                )
            )

    # Metrics
    metrics = [
        Metric(label="Databases with a match", value=f"{len(matches)} of {len(FOLDSEEK_DATABASES)}"),
        Metric(label="Modelled residues", value=f"{modelled} of {length}"),
        Metric(label="Model atoms", value=f"{profile.atom_count:,}"),
        Metric(label="Model size", value=dimensions),
    ]
    protparam = "Physicochemical profile · ProtParam"
    metrics += [
        Metric(label="Molecular weight", value=f"{profile.mol_weight:,.2f} Da", group=protparam),
        Metric(label="Isoelectric point (pI)", value=f"{profile.pI:.2f}", group=protparam),
        Metric(
            label="GRAVY",
            value=_signed(profile.gravy, 3),
            hint="Grand average of hydropathy. Below 0 means hydrophilic.",
            group=protparam,
        ),
        Metric(
            label="Instability index",
            value=f"{profile.instability:.2f}",
            hint="Values below 40 suggest a stable protein.",
            group=protparam,
        ),
    ]
    if quality_values:
        high = sum(1 for value in quality_values if value >= 0.8)
        low = sum(1 for value in quality_values if value < 0.6)
        quality_group = "Model quality · local QMEAN"
        metrics += [
            Metric(
                label="Mean local quality",
                value=f"{sum(quality_values) / len(quality_values):.2f}",
                hint="Average local QMEAN score (0–1) over the modelled residues.",
                group=quality_group,
            ),
            Metric(label="High quality (≥ 0.8)", value=f"{round(100 * high / len(quality_values))}% of residues", group=quality_group),
            Metric(label="Low quality (< 0.6)", value=f"{round(100 * low / len(quality_values))}% of residues", group=quality_group),
        ]
    metrics.append(Metric(label="Project ID", value=project_id, group="Swiss-Model"))

    # Evidence
    evidence: list[EvidenceItem] = []
    for match in matches:
        details = f"E-value {_format_evalue(match.evalue)}"
        if match.probability is not None:
            details += f", probability {match.probability:.2f}"
        evidence.append(
            EvidenceItem(polarity="positive", text=f"Foldseek ({match.database}): top match {match.identifier} ({details}).")
        )
    if not matches:
        evidence.append(
            EvidenceItem(polarity="negative", text="Foldseek found no significant structural match in the PDB or AlphaFold DB.")
        )
    evidence.append(
        EvidenceItem(polarity="neutral", text=f"Swiss-Model built a model of {profile.atom_count:,} atoms, {dimensions}.")
    )
    if quality_values:
        low_share = round(100 * sum(1 for value in quality_values if value < 0.6) / len(quality_values))
        if low_share >= 20:
            evidence.append(
                EvidenceItem(polarity="negative", text=f"{low_share}% of modelled residues have low local quality (QMEAN below 0.6).")
            )

    table = Table(
        key="structural-matches",
        title="Structural matches",
        caption="Foldseek search (3Di + amino acids) of the Swiss-Model model; top hit per database",
        columns=[
            TableColumn(key="database", label="Database", mono=True),
            TableColumn(key="match", label="Match", mono=True),
            TableColumn(key="description", label="Description"),
            TableColumn(key="evalue", label="E-value", align="right", mono=True),
            TableColumn(key="probability", label="Probability", align="right"),
            TableColumn(key="identity", label="Identity", align="right"),
            TableColumn(key="residues", label="Query residues", align="right", mono=True),
        ],
        rows=[
            {
                "database": match.database,
                "match": match.identifier,
                "description": match.description or "—",
                "evalue": _format_evalue(match.evalue),
                "probability": f"{match.probability:.2f}" if match.probability is not None else "—",
                "identity": f"{match.identity:.1f}%" if match.identity is not None else "—",
                "residues": f"{match.start}–{match.end}" if match.start is not None and match.end is not None else "—",
            }
            for match in matches
        ],
    )

    raw: dict[str, Any] = {
        "swissmodel_project_id": project_id,
        "foldseek_top_hits": {
            database: {key: hit[key] for key in _KEPT_HIT_FIELDS if key in hit} for database, hit in hits.items()
        },
        "properties": {
            "molecular_weight_da": round(profile.mol_weight, 2),
            "isoelectric_point": round(profile.pI, 2),
            "gravy": round(profile.gravy, 3),
            "instability_index": round(profile.instability, 2),
        },
        "model": {
            "atoms": profile.atom_count,
            "dimensions_angstrom": [round(span, 1) for span in profile.spans],
            "modelled_residues": modelled,
        },
        "wet_lab_report": [{"title": title, "text": text} for title, text in report],
    }

    return LevelResult(
        source="live",
        headline=headline,
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=[table],
        notes=[Note(kind="recommendation", title=title, text=text) for title, text in report],
        links=[match.link for match in matches if match.link is not None],
        raw=raw,
    )


# --- The entry point used by the app ------------------------------------------------


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Run the notebook's pipeline (Steps 1A, 1B, 2, 3) and return the result."""
    if not SWISSMODEL_TOKEN:
        raise LevelSkipped(
            "Tertiary-structure analysis needs a Swiss-Model API token. "
            "Add SWISSMODEL_TOKEN to UI/backend/.env and restart the backend."
        )

    with tempfile.TemporaryDirectory(prefix="pfp-tertiary-") as directory:
        try:
            project_id, pdb_path, pdb_data = fold_sequence(sequence, SWISSMODEL_TOKEN, ctx, Path(directory))
        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not reach Swiss-Model ({error.__class__.__name__}). Check the internet connection."
            ) from error
        try:
            hits = identify_structure(pdb_path.name, pdb_data, ctx)
        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not reach Foldseek ({error.__class__.__name__}). Check the internet connection."
            ) from error
        ctx.report("Profiling the predicted model…")
        profile = analyze_properties(sequence, str(pdb_path))

    props = {"pI": profile.pI, "gravy": profile.gravy, "instability": profile.instability}
    report = generate_wet_lab_report(props, hits)
    return _to_level_result(sequence, project_id, hits, profile, report)
