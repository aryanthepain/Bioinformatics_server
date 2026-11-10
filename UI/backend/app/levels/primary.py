"""Primary structure: the team's final notebook "Final_Primary_structure.ipynb" (3.1-fast-local).

The notebook's fast profile, with the remote EBI services as optional modules:

  fast local profile (under a minute)   optional remote EMBL-EBI services (minutes)
    validated sequence + query ID         BLASTp against UniProtKB/Swiss-Prot
    ProtParam                             InterProScan (domains, GO, pathways)
    DIAMOND --fast against Swiss-Prot
    HMMER hmmscan against Pfam-A
    ESM-2 embedding (esm2_t6_8M, 320-d) + nearest neighbours in the demo reference
                 UniProt metadata for the 3 best candidates
                                  |
        evidence integration -> confidence tier A / B / C / D

Here it runs in two phases, so the website stays fast:
  1. analyze(): the notebook's fast profile (RUN_EBI_BLAST = RUN_INTERPROSCAN = False):
     the local tools, the ESM-2 retrieval and the UniProt metadata. The result is
     shown, and used by the prediction, straight away.
  2. refine(): only when the server has an EBI contact e-mail (PFP_EBI_EMAIL), the
     optional BLASTp and InterProScan modules, then the same evidence integration
     on all modules. The runner calls it in the background (app/runner.py) and the
     result and prediction are updated when it finishes. Without the e-mail the
     result stays the notebook's fast profile.

The notebook's functions keep their names, thresholds, rules and texts. Plumbing
changes only:
  * tool paths, databases and the EBI contact e-mail come from configuration;
  * DIAMOND and hmmscan, HTTP retries and EBI polling stop when the user cancels;
  * safe_module lets a cancellation through instead of recording "unavailable";
  * BLASTp and InterProScan run at the same time, and UniProt entries already
    fetched are not fetched again; UniProt lookups stop after two failures in a
    row (the server is then unreachable), so they cannot hold up the result.
Additions used only for display (they never change the tier):
  * DIAMOND also writes each subject's title, so the candidates after the first
    three (which get no UniProt lookup) and hits found while UniProt cannot be
    reached keep a name;
  * each Pfam domain keeps its description from the hmmscan table.
Left out on purpose: the user-supplied reference FASTA for the ESM-2 retrieval (the
notebook's REFERENCE_FASTA_PATH, a file upload in Colab; the demo reference is used,
as in the notebook's default), the validation, sensitivity and benchmark sections
(experiments on the notebook itself, reproduced by scripts/check_primary.py) and
the report files.
"""

import copy
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from ..config import (
    DIAMOND_BIN,
    EBI_BLAST_TIMEOUT_SECONDS,
    EBI_EMAIL,
    EBI_INTERPRO_TIMEOUT_SECONDS,
    HMMSCAN_BIN,
    PRIMARY_DATA_DIR,
    PRIMARY_TOOL_TIMEOUT_SECONDS,
)
from ..jobs import AnalysisCancelled, LevelSkipped, StageContext
from ..mllock import ML_LOCK
from ..schemas import (
    EvidenceItem,
    Headline,
    LevelResult,
    Link,
    Metric,
    Note,
    Segment,
    Table,
    TableColumn,
    Track,
)

logger = logging.getLogger(__name__)

# Change this whenever the logic below changes, so cached results are not reused.
CACHE_VERSION = "primary-4"
PIPELINE_VERSION = "3.1-fast-local"
EXECUTION_PROFILE = "fast_local"
NOTEBOOK = "Final_Primary_structure.ipynb"

# ---------------- module switches (notebook section 1, fast profile) ----------------
# RUN_EBI_BLAST / RUN_INTERPROSCAN are False in the notebook ("remote queue can exceed the
# 5-minute budget"); here they are the optional background phase, on only with PFP_EBI_EMAIL.
USE_DEMO_REFERENCE = True  # small illustrative retrieval reference

# ---------------- decision thresholds (notebook section 1) ----------------
IDENTITY_THRESHOLD = 30.0  # % identity: rule-of-thumb lower bound for confident homology transfer
QUERY_COVERAGE_THRESHOLD = 80.0  # % of query covered by the alignment
VERY_HIGH_IDENTITY = 90.0  # near-identical match
HMMER_EVAL_THRESHOLD = 1e-10  # Pfam domain independent E-value

ESM_MODEL_NAME = "facebook/esm2_t6_8M_UR50D"
EBI_BASE = "https://www.ebi.ac.uk/Tools/services/rest"
DIAMOND_DB = PRIMARY_DATA_DIR / "swissprot.dmnd"
PFAM_HMM = PRIMARY_DATA_DIR / "Pfam-A.hmm"
PFAM_PRESSED = [Path(f"{PFAM_HMM}{suffix}") for suffix in (".h3m", ".h3i", ".h3f", ".h3p")]

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")
EBI_MODULES = ("ebi_blastp", "interproscan")


# =====================================================================================
# Setup checks and plumbing
# =====================================================================================


def missing_setup() -> list[str]:
    """What still needs installing before the local tools can run (empty = ready)."""
    missing: list[str] = []
    if shutil.which(DIAMOND_BIN) is None:
        missing.append("DIAMOND (brew install diamond)")
    if shutil.which(HMMSCAN_BIN) is None:
        missing.append("HMMER (brew install hmmer)")
    if not DIAMOND_DB.is_file():
        missing.append("the Swiss-Prot database")
    if not PFAM_HMM.is_file() or not all(path.is_file() for path in PFAM_PRESSED):
        missing.append("the pressed Pfam-A database")
    return missing


def ebi_enabled() -> bool:
    """The remote EBI modules run only when a contact e-mail is configured."""
    return bool(EBI_EMAIL)


def _run_command(cmd: list[str], ctx: StageContext, timeout: float) -> tuple[int, str]:
    """subprocess.run with capture, but stopped when the user cancels or it takes too long.

    Returns (exit code, standard error).
    """
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.monotonic() + timeout
    while True:
        try:
            _, stderr = process.communicate(timeout=0.5)
            return process.returncode, stderr.decode(errors="replace").strip()
        except subprocess.TimeoutExpired:
            if ctx.cancelled or time.monotonic() > deadline:
                process.kill()
                process.communicate()
                if ctx.cancelled:
                    raise AnalysisCancelled() from None
                raise RuntimeError(f"{Path(cmd[0]).name} did not finish within {timeout / 60:.0f} minutes.") from None


class _Progress:
    """One live progress line for several modules running at the same time."""

    def __init__(self, ctx: StageContext, names: list[str]) -> None:
        self._ctx = ctx
        self._lock = threading.Lock()
        self._state = dict.fromkeys(names, "submitting")

    def set(self, name: str, text: str) -> None:
        with self._lock:
            self._state[name] = text

    def report(self) -> None:
        with self._lock:
            parts = [f"{name}: {text}" for name, text in self._state.items()]
        self._ctx.report(" · ".join(parts))  # the interface shows the elapsed time itself


def _wait_for(futures: dict[str, Future[Any]], report: Callable[[], None]) -> None:
    """Wait for the futures, reporting progress (report() raises if the user cancels)."""
    while not all(future.done() for future in futures.values()):
        report()
        time.sleep(0.5)


# =====================================================================================
# Notebook section 2 - input validation
# =====================================================================================


def clean_sequence(raw):
    lines = [x.strip() for x in raw.strip().splitlines() if x.strip()]
    seq = re.sub(r"\s+", "", "".join(x for x in lines if not x.startswith(">"))).upper()
    if not seq:
        raise ValueError("Empty protein sequence.")
    invalid = sorted(set(seq) - VALID_AA)
    if invalid:
        raise ValueError(f"Unsupported amino-acid symbols: {invalid}. Resolve these explicitly.")
    # (The notebook's warnings.warn for < 10 residues is shown as a note by build_level_result.)
    return seq


def make_query_id(seq):
    return "query_" + hashlib.sha1(seq.encode()).hexdigest()[:10]


# =====================================================================================
# Notebook section 3 - shared helpers
# =====================================================================================

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "IntegratedProteinPipeline/3.0 (academic use)"})


