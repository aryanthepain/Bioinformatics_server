"""Compare the primary-structure module with the final notebook's recorded results.

From the backend folder, after running scripts/setup_primary.sh:

    uv run python scripts/check_primary.py               # the single-query run + 3 more proteins (a few minutes)
    uv run python scripts/check_primary.py --benchmark   # also the notebook's section 17 (about 15 minutes)
    uv run python scripts/check_primary.py --ebi         # also the optional EBI BLASTp + InterProScan for AKT1
    uv run python scripts/check_primary.py --examples    # also cache every example of the app

It runs the proteins of "Final_Primary_structure.ipynb" (pipeline 3.1-fast-local)
through the ported module and compares the results with the output recorded in
the notebook:

  * sections 2-12, the notebook's single-query run (fast profile) for human AKT1:
    query ID, ProtParam table and interpretation, the DIAMOND --fast table, the
    HMMER/Pfam domains, the UniProt metadata of the 3 best candidates, the ESM-2
    embedding and its nearest neighbours in the demo reference, and the tier with
    its rationale;
  * section 17, the three other known reference proteins (bacteriorhodopsin, p53,
    ubiquitin) through the same fast profile: top hit, identity, coverage, UniProt
    name, best Pfam domain, ESM-2 nearest neighbour and tier;
  * --benchmark, all of section 17: the four known proteins and AKT1 diverged to
    ~90, 70, 50 and 30% identity (the notebook's own diverge_sequence and seeds),
    each searched with DIAMOND --fast and --sensitive, with the run times;
  * --ebi, the optional remote modules for AKT1 (needs PFP_EBI_EMAIL in .env). The
    final notebook leaves them off, so the BLASTp reference values are those its
    previous version (3.0-merged) recorded with the same, unchanged functions.

  PASS  identical to the notebook
  NOTE  differs for an expected reason (a newer Swiss-Prot, Pfam or Biopython release,
        or CPU instead of the notebook's GPU for ESM-2)
  FAIL  differs where it must not

Results for the app's example proteins are saved to the cache, so the app shows their
primary-structure results instantly afterwards.
"""

import argparse
import math
import random
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # lets "import app" work

from app import cache  # noqa: E402
from app.examples import EXAMPLES, find_example  # noqa: E402
from app.jobs import JobStore, StageContext  # noqa: E402
from app.levels import primary  # noqa: E402
from app.schemas import LevelResult  # noqa: E402

KNOWN = primary.KNOWN_PROTEINS  # section 10b: the notebook's four reference proteins, verbatim
AKT1 = KNOWN["AKT1 (human)"]["sequence"]

# ---------------------------------------------------------------- the single-query run (sections 2-12)
AKT1_QUERY_ID = "query_f5b6010754"

# Section 4 (cell 14): ProtParam of the AKT1 query, as displayed (4 decimals), and its interpretation.
AKT1_PROTPARAM = {
    "length_aa": 480.0, "molecular_weight_Da": 55685.78, "theoretical_pI": 5.751,
    "instability_index_heuristic": 35.465, "gravy": -0.5748, "aromaticity": 0.1083, "aliphatic_index": 71.687,
    "helix_propensity_fraction": 0.3479, "turn_propensity_fraction": 0.2417, "sheet_propensity_fraction": 0.3563,
}
AKT1_INTERPRETATION = [
    "Instability index <= 40: heuristic does not flag instability (does not prove stability).",
    "Negative GRAVY: hydrophilic on average (does not by itself establish localization/solubility).",
    "Theoretical pI < 7.4: expected net negative charge at pH 7.4 (anion-exchange binding possible; test experimentally).",
]

# Section 6 (cell 24): the DIAMOND --fast table, first ten rows.
# (hit_id, identity %, query coverage %, E-value, bit score)
AKT1_DIAMOND = [
    ("sp|P31749|AKT1_HUMAN", 100.0, 100.00, 0.0, 976.0),
    ("sp|P31750|AKT1_MOUSE", 98.3, 100.00, 0.0, 960.0),
    ("sp|P31748|AKT_MLVAT", 98.3, 100.00, 0.0, 960.0),
    ("sp|P47196|AKT1_RAT", 98.1, 100.00, 0.0, 959.0),
    ("sp|Q01314|AKT1_BOVIN", 96.9, 100.00, 0.0, 946.0),
    ("sp|Q98TY9|AKT1_XENLA", 93.1, 100.00, 0.0, 909.0),
    ("sp|Q60823|AKT2_MOUSE", 81.8, 99.38, 5.40e-297, 812.0),
    ("sp|P31751|AKT2_HUMAN", 81.6, 99.38, 1.09e-296, 811.0),
    ("sp|Q7ZX15|AKT2A_XENLA", 80.6, 99.38, 6.22e-295, 807.0),
    ("sp|P47197|AKT2_RAT", 81.4, 99.38, 1.04e-294, 806.0),
]

