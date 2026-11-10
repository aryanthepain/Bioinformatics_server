"""Tertiary structure: AlphaFold DB, Foldseek, ProtParam and structure analysis.

Ported from the team notebook "Tertiary_protein_identification.ipynb". Its steps
keep their names, order, logic, thresholds and texts:

  Step 1A  fetch_alphafold_structure()   AlphaFold DB model of a UniProt entry
  Step 1B  identify_structure()          Foldseek searches pdb100 and afdb50
  Step 2   analyze_properties()          ProtParam profile and model geometry
  Step 3   analyze_tertiary_structure()  confidence (pLDDT), disorder, secondary
           (analyze_structure,            structure (pydssp), compactness, surface,
            best_hit,                     best structural match, and UniProt
            transfer_uniprot_annotation)  annotation transfer from the AlphaFold DB match

The UniProt ID is the primary level's closest Swiss-Prot match (its best hit,
whatever its similarity), so this level starts as soon as the primary level has
its first result. The structure analysed is therefore that protein's, which is
the query's own only when the match is identical; the result says how similar
the two are. When there is no match, or the match has no AlphaFold DB model,
the level is skipped and says why.

Changes are plumbing only:
  * results are returned instead of printed (the printed report is kept, line by
    line, in the result);
  * every web request has a timeout, every polling loop has a time limit, a
    brief network hiccup is retried, and waiting stops as soon as the user
    presses Cancel;
  * pydssp is imported where it is used, so a missing package skips only the
    secondary-structure part (the notebook's own "(secondary structure
    skipped: ...)" message), and annotation features without a position are
    ignored instead of stopping the analysis;
  * the model file lives in a private temporary folder that is always removed.
"""

import logging
import math
import os
import re
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any

import requests

from ..config import FOLDSEEK_TIMEOUT_SECONDS, HTTP_TIMEOUT_SECONDS
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
    Polarity,
    Segment,
    Table,
    TableColumn,
    Tone,
    Track,
)
from .quaternary import Homologue, primary_homologue

logger = logging.getLogger(__name__)

# Change this whenever the logic below changes, so cached results are not reused.
CACHE_VERSION = "tertiary-2"

ALPHAFOLD_API_URL = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"

FOLDSEEK_SUBMIT_URL = "https://search.foldseek.com/api/ticket"
FOLDSEEK_STATUS_URL = "https://search.foldseek.com/api/ticket/{ticket_id}"
FOLDSEEK_RESULT_URL = "https://search.foldseek.com/api/result/{ticket_id}/0"
FOLDSEEK_POLL_SECONDS = 2  # as in the notebook
FOLDSEEK_DATABASES = ("pdb100", "afdb50")

MAX_CONSECUTIVE_NETWORK_ERRORS = 3
MINUS = "−"


# --- Small helpers -------------------------------------------------------------


def _brief(text: str, limit: int = 200) -> str:
    collapsed = " ".join(str(text).split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _biopython() -> Any:
    """The Biopython module, or a clear message if it is missing."""
    try:
        import Bio.PDB
        import Bio.SeqUtils.ProtParam
    except ImportError as error:
        raise RuntimeError(
            "Biopython is not installed. Run `uv sync` in UI/backend, then restart the backend."
        ) from error
    import Bio

    return Bio


def _get_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, Any]:
    """GET a URL and return (status code, parsed JSON or None)."""
    response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return response.status_code, payload


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None  # rejects NaN and infinity


# --- Step 1A: 3D structure (AlphaFold DB) ----------------------------------------


def fetch_alphafold_structure(uniprot_id: str, ctx: StageContext, workdir: Path) -> tuple[dict[str, Any], Path, str]:
    """Download the AlphaFold DB model of a UniProt entry.

    Returns (the AlphaFold DB entry's details, path of the saved PDB file, PDB text).
    """
    ctx.report(f"Fetching the AlphaFold DB structure of {uniprot_id}…")
    url = ALPHAFOLD_API_URL.format(uniprot_id=uniprot_id)

    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)

    if response.status_code == 404:
        raise LevelSkipped(f"AlphaFold DB has no structure for {uniprot_id}, so there is no 3D model to analyse.")
    if response.status_code != 200:
        raise RuntimeError(f"AlphaFold DB lookup failed! HTTP {response.status_code}. Ensure the UniProt ID is valid.")

    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError("AlphaFold DB returned an answer that is not JSON.") from error
    if not data:
        raise LevelSkipped(f"No AlphaFold structure found for this UniProt ID ({uniprot_id}).")

    entry = data[0] if isinstance(data, list) else data
    pdb_url = entry.get("pdbUrl") if isinstance(entry, dict) else None
    if not pdb_url:
        raise RuntimeError("AlphaFold DB returned no download address for the structure.")

    ctx.check_cancelled()
    pdb_response = requests.get(pdb_url, timeout=HTTP_TIMEOUT_SECONDS)
    if pdb_response.status_code != 200:
        raise RuntimeError("Failed to download the physical PDB coordinates.")

    pdb_data = pdb_response.text
    if "ATOM" not in pdb_data:
        raise RuntimeError("The AlphaFold DB download contains no atoms.")
    pdb_path = workdir / f"alphafold_{uniprot_id}.pdb"
    pdb_path.write_text(pdb_data, encoding="utf-8")

    details = {
        key: entry.get(key)
        for key in (
            "entryId",
            "uniprotAccession",
            "uniprotDescription",
            "gene",
            "organismScientificName",
            "latestVersion",
            "modelCreatedDate",
            "uniprotStart",
            "uniprotEnd",
            "globalMetricValue",
        )
        if entry.get(key) is not None
    }
    return details, pdb_path, pdb_data