def request_with_retry(method, url, *, ctx, max_retries=4, timeout=60, **kwargs):
    last_error = None
    for attempt in range(max_retries):
        ctx.check_cancelled()
        try:
            r = SESSION.request(method, url, timeout=timeout, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                ctx.sleep(min(2**attempt, 20))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries - 1:
                ctx.sleep(min(2**attempt, 20))
    raise RuntimeError(f"HTTP request failed after retries: {last_error}")


def ebi_job(tool, params, result_type, *, ctx, on_status=None, poll_seconds=20, max_wait_seconds=3600):
    payload = dict(params)
    payload["email"] = EBI_EMAIL
    job_id = request_with_retry("POST", f"{EBI_BASE}/{tool}/run", ctx=ctx, data=payload, timeout=90).text.strip()
    if not job_id:
        raise RuntimeError(f"{tool}: empty job ID returned")
    t0 = time.time()
    while time.time() - t0 < max_wait_seconds:
        status = request_with_retry("GET", f"{EBI_BASE}/{tool}/status/{job_id}", ctx=ctx).text.strip().upper()
        if on_status is not None:
            on_status(status.lower())
        if status == "FINISHED":
            break
        if status in {"FAILURE", "ERROR", "NOT_FOUND"}:
            raise RuntimeError(f"{tool} job {job_id} ended with status {status}")
        ctx.sleep(poll_seconds)
    else:
        raise TimeoutError(f"{tool} job {job_id} exceeded {max_wait_seconds}s")
    res = request_with_retry("GET", f"{EBI_BASE}/{tool}/result/{job_id}/{result_type}", ctx=ctx, timeout=180)
    return {"job_id": job_id, "status": "FINISHED", "result": res.text}


def safe_module(name, fn):
    t0 = time.perf_counter()
    try:
        data = fn()
        return {"source": name, "status": "success",
                "elapsed_seconds": round(time.perf_counter() - t0, 3), "data": data}
    except AnalysisCancelled:
        raise  # the user stopped the analysis: not a module failure
    except Exception as exc:  # noqa: BLE001 - recorded as "unavailable", as in the notebook
        return {"source": name, "status": "unavailable",
                "elapsed_seconds": round(time.perf_counter() - t0, 3),
                "error": str(exc), "data": None}


def skipped(name):
    return {"source": name, "status": "skipped", "data": None}


def write_fasta(path, seq, identifier="query"):
    Path(path).write_text(f">{identifier}\n" + "\n".join(textwrap.wrap(seq, 60)) + "\n")
    return str(path)


def normalize_uniprot_accession(text):
    """'sp|P31749|AKT1_HUMAN' -> 'P31749';  'UniProtKB:P31749' -> 'P31749'."""
    text = str(text or "").strip()
    m = re.search(r"(?:sp|tr)\|([^|]+)\|", text, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    if ":" in text:
        text = text.split(":")[-1]
    if "|" in text:
        parts = text.split("|")
        text = next((p for p in parts if re.fullmatch(r"[A-Z0-9]{6,10}(?:-[0-9]+)?", p)), parts[-1])
    return text.split()[0] if text else None


# =====================================================================================
# Notebook section 4 - physicochemical analysis
# =====================================================================================


def _protein_analysis() -> Any:
    try:
        from Bio.SeqUtils.ProtParam import ProteinAnalysis
    except ImportError as error:
        raise RuntimeError("Biopython is not installed. Run `uv sync` in UI/backend.") from error
    return ProteinAnalysis


def protparam_analysis(sequence):
    p = _protein_analysis()(sequence)
    helix, turn, sheet = p.secondary_structure_fraction()
    n = len(sequence)
    pct = {aa: 100.0 * sequence.count(aa) / n for aa in sorted(VALID_AA)}
    # Ikai (1980): AI = %Ala + 2.9*%Val + 3.9*(%Ile + %Leu)
    aliphatic = pct["A"] + 2.9 * pct["V"] + 3.9 * (pct["I"] + pct["L"])
    return {
        "length_aa": n,
        "molecular_weight_Da": round(p.molecular_weight(), 2),
        "theoretical_pI": round(p.isoelectric_point(), 3),
        "instability_index_heuristic": round(p.instability_index(), 3),
        "gravy": round(p.gravy(), 4),
        "aromaticity": round(p.aromaticity(), 4),
        "aliphatic_index": round(aliphatic, 3),
        "helix_propensity_fraction": round(helix, 4),
        "turn_propensity_fraction": round(turn, 4),
        "sheet_propensity_fraction": round(sheet, 4),
        "amino_acid_percent": {k: round(v, 3) for k, v in pct.items()},
    }


def interpret_physicochemical(phys):
    out = []
    ii = phys["instability_index_heuristic"]
    out.append("Instability index > 40: sequence-based heuristic flags possible in-vitro instability (not a measurement)."
               if ii > 40 else
               "Instability index <= 40: heuristic does not flag instability (does not prove stability).")
    g = phys["gravy"]
    out.append("Positive GRAVY: hydrophobic on average (does not by itself prove membrane localization)."
               if g > 0 else
               "Negative GRAVY: hydrophilic on average (does not by itself establish localization/solubility).")
    pI = phys["theoretical_pI"]
    if pI < 7.4:
        out.append("Theoretical pI < 7.4: expected net negative charge at pH 7.4 (anion-exchange binding possible; test experimentally).")
    elif pI > 7.4:
        out.append("Theoretical pI > 7.4: expected net positive charge at pH 7.4 (cation-exchange binding possible; test experimentally).")
    else:
        out.append("Theoretical pI ~ 7.4: net charge may be close to zero at that pH.")
    return out


# =====================================================================================
# Notebook section 5 - EMBL-EBI BLASTp against UniProtKB/Swiss-Prot (remote)
# =====================================================================================


def _xml_child(el, tag):
    return next((c for c in el if c.tag.split("}")[-1] == tag), None)


def _xml_text(el, tag, default=None):
    c = _xml_child(el, tag)
    return default if (c is None or c.text is None) else c.text.strip()


def run_ebi_blast(sequence, top_n=20, *, ctx, on_status=None):
    job = ebi_job("ncbiblast",
                  {"program": "blastp", "stype": "protein",
                   "database": "uniprotkb_swissprot", "sequence": sequence},
                  result_type="xml", poll_seconds=20, ctx=ctx, on_status=on_status,
                  max_wait_seconds=EBI_BLAST_TIMEOUT_SECONDS)
    raw = job["result"]
    if not raw or not raw.strip():
        raise RuntimeError("BLAST returned empty XML.")
    root = ET.fromstring(raw)
    result = next((e for e in root.iter() if e.tag.split("}")[-1] == "SequenceSimilaritySearchResult"), None)
    if result is None:
        raise RuntimeError("SequenceSimilaritySearchResult not found in BLAST XML.")
    hits_el = _xml_child(result, "hits")
    if hits_el is None:
        return {"job_id": job["job_id"], "hits": []}

    hits = []
    for hit in list(hits_el)[:top_n]:
        if hit.tag.split("}")[-1] != "hit":
            continue
        subject_len = int(hit.attrib.get("length", 0))
        aln_el = _xml_child(hit, "alignments")
        if aln_el is None:
            continue
        for aln in aln_el:
            if aln.tag.split("}")[-1] != "alignment":
                continue
            q = _xml_child(aln, "querySeq"); m = _xml_child(aln, "matchSeq")
            if q is None:
                continue
            qs, qe = int(q.attrib.get("start", 0)), int(q.attrib.get("end", 0))
            qspan = abs(qe - qs) + 1
            ss = se = sspan = None
            if m is not None:
                ss, se = int(m.attrib.get("start", 0)), int(m.attrib.get("end", 0))
                sspan = abs(se - ss) + 1
            hits.append({
                "method": "BLASTp (EBI)",
                "hit_id": hit.attrib.get("id"),
                "accession": normalize_uniprot_accession(hit.attrib.get("ac") or hit.attrib.get("id")),
                "title": hit.attrib.get("description", ""),
                "identity_percent": round(float(_xml_text(aln, "identity", 0)), 2),
                "query_coverage_percent_approx": round(100.0 * qspan / len(sequence), 2),
                "subject_coverage_percent_approx": round(100.0 * sspan / subject_len, 2) if (subject_len and sspan) else None,
                "alignment_length": qspan,
                "query_start": qs, "query_end": qe, "subject_start": ss, "subject_end": se,
                "evalue": float(_xml_text(aln, "expectation", 0)),
                "bitscore": float(_xml_text(aln, "bits", 0)),
            })
    hits.sort(key=lambda h: (-h["bitscore"], h["evalue"]))
    return {"job_id": job["job_id"], "hits": hits}


# =====================================================================================
# Notebook section 6 - local DIAMOND against Swiss-Prot
# =====================================================================================


def run_local_diamond(sequence, db=DIAMOND_DB, top_n=20, evalue=1e-5, mode='fast', *, ctx):
    if mode not in {"fast", "sensitive"}:
        raise ValueError("mode must be either fast or sensitive")
    exe = shutil.which(DIAMOND_BIN)
    if exe is None:
        raise RuntimeError("DIAMOND executable not found (run scripts/setup_primary.sh).")
    if not Path(db).exists():
        raise FileNotFoundError(f"DIAMOND database not found: {db}")
    with tempfile.TemporaryDirectory(prefix="pfp-diamond-") as td:
        fasta, out = Path(td) / "q.fasta", Path(td) / "hits.tsv"
        write_fasta(fasta, sequence)
        cmd = [exe, "blastp", "--db", str(db), "--query", str(fasta), "--out", str(out),
               "--outfmt", "6", "qseqid", "sseqid", "pident", "length", "qstart", "qend",
               "sstart", "send", "evalue", "bitscore", "qlen", "slen",
               "stitle",  # display only: the subject's name, organism and gene
               "--max-target-seqs", str(top_n), "--evalue", str(evalue),
               ("--fast" if mode == "fast" else "--sensitive"), "--threads", "4", "--quiet"]
        returncode, stderr = _run_command(cmd, ctx, PRIMARY_TOOL_TIMEOUT_SECONDS)
        if returncode != 0:
            raise RuntimeError(stderr or "DIAMOND failed")
        hits = []
        if out.exists():
            for line in out.read_text().splitlines():
                x = line.split("\t")
                if len(x) != 13:
                    continue
                qs, qe, ss, se = map(int, x[4:8]); qlen, slen = int(x[10]), int(x[11])
                hits.append({
                    "method": "DIAMOND (local)",
                    "hit_id": x[1], "accession": normalize_uniprot_accession(x[1]), "title": x[12] or None,
                    "identity_percent": float(x[2]),
                    "alignment_length": int(x[3]),
                    "query_coverage_percent_approx": round(100.0 * (abs(qe - qs) + 1) / qlen, 2) if qlen else 0.0,
                    "subject_coverage_percent_approx": round(100.0 * (abs(se - ss) + 1) / slen, 2) if slen else None,
                    "query_start": qs, "query_end": qe, "subject_start": ss, "subject_end": se,
                    "evalue": float(x[8]), "bitscore": float(x[9]),
                })
    hits.sort(key=lambda h: (-h["bitscore"], h["evalue"]))
    return {"hits": hits, "database": str(db)}


# =====================================================================================
# Notebook section 7 - InterProScan (remote)
# =====================================================================================


def run_interpro(sequence, *, ctx, on_status=None):
    job = ebi_job("iprscan5", {"sequence": sequence, "goterms": "true", "pathways": "true"},
                  result_type="tsv", poll_seconds=30, ctx=ctx, on_status=on_status,
                  max_wait_seconds=EBI_INTERPRO_TIMEOUT_SECONDS)
    def to_int(v):
        try: return int(v)
        except (TypeError, ValueError): return None
    def to_float(v):
        try: return float(v)
        except (TypeError, ValueError): return None
    rows = []
    for line in job["result"].splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        c = line.rstrip("\n").split("\t")
        if len(c) < 15:
            continue
        rows.append({
            "analysis": c[3], "signature_accession": c[4], "signature_description": c[5],
            "start": to_int(c[6]), "end": to_int(c[7]), "score": to_float(c[8]),
            "interpro_accession": c[11] if c[11] != "-" else None,
            "interpro_description": c[12] if c[12] != "-" else None,
            "go_terms": c[13].split("|") if c[13] and c[13] != "-" else [],
            "pathways": c[14].split("|") if c[14] and c[14] != "-" else [],
        })
    return {"job_id": job["job_id"], "matches": rows}


# =====================================================================================
# Notebook section 8 - local HMMER (hmmscan) against Pfam-A
# =====================================================================================


def run_local_hmmer(sequence, hmm_db=PFAM_HMM, evalue_cutoff=1e-5, *, ctx):
    exe = shutil.which(HMMSCAN_BIN)
    if exe is None:
        raise RuntimeError("hmmscan not found (run scripts/setup_primary.sh).")
    if not Path(hmm_db).exists():
        raise FileNotFoundError(f"Pfam HMM database not found: {hmm_db}")
    with tempfile.TemporaryDirectory(prefix="pfp-hmmer-") as td:
        fasta, out = Path(td) / "q.fasta", Path(td) / "dom.tbl"
        write_fasta(fasta, sequence)
        returncode, stderr = _run_command(
            [exe, "--cpu", "4", "--noali", "-o", os.devnull, "--domtblout", str(out),
             "-E", str(evalue_cutoff), "--domE", str(evalue_cutoff), str(hmm_db), str(fasta)],
            ctx, PRIMARY_TOOL_TIMEOUT_SECONDS)
        if returncode != 0:
            raise RuntimeError(stderr or "hmmscan failed")
        domains = []
        if out.exists():
            for line in out.read_text().splitlines():
                if not line or line.startswith("#"):
                    continue
                x = line.split(maxsplit=22)
                if len(x) < 22:
                    continue
                domains.append({
                    "pfam_name": x[0], "pfam_accession": x[1], "pfam_accession_base": x[1].split(".")[0],
                    "full_sequence_evalue": float(x[6]),
                    "domain_i_evalue": float(x[12]), "domain_score": float(x[13]),
                    "hmm_from": int(x[15]), "hmm_to": int(x[16]),
                    "alignment_from": int(x[17]), "alignment_to": int(x[18]),
                    "envelope_from": int(x[19]), "envelope_to": int(x[20]),
                    "accuracy": float(x[21]),
                    "description": x[22].strip() if len(x) > 22 else "",  # display only
                })
    domains.sort(key=lambda d: d["domain_i_evalue"])
    return {"domains": domains, "database": str(hmm_db)}


# =====================================================================================
# Notebook section 9 - UniProt metadata for homology candidates
# =====================================================================================


def merge_homology(*modules):
    """Combine hit lists from BLAST and DIAMOND into one table; keep the best alignment per accession."""
    best = {}
    for mod in modules:
        if mod and mod.get("status") == "success":
            for h in (mod.get("data") or {}).get("hits", []):
                acc = h.get("accession")
                if acc and (acc not in best or h["bitscore"] > best[acc]["bitscore"]):
                    best[acc] = h
    return sorted(best.values(), key=lambda h: (-h["bitscore"], h["evalue"]))


def fetch_uniprot_entry(accession, *, ctx):
    acc = normalize_uniprot_accession(accession)
    if not acc:
        raise ValueError("No UniProt accession could be extracted.")
    j = request_with_retry("GET", f"https://rest.uniprot.org/uniprotkb/{acc}.json", ctx=ctx, max_retries=1, timeout=8).json()
    pd_ = j.get("proteinDescription", {})
    name = pd_.get("recommendedName", {}).get("fullName", {}).get("value")
    if not name:
        subs = pd_.get("submissionNames", [])
        name = subs[0].get("fullName", {}).get("value") if subs else None
    genes = j.get("genes", [])
    org = j.get("organism", {})
    func = [t["value"] for c in j.get("comments", []) if c.get("commentType") == "FUNCTION"
            for t in c.get("texts", []) if t.get("value")]
    entry_type = str(j.get("entryType", "")).lower()
    return {
        "accession": j.get("primaryAccession", acc),
        "entry_type": j.get("entryType"),
        "reviewed": entry_type.startswith("uniprotkb reviewed") or "swiss-prot" in entry_type,
        "protein_name": name,
        "gene_name": genes[0].get("geneName", {}).get("value") if genes else None,
        "organism": org.get("scientificName"),
        "taxon_id": org.get("taxonId"),
        "function_annotation": " ".join(func) or None,
        "sequence_length": j.get("sequence", {}).get("length"),
        "uniprot_url": f"https://www.uniprot.org/uniprotkb/{acc}",
    }


def enrich_hits(hits, max_entries=3, *, ctx, known=None):
    """known: UniProt entries already fetched (by accession), which are reused."""
    known = known or {}
    out = []
    failures = 0
    for h in hits[:max_entries]:
        if h["accession"] in known:
            out.append({**h, "uniprot": known[h["accession"]]})
            continue
        if failures >= 2:
            out.append({**h, "uniprot_error": "skipped: UniProt could not be reached"})
            continue
        try:
            out.append({**h, "uniprot": fetch_uniprot_entry(h["accession"], ctx=ctx)})
            failures = 0
        except AnalysisCancelled:
            raise
        except Exception as e:  # noqa: BLE001 - recorded per entry, as in the notebook
            out.append({**h, "uniprot_error": str(e)})
            failures += 1
        ctx.sleep(0.05)
    return out


# =====================================================================================
# Notebook section 10 - ESM-2 protein language-model embedding
# =====================================================================================

_ESM: dict[str, Any] = {"tokenizer": None, "model": None, "torch": None, "device": None}
_ESM_LOCK = threading.Lock()


def load_esm2():
    with _ESM_LOCK, ML_LOCK:  # ML_LOCK: one thread at a time imports and loads the ML libraries (app/mllock.py)
        if _ESM["model"] is None:
            try:
                import torch
                from transformers import AutoTokenizer, EsmModel
            except ImportError as error:
                raise RuntimeError(
                    "PyTorch and Transformers are not installed. Run `uv sync` in UI/backend, then restart the backend."
                ) from error
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device.type == "cpu":  # the notebook's fast-profile preflight (section 1)
                torch.set_num_threads(4)
            tokenizer = AutoTokenizer.from_pretrained(ESM_MODEL_NAME)
            model = EsmModel.from_pretrained(ESM_MODEL_NAME).to(device).eval()
            _ESM.update(tokenizer=tokenizer, model=model, torch=torch, device=device)
    return _ESM["tokenizer"], _ESM["model"]


def esm2_embedding(sequence, chunk_size=900, overlap=100):
    import numpy as np

    tok, model = load_esm2()
    torch, device = _ESM["torch"], _ESM["device"]
    if len(sequence) <= chunk_size:
        chunks = [sequence]
    else:
        chunks, step = [], chunk_size - overlap
        for s in range(0, len(sequence), step):
            chunks.append(sequence[s:s + chunk_size])
            if s + chunk_size >= len(sequence):
                break
    vecs, weights = [], []
    with torch.no_grad():
        for ch in chunks:
            enc = {k: v.to(device) for k, v in tok(ch, return_tensors="pt", add_special_tokens=True).items()}
            hidden = model(**enc).last_hidden_state
            vecs.append(hidden[0, 1:1 + len(ch), :].mean(dim=0).cpu().numpy())   # drop BOS/EOS
            weights.append(len(ch))
    return np.average(np.vstack(vecs), axis=0, weights=np.array(weights)).astype(np.float32)


def run_esm2(sequence):
    vec = esm2_embedding(sequence)
    return {"model": ESM_MODEL_NAME, "embedding": vec.tolist(), "dimensions": int(vec.shape[0])}


# =====================================================================================
# Notebook section 10b - embedding retrieval against a labelled reference
# =====================================================================================

# The same four well-characterised proteins are reused for validation in Section 13.
KNOWN_PROTEINS = {
    "AKT1 (human)": {
        "accession": "P31749",
        "function": "RAC-alpha serine/threonine-protein kinase (AGC kinase, PI3K/AKT signalling)",
        "expected_regex": r"P31749|AKT1",
        "sequence": "MSDVAIVKEGWLHKRGEYIKTWRPRYFLLKNDGTFIGYKERPQDVDQREAPLNNFSVAQCQLMKTERPRPNTFIIRCLQWTTVIERTFHVETPEEREEWTTAIQTVADGLKKQEEEEMDFRSGSPSDNSGAEEMEVSLAKPKHRVTMNEFEYLKLLGKGTFGKVILVKEKATGRYYAMKILKKEVIVAKDEVAHTLTENRVLQNSRHPFLTALKYSFQTHDRLCFVMEYANGGELFFHLSRERVFSEDRARFYGAEIVSALDYLHSEKNVVYRDLKLENLMLDKDGHIKITDFGLCKEGIKDGATMKTFCGTPEYLAPEVLEDNDYGRAVDWWGLGVVMYEMMCGRLPFYNQDHEKLFELILMEEIRFPRTLGPEAKSLLSGLLKKDPKQRLGGGSEDAKEIMQHRFFAGIVWQHVYEKKLSPPFKPQVTSETDTRYFDEEFTAQMITITPPDQDDSMECVDSERRPHFPQFSYSASGTA",
    },
    "Bacteriorhodopsin": {
        "accession": "P02945",
        "function": "Bacteriorhodopsin (light-driven proton pump, membrane protein)",
        "expected_regex": r"P02945|BACR",
        "sequence": "MLELLPTAVEGVSQAQITGRPEWIWLALGTALMGLGTLYFLVKGMGVSDPDAKKFYAITTLVPAIAFTMYLSMLLGYGLTMVPFGGEQNPIYWARYADWLFTTPLLLLDLALLVDADQGTILALVGADGIMIGTGLVGALTKVYSYRFVWWAISTAAMLYILYVLFFGFTSKAESMRPEVASTFKVLRNVTVVLWSAYPVVWLIGSEGAGIVPLNIETLLFMVLDVSAKVGFGLILLRSRAIFGEAEAPEPSAGDGAAATSD",
    },
    "p53 (human)": {
        "accession": "P04637",
        "function": "Cellular tumor antigen p53 (transcription factor, tumour suppressor)",
        "expected_regex": r"P04637|P53_",
        "sequence": "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHECSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD",
    },
    "Ubiquitin": {
        "accession": "Q865C5",
        "function": "Ubiquitin (protein modification / degradation signal)",
        "expected_regex": r"UBIQ|UBB_|UBC_|RS27A|UBA52|Ubiquitin",   # identical in many species -> ties
        "sequence": "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
    },
}
DEMO_REFERENCE_TYPE = "DEMO (4 proteins, illustration only)"


def demo_reference():
    return [{"accession": v["accession"], "function": v["function"], "sequence": v["sequence"]}
            for v in KNOWN_PROTEINS.values()]


_REF_VEC_CACHE: dict[str, Any] = {}


def _ref_vector(seq):
    key = hashlib.sha1(seq.encode()).hexdigest()
    if key not in _REF_VEC_CACHE:
        _REF_VEC_CACHE[key] = esm2_embedding(seq)
    return _REF_VEC_CACHE[key]


def cosine_similarity_matrix(q, M):
    import numpy as np

    q = q / (np.linalg.norm(q) + 1e-12)
    M = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-12)
    return M @ q


def esm_retrieval(query_seq, query_vec, refs, top_k=10):
    import numpy as np

    kept = [r for r in refs if r["sequence"] != query_seq]       # leakage guard
    excluded = len(refs) - len(kept)
    if not kept:
        raise ValueError("No reference sequences left after excluding identical sequences.")
    sims = cosine_similarity_matrix(np.asarray(query_vec, dtype=np.float32),
                                    np.vstack([_ref_vector(r["sequence"]) for r in kept]))
    order = np.argsort(-sims)[:top_k]
    return {"status": "success", "reference_size": len(kept), "identical_sequences_excluded": excluded,
            "hits": [{"accession": kept[i]["accession"], "function": kept[i]["function"],
                      "cosine_similarity": float(sims[i])} for i in order]}


def run_embedding_retrieval(sequence, esm_result):
    """The notebook's section 10b cell, with the demo reference (USE_DEMO_REFERENCE = True)."""
    embedding_retrieval = {"status": "skipped", "hits": []}
    if esm_result["status"] == "success":
        try:
            refs = demo_reference() if USE_DEMO_REFERENCE else []
            if refs:
                embedding_retrieval = esm_retrieval(sequence, esm_result["data"]["embedding"], refs)
                embedding_retrieval["reference_type"] = DEMO_REFERENCE_TYPE
        except Exception as e:  # noqa: BLE001 - recorded as "unavailable", as in the notebook
            embedding_retrieval = {"status": "unavailable", "error": str(e), "hits": []}
    return embedding_retrieval


# =====================================================================================
# Notebook section 11 - evidence integration and confidence tier
# =====================================================================================


def assess_function(homology_hits, hmmer_domains=None, interpro_matches=None):
    homology_hits, hmmer_domains, interpro_matches = homology_hits or [], hmmer_domains or [], interpro_matches or []
    best = max(homology_hits, key=lambda h: h["bitscore"]) if homology_hits else None

    ident = best["identity_percent"] if best else 0.0
    cov = best["query_coverage_percent_approx"] if best else 0.0
    strong = bool(best) and ident >= IDENTITY_THRESHOLD and cov >= QUERY_COVERAGE_THRESHOLD
    very_high = bool(best) and ident >= VERY_HIGH_IDENTITY and cov >= 90.0

    best_dom = min(hmmer_domains, key=lambda d: d["domain_i_evalue"]) if hmmer_domains else None
    hmmer_ok = bool(best_dom) and best_dom["domain_i_evalue"] < HMMER_EVAL_THRESHOLD
    ipr_ok = any(m.get("interpro_accession") for m in interpro_matches)
    domain_support = hmmer_ok or ipr_ok

    if very_high and domain_support:   tier = "A - Strong"
    elif (strong and domain_support) or very_high: tier = "B - Probable"
    elif strong or domain_support:     tier = "C - Partial (family/domain-level hypothesis)"
    else:                              tier = "D - Inconclusive / uncharacterised"

    why = []
    if best:
        why.append(f"Best homology hit: {best['accession']} - {ident:.1f}% identity, {cov:.1f}% query coverage, "
                   f"E={best['evalue']:.1e} ({best['method']}) -> {'strong' if strong else 'not strong'} by thresholds "
                   f"(>= {IDENTITY_THRESHOLD}% identity and >= {QUERY_COVERAGE_THRESHOLD}% coverage).")
    else:
        why.append("No homology hit available (modules skipped, unavailable, or no significant hit).")
    if best_dom:
        why.append(f"Best Pfam domain (HMMER): {best_dom['pfam_name']} ({best_dom['pfam_accession']}), "
                   f"independent E={best_dom['domain_i_evalue']:.1e} -> {'passes' if hmmer_ok else 'fails'} E < {HMMER_EVAL_THRESHOLD:g}.")
    if interpro_matches:
        n_int = len({m['interpro_accession'] for m in interpro_matches if m.get('interpro_accession')})
        why.append(f"InterProScan: {len(interpro_matches)} signature matches, {n_int} integrated InterPro entries.")
    if not (best_dom or interpro_matches):
        why.append("No domain evidence available (modules skipped, unavailable, or no domain found).")
    return {"tier": tier, "strong_homology": strong, "very_high_identity": very_high,
            "domain_support": domain_support, "best_hit": best, "best_domain": best_dom, "rationale": why}


def homology_concordance(blast_mod, diamond_mod):
    def top(mod):
        hs = (mod.get("data") or {}).get("hits", []) if mod.get("status") == "success" else []
        return max(hs, key=lambda h: h["bitscore"])["accession"] if hs else None
    b, d = top(blast_mod), top(diamond_mod)
    return {"blast_top": b, "diamond_top": d,
            "comparable": bool(b and d), "agree": (b == d) if (b and d) else None}


def domain_concordance(interpro_matches, hmmer_domains):
    ipr = {re.sub(r"\..*$", "", m["signature_accession"]) for m in (interpro_matches or [])
           if m.get("analysis") == "Pfam"}
    hmm = {d["pfam_accession_base"] for d in (hmmer_domains or []) if d["domain_i_evalue"] < HMMER_EVAL_THRESHOLD}
    return {"interpro_pfam": sorted(ipr), "hmmer_pfam": sorted(hmm),
            "shared": sorted(ipr & hmm), "only_interpro": sorted(ipr - hmm), "only_hmmer": sorted(hmm - ipr),
            "comparable": bool(ipr and hmm)}


def domain_architecture(interpro_matches):
    """One row per integrated InterPro entry, with the residue ranges of its member signatures."""
    groups = {}
    for m in interpro_matches or []:
        acc = m.get("interpro_accession")
        if not acc or m.get("start") is None:
            continue
        g = groups.setdefault(acc, {"interpro_accession": acc, "description": m.get("interpro_description"),
                                    "start": m["start"], "end": m["end"], "members": set(), "go_terms": set()})
        g["start"], g["end"] = min(g["start"], m["start"]), max(g["end"], m["end"])
        g["members"].add(m["analysis"]); g["go_terms"].update(m.get("go_terms", []))
    rows = [{**g, "members": ", ".join(sorted(g["members"])), "go_terms": "; ".join(sorted(g["go_terms"]))}
            for g in groups.values()]
    return sorted(rows, key=lambda r: r["start"])


def build_evidence_summary(homology_hits, uniprot_module, interpro_module, hmmer_module,
                           blast_module, diamond_module, embedding_module):
    ipr = (interpro_module.get("data") or {}).get("matches", []) if interpro_module.get("status") == "success" else []
    hmm = (hmmer_module.get("data") or {}).get("domains", []) if hmmer_module.get("status") == "success" else []
    meta = {}
    for item in (uniprot_module.get("data") or []):
        m = item.get("uniprot") or {}
        if m.get("accession"):
            meta[normalize_uniprot_accession(m["accession"])] = m
    cands = []
    for h in homology_hits:
        m = meta.get(h["accession"], {})
        cands.append({
            "accession": h["accession"], "method": h["method"],
            "protein_name": m.get("protein_name") or h.get("title"), "gene_name": m.get("gene_name"),
            "organism": m.get("organism"), "reviewed": m.get("reviewed"),
            "identity_percent": h["identity_percent"], "query_coverage_percent_approx": h["query_coverage_percent_approx"],
            "subject_coverage_percent_approx": h.get("subject_coverage_percent_approx"),
            "evalue": h["evalue"], "bitscore": h["bitscore"],
            "function_annotation": m.get("function_annotation"), "uniprot_url": m.get("uniprot_url"),
        })
    return {
        "assessment": assess_function(homology_hits, hmm, ipr),
        "top_homology_candidates": cands[:10],
        "domain_architecture": domain_architecture(ipr),
        "interpro_signatures": ipr,
        "hmmer_pfam_domains": hmm,
        "esm2_nearest_neighbours": embedding_module.get("hits", [])[:10] if embedding_module.get("status") == "success" else [],
        "concordance": {"homology": homology_concordance(blast_module, diamond_module),
                        "domains": domain_concordance(ipr, hmm)},
        "interpretation_notes": [
            "Identity and coverage are parsed from real alignments; coverage is the aligned query span (check HSPs for multi-segment hits).",
            "BLAST/DIAMOND hits are homology evidence and do not by themselves prove identical function.",
            "InterPro / Pfam signatures support domain- or family-level interpretation; overlapping signatures can describe the same region.",
            "UniProt annotations must be read with their reviewed status and evidence provenance.",
            "ESM-2 embeddings do not identify a protein; retrieval requires a labelled, non-redundant reference set.",
            "The tier is a rule-based summary, not a calibrated probability.",
        ],
    }


# =====================================================================================
# The two phases
# =====================================================================================


def _pending(name):
    """An EBI module that has not run yet (it runs in phase 2)."""
    return {"source": name, "status": "pending", "data": None}


def _not_configured(name):
    return {**skipped(name), "reason": "Optional remote module, off as in the notebook's fast profile "
                                       "(it runs only when the server has an EBI contact e-mail, PFP_EBI_EMAIL)."}


def _uniprot_module(modules, ctx, known=None):
    merged_hits = merge_homology(modules["ebi_blastp"], modules["local_diamond"])
    if not merged_hits:
        return {"source": "UniProt metadata", "status": "skipped", "data": []}
    return safe_module("UniProt metadata", lambda: enrich_hits(merged_hits, ctx=ctx, known=known))


def run_local_modules(sequence: str, ctx: StageContext) -> tuple[dict[str, Any], list[float] | None]:
    """Phase 1: the notebook's fast profile - local DIAMOND, HMMER, ESM-2 and ProtParam at the same
    time (its FAST_EXECUTOR / run_fast_suite), the ESM-2 retrieval, then UniProt for the best hits."""
    if _ESM["model"] is None:
        ctx.report("Loading the ESM-2 model (first analysis only)…")
    started = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="primary")
    try:
        futures = {
            "DIAMOND": pool.submit(safe_module, "Local DIAMOND", lambda: run_local_diamond(sequence, ctx=ctx)),
            "HMMER": pool.submit(safe_module, "Local HMMER/Pfam", lambda: run_local_hmmer(sequence, ctx=ctx)),
            "ESM-2": pool.submit(safe_module, "ESM-2", lambda: run_esm2(sequence)),
        }
        physicochemical = protparam_analysis(sequence)

        def report() -> None:
            waiting = [name for name, future in futures.items() if not future.done()]
            elapsed = int(time.monotonic() - started)
            ctx.report(f"Waiting for {', '.join(waiting)} · {elapsed // 60}:{elapsed % 60:02d} elapsed")

        _wait_for(futures, report)
        diamond, hmmer, esm = (futures[name].result() for name in ("DIAMOND", "HMMER", "ESM-2"))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    embedding = (esm.get("data") or {}).get("embedding") if esm["status"] == "success" else None
    if esm["status"] == "success":
        ctx.report("Comparing the ESM-2 embedding with the reference proteins…")
    embedding_retrieval = run_embedding_retrieval(sequence, esm)
    ctx.check_cancelled()
    modules = {
        "ebi_blastp": _pending("EMBL-EBI BLASTp") if ebi_enabled() else _not_configured("EMBL-EBI BLASTp"),
        "local_diamond": diamond,
        "interproscan": _pending("InterProScan") if ebi_enabled() else _not_configured("InterProScan"),
        "local_hmmer_pfam": hmmer,
        "esm2": {"source": "ESM-2", "status": esm.get("status"), "error": esm.get("error"),
                 "dimensions": (esm.get("data") or {}).get("dimensions"), "model": ESM_MODEL_NAME,
                 "device": str(_ESM["device"]) if _ESM["device"] is not None else None,
                 "elapsed_seconds": esm.get("elapsed_seconds")},
        "physicochemical": physicochemical,
        "embedding_retrieval": embedding_retrieval,
    }
    ctx.report("Looking up the best candidates in UniProt…")
    modules["uniprot"] = _uniprot_module(modules, ctx)
    return modules, [round(float(value), 6) for value in embedding] if embedding is not None else None