# Section 8 (cell 30): the HMMER/Pfam table.
# (Pfam name, accession, independent E-value, domain score, alignment from, alignment to)
AKT1_PFAM = [
    ("Pkinase", "PF00069.32", 3.4e-79, 267.5, 150, 408),
    ("PK_Tyr_Ser-Thr", "PF07714.24", 1.5e-34, 121.0, 152, 391),
    ("PH", "PF00169.37", 1.0e-18, 69.3, 7, 106),
    ("Pkinase_C", "PF00433.31", 1.6e-10, 43.0, 429, 474),
    ("Kinase-like", "PF14531.13", 1.5e-07, 32.6, 257, 391),
]

# Section 9 (cells 24 and 30): UniProt metadata for the 3 best candidates.
# (accession, protein name, gene, organism, reviewed)
AKT1_UNIPROT = [
    ("P31749", "RAC-alpha serine/threonine-protein kinase", "AKT1", "Homo sapiens", True),
    ("P31750", "RAC-alpha serine/threonine-protein kinase", "Akt1", "Mus musculus", True),
    ("P31748", "AKT kinase-transforming protein", "V-AKT", "AKT8 murine leukemia virus", True),
]
AKT1_FUNCTION_START = ("AKT1 is one of 3 closely related serine/threonine-protein kinases (AKT1, AKT2 and AKT3) "
                       "called the AKT kinase")

# Section 10b (cell 28): ESM-2 retrieval against the demo reference (AKT1 itself excluded).
AKT1_NEIGHBOURS = [("P04637", 0.824968), ("Q865C5", 0.770458), ("P02945", 0.727046)]

# Section 11 (cell 30): the tier and its rationale.
AKT1_TIER = "A - Strong"
AKT1_RATIONALE = [
    "Best homology hit: P31749 - 100.0% identity, 100.0% query coverage, E=0.0e+00 (DIAMOND (local)) -> strong by "
    "thresholds (>= 30.0% identity and >= 80.0% coverage).",
    "Best Pfam domain (HMMER): Pkinase (PF00069.32), independent E=3.4e-79 -> passes E < 1e-10.",
]
NOTEBOOK_WALL_SECONDS = 46.24  # "FAST PIPELINE WALL TIME", on a Colab GPU

# ---------------------------------------------------------------- section 17 (cells 39 and 41)
# Recorded for both DIAMOND modes; --fast and --sensitive gave the same values for every case.
# case -> (top accession, identity %, query coverage %, UniProt name, gene, organism (start), reviewed,
#          best Pfam, its accession, its independent E-value, Pfam domain count, tier,
#          ESM-2 nearest accession, its cosine similarity)
BENCHMARK = {
    "AKT1 (human)": ("P31749", 100.0, 100.00, "RAC-alpha serine/threonine-protein kinase", "AKT1", "Homo sapiens", True,
                     "Pkinase", "PF00069.32", 3.4e-79, 5, "A - Strong", "P04637", 0.824968),
    "Bacteriorhodopsin": ("P02945", 100.0, 100.00, "Bacteriorhodopsin", "bop",
                          "Halobacterium salinarum (strain ATCC 700922 / ", True,
                          "Bac_rhodopsin", "PF01036.26", 7.7e-79, 1, "A - Strong", "P04637", 0.896905),
    "p53 (human)": ("P04637", 99.7, 100.00, "Cellular tumor antigen p53", "TP53", "Homo sapiens", True,
                    "P53", "PF00870.25", 3.3e-62, 4, "A - Strong", "P02945", 0.896905),
    "Ubiquitin": ("Q865C5", 100.0, 100.00, "Ubiquitin", None, "Camelus dromedarius", True,
                  "ubiquitin", "PF00240.30", 1.4e-33, 3, "A - Strong", "P04637", 0.787950),
    "AKT1 simulated divergence ~90%": ("P31749", 90.0, 100.00, "RAC-alpha serine/threonine-protein kinase", "AKT1",
                                       "Homo sapiens", True, "Pkinase", "PF00069.32", 8.4e-69, 5, "A - Strong",
                                       "P31749", 0.994080),
    "AKT1 simulated divergence ~70%": ("P31749", 70.0, 100.00, "RAC-alpha serine/threonine-protein kinase", "AKT1",
                                       "Homo sapiens", True, "Pkinase", "PF00069.32", 8.6e-48, 4, "B - Probable",
                                       "P04637", 0.929889),
    "AKT1 simulated divergence ~50%": ("P31749", 50.0, 100.00, "RAC-alpha serine/threonine-protein kinase", "AKT1",
                                       "Homo sapiens", True, "Pkinase", "PF00069.32", 1.8e-19, 1, "B - Probable",
                                       "P04637", 0.923471),
    "AKT1 simulated divergence ~30%": ("P31749", 30.4, 97.29, "RAC-alpha serine/threonine-protein kinase", "AKT1",
                                       "Homo sapiens", True, "Pkinase", "PF00069.32", 2.2e-09, 1,
                                       "C - Partial (family/domain-level hypothesis)", "P04637", 0.952942),
}
BENCHMARK_SECONDS = {"fast": 16.0, "sensitive": 103.3}  # mean DIAMOND wall time over the 8 cases (Colab)
BENCHMARK_MODES = ["fast", "sensitive"]
BENCHMARK_TOP_N = 10
MUTATION_TARGETS = [90, 70, 50, 30]