# --- Step 1B: tertiary identification (Foldseek) ----------------------------------


def identify_structure(pdb_filename: str, pdb_data: str, ctx: StageContext) -> dict[str, dict[str, Any]]:
    """Search the structure against pdb100 and afdb50; return the top hit per database."""
    ctx.report("Searching the PDB and AlphaFold DB with Foldseek…")
    fs_submit_url = FOLDSEEK_SUBMIT_URL
    files = {"q": (pdb_filename, pdb_data)}
    data = [("mode", "3diaa"), ("database[]", "pdb100"), ("database[]", "afdb50")]

    res = requests.post(fs_submit_url, files=files, data=data, timeout=HTTP_TIMEOUT_SECONDS)
    if res.status_code != 200:
        raise RuntimeError(f"Foldseek submission rejected! HTTP {res.status_code}: {_brief(res.text)}")

    try:
        ticket_id = res.json().get("id")
    except (ValueError, AttributeError):
        ticket_id = None
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
            raise RuntimeError("Foldseek rejected the AlphaFold output.")

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
                    if isinstance(top_hit, dict):
                        top_hits[str(db_name)] = top_hit

    return top_hits


# --- Step 2: physicochemical and structural profile --------------------------------


def analyze_properties(sequence: str, pdb_filename: str) -> dict[str, Any]:
    """ProtParam profile of the query sequence, plus atom count and size of the structure."""
    _biopython()
    from Bio.PDB import PDBParser
    from Bio.SeqUtils.ProtParam import ProteinAnalysis

    analysis = ProteinAnalysis(sequence)
    mol_weight = analysis.molecular_weight()
    pI = analysis.isoelectric_point()
    gravy = analysis.gravy()
    instability = analysis.instability_index()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = PDBParser()
        structure = parser.get_structure("Predicted", pdb_filename)

    atoms = list(structure[0].get_atoms())
    coords = [atom.get_coord() for atom in atoms]

    if coords:
        x_span = max(c[0] for c in coords) - min(c[0] for c in coords)
        y_span = max(c[1] for c in coords) - min(c[1] for c in coords)
        z_span = max(c[2] for c in coords) - min(c[2] for c in coords)
    else:
        x_span = y_span = z_span = 0.0

    return {
        "pI": float(pI),
        "gravy": float(gravy),
        "instability": float(instability),
        "mol_weight": float(mol_weight),
        "atoms": len(atoms),
        "spans": (float(x_span), float(y_span), float(z_span)),
    }


# --- Step 3: tertiary structure analysis -------------------------------------------

MAX_ASA = dict(A=129, R=274, N=195, D=193, C=167, E=223, Q=225, G=104, H=224, I=197,
               L=201, K=236, M=224, F=240, P=159, S=155, T=172, W=285, Y=263, V=174)
HYDROPHOBIC = set("AVILMFWC")


def _runs(mask: Any, min_len: int) -> list[tuple[int, int]]:
    """Contiguous True runs of at least min_len -> list of (start, end), 1-based."""
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        if not m and start is not None:
            if i - start >= min_len:
                out.append((start + 1, i))
            start = None
    return out