def run_ebi_modules(sequence: str, modules: dict[str, Any], ctx: StageContext) -> dict[str, Any]:
    """Phase 2: BLASTp and InterProScan (those not yet successful), then UniProt for new candidates."""
    modules = copy.deepcopy(modules)
    jobs = {
        "ebi_blastp": ("BLASTp", "EMBL-EBI BLASTp", run_ebi_blast),
        "interproscan": ("InterProScan", "InterProScan", run_interpro),
    }
    todo = [key for key in EBI_MODULES if modules[key].get("status") != "success"]
    progress = _Progress(ctx, [jobs[key][0] for key in todo])
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="primary-ebi")
    try:
        futures: dict[str, Future[Any]] = {}
        for key in todo:
            label, name, run = jobs[key]

            def call(label=label, run=run):
                return run(sequence, ctx=ctx, on_status=lambda status: progress.set(label, status))

            futures[key] = pool.submit(safe_module, name, call)
        _wait_for(futures, progress.report)
        for key, future in futures.items():
            modules[key] = future.result()
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    known = {  # by the hit's accession, which is what enrich_hits looks up
        item["accession"]: item["uniprot"]
        for item in (modules.get("uniprot") or {}).get("data") or []
        if isinstance(item.get("uniprot"), dict) and item.get("accession")
    }
    ctx.report("Looking up new candidates in UniProt…")
    modules["uniprot"] = _uniprot_module(modules, ctx, known)
    return modules