# Section 5 of the previous notebook version (3.0-merged, where EBI ran by default): the first ten
# EBI BLASTp hits for AKT1. (accession, identity %, query coverage %, subject coverage %, bit score)
AKT1_BLAST = [
    ("P31749", 100.0, 100.00, 100.00, 986.9),
    ("P31748", 98.3, 100.00, 95.81, 971.1),
    ("P31750", 98.3, 100.00, 100.00, 971.1),
    ("P47196", 98.1, 100.00, 100.00, 970.3),
    ("Q01314", 96.9, 100.00, 100.00, 956.8),
    ("Q98TY9", 93.1, 100.00, 100.00, 920.2),
    ("Q60823", 81.8, 99.38, 99.38, 823.2),
    ("P31751", 81.6, 99.38, 99.38, 822.4),
    ("Q7ZX15", 80.6, 99.38, 99.38, 818.1),
    ("P47197", 81.4, 99.38, 99.38, 817.4),
]

# Section 14 (cell 36): the notebook's divergence model, copied verbatim (section 17 uses it).
CONSERVATIVE_GROUPS = ["AVLIM", "FYW", "KRH", "DE", "ST", "NQ"]


def _substitute(aa, rng, p_conservative=0.6):
    if rng.random() < p_conservative:
        for g in CONSERVATIVE_GROUPS:
            if aa in g and len(g) > 1:
                return rng.choice([x for x in g if x != aa])
    return rng.choice([x for x in sorted(primary.VALID_AA) if x != aa])


def diverge_sequence(seq, target_identity, seed=42):
    rng = random.Random(seed)
    n_mut = round(len(seq) * (1 - target_identity / 100.0))
    out = list(seq)
    for p in rng.sample(range(len(seq)), n_mut):
        out[p] = _substitute(seq[p], rng)
    return "".join(out)


def actual_identity(a, b):
    return 100.0 * sum(x == y for x, y in zip(a, b)) / len(a)


def benchmark_cases() -> list[dict[str, Any]]:
    """Section 17's EXPERIMENT_CASES: the four known proteins, then the AKT1 variants."""
    cases = [{"case": name, "sequence": info["sequence"], "simulated_identity": 100.0} for name, info in KNOWN.items()]
    for target in MUTATION_TARGETS:
        variant = diverge_sequence(AKT1, target, seed=2026 + target)
        cases.append({"case": f"AKT1 simulated divergence ~{target}%", "sequence": variant,
                      "simulated_identity": round(actual_identity(AKT1, variant), 2)})
    return cases


class QuietContext(StageContext):
    """Prints a progress message only when its first part changes."""

    last = ""

    def report(self, message: str) -> None:
        self.check_cancelled()
        stem = message.split(" · ")[0]
        if stem != self.last:
            self.last = stem
            print(f"      {time.strftime('%H:%M:%S')}  {stem}", flush=True)


passes = notes = 0
failures: list[str] = []


def result(kind: str, text: str) -> None:
    global passes, notes
    print(f"  {kind:<4}  {text}")
    if kind == "PASS":
        passes += 1
    elif kind == "NOTE":
        notes += 1
    else:
        failures.append(text)


def close(actual: float | None, expected: float, digits: int, note_within: float, label: str, why: str) -> None:
    """PASS when equal at the notebook's precision, NOTE when within note_within, else FAIL."""
    if actual is None:
        result("FAIL", f"{label}: missing (notebook: {expected})")
    elif round(actual, digits) == round(expected, digits):
        result("PASS", f"{label} {round(actual, digits)}")
    elif abs(actual - expected) <= note_within:
        result("NOTE", f"{label} {round(actual, digits)} (notebook: {expected}; {why})")
    else:
        result("FAIL", f"{label} {round(actual, digits)} (notebook: {expected})")