def analyze_structure(pdb_filename: str) -> dict[str, Any]:
    _biopython()
    import numpy as np
    from Bio.PDB import PDBParser, ShrakeRupley
    from Bio.SeqUtils import seq1

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = PDBParser(QUIET=True).get_structure("m", pdb_filename)[0]
    res = [r for r in model.get_residues() if r.id[0] == " " and "CA" in r]
    seq = "".join(seq1(r.get_resname()) for r in res)
    n = len(res)
    if n == 0:
        raise RuntimeError("The structure contains no amino-acid residues.")

    # Confidence (pLDDT lives in the B-factor column; some tools use a 0-1 scale)
    raw = np.array([r["CA"].get_bfactor() for r in res])
    has_plddt = (not os.path.basename(pdb_filename).startswith("rcsb_")) and raw.max() > 0
    plddt = (raw * 100 if raw.max() <= 1 else raw) if has_plddt else np.full(n, np.nan)
    if plddt.max() <= 1.0:
        plddt = plddt * 100

    # Compactness vs. empirical expectation for globular proteins
    ca = np.array([r["CA"].get_coord() for r in res])
    rg = float(np.sqrt(((ca - ca.mean(0)) ** 2).sum(1).mean()))
    rg_exp = 2.2 * n ** 0.38

    # Relative solvent accessibility
    ShrakeRupley().compute(model, level="R")
    rsa = np.array([min(r.sasa / MAX_ASA.get(a, 200), 1.0) for r, a in zip(res, seq, strict=True)])
    exposed = rsa > 0.25
    n_exp = max(exposed.sum(), 1)
    surf_hphob = sum(exposed[i] and seq[i] in HYDROPHOBIC for i in range(n)) / n_exp
    surf_charge = sum((seq[i] in "KR") - (seq[i] in "DE") for i in range(n) if exposed[i])

    # Secondary structure (pure-python DSSP)
    ss_frac = None
    ss_states = None  # addition for the residue map: one letter (H, E or -) per residue
    ss_error = None  # addition: why it was skipped, for the interface
    try:
        with ML_LOCK:  # plumbing: the levels' threads import the ML libraries in turn (app/mllock.py)
            import pydssp

        coords = np.array([[r["N"].get_coord(), r["CA"].get_coord(),
                            r["C"].get_coord(), r["O"].get_coord()] for r in res])
        ss = pydssp.assign(coords, out_type="c3")
        ss = np.array(ss).astype(str)
        ss_frac = {"helix": float((ss == "H").mean()), "strand": float((ss == "E").mean())}
        ss_frac["coil"] = 1 - ss_frac["helix"] - ss_frac["strand"]
        ss_states = "".join(str(state) for state in ss.reshape(-1))
    except Exception as e:  # noqa: BLE001 - as in the notebook: only this part is skipped
        ss_error = f"(secondary structure skipped: {e})"

    return dict(n=n, seq=seq, plddt=plddt, has_plddt=has_plddt, rg=rg, rg_exp=rg_exp, rsa=rsa,
                surf_hphob=surf_hphob, surf_charge=surf_charge, ss=ss_frac,
                disordered=_runs(plddt < 50, 10), low_conf=_runs(plddt < 70, 10),
                # additions for the interface (read-only):
                ss_states=ss_states, ss_error=ss_error, residue_numbers=[int(r.id[1]) for r in res])