def needs_refinement(result: LevelResult) -> bool:
    """True when the EBI modules are enabled but have not all succeeded for this result."""
    if not ebi_enabled() or result.source != "live" or not isinstance(result.raw, dict):
        return False
    modules = result.raw.get("modules")
    if not isinstance(modules, dict):
        return False
    return any((modules.get(key) or {}).get("status") != "success" for key in EBI_MODULES)


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Phase 1, shown straight away. The runner then calls refine() if needs_refinement()."""
    missing = missing_setup()
    if missing:
        raise LevelSkipped(
            "Primary-structure analysis is not set up yet (missing: "
            + ", ".join(missing)
            + "). Run scripts/setup_primary.sh once, then restart the backend."
        )
    sequence = clean_sequence(sequence)
    modules, embedding = run_local_modules(sequence, ctx)
    return build_level_result(sequence, modules, embedding)


def refine(sequence: str, result: LevelResult, ctx: StageContext) -> LevelResult:
    """Phase 2: add BLASTp and InterProScan to the modules of `result` and integrate again."""
    sequence = clean_sequence(sequence)
    modules = run_ebi_modules(sequence, result.raw["modules"], ctx)
    return build_level_result(sequence, modules, result.raw.get("esm2_embedding"))


# =====================================================================================
# Translating the results for the interface
# =====================================================================================

_MODULE_ORDER = ("local_diamond", "ebi_blastp", "local_hmmer_pfam", "interproscan", "uniprot", "esm2",
                 "embedding_retrieval")
_MODULE_LABEL = {"embedding_retrieval": "ESM-2 retrieval (demo reference)"}
_NO_RETRIEVAL = {"status": "skipped", "hits": []}  # the notebook's value when ESM-2 did not run


def _module_label(key: str, module: dict[str, Any]) -> str:
    return _MODULE_LABEL.get(key) or module.get("source") or key


def _seconds(value: Any) -> str:
    return f"{value:.1f} s" if isinstance(value, (int, float)) else "—"


def _short(text: str | None, limit: int = 400) -> str:
    return textwrap.shorten(str(text or ""), limit, placeholder=" …") if text else ""


def _entry_name(hit_id: str | None) -> str:
    """'sp|P69905|HBA_HUMAN' or 'SP:HBA_HUMAN' -> 'HBA_HUMAN'."""
    text = str(hit_id or "").strip()
    if "|" in text:
        parts = text.split("|")
        return parts[2] if len(parts) > 2 and parts[2] else parts[-1]
    return text.split(":")[-1] if text else ""


def _title_parts(title: str | None, hit_id: str | None) -> tuple[str, str, str]:
    """A Swiss-Prot title -> (protein, organism, gene).

    DIAMOND titles start with the identifier ('sp|P69905|HBA_HUMAN Hemoglobin ...'),
    BLAST descriptions do not ('Hemoglobin subunit alpha OS=Homo sapiens ...').
    """
    text = str(title or "").strip()
    first, _, rest = text.partition(" ")
    if (hit_id and first == hit_id) or "|" in first:
        text = rest
    protein = text.split(" OS=", 1)[0].strip()
    organism = re.search(r"OS=(.+?)(?= OX=| GN=| PE=| SV=|$)", text)
    gene = re.search(r" GN=(\S+)", text)
    return protein, organism.group(1).strip() if organism else "", gene.group(1) if gene else ""


def describe_candidate(hit: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    """The readable details of a homology hit: UniProt metadata first, then its title."""
    candidate = candidate or {}
    protein, organism, gene = _title_parts(hit.get("title"), hit.get("hit_id"))
    if candidate.get("protein_name") and candidate.get("protein_name") != hit.get("title"):
        protein = candidate["protein_name"]
    return {
        "accession": hit.get("accession") or "",
        "entry": _entry_name(hit.get("hit_id")) or hit.get("accession") or "",
        "protein": protein,
        "organism": candidate.get("organism") or organism,
        "gene": candidate.get("gene_name") or gene,
        "reviewed": candidate.get("reviewed"),
        "function": candidate.get("function_annotation"),
    }


def _tier_parts(tier: str) -> tuple[str, str]:
    """'A - Strong' -> ('A', 'Strong')."""
    letter, _, text = tier.partition(" - ")
    return letter.strip(), text.strip()


def _significant_domains(domains: list[dict[str, Any]], length: int) -> list[dict[str, Any]]:
    """Pfam domains passing the tier's E-value threshold, without overlaps, in sequence order."""
    kept: list[dict[str, Any]] = []
    for domain in sorted(domains, key=lambda d: d["domain_i_evalue"]):
        if domain["domain_i_evalue"] >= HMMER_EVAL_THRESHOLD:
            continue
        start, end = max(1, domain["envelope_from"]), min(length, domain["envelope_to"])
        if start <= end and all(end < other["start"] or start > other["end"] for other in kept):
            kept.append({**domain, "start": start, "end": end})
    return sorted(kept, key=lambda d: d["start"])