def same_evalue(label: str, actual: float, expected: float, digits: int, why: str) -> None:
    """E-values: PASS at the printed precision, NOTE within 6 orders of magnitude, else FAIL."""
    if f"{actual:.{digits}e}" == f"{expected:.{digits}e}":
        result("PASS", f"{label} {actual:.{digits}e}")
    elif expected == 0.0 or actual == 0.0:
        result("NOTE" if max(actual, expected) < 1e-100 else "FAIL",
               f"{label} {actual:.{digits}e} (notebook: {expected:.{digits}e}; {why})")
    elif abs(math.log10(max(actual, 1e-300)) - math.log10(max(expected, 1e-300))) < 6:
        result("NOTE", f"{label} {actual:.{digits}e} (notebook: {expected:.{digits}e}; {why})")
    else:
        result("FAIL", f"{label} {actual:.{digits}e} (notebook: {expected:.{digits}e})")


def same_pfam_accession(label: str, actual: str | None, expected: str) -> None:
    """Pfam accessions: PASS when equal, NOTE when only the version suffix differs (another Pfam release)."""
    if actual == expected:
        result("PASS", f"{label} {actual}")
    elif actual and actual.split(".")[0] == expected.split(".")[0]:
        result("NOTE", f"{label} {actual} (notebook: {expected}; another Pfam release)")
    else:
        result("FAIL", f"{label} {actual} (notebook: {expected})")


def check_modules(modules: dict[str, Any]) -> None:
    for key in ("local_diamond", "local_hmmer_pfam", "esm2"):
        module = modules[key]
        if module.get("status") != "success":
            result("FAIL", f"{module.get('source')}: {module.get('status')} - {module.get('error')}")


def compare_neighbour(label: str, hits: list[dict[str, Any]], accession: str, cosine: float) -> None:
    if not hits:
        result("FAIL", f"{label}: no neighbours (notebook: {accession}, cosine {cosine:.3f})")
        return
    first = hits[0]
    if first["accession"] != accession:
        result("FAIL", f"{label} {first['accession']} (notebook: {accession})")
        return
    close(first["cosine_similarity"], cosine, 3, 0.01, f"{label} {accession}, cosine", "ESM-2 on CPU instead of GPU")


def compare_single_query(level: LevelResult, seconds: float) -> None:
    """Sections 2-12: the notebook's single-query run for AKT1."""
    raw = level.raw or {}
    modules = raw["modules"]
    check_modules(modules)
    summary = raw["evidence_summary"]
    biopython = "Biopython version differs"
    database = "DIAMOND or Swiss-Prot version differs"

    print("  Section 2 - input validation")
    query_id = raw["query"]["query_id"]
    result("PASS" if query_id == AKT1_QUERY_ID else "FAIL", f"query ID {query_id} (notebook: {AKT1_QUERY_ID})")
    result("PASS" if raw["query"]["length_aa"] == 480 else "FAIL", f"length {raw['query']['length_aa']} aa (notebook: 480)")

    print("  Section 4 - ProtParam table and interpretation")
    physico = modules["physicochemical"]
    for key, expected in AKT1_PROTPARAM.items():
        close(float(physico[key]), expected, 4, abs(expected) * 0.01, f"ProtParam {key}", biopython)
    for expected, actual in zip(AKT1_INTERPRETATION, raw["physicochemical_interpretation"], strict=True):
        result("PASS" if expected == actual else "FAIL", f"interpretation: {actual[:72]}…")

    print("  Section 6 - local DIAMOND (--fast), first ten rows")
    hits = (modules["local_diamond"].get("data") or {}).get("hits", [])
    got = [h["hit_id"] for h in hits[:10]]
    expected_ids = [row[0] for row in AKT1_DIAMOND]
    bits = {h["hit_id"]: h["bitscore"] for h in hits}
    if got == expected_ids:
        result("PASS", "the same first ten hits, in the same order")
    elif sorted(got) == sorted(expected_ids) and [bits[i] for i in got] == sorted((bits[i] for i in got), reverse=True):
        result("PASS", "the same first ten hits (entries with equal bit scores in another order)")
    else:
        result("NOTE", f"first hits {got} (notebook: {expected_ids}; {database})")
    by_id = {h["hit_id"]: h for h in hits}
    for hit_id, identity, coverage, evalue, bitscore in AKT1_DIAMOND:
        hit = by_id.get(hit_id)
        if hit is None:
            result("NOTE", f"{hit_id}: not among the hits ({database})")
            continue
        text = (f"{hit_id}: {hit['identity_percent']}% identity, {hit['query_coverage_percent_approx']}% coverage, "
                f"E={hit['evalue']:.2e}, {hit['bitscore']:g} bits")
        same = (round(hit["identity_percent"], 1) == identity
                and round(hit["query_coverage_percent_approx"], 2) == coverage)
        if same and hit["bitscore"] == bitscore and f"{hit['evalue']:.2e}" == f"{evalue:.2e}":
            result("PASS", text)
        elif abs(hit["identity_percent"] - identity) <= 1.0 and abs(hit["query_coverage_percent_approx"] - coverage) <= 1.0:
            result("NOTE", f"{text} (notebook: {identity}%, {coverage}%, E={evalue:.2e}, {bitscore:g} bits; {database})")
        else:
            result("FAIL", f"{text} (notebook: {identity}%, {coverage}%, E={evalue:.2e}, {bitscore:g} bits)")

    print("  Section 8 - local HMMER/Pfam")
    domains = {d["pfam_name"]: d for d in (modules["local_hmmer_pfam"].get("data") or {}).get("domains", [])}
    pfam_why = "E-values shift slightly between Pfam and HMMER releases"
    for name, accession, i_evalue, score, start, end in AKT1_PFAM:
        domain = domains.get(name)
        if domain is None:
            result("FAIL" if i_evalue < primary.HMMER_EVAL_THRESHOLD else "NOTE",
                   f"Pfam {name}: not found (notebook: E={i_evalue:.1e})")
            continue
        same_pfam_accession(f"Pfam {name} accession", domain["pfam_accession"], accession)
        same_evalue(f"Pfam {name} independent E-value", domain["domain_i_evalue"], i_evalue, 1, pfam_why)
        span = (domain["alignment_from"], domain["alignment_to"])
        if span == (start, end) and domain["domain_score"] == score:
            result("PASS", f"Pfam {name} residues {start}-{end}, score {score}")
        else:
            result("NOTE", f"Pfam {name} residues {span[0]}-{span[1]}, score {domain['domain_score']} "
                           f"(notebook: {start}-{end}, {score}; {pfam_why})")
    if len(domains) != len(AKT1_PFAM):
        result("NOTE", f"{len(domains)} Pfam domains (notebook: {len(AKT1_PFAM)}; another Pfam release)")

    print("  Section 9 - UniProt metadata for the 3 best candidates")
    uniprot = modules["uniprot"]
    items = uniprot.get("data") or []
    result("PASS" if uniprot.get("status") == "success" and len(items) == 3 else "FAIL",
           f"UniProt: {uniprot.get('status')} | entries: {len(items)} (notebook: success | entries: 3)")
    candidates = {c["accession"]: c for c in summary["top_homology_candidates"]}
    for accession, name, gene, organism, reviewed in AKT1_UNIPROT:
        candidate = candidates.get(accession)
        if candidate is None:
            result("NOTE", f"{accession}: not among the candidates (Swiss-Prot version differs)")
            continue
        got_row = (candidate.get("protein_name"), candidate.get("gene_name"), candidate.get("organism"), candidate.get("reviewed"))
        text = f"{accession}: {got_row[0]} [{got_row[1]}] - {got_row[2]}, reviewed {got_row[3]}"
        result("PASS" if got_row == (name, gene, organism, reviewed) else "FAIL",
               text if got_row == (name, gene, organism, reviewed) else f"{text} (notebook: {name} [{gene}] - {organism}, reviewed {reviewed})")
    function = str((candidates.get("P31749") or {}).get("function_annotation") or "")
    result("PASS" if function.startswith(AKT1_FUNCTION_START) else "NOTE",
           f"UniProt FUNCTION of P31749: {function[:70]}… " + ("" if function.startswith(AKT1_FUNCTION_START)
                                                             else "(notebook: AKT1 is one of 3 closely related …; UniProt text updated)"))
    rest = [c for c in summary["top_homology_candidates"][3:] if c.get("reviewed") is not None]
    result("PASS" if not rest else "FAIL", "no UniProt lookup beyond the 3 best candidates (notebook: None for rows 4-10)")

    print("  Section 10 - ESM-2 embedding and retrieval (demo reference)")
    dims = modules["esm2"].get("dimensions")
    result("PASS" if dims == 320 else "FAIL", f"ESM-2 embedding: {dims} dimensions (notebook: 320)")
    retrieval = modules["embedding_retrieval"]
    shape = (retrieval.get("status"), retrieval.get("reference_size"), retrieval.get("identical_sequences_excluded"))
    result("PASS" if shape == ("success", 3, 1) else "FAIL",
           f"retrieval {shape[0]}, size={shape[1]}, identical excluded={shape[2]} (notebook: success, 3, 1)")
    neighbours = retrieval.get("hits") or []
    if [h["accession"] for h in neighbours] == [a for a, _ in AKT1_NEIGHBOURS]:
        result("PASS", "neighbours in the notebook's order: " + ", ".join(a for a, _ in AKT1_NEIGHBOURS))
    else:
        result("FAIL", f"neighbours {[h['accession'] for h in neighbours]} (notebook: {[a for a, _ in AKT1_NEIGHBOURS]})")
    for hit, (accession, cosine) in zip(neighbours, AKT1_NEIGHBOURS):
        if hit["accession"] == accession:
            close(hit["cosine_similarity"], cosine, 3, 0.01, f"cosine {accession}", "ESM-2 on CPU instead of GPU")

    print("  Section 11 - evidence integration")
    assessment = summary["assessment"]
    result("PASS" if assessment["tier"] == AKT1_TIER else "FAIL", f"tier {assessment['tier']} (notebook: {AKT1_TIER})")
    for expected, actual in zip(AKT1_RATIONALE, assessment["rationale"], strict=False):
        if actual == expected:
            result("PASS", f"rationale: {actual[:80]}…")
        elif re.sub(r"PF\d+\.\d+|E=[\d.e+-]+", "", actual) == re.sub(r"PF\d+\.\d+|E=[\d.e+-]+", "", expected):
            result("NOTE", f"rationale: {actual} (notebook: {expected}; another Pfam release)")
        else:
            result("FAIL", f"rationale: {actual} (notebook: {expected})")
    statuses = {key: (modules.get(key) or {}).get("status") for key in
                ("local_diamond", "local_hmmer_pfam", "uniprot", "esm2", "embedding_retrieval")}
    result("PASS" if set(statuses.values()) == {"success"} else "FAIL", f"module status {statuses}")
    print(f"      wall time of the local modules: {seconds:.1f} s (notebook: {NOTEBOOK_WALL_SECONDS} s on a Colab GPU)")


def compare_case(name: str, level: LevelResult) -> None:
    """Section 17's columns for one known protein, through the app's fast profile."""
    (accession, identity, coverage, protein, gene, organism, reviewed, pfam, pfam_accession, pfam_evalue,
     domain_count, tier, nearest, cosine) = BENCHMARK[name]
    raw = level.raw or {}
    modules = raw["modules"]
    check_modules(modules)
    summary = raw["evidence_summary"]
    assessment = summary["assessment"]
    best, domain = assessment["best_hit"], assessment["best_domain"]
    database = "DIAMOND or Swiss-Prot version differs"
    regex = next((info["expected_regex"] for key, info in KNOWN.items() if key == name), accession)

    got = best["accession"] if best else None
    if got == accession:
        result("PASS", f"top hit {got}")
    elif best and re.search(regex, f"{best['hit_id']} {best.get('title') or ''}"):
        result("NOTE", f"top hit {got} instead of {accession} (an equally good entry; Swiss-Prot release differs)")
    else:
        result("FAIL", f"top hit {got} (notebook: {accession})")
    if best:
        close(best["identity_percent"], identity, 1, 1.0, "identity %", database)
        close(best["query_coverage_percent_approx"], coverage, 2, 1.0, "query coverage %", database)
        candidate = next((c for c in summary["top_homology_candidates"] if c["accession"] == got), {})
        row = (candidate.get("protein_name"), candidate.get("gene_name"), candidate.get("organism"), candidate.get("reviewed"))
        ok = (got == accession and row[0] == protein and row[1] == gene and str(row[2] or "").startswith(organism)
              and row[3] == reviewed)
        result("PASS" if ok else ("NOTE" if got != accession else "FAIL"),
               f"UniProt {row[0]} [{row[1]}] - {row[2]}, reviewed {row[3]}"
               + ("" if ok else f" (notebook: {protein} [{gene}] - {organism}…, reviewed {reviewed})"))

    if domain and domain["pfam_name"] == pfam:
        result("PASS", f"best Pfam domain {pfam}")
        same_pfam_accession("its accession", domain["pfam_accession"], pfam_accession)
        same_evalue("its independent E-value", domain["domain_i_evalue"], pfam_evalue, 1,
                    "E-values shift slightly between Pfam and HMMER releases")
    else:
        result("FAIL", f"best Pfam domain {domain['pfam_name'] if domain else None} (notebook: {pfam})")
    count = len(summary["hmmer_pfam_domains"])
    result("PASS" if count == domain_count else "NOTE",
           f"Pfam domains: {count}" + ("" if count == domain_count else f" (notebook: {domain_count}; another Pfam release)"))
    compare_neighbour("ESM-2 nearest neighbour", modules["embedding_retrieval"].get("hits") or [], nearest, cosine)
    result("PASS" if assessment["tier"] == tier else "FAIL", f"tier {assessment['tier']} (notebook: {tier})")


def run_benchmark(ctx: StageContext) -> None:
    """Section 17's run_benchmark_case for every case: shared HMMER and ESM-2, DIAMOND in both modes."""
    times: dict[str, list[float]] = {mode: [] for mode in BENCHMARK_MODES}
    for case in benchmark_cases():
        name, sequence = case["case"], case["sequence"]
        (accession, identity, coverage, _protein, _gene, _organism, _reviewed, pfam, _pfam_accession, pfam_evalue,
         domain_count, tier, nearest, cosine) = BENCHMARK[name]
        print(f"\n{name} ({len(sequence)} aa, {case['simulated_identity']}% identical to AKT1)")
        hmm_mod = primary.safe_module("HMMER/Pfam", lambda s=sequence: primary.run_local_hmmer(s, ctx=ctx))
        hmm_domains = (hmm_mod.get("data") or {}).get("domains", []) if hmm_mod["status"] == "success" else []
        if hmm_mod["status"] != "success":
            result("FAIL", f"HMMER/Pfam: {hmm_mod.get('error')}")
        esm_mod = primary.safe_module("ESM-2", lambda s=sequence: primary.run_esm2(s))
        esm_hits = []
        if esm_mod["status"] == "success":
            esm_hits = primary.esm_retrieval(sequence, esm_mod["data"]["embedding"], primary.demo_reference(), top_k=4)["hits"]
        best_dom = min(hmm_domains, key=lambda d: d.get("domain_i_evalue", float("inf"))) if hmm_domains else None
        if best_dom and best_dom["pfam_name"] == pfam:
            same_evalue(f"best Pfam {pfam}, independent E-value", best_dom["domain_i_evalue"], pfam_evalue, 1,
                        "E-values shift slightly between Pfam and HMMER releases")
        else:
            result("FAIL", f"best Pfam {best_dom['pfam_name'] if best_dom else None} (notebook: {pfam})")
        result("PASS" if len(hmm_domains) == domain_count else "NOTE",
               f"Pfam domains: {len(hmm_domains)} (notebook: {domain_count})")
        compare_neighbour("ESM-2 nearest neighbour", esm_hits, nearest, cosine)
        for mode in BENCHMARK_MODES:
            started = time.perf_counter()
            mod = primary.safe_module(f"DIAMOND {mode}", lambda m=mode, s=sequence: primary.run_local_diamond(
                s, top_n=BENCHMARK_TOP_N, mode=m, ctx=ctx))
            elapsed = time.perf_counter() - started
            times[mode].append(elapsed)
            hits = (mod.get("data") or {}).get("hits", []) if mod["status"] == "success" else []
            if mod["status"] != "success":
                result("FAIL", f"DIAMOND {mode}: {mod.get('error')}")
                continue
            best = max(hits, key=lambda h: h.get("bitscore", 0)) if hits else None
            assessment = primary.assess_function(hits, hmm_domains, [])
            got = best["accession"] if best else None
            top5 = [h.get("accession") for h in sorted(hits, key=lambda z: -z.get("bitscore", 0))[:5]]
            print(f"    DIAMOND --{mode}: {elapsed:.1f} s")
            result("PASS" if got == accession else ("NOTE" if accession in top5 else "FAIL"),
                   f"  --{mode} top hit {got} (notebook: {accession})")
            if best:
                close(best["identity_percent"], identity, 1, 1.0, f"  --{mode} identity %", "DIAMOND or Swiss-Prot version differs")
                close(best["query_coverage_percent_approx"], coverage, 2, 1.0, f"  --{mode} query coverage %",
                      "DIAMOND or Swiss-Prot version differs")
            result("PASS" if assessment["tier"] == tier else "FAIL", f"  --{mode} tier {assessment['tier']} (notebook: {tier})")
    fast = sum(times["fast"]) / len(times["fast"])
    sensitive = sum(times["sensitive"]) / len(times["sensitive"])
    print(f"\n  Mean DIAMOND time: --fast {fast:.1f} s, --sensitive {sensitive:.1f} s, ratio {sensitive / fast:.2f}x "
          f"(notebook on Colab: {BENCHMARK_SECONDS['fast']} s, {BENCHMARK_SECONDS['sensitive']} s, about 6.5x)")


def compare_blast(modules: dict[str, Any]) -> None:
    blast = modules["ebi_blastp"]
    if blast.get("status") != "success":
        result("FAIL", f"EBI BLASTp: {blast.get('status')} - {blast.get('error') or blast.get('reason')}")
        return
    hits = blast["data"]["hits"]
    got = [h["accession"] for h in hits[:10]]
    expected = [row[0] for row in AKT1_BLAST]
    if got == expected:
        result("PASS", "EBI BLASTp: the same first ten hits, in the same order")
    else:
        result("NOTE", f"EBI BLASTp first hits {got} (recorded: {expected}; Swiss-Prot release differs)")
    by_accession = {h["accession"]: h for h in hits}
    for accession, identity, query_cov, subject_cov, bits in AKT1_BLAST:
        hit = by_accession.get(accession)
        if hit is None:
            continue
        same = (
            round(hit["identity_percent"], 1) == identity
            and round(hit["query_coverage_percent_approx"], 2) == query_cov
            and round(hit["subject_coverage_percent_approx"] or 0.0, 2) == subject_cov
        )
        text = (f"{accession}: {hit['identity_percent']}% identity, query {hit['query_coverage_percent_approx']}%, "
                f"subject {hit['subject_coverage_percent_approx']}%, {hit['bitscore']} bits")
        if same and hit["bitscore"] == bits:
            result("PASS", text)
        elif same:
            result("NOTE", f"{text} (recorded: {bits} bits; BLAST or database version differs)")
        else:
            result("FAIL", f"{text} (recorded: {identity}%, {query_cov}%, {subject_cov}%, {bits} bits)")


def run_local(sequence: str, ctx: StageContext) -> tuple[LevelResult, float]:
    started = time.monotonic()
    modules, embedding = primary.run_local_modules(sequence, ctx)
    seconds = time.monotonic() - started
    print(f"      finished in {seconds:.0f} s")
    return primary.build_level_result(sequence, modules, embedding), seconds


def save(sequence: str, level: LevelResult) -> None:
    if find_example(sequence) is not None:
        cache.store("primary", primary.CACHE_VERSION, sequence, level)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--benchmark", action="store_true", help="also run the notebook's section 17 (fast vs sensitive)")
    parser.add_argument("--ebi", action="store_true", help="also run the optional EBI BLASTp and InterProScan for AKT1")
    parser.add_argument("--examples", action="store_true", help="also run and cache every example of the app")
    args = parser.parse_args()

    missing = primary.missing_setup()
    if missing:
        print("FAIL  Not set up yet. Missing: " + ", ".join(missing))
        print("      Run: bash scripts/setup_primary.sh")
        return 1
    if args.ebi and not primary.ebi_enabled():
        print("FAIL  --ebi needs an EBI contact e-mail: set PFP_EBI_EMAIL in backend/.env")
        return 1

    ctx = QuietContext(JobStore(), "check", "primary", threading.Event())
    done: set[str] = set()

    print(f"Sections 2-12 - the notebook's single-query run ({primary.PIPELINE_VERSION}, fast profile): AKT1 (human)")
    akt1_level, seconds = run_local(AKT1, ctx)
    compare_single_query(akt1_level, seconds)
    save(AKT1, akt1_level)
    done.add(AKT1)

    print("\nSection 17 - the other known reference proteins, through the same fast profile")
    for name, info in KNOWN.items():
        if info["sequence"] == AKT1:
            continue
        print(f"\n{name} ({len(info['sequence'])} residues)")
        level, _ = run_local(info["sequence"], ctx)
        compare_case(name, level)
        save(info["sequence"], level)
        done.add(info["sequence"])

    if args.benchmark:
        print("\nSection 17 - the full benchmark: DIAMOND --fast and --sensitive on 8 cases (about 15 minutes)")
        run_benchmark(ctx)

    if args.ebi:
        print("\nOptional remote modules - EBI BLASTp and InterProScan for AKT1 (several minutes)")
        started = time.monotonic()
        refined = primary.refine(AKT1, akt1_level, ctx)
        print(f"      finished in {time.monotonic() - started:.0f} s")
        modules = (refined.raw or {})["modules"]
        compare_blast(modules)
        interpro = modules["interproscan"]
        architecture = (refined.raw or {})["evidence_summary"]["domain_architecture"]
        if interpro.get("status") == "success" and architecture:
            entries = ", ".join(f"{row['interpro_accession']} {row['description']}" for row in architecture[:4])
            result("PASS", f"InterProScan: {len(interpro['data']['matches'])} signatures; entries {entries}")
        else:
            result("FAIL", f"InterProScan: {interpro.get('status')} - {interpro.get('error') or 'no InterPro entry'}")
        tier = (refined.raw or {})["evidence_summary"]["assessment"]["tier"]
        result("PASS" if tier == "A - Strong" else "FAIL", f"tier with all modules {tier} (expected: A - Strong)")
        save(AKT1, refined)

    if args.examples:
        for example in EXAMPLES:
            if example.sequence in done:
                continue
            print(f"\nApp example {example.name} ({len(example.sequence)} residues), for the cache")
            level, _ = run_local(example.sequence, ctx)
            check_modules((level.raw or {})["modules"])
            print(f"      {level.summary}")
            save(example.sequence, level)

    print(f"\n{passes} passed, {notes} notes, {len(failures)} failed")
    if failures:
        print("\nFAILED:")
        for text in failures:
            print(f"  - {text}")
        return 1
    print("PASS  The ported module reproduces the notebook (any NOTE lines are explained above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