def best_hit(foldseek_hits: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    hits = list(foldseek_hits.values())
    return max(hits, key=lambda h: (float(h.get("prob", 0)), -float(h.get("eval", 1e9)))) if hits else None


def transfer_uniprot_annotation(hit: dict[str, Any], plddt: Any) -> dict[str, Any] | None:
    """Map UniProt active/binding/metal sites from an AFDB hit onto the query via the alignment."""
    import numpy as np

    m = re.match(r"AF-([A-Z0-9]+)-F\d+", hit.get("target", ""))
    if not m:
        return None
    acc = m.group(1)
    try:
        r = requests.get(UNIPROT_ENTRY_URL.format(accession=acc), timeout=30)
    except requests.RequestException:
        return None  # treated like the notebook's "not 200": no annotation
    if r.status_code != 200:
        return None
    j = r.json()
    q, t = int(hit["qStartPos"]), int(hit["dbStartPos"])
    mapping = {}
    for qa, ta in zip(hit["qAln"], hit["dbAln"], strict=False):
        if qa != "-" and ta != "-":
            mapping[t] = (q, qa == ta)
        q += qa != "-"
        t += ta != "-"

    name = (j.get("proteinDescription", {}).get("recommendedName", {})
              .get("fullName", {}).get("value", "n/a"))
    func = next((c["texts"][0]["value"] for c in j.get("comments", [])
                 if c.get("commentType") == "FUNCTION" and c.get("texts")), None)
    sites = []
    for f in j.get("features", []):
        if f["type"] not in ("Active site", "Binding site", "Metal binding"):
            continue
        s, e = f["location"]["start"].get("value"), f["location"]["end"].get("value")
        if not isinstance(s, int) or not isinstance(e, int):
            continue  # addition: a position UniProt marks as unknown cannot be mapped
        mapped = [mapping[p] for p in range(s, e + 1) if p in mapping]
        if not mapped:
            continue
        qpos = [p for p, _ in mapped]
        in_model = [plddt[p - 1] for p in qpos if p <= len(plddt)]
        sites.append(dict(type=f["type"], target_range=(s, e), query_range=(min(qpos), max(qpos)),
                          conserved=all(c for _, c in mapped),
                          ligand=f.get("ligand", {}).get("name"),
                          site_plddt=float(np.mean(in_model)) if in_model else float("nan")))
    return dict(accession=acc, name=name, function=func, sites=sites)


def _coverage(h: dict[str, Any]) -> float:
    return (int(h["qEndPos"]) - int(h["qStartPos"]) + 1) / int(h["qLen"]) if "qLen" in h else float("nan")


def analyze_tertiary_structure(
    pdb_filename: str, foldseek_hits: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    """Step 3. Returns (the structure analysis, the notebook's report as (kind, line) pairs, findings)."""
    import numpy as np

    lines: list[tuple[str, str]] = []
    findings: dict[str, Any] = {"best": None, "afdb_hit": None, "transfer": None, "annotation": None}
    s = analyze_structure(pdb_filename)

    if s["has_plddt"]:
        mean_pl = s["plddt"].mean()
        lines.append(("confidence", (f"CONFIDENCE: mean pLDDT {mean_pl:.1f} "
                      f"({'high' if mean_pl > 80 else 'moderate' if mean_pl > 70 else 'LOW - treat everything below as tentative'})")))
        if s["disordered"]:
            lines.append(("disorder", f"DISORDER: likely disordered regions (pLDDT<50): {s['disordered']}"))
        else:
            lines.append(("disorder", "DISORDER: no extended low-pLDDT regions."))
    else:
        lines.append(("confidence", ("CONFIDENCE: experimental structure, so no pLDDT. Treat as high confidence "
                      "(for NMR, check ensemble variability if you need flexibility).")))

    # 3. Fold content and compactness
    if s["ss"]:
        lines.append(("secondary", f"SECONDARY STRUCTURE: {s['ss']['helix']:.0%} helix, {s['ss']['strand']:.0%} strand, {s['ss']['coil']:.0%} coil"))
    ratio = s["rg"] / s["rg_exp"]
    lines.append(("compactness", (f"COMPACTNESS: Rg {s['rg']:.1f} A vs ~{s['rg_exp']:.1f} A expected for a globular protein of {s['n']} aa "
                  f"({'compact' if ratio < 1.15 else 'extended or multi-domain/disordered tails'})")))

    # 4. Surface chemistry
    lines.append(("surface", (f"SURFACE: {s['surf_hphob']:.0%} of exposed residues are hydrophobic "
                  f"({'unusually high - possible interaction patch, membrane association or aggregation risk' if s['surf_hphob'] > 0.35 else 'typical'}); "
                  f"net exposed charge {s['surf_charge']:+d}")))

    # 5. Homology and annotation transfer
    best = best_hit(foldseek_hits)
    if not best:
        lines.append(("homology", ("HOMOLOGY: no Foldseek hits. Candidate fold novelty, or the model is poor. "
                      "Consider pocket detection (e.g. fpocket) on the PDB.")))
        return s, lines, findings
    findings["best"] = best
    lines.append(("homology", (f"HOMOLOGY (best overall): {best.get('target')} | prob {float(best.get('prob', 0)):.2f} | "
                  f"seq id {best.get('seqId', 'n/a')} | coverage {_coverage(best):.0%} | E-value {best.get('eval', 'n/a')}")))

    afdb_hit = next((h for k, h in foldseek_hits.items() if k.startswith("afdb")), None)
    if afdb_hit is None:
        lines.append(("transfer", "No AFDB hit, so no automatic annotation transfer."))
        findings["transfer"] = "no AFDB hit"
        return s, lines, findings
    findings["afdb_hit"] = afdb_hit

    prob, qcov = float(afdb_hit.get("prob", 0)), _coverage(afdb_hit)
    lines.append(("transfer", f"Annotation source (AFDB): {afdb_hit.get('target')} | prob {prob:.2f} | coverage {qcov:.0%}"))
    if prob < 0.5 or not qcov >= 0.5:
        lines.append(("transfer", "-> Weak or partial match; shared fold is possible but don't infer function."))
        findings["transfer"] = "weak"
        return s, lines, findings

    try:
        ann = transfer_uniprot_annotation(afdb_hit, s["plddt"])
    except (KeyError, TypeError, ValueError):  # addition: an answer in an unexpected shape
        ann = None
    if not ann:
        lines.append(("transfer", "(Could not retrieve UniProt annotation for this hit.)"))
        findings["transfer"] = "unavailable"
        return s, lines, findings
    findings["transfer"] = "transferred"
    findings["annotation"] = ann

    lines.append(("annotation", f"Matched protein: {ann['name']} ({ann['accession']})"))
    if ann["function"]:
        lines.append(("annotation", f"Annotated function (of the HIT, not your protein): {ann['function'][:300]}"))
    for site in ann["sites"]:
        flag = "CONSERVED" if site["conserved"] else "residues differ"
        pl = "" if np.isnan(site["site_plddt"]) else f", site pLDDT {site['site_plddt']:.0f}"
        lines.append(("site", (f"{site['type']} {site['ligand'] or ''}: hit {site['target_range']} -> "
                      f"query {site['query_range']} [{flag}{pl}]")))
    lines.append(("advice", ("Conserved site residues support a shared function; if they differ, "
                  "the fold may be shared while the function has diverged.")))
    return s, lines, findings


# --- Translating the results for the interface ----------------------------------------

_PDB_ID = re.compile(r"^([0-9][A-Za-z0-9]{3})(?:[-_.]|$)")
_AFDB_ID = re.compile(r"^AF-([A-Za-z0-9]+)-F\d+")

# AlphaFold's own confidence bands for pLDDT.
_PLDDT_BANDS: list[tuple[float, Tone, str]] = [
    (90.0, "confidence-very-high", "Very high (pLDDT ≥ 90)"),
    (70.0, "confidence-high", "Confident (70–90)"),
    (50.0, "confidence-low", "Low (50–70)"),
    (float("-inf"), "confidence-very-low", "Very low (< 50)"),
]
_SS_TONES: dict[str, tuple[Tone, str]] = {"H": ("helix", "Helix"), "E": ("strand", "Strand"), "-": ("coil", "Coil")}

_KEPT_HIT_FIELDS = (
    "target",
    "eval",
    "prob",
    "seqId",
    "alnLength",
    "qStartPos",
    "qEndPos",
    "qLen",
    "dbStartPos",
    "dbEndPos",
    "dbLen",
    "taxName",
    "taxId",
)


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


def _percent(fraction: float | None) -> str:
    return f"{round(100 * fraction)}%" if fraction is not None else "—"


def _match_name(database: str, target: str) -> tuple[str, str, Link | None]:
    """'AF-P69905-F1-model_v6 Hemoglobin…' -> ('AlphaFold DB P69905', 'Hemoglobin…', link)."""
    token, _, description = target.partition(" ")
    afdb = _AFDB_ID.match(token)
    pdb = _PDB_ID.match(token)
    if afdb:
        identifier = afdb.group(1)
        return (f"AlphaFold DB {identifier}", description.strip(),
                Link(label=f"AlphaFold DB {identifier}", url=f"https://alphafold.ebi.ac.uk/entry/{identifier}"))
    if pdb and database.lower().startswith("pdb"):
        pdb_id = pdb.group(1).upper()
        chain = token.rsplit("_", 1)[1] if "_" in token else ""
        return (f"PDB {pdb_id}" + (f" chain {chain}" if chain else ""), description.strip(),
                Link(label=f"PDB {pdb_id}", url=f"https://www.rcsb.org/structure/{pdb_id}"))
    return token, description.strip(), None


def _maps_onto_query(sequence: str, structure_sequence: str, numbers: list[int]) -> bool:
    """True if the structure's residues line up with the query, position by position."""
    if not numbers or len(numbers) != len(structure_sequence):
        return False
    agree = sum(
        1 for number, letter in zip(numbers, structure_sequence, strict=True)
        if 1 <= number <= len(sequence) and sequence[number - 1] == letter
    )
    return agree >= 0.9 * max(len(sequence), len(structure_sequence))


def _state_runs(values: list[tuple[int, Tone]]) -> list[Segment]:
    """(position, tone) pairs -> one segment per run of the same tone."""
    segments: list[Segment] = []
    for position, tone in values:
        last = segments[-1] if segments else None
        if last is not None and last.tone == tone and last.end + 1 == position:
            segments[-1] = Segment(start=last.start, end=position, tone=tone)
        else:
            segments.append(Segment(start=position, end=position, tone=tone))
    return segments


def _plddt_tone(value: float) -> Tone:
    for threshold, tone, _ in _PLDDT_BANDS:
        if value >= threshold:
            return tone
    return _PLDDT_BANDS[-1][1]


def _line_polarity(kind: str, text: str, mean_plddt: float | None) -> Polarity:
    if kind == "confidence":
        return "negative" if mean_plddt is not None and mean_plddt <= 70 else "positive"
    if kind == "disorder":
        return "neutral" if text.startswith("DISORDER: no") else "negative"
    if kind == "homology":
        return "negative" if text.startswith("HOMOLOGY: no") else "positive"
    if kind == "transfer":
        return "negative" if ("Weak" in text or "Could not" in text or text.startswith("No AFDB")) else "neutral"
    if kind == "site":
        return "positive" if "CONSERVED" in text else "negative"
    return "neutral"


def _template_line(template: Homologue) -> str:
    name = template.protein or template.entry
    identity = f"{template.identity:.1f}% identical over {template.coverage:.1f}% of the query"
    return f"{name} ({template.accession}{', ' + template.organism if template.organism else ''}), {identity}"


def _to_level_result(
    sequence: str,
    template: Homologue,
    alphafold: dict[str, Any],
    hits: dict[str, dict[str, Any]],
    props: dict[str, Any],
    s: dict[str, Any],
    lines: list[tuple[str, str]],
    findings: dict[str, Any],
) -> LevelResult:
    length = len(sequence)
    plddt_values = [float(v) for v in s["plddt"]] if s["has_plddt"] else []
    mean_plddt = sum(plddt_values) / len(plddt_values) if plddt_values else None
    confidence_word = (
        "experimental structure" if not s["has_plddt"]
        else "high" if mean_plddt is not None and mean_plddt > 80
        else "moderate" if mean_plddt is not None and mean_plddt > 70
        else "low"
    )
    identical = template.identity >= 100.0 and template.coverage >= 100.0 and len(s["seq"]) == length
    maps = _maps_onto_query(sequence, s["seq"], s["residue_numbers"])

    best = findings["best"]
    best_name = best_description = None
    if best is not None:
        database = next((key for key, hit in hits.items() if hit is best), "")
        best_name, best_description, _ = _match_name(database, str(best.get("target", "")))
    annotation = findings["annotation"]
    afdb_hit = findings["afdb_hit"]

    # Headline and summary
    if mean_plddt is not None:
        headline = Headline(value=f"{mean_plddt:.1f}", label=f"mean pLDDT · {confidence_word} confidence")
    else:
        headline = Headline(value="—", label="experimental structure (no pLDDT)")
    opening = (
        f"AlphaFold DB structure of {template.accession} ({template.protein or template.entry}), "
        + ("identical to the query" if identical else
           f"the primary level's closest match: {template.identity:.1f}% identical over {template.coverage:.1f}% of the query")
        + "."
    )
    if best is not None:
        described = f"{best_name} ({best_description})" if best_description else best_name
        found = f" Best structural match: {described}, probability {float(best.get('prob', 0)):.2f}."
    else:
        found = " Foldseek found no structural match."
    if annotation is not None:
        found += f" Annotation transferred from {annotation['accession']}."
    summary = opening + (f" Mean pLDDT {mean_plddt:.1f} ({confidence_word})." if mean_plddt is not None else "") + found

    # Tracks (only when the structure's residues are the query's)
    tracks: list[Track] = []
    if maps:
        numbers = s["residue_numbers"]
        if plddt_values:
            tracks.append(Track(
                key="plddt",
                label="AlphaFold confidence",
                caption="Tertiary · pLDDT",
                style="states",
                segments=_state_runs([(number, _plddt_tone(value)) for number, value in zip(numbers, plddt_values, strict=True)
                                      if 1 <= number <= length]),
                legend=[LegendItem(label=label, tone=tone) for _, tone, label in _PLDDT_BANDS],
            ))
        if s["ss_states"] and len(s["ss_states"]) == len(numbers):
            tracks.append(Track(
                key="structure-ss",
                label="Helix / strand",
                caption="Tertiary · DSSP of the structure",
                style="states",
                segments=_state_runs([(number, _SS_TONES.get(state, _SS_TONES["-"])[0])
                                      for number, state in zip(numbers, s["ss_states"], strict=True) if 1 <= number <= length]),
                legend=[LegendItem(label=label, tone=tone) for tone, label in _SS_TONES.values()],
                overview=False,
            ))
        if annotation and annotation["sites"]:
            sites = [site for site in annotation["sites"] if 1 <= site["query_range"][0] <= site["query_range"][1] <= length]
            if sites:
                tracks.append(Track(
                    key="transferred-sites",
                    label="Functional sites",
                    caption=f"Tertiary · from {annotation['accession']}",
                    style="marks",
                    segments=[Segment(start=site["query_range"][0], end=site["query_range"][1],
                                      tone="ink" if site["conserved"] else "uncertain",
                                      label=f"{site['type']}{' · ' + site['ligand'] if site['ligand'] else ''}")
                              for site in sites],
                    legend=[LegendItem(label="Conserved site", tone="ink"), LegendItem(label="Residues differ", tone="uncertain")],
                ))

    # Metrics
    x_span, y_span, z_span = props["spans"]
    dimensions = f"{x_span:.1f} × {y_span:.1f} × {z_span:.1f} Å"
    ratio = s["rg"] / s["rg_exp"]
    best_prob = _number(best.get("prob")) if best is not None else None
    metrics = [
        Metric(label="Best match probability", value=f"{best_prob:.2f}" if best_prob is not None else "—",
               hint="Foldseek's probability that the best structural match is a true homologue."),
        Metric(label="Databases with a match", value=f"{len(hits)} of {len(FOLDSEEK_DATABASES)}"),
        Metric(label="Structure residues", value=f"{s['n']:,}"),
        Metric(label="Template identity", value=f"{template.identity:.1f}%",
               hint="Identity of the structure's protein to the query (primary level)."),
    ]
    structure_group = "Structure · AlphaFold DB"
    metrics += [
        Metric(label="UniProt entry", value=f"{template.accession}" + (f" ({template.entry})" if template.entry else ""), group=structure_group),
        Metric(label="AlphaFold DB entry", value=str(alphafold.get("entryId") or f"AF-{template.accession}-F1")
               + (f" · v{alphafold['latestVersion']}" if alphafold.get("latestVersion") else ""), group=structure_group),
        Metric(label="Coverage of the query", value=f"{template.coverage:.1f}%", group=structure_group),
        Metric(label="Atoms", value=f"{props['atoms']:,}", group=structure_group),
        Metric(label="Size", value=dimensions, group=structure_group),
    ]
    confidence_group = "Confidence · pLDDT"
    if plddt_values:
        very_high = sum(1 for v in plddt_values if v >= 90)
        low = sum(1 for v in plddt_values if v < 70)
        metrics += [
            Metric(label="Mean pLDDT", value=f"{mean_plddt:.1f}",
                   hint="AlphaFold's per-residue confidence (0–100); above 70 is confident.", group=confidence_group),
            Metric(label="Very high (≥ 90)", value=f"{round(100 * very_high / len(plddt_values))}% of residues", group=confidence_group),
            Metric(label="Below 70", value=f"{round(100 * low / len(plddt_values))}% of residues", group=confidence_group),
            Metric(label="Likely disordered (pLDDT < 50, ≥ 10 residues)",
                   value=", ".join(f"{a}–{b}" for a, b in s["disordered"]) or "none", group=confidence_group),
        ]
    if s["ss"]:
        ss_group = "Secondary structure · DSSP (pydssp)"
        metrics += [
            Metric(label="Helix", value=_percent(s["ss"]["helix"]), group=ss_group),
            Metric(label="Strand", value=_percent(s["ss"]["strand"]), group=ss_group),
            Metric(label="Coil", value=_percent(s["ss"]["coil"]), group=ss_group),
        ]
    shape_group = "Shape and surface"
    metrics += [
        Metric(label="Radius of gyration", value=f"{s['rg']:.1f} Å (expected ~{s['rg_exp']:.1f} Å)",
               hint="Expected for a globular protein of this length: 2.2 × N^0.38 Å.", group=shape_group),
        Metric(label="Shape", value="compact" if ratio < 1.15 else "extended or multi-domain/disordered tails", group=shape_group),
        Metric(label="Hydrophobic surface", value=f"{s['surf_hphob']:.0%} of exposed residues", group=shape_group),
        Metric(label="Net exposed charge", value=f"{int(s['surf_charge']):+d}".replace("-", MINUS), group=shape_group),
    ]
    protparam = "Physicochemical profile · ProtParam (query)"
    metrics += [
        Metric(label="Molecular weight", value=f"{props['mol_weight']:,.2f} Da", group=protparam),
        Metric(label="Isoelectric point (pI)", value=f"{props['pI']:.2f}", group=protparam),
        Metric(label="GRAVY", value=_signed(props["gravy"], 3),
               hint="Grand average of hydropathy. Below 0 means hydrophilic.", group=protparam),
        Metric(label="Instability index", value=f"{props['instability']:.2f}",
               hint="Values below 40 suggest a stable protein.", group=protparam),
    ]

    # Evidence: the notebook's report, line by line
    evidence = [
        EvidenceItem(polarity=_line_polarity(kind, text, mean_plddt), text=text)
        for kind, text in lines
        if kind not in ("advice",) and not (kind == "annotation" and text.startswith("Annotated function"))
    ]
    if s["ss_error"]:
        evidence.append(EvidenceItem(polarity="neutral", text=s["ss_error"]))

    # Notes
    notes: list[Note] = []
    if not identical:
        notes.append(Note(
            kind="caution",
            title="This is the structure of the matched protein",
            text=(
                f"The structure is {template.accession}'s, from AlphaFold DB: it is {template.identity:.1f}% identical "
                f"to the query over {template.coverage:.1f}% of its length (the primary level's closest Swiss-Prot "
                "match). Read it as the structure of a related protein, not as a model of the query."
                + ("" if maps else " Its residues are not shown on the query's residue map, because they do not line up with the query.")
            ),
        ))
    if annotation is not None and annotation.get("function"):
        notes.append(Note(
            kind="observation",
            title=f"Annotated function of {annotation['accession']} (the structural match, not your protein)",
            text=_brief(annotation["function"], 900),
        ))
    if annotation is not None:
        notes.append(Note(
            kind="recommendation",
            title="Reading the transferred sites",
            text="Conserved site residues support a shared function; if they differ, the fold may be shared while the function has diverged.",
        ))
    if s["ss_error"]:
        notes.append(Note(kind="caution", title="Secondary structure not computed", text=s["ss_error"].strip("()")))

    # Tables
    matches = []
    links: list[Link] = [
        Link(label=f"AlphaFold DB {template.accession}", url=f"https://alphafold.ebi.ac.uk/entry/{template.accession}"),
        Link(label=f"UniProt {template.accession}", url=f"https://www.uniprot.org/uniprotkb/{template.accession}/entry"),
    ]
    for database, hit in hits.items():
        name, description, link = _match_name(database, str(hit.get("target", "")))
        identity = _number(hit.get("seqId"))
        if identity is not None and identity <= 1:
            identity *= 100  # Foldseek may report identity as a fraction
        coverage = _coverage(hit)
        prob = _number(hit.get("prob"))
        matches.append({
            "database": database,
            "match": name,
            "description": description or "—",
            "evalue": _format_evalue(_number(hit.get("eval"))),
            "probability": f"{prob:.2f}" if prob is not None else "—",
            "identity": f"{identity:.1f}%" if identity is not None else "—",
            "coverage": _percent(coverage) if math.isfinite(coverage) else "—",
            "best": "best" if hit is best else "",
        })
        if link is not None and all(existing.url != link.url for existing in links):
            links.append(link)
    tables = [Table(
        key="structural-matches",
        title="Structural matches",
        caption=f"Foldseek search (3Di + amino acids) of the AlphaFold DB structure of {template.accession}; top hit per database",
        columns=[
            TableColumn(key="database", label="Database", mono=True),
            TableColumn(key="match", label="Match", mono=True),
            TableColumn(key="description", label="Description"),
            TableColumn(key="evalue", label="E-value", align="right", mono=True),
            TableColumn(key="probability", label="Probability", align="right"),
            TableColumn(key="identity", label="Identity", align="right"),
            TableColumn(key="coverage", label="Coverage", align="right"),
            TableColumn(key="best", label="", align="right"),
        ],
        rows=matches,
    )]
    if annotation is not None and annotation["sites"]:
        tables.append(Table(
            key="transferred-sites",
            title="Functional sites transferred",
            caption=f"UniProt active, binding and metal sites of {annotation['accession']}, mapped through the Foldseek alignment "
                    f"onto the structure of {template.accession}",
            columns=[
                TableColumn(key="type", label="Site"),
                TableColumn(key="ligand", label="Ligand"),
                TableColumn(key="hit", label=f"{annotation['accession']} residues", align="right", mono=True),
                TableColumn(key="structure", label=f"{template.accession} residues", align="right", mono=True),
                TableColumn(key="conserved", label="Residues"),
                TableColumn(key="plddt", label="Site pLDDT", align="right"),
            ],
            rows=[{
                "type": site["type"],
                "ligand": site["ligand"] or "—",
                "hit": f"{site['target_range'][0]}–{site['target_range'][1]}",
                "structure": f"{site['query_range'][0]}–{site['query_range'][1]}",
                "conserved": "conserved" if site["conserved"] else "differ",
                "plddt": "—" if not math.isfinite(site["site_plddt"]) else f"{site['site_plddt']:.0f}",
            } for site in annotation["sites"]],
        ))
    if annotation is not None:
        link = Link(label=f"UniProt {annotation['accession']}", url=f"https://www.uniprot.org/uniprotkb/{annotation['accession']}/entry")
        if all(existing.url != link.url for existing in links):
            links.append(link)

    def _plain_hit(hit: dict[str, Any]) -> dict[str, Any]:
        return {key: hit[key] for key in _KEPT_HIT_FIELDS if key in hit}

    raw: dict[str, Any] = {
        "uniprot_id": template.accession,
        "template": {
            "accession": template.accession, "entry": template.entry, "protein": template.protein,
            "organism": template.organism, "gene": template.gene, "identity": template.identity,
            "coverage": template.coverage, "passed": template.passed,
        },
        "alphafold": alphafold,
        "foldseek_top_hits": {database: _plain_hit(hit) for database, hit in hits.items()},
        "properties": {
            "molecular_weight_da": round(props["mol_weight"], 2),
            "isoelectric_point": round(props["pI"], 2),
            "gravy": round(props["gravy"], 3),
            "instability_index": round(props["instability"], 2),
        },
        "model": {"atoms": props["atoms"], "dimensions_angstrom": [round(span, 1) for span in props["spans"]]},
        "structure": {
            "residues": s["n"],
            "has_plddt": bool(s["has_plddt"]),
            "mean_plddt": round(mean_plddt, 1) if mean_plddt is not None else None,
            "plddt": [round(v, 1) for v in plddt_values],
            "disordered": [list(run) for run in s["disordered"]],
            "low_confidence": [list(run) for run in s["low_conf"]],
            "secondary_structure": None if not s["ss"] else {k: round(v, 3) for k, v in s["ss"].items()},
            "radius_of_gyration": round(s["rg"], 2),
            "radius_of_gyration_expected": round(s["rg_exp"], 2),
            "surface_hydrophobic_fraction": round(float(s["surf_hphob"]), 3),
            "surface_net_charge": int(s["surf_charge"]),
            "maps_onto_query": maps,
        },
        "best_hit": None if best is None else {**_plain_hit(best), "coverage": _number(_coverage(best))},
        "annotation_transfer": {
            "status": findings["transfer"],  # None (no hits), "no AFDB hit", "weak", "unavailable" or "transferred"
            "afdb_hit": None if afdb_hit is None else {**_plain_hit(afdb_hit), "coverage": _number(_coverage(afdb_hit))},
            "annotation": None if annotation is None else {
                "accession": annotation["accession"],
                "name": annotation["name"],
                "function": annotation["function"],
                "sites": [
                    {**site, "target_range": list(site["target_range"]), "query_range": list(site["query_range"]),
                     "site_plddt": _number(site["site_plddt"])}
                    for site in annotation["sites"]
                ],
            },
        },
        "report": [text for _, text in lines] + ([s["ss_error"]] if s["ss_error"] else []),
    }

    return LevelResult(
        source="live",
        headline=headline,
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )


# --- The entry point used by the app ------------------------------------------------


def template_from_primary(ctx: StageContext) -> Homologue:
    """The UniProt entry to analyse: the primary level's closest Swiss-Prot match."""
    result = ctx.level_result("primary")
    if result is None:
        raise LevelSkipped(
            "This level analyses the AlphaFold DB structure of the primary level's closest Swiss-Prot match, "
            "but the primary level gave no result."
        )
    if result.source != "live":
        raise LevelSkipped("The primary level shows placeholder data, so there is no UniProt ID to analyse.")
    template = primary_homologue(result)
    if template is None:
        raise LevelSkipped(
            "The primary level found no Swiss-Prot match, so there is no UniProt ID to fetch an AlphaFold DB structure for."
        )
    return template


def run(sequence: str, template: Homologue, ctx: StageContext) -> LevelResult:
    """The notebook's pipeline (Steps 1A, 1B, 2, 3) for one UniProt entry."""
    with tempfile.TemporaryDirectory(prefix="pfp-tertiary-") as directory:
        try:
            alphafold, pdb_path, pdb_data = fetch_alphafold_structure(template.accession, ctx, Path(directory))
        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not reach AlphaFold DB ({error.__class__.__name__}). Check the internet connection."
            ) from error
        try:
            hits = identify_structure(pdb_path.name, pdb_data, ctx)
        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not reach Foldseek ({error.__class__.__name__}). Check the internet connection."
            ) from error
        ctx.report("Profiling the structure (ProtParam, size)…")
        props = analyze_properties(sequence, str(pdb_path))
        ctx.report("Analysing the structure (confidence, secondary structure, surface, annotation)…")
        s, lines, findings = analyze_tertiary_structure(str(pdb_path), hits)
    ctx.check_cancelled()
    return _to_level_result(sequence, template, alphafold, hits, props, s, lines, findings)


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """The app's entry point: analyse the structure of the primary level's closest match."""
    return run(sequence, template_from_primary(ctx), ctx)