def _evidence(assessment: dict[str, Any], ipr: list[dict[str, Any]]) -> list[EvidenceItem]:
    """The notebook's rationale lines, each marked as supporting or not."""
    why = list(assessment["rationale"])
    items: list[EvidenceItem] = []
    best_dom = assessment["best_domain"]
    if assessment["best_hit"]:
        items.append(EvidenceItem(polarity="positive" if assessment["strong_homology"] else "negative", text=why.pop(0)))
    else:
        items.append(EvidenceItem(polarity="negative", text=why.pop(0)))
    if best_dom:
        passes = best_dom["domain_i_evalue"] < HMMER_EVAL_THRESHOLD
        items.append(EvidenceItem(polarity="positive" if passes else "negative", text=why.pop(0)))
    if ipr:
        integrated = any(m.get("interpro_accession") for m in ipr)
        items.append(EvidenceItem(polarity="positive" if integrated else "neutral", text=why.pop(0)))
    for line in why:  # "No domain evidence available ..."
        items.append(EvidenceItem(polarity="negative", text=line))
    if assessment["very_high_identity"]:
        items.append(EvidenceItem(
            polarity="positive",
            text=f"Near-identical Swiss-Prot entry (>= {VERY_HIGH_IDENTITY:g}% identity and >= 90% query coverage).",
        ))
    return items


def build_level_result(sequence: str, modules: dict[str, Any], embedding: list[float] | None) -> LevelResult:
    """The notebook's evidence summary (section 11) for these modules, laid out for the interface."""
    length = len(sequence)
    blast, diamond = modules["ebi_blastp"], modules["local_diamond"]
    hmmer, interpro = modules["local_hmmer_pfam"], modules["interproscan"]
    merged_hits = merge_homology(blast, diamond)
    retrieval = modules.get("embedding_retrieval") or _NO_RETRIEVAL
    summary_data = build_evidence_summary(
        merged_hits, modules["uniprot"], interpro, hmmer, blast, diamond, retrieval
    )
    query_id = make_query_id(sequence)
    remote_ran = [key for key in EBI_MODULES if modules[key].get("status") == "success"]
    assessment = summary_data["assessment"]
    hmm, ipr = summary_data["hmmer_pfam_domains"], summary_data["interpro_signatures"]
    candidates = {c["accession"]: c for c in summary_data["top_homology_candidates"]}
    best = assessment["best_hit"]
    hit = describe_candidate(best, candidates.get(best["accession"])) if best else None
    best_dom = assessment["best_domain"]
    hmmer_ok = bool(best_dom) and best_dom["domain_i_evalue"] < HMMER_EVAL_THRESHOLD
    architecture = summary_data["domain_architecture"]
    letter, tier_text = _tier_parts(assessment["tier"])
    physicochemical = modules["physicochemical"]
    interpretation = interpret_physicochemical(physicochemical)
    ebi_pending = [key for key in EBI_MODULES if modules[key].get("status") == "pending"]

    # --- Summary sentence
    if hit is not None:
        where = f", {hit['organism']}" if hit["organism"] else ""
        summary = (
            f"Closest Swiss-Prot entry: {hit['protein'] or hit['entry']} ({hit['accession']}{where}), "
            f"{best['identity_percent']:.1f}% identity over {best['query_coverage_percent_approx']:.1f}% of the query"
            f" ({best['method']})."
        )
        if not assessment["strong_homology"]:
            summary += (f" This is below the homology thresholds (>= {IDENTITY_THRESHOLD:g}% identity and "
                        f">= {QUERY_COVERAGE_THRESHOLD:g}% coverage).")
    else:
        summary = "No Swiss-Prot homologue was found."
    if hmmer_ok:
        summary += f" Pfam domain {best_dom['pfam_name']} detected (independent E-value {best_dom['domain_i_evalue']:.1e})."
    elif architecture:
        summary += f" InterProScan matched {len(architecture)} integrated InterPro {'entry' if len(architecture) == 1 else 'entries'}."
    else:
        summary += " No Pfam domain passed the E-value threshold."
    summary += f" Evidence tier {letter}: {tier_text}."

    # --- Key figures
    metrics = [
        Metric(label="Best-hit identity", value=f"{best['identity_percent']:.1f}%" if best else "—"),
        Metric(label="Query coverage", value=f"{best['query_coverage_percent_approx']:.1f}%" if best else "—"),
        Metric(label="Best Pfam domain", value=best_dom["pfam_name"] if hmmer_ok else "None"),
        Metric(label="Domain E-value", value=f"{best_dom['domain_i_evalue']:.1e}" if hmmer_ok else "—"),
    ]
    if interpro.get("status") == "success":
        metrics.append(Metric(label="InterPro entries", value=str(len(architecture))))

    query_group = "Query · sequence validation"
    metrics += [
        Metric(label="Query ID", value=query_id, group=query_group),
        Metric(label="Length", value=f"{length} aa", group=query_group),
        Metric(label="Input", value="primary amino-acid sequence (FASTA or raw)", group=query_group),
        Metric(label="Residues accepted", value="the 20 standard amino acids only", group=query_group),
        Metric(label="Pipeline", value=f"{PIPELINE_VERSION} ({EXECUTION_PROFILE})", group=query_group),
    ]

    protparam = "Physicochemical profile · ProtParam"
    metrics += [
        Metric(label="Molecular weight", value=f"{physicochemical['molecular_weight_Da'] / 1000:.2f} kDa", group=protparam),
        Metric(label="Theoretical pI", value=str(physicochemical["theoretical_pI"]), group=protparam),
        Metric(label="Instability index (heuristic)", value=str(physicochemical["instability_index_heuristic"]), group=protparam),
        Metric(label="GRAVY", value=str(physicochemical["gravy"]), group=protparam),
        Metric(label="Aromaticity", value=str(physicochemical["aromaticity"]), group=protparam),
        Metric(label="Aliphatic index", value=str(physicochemical["aliphatic_index"]), group=protparam),
        Metric(label="Helix propensity fraction", value=str(physicochemical["helix_propensity_fraction"]), group=protparam),
        Metric(label="Turn propensity fraction", value=str(physicochemical["turn_propensity_fraction"]), group=protparam),
        Metric(label="Sheet propensity fraction", value=str(physicochemical["sheet_propensity_fraction"]), group=protparam),
    ]
    composition = "Amino-acid composition (%)"
    metrics += [
        Metric(label=aa, value=f"{value:.2f}", group=composition)
        for aa, value in physicochemical["amino_acid_percent"].items()
    ]
    esm = modules["esm2"]
    embedding_group = "Sequence embedding · ESM-2"
    metrics += [
        Metric(label="Model", value=ESM_MODEL_NAME, group=embedding_group),
        Metric(label="Status", value=str(esm.get("status")), group=embedding_group),
        Metric(label="Dimensions", value=str(esm.get("dimensions") or "—"), group=embedding_group),
        Metric(label="Device", value=str(esm.get("device") or "—"), group=embedding_group),
    ]
    neighbours = summary_data["esm2_nearest_neighbours"]
    if neighbours:
        nearest = neighbours[0]
        metrics.append(Metric(
            label="Nearest neighbour (demo reference)",
            value=f"{nearest['accession']} · cosine {nearest['cosine_similarity']:.3f}",
            group=embedding_group,
        ))
    rules = "Evidence tier rules (from the notebook)"
    metrics += [
        Metric(label="Strong homology", value=f"≥ {IDENTITY_THRESHOLD:g}% identity and ≥ {QUERY_COVERAGE_THRESHOLD:g}% coverage", group=rules),
        Metric(label="Very high identity", value=f"≥ {VERY_HIGH_IDENTITY:g}% identity and ≥ 90% coverage", group=rules),
        Metric(label="Domain support", value=f"Pfam independent E < {HMMER_EVAL_THRESHOLD:.0e}, or an integrated InterPro entry", group=rules),
        Metric(label="A · Strong", value="very high identity and domain support", group=rules),
        Metric(label="B · Probable", value="strong homology and domain support, or very high identity", group=rules),
        Metric(label="C · Partial", value="strong homology or domain support", group=rules),
        Metric(label="D · Inconclusive", value="neither", group=rules),
    ]

    # --- Evidence: the notebook's rationale, cross-checks and the curated function
    evidence = _evidence(assessment, ipr)
    concordance = summary_data["concordance"]
    homology_check, domain_check = concordance["homology"], concordance["domains"]
    if homology_check["comparable"]:
        agree = "agree" if homology_check["agree"] else "differ"
        evidence.append(EvidenceItem(
            polarity="neutral",
            text=f"Cross-check: BLAST top hit {homology_check['blast_top']} and DIAMOND top hit "
                 f"{homology_check['diamond_top']} {agree}.",
        ))
    if domain_check["comparable"]:
        evidence.append(EvidenceItem(
            polarity="neutral",
            text="Cross-check of Pfam domains: shared " + (", ".join(domain_check["shared"]) or "none")
                 + "; only InterProScan " + (", ".join(domain_check["only_interpro"]) or "none")
                 + "; only HMMER " + (", ".join(domain_check["only_hmmer"]) or "none") + ".",
        ))
    if hit is not None and hit["function"]:
        evidence.append(EvidenceItem(
            polarity="neutral", text=f"UniProt FUNCTION of {hit['accession']} (curated): {_short(hit['function'])}"
        ))

    # --- Notes
    notes: list[Note] = []
    if length < 10:  # the notebook's clean_sequence warning
        notes.append(Note(kind="caution", title="Very short sequence",
                          text="Very short sequence: homology and functional predictions may be unreliable."))
    if ebi_pending:
        notes.append(Note(
            kind="caution",
            title="Remote EBI analyses not included",
            text="EBI BLASTp and InterProScan had not finished when this result was produced, so homology "
                 "comes from DIAMOND and domain evidence from HMMER/Pfam only.",
        ))
    if any(modules[key].get("reason") for key in EBI_MODULES):
        notes.append(Note(
            kind="observation",
            title="Fast local profile",
            text="As in the notebook's default fast profile, the optional remote EBI modules (BLASTp, InterProScan) "
                 "are off on this server, so homology comes from local DIAMOND and domain evidence from local "
                 "HMMER/Pfam.",
        ))
    for key in _MODULE_ORDER:
        module = modules.get(key) or {}
        if module.get("status") == "unavailable":
            notes.append(Note(kind="caution", title=f"{_module_label(key, module)} unavailable",
                              text=_short(module.get("error"), 400)))
    for title, text in zip(("Stability", "Hydropathy", "Charge at pH 7.4"), interpretation, strict=True):
        notes.append(Note(kind="observation", title=title, text=text))
    notes.append(Note(kind="recommendation", title="Reading this result", text=" ".join(summary_data["interpretation_notes"])))

    # --- Tables
    candidate_rows = []
    for candidate in summary_data["top_homology_candidates"]:
        hit_details = describe_candidate(
            next((h for h in merged_hits if h["accession"] == candidate["accession"]), {}), candidate
        )
        candidate_rows.append({
            "entry": candidate["accession"],
            "protein": hit_details["protein"] or "—",
            "gene": hit_details["gene"] or "—",
            "organism": hit_details["organism"] or "—",
            "reviewed": {True: "yes", False: "no"}.get(candidate.get("reviewed"), "—"),
            "identity": f"{candidate['identity_percent']:.1f}%",
            "coverage": f"{candidate['query_coverage_percent_approx']:.1f}%",
            "evalue": f"{candidate['evalue']:.1e}",
            "bits": f"{candidate['bitscore']:g}",
            "method": candidate["method"],
        })
    tables = [
        Table(
            key="homology-candidates",
            title="Swiss-Prot candidates",
            caption=("Best alignment per entry from local DIAMOND (--fast)"
                     + (" and EBI BLASTp" if blast.get("status") == "success" else "")
                     + "; the first row is the best hit. UniProt metadata (name, gene, organism, reviewed status, "
                       "function) is looked up for the 3 best candidates, as in the notebook; the other rows show "
                       "the Swiss-Prot title"),
            columns=[
                TableColumn(key="entry", label="Entry", mono=True),
                TableColumn(key="protein", label="Protein"),
                TableColumn(key="gene", label="Gene"),
                TableColumn(key="organism", label="Organism"),
                TableColumn(key="reviewed", label="Reviewed"),
                TableColumn(key="identity", label="Identity", align="right"),
                TableColumn(key="coverage", label="Coverage", align="right"),
                TableColumn(key="evalue", label="E-value", align="right", mono=True),
                TableColumn(key="bits", label="Bit score", align="right"),
                TableColumn(key="method", label="Found by"),
            ],
            rows=candidate_rows,
        ),
        Table(
            key="pfam-domains",
            title="Pfam domains",
            caption=f"hmmscan against Pfam-A (E ≤ 1e-05); domains with independent E-value < {HMMER_EVAL_THRESHOLD:.0e} count as domain support",
            columns=[
                TableColumn(key="family", label="Family"),
                TableColumn(key="accession", label="Accession", mono=True),
                TableColumn(key="description", label="Description"),
                TableColumn(key="residues", label="Residues", align="right", mono=True),
                TableColumn(key="evalue", label="Independent E-value", align="right", mono=True),
                TableColumn(key="support", label="Domain support"),
            ],
            rows=[
                {
                    "family": domain["pfam_name"],
                    "accession": domain["pfam_accession"],
                    "description": domain.get("description") or "—",
                    "residues": f"{domain['envelope_from']}–{domain['envelope_to']}",
                    "evalue": f"{domain['domain_i_evalue']:.1e}",
                    "support": "yes" if domain["domain_i_evalue"] < HMMER_EVAL_THRESHOLD else "no",
                }
                for domain in sorted(hmm, key=lambda d: d["envelope_from"])
            ],
        ),
    ]
    if interpro.get("status") == "success":
        tables.append(Table(
            key="interpro-architecture",
            title="Domain architecture (InterPro)",
            caption="InterProScan: one row per integrated InterPro entry, with its member databases and GO terms",
            columns=[
                TableColumn(key="entry", label="InterPro", mono=True),
                TableColumn(key="description", label="Description"),
                TableColumn(key="residues", label="Residues", align="right", mono=True),
                TableColumn(key="members", label="Member databases"),
                TableColumn(key="go", label="GO terms"),
            ],
            rows=[
                {
                    "entry": row["interpro_accession"],
                    "description": row["description"] or "—",
                    "residues": f"{row['start']}–{row['end']}",
                    "members": row["members"],
                    "go": row["go_terms"] or "—",
                }
                for row in architecture
            ],
        ))
        tables.append(Table(
            key="interpro-signatures",
            title="InterProScan signatures",
            caption="Every member-database match returned by InterProScan",
            columns=[
                TableColumn(key="database", label="Database"),
                TableColumn(key="signature", label="Signature", mono=True),
                TableColumn(key="description", label="Description"),
                TableColumn(key="residues", label="Residues", align="right", mono=True),
                TableColumn(key="interpro", label="InterPro", mono=True),
            ],
            rows=[
                {
                    "database": match["analysis"],
                    "signature": match["signature_accession"],
                    "description": match["signature_description"] or "—",
                    "residues": f"{match['start']}–{match['end']}" if match["start"] is not None else "—",
                    "interpro": match["interpro_accession"] or "—",
                }
                for match in ipr
            ],
        ))
    if neighbours:
        tables.append(Table(
            key="esm2-neighbours",
            title="ESM-2 nearest neighbours (demo reference)",
            caption=(f"Cosine similarity of the 320-d ESM-2 embedding to the notebook's {DEMO_REFERENCE_TYPE} - "
                     f"{retrieval.get('reference_size')} compared, {retrieval.get('identical_sequences_excluded')} "
                     "identical sequence(s) excluded (leakage guard). Retrieval similarity, not a probability or an "
                     "identification; it does not change the tier"),
            columns=[
                TableColumn(key="accession", label="Reference", mono=True),
                TableColumn(key="function", label="Function"),
                TableColumn(key="cosine", label="Cosine similarity", align="right", mono=True),
            ],
            rows=[
                {"accession": row["accession"], "function": row["function"], "cosine": f"{row['cosine_similarity']:.4f}"}
                for row in neighbours
            ],
        ))
    module_rows = []
    for key in _MODULE_ORDER:
        module = modules.get(key) or _NO_RETRIEVAL
        status = module.get("status")
        data = module.get("data")
        if status == "success" and key in ("local_diamond", "ebi_blastp"):
            detail = f"{len(data.get('hits', []))} alignments"
        elif status == "success" and key == "local_hmmer_pfam":
            detail = f"{len(data.get('domains', []))} domains (E ≤ 1e-05)"
        elif status == "success" and key == "interproscan":
            detail = f"{len(data.get('matches', []))} signature matches"
        elif status == "success" and key == "uniprot":
            detail = f"{sum(1 for item in data if item.get('uniprot'))} entries"
        elif status == "success" and key == "esm2":
            detail = f"{module.get('dimensions')}-dimensional embedding"
        elif status == "success" and key == "embedding_retrieval":
            detail = (f"{len(module.get('hits') or [])} neighbours among {module.get('reference_size')} reference "
                      f"proteins ({module.get('identical_sequences_excluded')} identical excluded)")
        elif status == "pending":
            detail = "not finished"
        elif status == "skipped" and key == "embedding_retrieval":
            detail = "ESM-2 did not run"
        else:
            detail = module.get("reason") or _short(module.get("error"), 160) or "—"
        module_rows.append({
            "module": _module_label(key, module),
            "status": "running or stopped" if status == "pending" else str(status),
            "time": _seconds(module.get("elapsed_seconds")),
            "detail": detail,
        })
    tables.append(Table(
        key="modules",
        title="Modules",
        caption=f"Each module of the notebook ({EXECUTION_PROFILE} profile), whether it ran and how long it took",
        columns=[
            TableColumn(key="module", label="Module"),
            TableColumn(key="status", label="Status"),
            TableColumn(key="time", label="Time", align="right"),
            TableColumn(key="detail", label="Detail"),
        ],
        rows=module_rows,
    ))

    # --- Tracks: Pfam domains on the combined map; InterPro and the homology region here
    tracks: list[Track] = []
    domains = _significant_domains(hmm, length)
    if domains:
        best_domain = min(domains, key=lambda d: d["domain_i_evalue"])
        tracks.append(Track(
            key="domains",
            label="Domains",
            caption="Primary · Pfam",
            style="blocks",
            segments=[
                Segment(start=d["start"], end=d["end"], tone="accent" if d is best_domain else "ink", label=d["pfam_name"])
                for d in domains
            ],
        ))
    interpro_segments = [
        Segment(start=max(1, row["start"]), end=min(length, row["end"]), tone="ink",
                label=row["description"] or row["interpro_accession"])
        for row in architecture
        if row["start"] is not None and row["end"] is not None and max(1, row["start"]) <= min(length, row["end"])
    ]
    if interpro_segments:
        tracks.append(Track(
            key="interpro", label="InterPro", caption="Primary · InterProScan", style="blocks",
            segments=interpro_segments, overview=not domains,
        ))
    if best is not None:
        qstart, qend = sorted((int(best["query_start"]), int(best["query_end"])))
        qstart, qend = max(1, qstart), min(length, qend)
        if qstart <= qend:
            tracks.append(Track(
                key="swissprot-hit",
                label="Swiss-Prot hit",
                caption=f"Primary · {best['method']}",
                style="blocks",
                segments=[Segment(start=qstart, end=qend, tone="neutral", label=hit["entry"] if hit else best["accession"])],
                overview=not domains and not interpro_segments,
            ))

    # --- Links
    links: list[Link] = []
    if hit is not None:
        links.append(Link(label=f"UniProt {hit['accession']}", url=f"https://www.uniprot.org/uniprotkb/{hit['accession']}/entry"))
    seen: set[str] = set()
    for domain in domains:
        pfam_id = domain["pfam_accession_base"]
        if pfam_id.startswith("PF") and pfam_id not in seen:
            seen.add(pfam_id)
            links.append(Link(label=f"Pfam {pfam_id} ({domain['pfam_name']})", url=f"https://www.ebi.ac.uk/interpro/entry/pfam/{pfam_id}/"))
    for row in architecture[:6]:
        links.append(Link(
            label=f"InterPro {row['interpro_accession']}",
            url=f"https://www.ebi.ac.uk/interpro/entry/InterPro/{row['interpro_accession']}/",
        ))

    raw = {
        "pipeline": f"{NOTEBOOK} ({PIPELINE_VERSION})",
        "query": {"query_id": query_id, "length_aa": length, "input_type": "primary amino-acid sequence"},
        "run_metadata": {
            "pipeline_version": PIPELINE_VERSION,
            "execution_profile": EXECUTION_PROFILE,
            "remote_modules_run": remote_ran,  # optional EBI modules that finished (background phase)
            "device": modules["esm2"].get("device"),
        },
        "thresholds": {
            "identity": IDENTITY_THRESHOLD, "query_coverage": QUERY_COVERAGE_THRESHOLD,
            "very_high_identity": VERY_HIGH_IDENTITY, "hmmer_evalue": HMMER_EVAL_THRESHOLD,
        },
        "modules": modules,
        "physicochemical_interpretation": interpretation,
        "evidence_summary": summary_data,
        "esm2_embedding": embedding,
        "sequence_sha1": hashlib.sha1(sequence.encode()).hexdigest()[:10],
    }

    return LevelResult(
        source="live",
        headline=Headline(value=f"Tier {letter}", label=f"{tier_text} · evidence tier"),
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )
