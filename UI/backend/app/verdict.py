"""The integration step: combine the four level results into one predicted function.

Same logic as the notebook "Function_Prediction_Integration_Final.ipynb" (sections 4 and 6
are copied here unchanged), so the website and the notebook give identical answers.

Function is predicted by transferring the annotation of a related, characterised
protein, so the confidence is

    P(function correct) = P(homologous to the template) x P(function conserved at this distance)

  Route (first that applies)          predicted function             P(homology)        P(conserved)
  1. sequence: the primary level's    the hit's protein name         0.99 (>= 40% id)   0.95 (>= 60%)
     best hit (DIAMOND or EBI                                        0.90 (30-40%)      0.80 (40-60%)
     BLASTp) shows strong homology                                                      0.55 (30-40%)
     (>= 30% identity, >= 80%
     coverage) and is characterised
  2. domain: domain support, i.e.     "X family member"              0.95               0.50
     a Pfam domain with E < 1e-10,
     else an integrated InterPro entry
  3. fold: the tertiary level's       "Structural similarity to X"   P(homology to the  0.25
     AlphaFold DB structure of the                                   match) x Foldseek
     primary level's match, which                                    prob of X
     shares the query's fold (the
     match passed the homology test)
     and is reliable (mean pLDDT >
     70), matches a characterised
     protein X (Foldseek prob >= 0.5
     over >= 50% of the structure)

The other levels are consistency checks, added on the log-odds scale:
  tertiary   none: it analyses the structure of the primary level's own match,
             so it cannot test a function transferred from that match
  secondary  agreement of the consensus with experimental PDB structures (helix/strand
             residues) >= 75% +0.4; < 60% -1.0
  quaternary template assembly CONFIRMED/SUPPORTED +0.4; CONFLICTING -0.5
             (halved below 40% identity)
Agreement is rewarded less than contradiction is penalised: agreement between
dependent levels is expected, a contradiction is informative.

Score = sigmoid(logit(base) + adjustments); bands: high >= 0.80, moderate >= 0.50.
Literature: Tian & Skolnick 2003 (J Mol Biol 333:863), Rost 1999 (Protein Eng 12:85),
Rost 2002 (J Mol Biol 318:595), Aloy et al. 2003 (J Mol Biol 332:989), van Kempen
et al. 2024 (Nat Biotechnol 42:243), Jumper et al. 2021 (Nature 596:583). The score is a literature-anchored estimate,
not a calibrated probability.

While levels are still running (or after they were stopped), the verdict also gives
the confidence range they could still produce: once the primary level is done the
predicted function is fixed, and each unfinished level can only add its agreement
bonus, its contradiction penalty or nothing. The exception is the primary level's
background step (EBI BLASTp and InterProScan): until it finishes, it can still
change the best match or the domain evidence, and the verdict says so. The secondary
level's background step (its comparison with PDB structures) counts as unfinished
until it ends.

When every level returned placeholder data (mock mode), the built-in examples
still show their known function, clearly marked as a placeholder.
"""

import logging
import math
import re
import textwrap

from .examples import find_example
from .levels.quaternary import assembly_name
from .schemas import (
    AnalysisJob,
    ConfidenceRange,
    CuratedFunction,
    GoTerm,
    LevelReport,
    LevelSupport,
    SupportState,
    Verdict,
    VerdictFact,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Reading the four modules' outputs (notebook section 4, unchanged)
# =============================================================================

GENERIC_GO = {
    "protein binding", "identical protein binding", "enzyme binding",
    "protein homodimerization activity", "protein heterodimerization activity", "molecular_function",
}
UNCHARACTERISED = re.compile(r"^(putative\s+)?(uncharacteri[sz]ed|UPF\d+)\b", re.IGNORECASE)


def _num(value):
    """A finite number, or None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _live(level):
    return isinstance(level, dict) and level.get("source") == "live"


def _swissprot_title(title, hit_id):
    """A Swiss-Prot title -> (protein, organism, gene).

    DIAMOND titles start with the identifier ('sp|P69905|HBA_HUMAN Hemoglobin subunit alpha OS=...'),
    EBI BLAST descriptions do not ('Hemoglobin subunit alpha OS=Homo sapiens OX=9606 ...').
    """
    text = str(title or "").strip()
    first, _, rest = text.partition(" ")
    if (hit_id and first == hit_id) or "|" in first:
        text = rest
    organism = re.search(r"OS=(.*?)(?: OX=| GN=| PE=| SV=|$)", text)
    gene = re.search(r" GN=(\S+)", text)
    return text.split(" OS=")[0].strip(), organism.group(1).strip() if organism else "", gene.group(1) if gene else ""


def _entry_name(hit_id, accession):
    """'sp|P69905|HBA_HUMAN' or 'SP:HBA_HUMAN' -> 'HBA_HUMAN'."""
    text = str(hit_id or "").strip()
    if "|" in text:
        parts = text.split("|")
        return parts[2] if len(parts) > 2 and parts[2] else parts[-1]
    return text.split(":")[-1] if text else accession


def _dict(value):
    return value if isinstance(value, dict) else {}


def _interpro_family(architecture):
    """The InterPro entry for a family-level prediction: one that integrates a Pfam signature
    if there is one, otherwise the entry most member databases agree on (then the longest)."""
    rows = [r for r in architecture or [] if isinstance(r, dict) and r.get("interpro_accession") and r.get("description")]
    if not rows:
        return None

    def rank(r):
        members = [m.strip() for m in str(r.get("members") or "").split(",") if m.strip()]
        return ("Pfam" in members, len(members), (_num(r.get("end")) or 0) - (_num(r.get("start")) or 0))

    return max(rows, key=rank)


def primary_evidence(level):
    """The primary notebook's own evidence summary: its best homology hit and its domain support."""
    if not _live(level):
        return {"ran": False}
    raw = _dict(level.get("raw"))
    summary = _dict(raw.get("evidence_summary"))
    assessment = _dict(summary.get("assessment"))
    threshold = _num(_dict(raw.get("thresholds")).get("hmmer_evalue")) or 1e-10
    best = _dict(assessment.get("best_hit"))
    identity, coverage = _num(best.get("identity_percent")), _num(best.get("query_coverage_percent_approx"))
    hit = None
    if best.get("accession") and identity is not None and coverage is not None:
        accession = str(best["accession"])
        candidate = next((c for c in summary.get("top_homology_candidates") or []
                          if isinstance(c, dict) and c.get("accession") == accession), {})
        protein, organism, gene = _swissprot_title(best.get("title"), best.get("hit_id"))
        if candidate.get("protein_name") and candidate["protein_name"] != best.get("title"):
            protein = str(candidate["protein_name"])  # UniProt's recommended name
        entry = _entry_name(best.get("hit_id"), accession)
        hit = {
            "accession": accession, "entry": entry,
            "protein": protein or entry, "organism": candidate.get("organism") or organism,
            "gene": candidate.get("gene_name") or gene, "method": best.get("method") or "",
            "identity": identity, "coverage": coverage, "evalue": _num(best.get("evalue")),
            "passed": assessment.get("strong_homology") is True,  # >= 30% identity and >= 80% query coverage
            "function": candidate.get("function_annotation") or None,  # UniProt's curated FUNCTION text
        }
    domain = None
    if assessment.get("domain_support") is True:  # Pfam E < 1e-10, or an integrated InterPro entry
        best_domain = _dict(assessment.get("best_domain"))
        evalue = _num(best_domain.get("domain_i_evalue"))
        if evalue is not None and evalue < threshold and best_domain.get("pfam_name"):
            domain = {
                "source": "Pfam", "name": str(best_domain["pfam_name"]),
                "accession": str(best_domain.get("pfam_accession_base") or best_domain.get("pfam_accession") or ""),
                "description": str(best_domain.get("description") or best_domain["pfam_name"]), "evalue": evalue,
            }
        else:
            entry = _interpro_family(summary.get("domain_architecture"))
            if entry is not None:
                domain = {
                    "source": "InterPro", "name": str(entry["interpro_accession"]),
                    "accession": str(entry["interpro_accession"]), "description": str(entry["description"]),
                    "evalue": None,
                }
    tier = assessment.get("tier")
    return {"ran": True, "hit": hit, "domain": domain, "tier": tier if isinstance(tier, str) else None}


def secondary_evidence(level):
    """Best agreement between the predicted secondary structure and experimental PDB structures.

    The final secondary notebook's compare_pdb_references (raw["pdb_references"], filled in by the
    level's background step; "pending" until then). Results of the earlier JPred/ProtBert notebook
    (raw["experimental_comparison"]) are still read, so older saved analyses keep their check.
    """
    if not _live(level):
        return {"ran": False}
    raw = level.get("raw") or {}
    pdb = raw.get("pdb_references")
    if isinstance(pdb, dict):
        status = str(pdb.get("status"))
        rows = [
            {"entity": r.get("PDB_entity"), "identity": r.get("Aligned_identity_pct"),
             "residues": r.get("Comparable_residues"), "agreement": r.get("SS_agreement_pct")}
            for r in pdb.get("rows") or [] if r.get("Status") == "OK"
        ]
    else:  # the earlier notebook's format
        status = "success"
        rows = [
            {"entity": r.get("PDB_entity"), "identity": r.get("Sequence_Identity_%"),
             "residues": r.get("Comparable_Residues"), "agreement": r.get("SS_Agreement_%")}
            for r in raw.get("experimental_comparison") or []
        ]
    rows = [r for r in rows if _num(r["agreement"]) is not None and _num(r["residues"]) is not None]
    best = max(rows, key=lambda r: (float(r["residues"]) >= 20, float(r["agreement"]))) if rows else None
    return {
        "ran": True,
        "pdb_status": status,  # success, pending (background step not finished), unavailable or off
        "best": None if best is None else {
            "entity": str(best["entity"]), "identity": _num(best["identity"]),
            "residues": int(float(best["residues"])), "agreement": float(best["agreement"]),
        },
    }


def _pretty_target(database, token):
    alphafold = re.match(r"^AF-([A-Za-z0-9]+)-F\d+", token)
    pdb = re.match(r"^([0-9][A-Za-z0-9]{3})(?:[-_.]|$)", token)
    if alphafold:
        return f"AlphaFold DB {alphafold.group(1)}"
    if pdb and database.lower().startswith("pdb"):
        chain = token.rsplit("_", 1)[1] if "_" in token else ""
        return f"PDB {pdb.group(1).upper()}" + (f" chain {chain}" if chain else "")
    return token


def tertiary_evidence(level):
    """The tertiary notebook's findings on the AlphaFold DB structure of the primary level's match."""
    if not _live(level):
        return {"ran": False}
    raw = _dict(level.get("raw"))
    template = _dict(raw.get("template"))
    structure = _dict(raw.get("structure"))
    transfer = _dict(raw.get("annotation_transfer"))
    best = None
    hit = _dict(raw.get("best_hit"))
    if hit.get("target"):
        token, _, description = str(hit["target"]).partition(" ")
        database = next((str(db) for db, h in _dict(raw.get("foldseek_top_hits")).items()
                         if _dict(h).get("target") == hit["target"]), "")
        best = {"database": database, "target": _pretty_target(database, token), "description": description.strip(),
                "evalue": _num(hit.get("eval")), "prob": _num(hit.get("prob")), "coverage": _num(hit.get("coverage"))}
    neighbour = None
    annotation, afdb = _dict(transfer.get("annotation")), _dict(transfer.get("afdb_hit"))
    if transfer.get("status") == "transferred" and annotation.get("accession"):
        sites = [site for site in annotation.get("sites") or [] if isinstance(site, dict)]
        description = str(afdb.get("target", "")).partition(" ")[2].strip()
        name = annotation.get("name")
        neighbour = {
            "accession": str(annotation["accession"]),
            "name": str(name) if name and name != "n/a" else description or str(annotation["accession"]),
            "function": str(annotation["function"]) if annotation.get("function") else None,
            "prob": _num(afdb.get("prob")), "coverage": _num(afdb.get("coverage")), "evalue": _num(afdb.get("eval")),
            "sites": len(sites), "conserved": sum(1 for site in sites if site.get("conserved") is True),
        }
    identity = _num(template.get("identity"))
    return {
        "ran": True,
        "template": str(template.get("accession") or raw.get("uniprot_id") or ""),
        "template_identity": identity,
        "template_coverage": _num(template.get("coverage")),
        # The structure shares the query's fold: its protein passed the primary homology test.
        "template_passed": template.get("passed") is True and identity is not None,
        "plddt": _num(structure.get("mean_plddt")),
        "experimental": structure.get("has_plddt") is False,
        "best": best,
        "neighbour": neighbour,  # the characterised AlphaFold DB match whose annotation was transferred
    }


def quaternary_evidence(level):
    """What the quaternary pipeline found for the analysed protein (assembly, complexes, GO terms)."""
    if not _live(level):
        return {"ran": False}
    raw = level.get("raw") or {}
    output = raw.get("pipeline_output") or {}
    assembly = output.get("target_self_assembly") or {}
    go_terms = []
    for term in (raw.get("uniprot") or {}).get("go_terms", []) or []:
        aspect, _, name = str(term.get("name", "")).partition(":")
        if aspect == "F" and name and name.lower() not in GENERIC_GO:
            go_terms.append([str(term.get("id")), name])
    go_terms.sort(key=lambda t: "activity" not in t[1].lower())  # activities first
    return {
        "ran": True,
        "mode": raw.get("input"),  # "homologue" or "sequence"
        "analysed": raw.get("analysed_target"),
        "status": str(assembly.get("confidence_status") or output.get("status") or "UNKNOWN"),
        "formula": assembly.get("formula"),
        "assembly_type": assembly.get("assembly_type"),
        "subunits": assembly.get("subunit_count"),
        "complexes": [[c.get("name"), c.get("complex_portal_id"), c.get("stoichiometry")]
                      for c in output.get("functional_complexes") or []],
        "go_mf": go_terms,
    }


def evidence_from_levels(levels):
    """levels: {'primary': LevelResult dict or None, 'secondary': ..., 'tertiary': ..., 'quaternary': ...}"""
    return {
        "primary": primary_evidence(levels.get("primary")),
        "secondary": secondary_evidence(levels.get("secondary")),
        "tertiary": tertiary_evidence(levels.get("tertiary")),
        "quaternary": quaternary_evidence(levels.get("quaternary")),
    }


# =============================================================================
# The model (notebook section 6, unchanged)
# =============================================================================

PARAMS = {
    # Route 1 - sequence homology (the primary notebook's best hit, DIAMOND or EBI BLASTp, that passed its thresholds)
    "seq_hom_40": 0.99,       # P(homologous) when identity >= 40%
    "seq_hom_30": 0.90,       # P(homologous) when identity is 30-40% (twilight zone, Rost 1999)
    "cons_60": 0.95,          # P(function conserved) at >= 60% identity (Tian & Skolnick 2003)
    "cons_40": 0.80,          # ... at 40-60% identity (first three EC digits reliable)
    "cons_30": 0.55,          # ... at 30-40% identity (function diverges, Rost 2002)
    # Route 2 - domain support (Pfam domain with independent E-value < 1e-10, else an integrated InterPro entry)
    "dom_hom": 0.95,          # P(the domain is a true family member)
    "dom_cons": 0.50,         # P(the family's function applies to this protein)
    # Route 3 - fold only (tertiary: Foldseek match of the AlphaFold DB structure of the primary level's match)
    "fold_cons": 0.25,        # P(function conserved | same fold only) (Aloy et al. 2003)
    "fold_prob": 0.5,         # the structural match counts if Foldseek's homology probability >= this ...
    "fold_cov": 0.5,          # ... over >= this fraction of the structure (both from the tertiary notebook)
    "plddt_min": 70.0,        # the structure is trusted only if its mean pLDDT is above this (AlphaFold "confident")
    # Consistency checks (log-odds adjustments)
    "ss_agree": 75.0,         # % agreement with experimental structures that counts as agreement
    "ss_contra": 60.0,        # % agreement below which it counts as a contradiction
    "ss_min_res": 20,         # minimum residues compared
    "d_ss_agree": 0.4,
    "d_ss_contra": -1.0,
    "d_q_good": 0.4,          # template's assembly CONFIRMED or SUPPORTED
    "d_q_conflict": -0.5,     # template's assembly evidence CONFLICTING
    "q_full_identity": 40.0,  # below this identity the quaternary adjustment is halved (Aloy et al. 2003)
    # Confidence bands
    "high": 0.80,
    "moderate": 0.50,
}


def logit(p):
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def p_homology_seq(identity, P):
    return P["seq_hom_40"] if identity >= 40 else P["seq_hom_30"]


def p_conserved_seq(identity, P):
    if identity >= 60:
        return P["cons_60"]
    if identity >= 40:
        return P["cons_40"]
    return P["cons_30"]


def fold_is_significant(tertiary, P):
    """The tertiary level transferred the annotation of a characterised structural match."""
    match = tertiary.get("neighbour") if tertiary.get("ran") else None
    return (bool(match) and bool(match["function"]) and not UNCHARACTERISED.match(match["name"])
            and match["prob"] is not None and match["prob"] >= P["fold_prob"]
            and match["coverage"] is not None and match["coverage"] >= P["fold_cov"])


def model_is_reliable(tertiary, P):
    """The structure is trusted: an experimental structure, or mean pLDDT above plddt_min."""
    if not tertiary.get("ran"):
        return False
    return tertiary.get("experimental") is True or (tertiary.get("plddt") is not None and tertiary["plddt"] > P["plddt_min"])


def family_label(description):
    lowered = description.lower()
    if lowered.endswith("family"):
        return f"{description} member"
    if lowered.endswith("domain"):
        return f"{description}-containing protein"
    return f"{description} family"


def predict(ev, P=PARAMS):
    """Chain of evidence: P(homology) x P(function conserved), then consistency checks in log-odds."""
    prim, sec, ter, quat = ev["primary"], ev["secondary"], ev["tertiary"], ev["quaternary"]
    hit = prim.get("hit") if prim.get("ran") else None
    domain = prim.get("domain") if prim.get("ran") else None
    named = hit is not None and hit["passed"] and not UNCHARACTERISED.match(hit["protein"] or hit["entry"])

    # ---- Step 1: choose the route (what is transferred, and how specific it is)
    if named:
        route, specificity = "sequence", "specific protein"
        function = hit["protein"]
        p_hom, p_cons = p_homology_seq(hit["identity"], P), p_conserved_seq(hit["identity"], P)
        basis = (f"closest Swiss-Prot protein {hit['accession']} ({hit['entry']}), "
                 f"{hit['identity']:.1f}% identity over {hit['coverage']:.1f}% of the query")
    elif domain is not None:
        route, specificity = "domain", "protein family"
        source = domain.get("source", "Pfam")
        function = f"{family_label(domain['description'])} ({source} {domain['accession']})"
        p_hom, p_cons = P["dom_hom"], P["dom_cons"]
        if domain.get("evalue") is not None:
            basis = f"{source} domain {domain['description']} ({domain['accession']}, E = {domain['evalue']:.1e})"
        else:
            basis = f"{source} entry {domain['description']} ({domain['accession']}, integrated InterProScan signatures)"
    elif (prim.get("ran") and ter.get("ran") and ter.get("template_passed")
          and model_is_reliable(ter, P) and fold_is_significant(ter, P)):
        match = ter["neighbour"]
        route, specificity = "fold", "fold only"
        function = f"Structural similarity to {match['name']} ({match['accession']})"
        # query ~ the structure's protein (sequence homology), then that structure ~ the match (Foldseek)
        p_hom, p_cons = p_homology_seq(ter["template_identity"], P) * match["prob"], P["fold_cons"]
        basis = (f"Foldseek match of the AlphaFold DB structure of {ter['template']} "
                 f"({ter['template_identity']:.1f}% identical to the query) to {match['accession']} "
                 f"(prob = {match['prob']:.2f}, coverage {match['coverage']:.0%})")
    else:
        route, specificity, function, p_hom, p_cons, basis = None, "none", "Function not determined", None, None, ""

    support = {key: ("not run" if not ev[key].get("ran") else "neutral") for key in ("primary", "secondary", "tertiary", "quaternary")}
    steps = []
    if route is None:
        return {"function": function, "route": None, "specificity": specificity, "score": None,
                "band": "undetermined", "steps": steps, "support": support, "basis": basis,
                "p_hom": None, "p_cons": None, "base": None}

    base = p_hom * p_cons
    total = logit(base)
    steps.append(("base", f"P(homology) {p_hom:.2f} x P(function conserved) {p_cons:.2f} = {base:.2f}", total))
    if route in ("sequence", "domain"):
        support["primary"] = "supports"
    else:
        support["tertiary"] = "supports"

    # ---- Step 2: consistency checks
    if route != "fold" and ter.get("ran"):
        # The structure is that of the primary level's own match, so it cannot test the transfer.
        steps.append(("tertiary", f"it analysed the AlphaFold DB structure of {ter.get('template') or 'the primary match'}, "
                                  "the primary level's own match, so it is not an independent test", 0.0))

    if sec.get("ran"):
        best = sec.get("best")
        if sec.get("pdb_status") == "pending":
            steps.append(("secondary", "the comparison with experimental PDB structures has not finished", 0.0))
        elif sec.get("pdb_status") == "unavailable":
            steps.append(("secondary", "the PDB reference lookup was unavailable", 0.0))
        elif best is None or best["residues"] < P["ss_min_res"]:
            steps.append(("secondary", "no experimental structure to compare with", 0.0))
        elif best["agreement"] >= P["ss_agree"]:
            steps.append(("secondary", f"{best['agreement']:.1f}% agreement with {best['entity']} ({best['residues']} residues)", P["d_ss_agree"]))
            support["secondary"] = "supports"
        elif best["agreement"] < P["ss_contra"]:
            steps.append(("secondary", f"only {best['agreement']:.1f}% agreement with {best['entity']}", P["d_ss_contra"]))
            support["secondary"] = "contradicts"
        else:
            steps.append(("secondary", f"{best['agreement']:.1f}% agreement with {best['entity']} (inconclusive)", 0.0))

    if quat.get("ran"):
        about_template = route == "sequence" and quat.get("mode") == "homologue" and quat.get("analysed") == hit["accession"]
        if not about_template:
            steps.append(("quaternary", "the pipeline did not analyse the predicted template", 0.0))
        else:
            factor = 1.0 if hit["identity"] >= P["q_full_identity"] else 0.5
            status = quat["status"]
            if status in ("CONFIRMED", "SUPPORTED"):
                steps.append(("quaternary", f"template assembly {quat['formula']} is {status}", P["d_q_good"] * factor))
                support["quaternary"] = "supports"
            elif status == "CONFLICTING":
                steps.append(("quaternary", "template assembly evidence is CONFLICTING", P["d_q_conflict"] * factor))
                support["quaternary"] = "contradicts"
            else:
                steps.append(("quaternary", f"template assembly status {status} (no adjustment)", 0.0))

    total = sum(delta for _, _, delta in steps)
    score = sigmoid(total)
    band = "high" if score >= P["high"] else "moderate" if score >= P["moderate"] else "low"
    return {"function": function, "route": route, "specificity": specificity, "score": score, "band": band,
            "steps": steps, "support": support, "basis": basis, "p_hom": p_hom, "p_cons": p_cons, "base": base}


# =============================================================================
# Turning the prediction into the interface's verdict
# =============================================================================

MAX_GO_TERMS = 6
_GO_ID = re.compile(r"^GO:\d{7}$")
# Level states meaning "not finished yet": the verdict is provisional.
_RUNNING = frozenset({"pending", "running"})
_ROUTE_TEXT = {
    "sequence": "Route 1 of 3, sequence homology",
    "domain": "Route 2 of 3, protein family (domain)",
    "fold": "Route 3 of 3, structural similarity",
}
_LEVEL_NAME = {"tertiary": "Tertiary", "secondary": "Secondary", "quaternary": "Quaternary"}


def _brief(text, limit):
    collapsed = " ".join(str(text).split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _level_results(job):
    """Each level's result as plain data, but only for levels that completed."""
    return {
        level.key: level.result.model_dump(mode="json")
        if level.status == "completed" and level.result is not None
        else None
        for level in job.levels
    }


def _template_context(ev, prediction):
    """The quaternary level's findings, if it analysed the template the function came from."""
    if prediction["route"] != "sequence":
        return None
    quat, hit = ev["quaternary"], ev["primary"]["hit"]
    if not quat.get("ran") or quat.get("mode") != "homologue" or quat.get("analysed") != hit["accession"]:
        return None
    return quat


def _join(names):
    """['a'] -> 'a'; ['a', 'b'] -> 'a and b'; ['a', 'b', 'c'] -> 'a, b and c'."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _percent(value):
    return f"{value:.1f}%" if value is not None else "?"


def _scientific(value):
    return f"{value:.1e}" if value is not None else "?"


def _description(ev, prediction, missing, running):
    """One sentence on how the function was reached; the facts (_facts) give the details."""
    route = prediction["route"]
    prim = ev["primary"]
    hit = prim.get("hit") if prim.get("ran") else None
    domain = prim.get("domain") if prim.get("ran") else None
    if route == "sequence":
        return (
            f"Transferred from the closest characterised Swiss-Prot protein ({_percent(hit['identity'])} identity), "
            "so the function is predicted at the level of the specific protein."
        )
    if route == "domain":
        opening = (
            "The closest Swiss-Prot protein is itself uncharacterised"
            if hit is not None and hit["passed"]
            else "No Swiss-Prot protein passed the homology test"
        )
        kind = "domain" if domain.get("source", "Pfam") == "Pfam" else "entry"
        return (
            f"{opening}, so a family-level function is predicted from the {domain.get('source', 'Pfam')} {kind} "
            f"{domain['description']}; members of a family can differ in their exact function."
        )
    if route == "fold":
        return (
            "Neither a characterised Swiss-Prot homologue nor a protein domain supported a function, so it is inferred "
            "from a characterised protein whose structure matches the AlphaFold DB structure of the closest "
            "Swiss-Prot match; similar folds can carry different functions, so treat it as a hint."
        )
    text = (
        "No characterised Swiss-Prot homologue, protein domain or characterised structural match "
        "supported a function."
    )
    if missing:
        levels = f"{' and '.join(missing)} level{'s' if len(missing) > 1 else ''}"
        text += f" The {levels} gave no result, so part of that evidence was missing."
    if running:
        text += f" The {' and '.join(running)} level{'s are' if len(running) > 1 else ' is'} still running."
    return text


def _go_terms(context):
    if context is None:
        return []
    terms, seen = [], set()
    for go_id, name in context["go_mf"]:
        if _GO_ID.match(str(go_id)) and go_id not in seen:
            seen.add(go_id)
            terms.append(GoTerm(id=go_id, term=name, aspect="molecular_function"))
    return terms[:MAX_GO_TERMS]


def _assembly(context):
    """The template's oligomeric state, e.g. 'Homotetramer (A4), confirmed'."""
    formula = str(context.get("formula") or "")
    subunits = _num(context.get("subunits"))
    name = assembly_name(str(context.get("assembly_type") or ""), int(subunits)) if subunits else "Uncharacterized"
    shown = f"{name} ({formula})" if name != "Uncharacterized" and formula else formula or name
    return f"{shown}, {str(context['status']).lower()}"


def _domain_fact(domain):
    """('Pfam domain', 'Globin (PF00042)') or ('InterPro entry', 'Globin-like (IPR009050)')."""
    source = domain.get("source", "Pfam")
    return (f"{source} {'domain' if source == 'Pfam' else 'entry'}", f"{domain['description']} ({domain['accession']})")


def _tier_text(tier):
    """'A - Strong' -> 'A · Strong'."""
    return str(tier).replace(" - ", " · ", 1)


def _facts(ev, prediction, context):
    """The key facts behind the prediction, shown as a grid under the predicted function."""
    route = prediction["route"]
    prim, ter = ev["primary"], ev["tertiary"]
    hit = prim.get("hit") if prim.get("ran") else None
    domain = prim.get("domain") if prim.get("ran") else None
    tier = prim.get("tier") if prim.get("ran") else None
    facts = []
    if route == "sequence":
        gene = f", gene {hit['gene']}" if hit.get("gene") else ""
        source = f"{hit['protein'] or hit['entry']} ({hit['accession']}{gene})"
        similarity = f"{_percent(hit['identity'])} identity over {_percent(hit['coverage'])} of the query"
        facts += [
            ("Basis", "Sequence homology (route 1 of 3)"),
            ("Closest Swiss-Prot protein", source + (f", {hit['organism']}" if hit["organism"] else "")),
            ("Similarity", similarity + (f" · {hit['method']}" if hit.get("method") else "")),
        ]
        if domain is not None:
            facts.append(_domain_fact(domain))
        if context is not None:
            if context.get("formula") and context["status"] in ("CONFIRMED", "SUPPORTED"):
                facts.append((f"Oligomeric state of {hit['accession']}", _assembly(context)))
            complexes = []
            for name, identifier, stoichiometry in context["complexes"][:2]:
                if name:
                    details = ", ".join(str(part) for part in (identifier, stoichiometry) if part)
                    complexes.append(f"{name} ({details})" if details else str(name))
            if complexes:
                facts.append(("Complex" if len(complexes) == 1 else "Complexes", "; ".join(complexes)))
        if tier:
            facts.append(("Primary evidence tier", _tier_text(tier)))
        facts.append(("Specificity", "Specific protein"))
    elif route == "domain":
        source = domain.get("source", "Pfam")
        facts += [
            ("Basis", f"{source} {'domain' if source == 'Pfam' else 'entry'} (route 2 of 3)"),
            _domain_fact(domain),
        ]
        if domain.get("evalue") is not None:
            facts.append(("Domain E-value", _scientific(domain["evalue"])))
        if hit is not None and hit["passed"]:
            source = f"{hit['protein'] or hit['entry']} ({hit['accession']})"
            facts.append(("Closest Swiss-Prot protein", f"{source}, uncharacterised"))
        elif hit is not None:
            similarity = f"{_percent(hit['identity'])} identity over {_percent(hit['coverage'])} of the query"
            facts.append(("Best Swiss-Prot hit", f"{hit['entry']}: {similarity} (below the homology thresholds)"))
        else:
            facts.append(("Best Swiss-Prot hit", "none found"))
        if tier:
            facts.append(("Primary evidence tier", _tier_text(tier)))
        facts.append(("Specificity", "Protein family"))
    elif route == "fold":
        match = ter["neighbour"]
        evalue = f", E-value {_scientific(match['evalue'])}" if match["evalue"] is not None else ""
        facts += [
            ("Basis", "Structural similarity (route 3 of 3)"),
            ("Structural match", f"{match['name']} ({match['accession']}, AlphaFold DB)"),
            ("Match statistics",
             f"homology probability {match['prob']:.2f} over {match['coverage']:.0%} of the structure{evalue}"),
            ("Structure analysed",
             f"AlphaFold DB {ter['template']}, {_percent(ter['template_identity'])} identical to the query over "
             f"{_percent(ter['template_coverage'])} of it"),
            ("Structure confidence",
             f"mean pLDDT {ter['plddt']:.1f}" if ter["plddt"] is not None else "experimental structure"),
        ]
        if match["sites"]:
            facts.append(("Functional sites", f"{match['conserved']} of {match['sites']} conserved"))
        if tier:
            facts.append(("Primary evidence tier", _tier_text(tier)))
        facts.append(("Specificity", "Fold only"))
    return [VerdictFact(label=label, value=value) for label, value in facts]


def _curated_function(ev, prediction):
    """UniProt's curated FUNCTION text of the protein the function was transferred from."""
    if prediction["route"] == "sequence":
        source = ev["primary"]["hit"]
    elif prediction["route"] == "fold":
        source = ev["tertiary"]["neighbour"]
    else:
        return None
    if not source.get("function"):
        return None
    text = textwrap.shorten(" ".join(str(source["function"]).split()), 600, placeholder=" …")
    return CuratedFunction(accession=source["accession"], text=text)


def _band(score, P):
    return "high" if score >= P["high"] else "moderate" if score >= P["moderate"] else "low"


def _confidence_range(ev, prediction, statuses, P, refining=frozenset()):
    """The confidence the levels that have not finished could still produce (None if none apply).

    Once the primary level has finished the route, and so the predicted function, is fixed
    (the fold route also needs the tertiary level, so it has finished too). An unfinished
    level can then only add the adjustment `predict` gives it: the agreement bonus, the
    contradiction penalty or nothing (the tertiary level gives none). The extremes of the range are all-agree and
    all-contradict. While the primary level's own background step (EBI BLASTp and
    InterProScan) still runs, the best match itself may still be refined: function_fixed
    is then False.
    """
    route = prediction["route"]
    if route is None or statuses.get("primary") not in ("completed", "failed", "skipped"):
        return None
    unfinished = {key for key, status in statuses.items() if status in _RUNNING or status == "cancelled"}
    possible = {}
    if "secondary" in unfinished or ("secondary" in refining and ev["secondary"].get("pdb_status") == "pending"):
        possible["secondary"] = (P["d_ss_contra"], P["d_ss_agree"])
    if "quaternary" in unfinished and route == "sequence":
        factor = 1.0 if ev["primary"]["hit"]["identity"] >= P["q_full_identity"] else 0.5
        possible["quaternary"] = (P["d_q_conflict"] * factor, P["d_q_good"] * factor)
    if not possible:
        return None
    total = sum(delta for _, _, delta in prediction["steps"])
    low = sigmoid(total + sum(min(0.0, worst) for worst, _ in possible.values()))
    high = sigmoid(total + sum(max(0.0, best) for _, best in possible.values()))
    levels = [key for key in ("primary", "secondary", "tertiary", "quaternary") if key in possible]
    return ConfidenceRange(
        low=round(low, 2),
        high=round(high, 2),
        low_tier=_band(low, P),
        high_tier=_band(high, P),
        levels=levels,
        stopped=all(statuses.get(key) == "cancelled" for key in levels),
        function_fixed="primary" not in refining,
    )


def _range_line(confidence_range):
    names = _join(confidence_range.levels)
    plural = "s" if len(confidence_range.levels) > 1 else ""
    low, high = confidence_range.low, confidence_range.high
    tiers = (
        f"{confidence_range.high_tier} either way"
        if confidence_range.low_tier == confidence_range.high_tier
        else f"{confidence_range.low_tier} to {confidence_range.high_tier}"
    )
    if confidence_range.stopped:
        return (
            f"Had the {names} level{plural} finished, the confidence would have been between {low:.2f} and "
            f"{high:.2f} ({tiers}); the predicted function would have been the same."
        )
    if not confidence_range.function_fixed:
        return (
            f"Still to come: the {names} check{plural} can move the confidence to between {low:.2f} and "
            f"{high:.2f} ({tiers}); the primary level's EBI BLASTp and InterProScan may still refine the best match."
        )
    return (
        f"Still to come: the {names} check{plural} can move the confidence to between {low:.2f} and {high:.2f} "
        f"({tiers}); the predicted function itself will not change."
    )


def _rationale(ev, prediction, context, P, statuses, confidence_range, refining=frozenset()):
    route = prediction["route"]
    if route is None:
        lines = [
            "No route applied: no characterised Swiss-Prot homologue passed the primary homology test, no Pfam domain "
            "or InterPro entry gave domain support, and the tertiary level found no characterised structural match "
            "for a reliable structure that shares the query's fold."
        ]
    else:
        lines = [f"{_ROUTE_TEXT[route]}: {prediction['basis']} (specificity: {prediction['specificity']})."]
        for level, text, delta in prediction["steps"]:
            if level == "base":
                lines.append(
                    f"Starting confidence: P(homology) {prediction['p_hom']:.2f} × P(function conserved) "
                    f"{prediction['p_cons']:.2f} = {prediction['base']:.2f} (log-odds {delta:+.2f})."
                )
            elif delta == 0:
                lines.append(f"{_LEVEL_NAME[level]} check: {text} (no adjustment).")
            else:
                lines.append(f"{_LEVEL_NAME[level]} check: {text} → {delta:+.2f} log-odds.")
    for key in ("primary", "secondary", "tertiary", "quaternary"):
        if not ev[key].get("ran"):
            status = statuses.get(key)
            if status in _RUNNING:
                lines.append(f"{key.capitalize()} level: still running; the prediction is updated when it finishes.")
            elif status == "cancelled":
                lines.append(f"{key.capitalize()} level: stopped before it finished, so it was not used.")
            else:
                lines.append(f"{key.capitalize()} level: no real (live) result, so it was not used.")
    if "primary" in refining:
        lines.append(
            "Primary level: its remote EBI BLASTp and InterProScan are still running; they can refine the best "
            "match and the domain evidence, and the prediction is updated when they finish."
        )
    if "secondary" in refining:
        lines.append(
            "Secondary level: its comparison with experimental PDB structures is still running; the prediction is "
            "updated when it finishes."
        )
    if prediction["score"] is not None:
        total = sum(delta for _, _, delta in prediction["steps"])
        lines.append(
            f"Confidence {prediction['score']:.2f} = sigmoid({total:.2f}): {prediction['band']} "
            f"(high ≥ {P['high']:.2f}, moderate ≥ {P['moderate']:.2f}). Agreement between levels is rewarded less "
            "than contradiction is penalised; the score is a literature-anchored estimate, not a calibrated probability."
        )
    if confidence_range is not None:
        lines.append(_range_line(confidence_range))
    return lines


def _support(level, state):
    if level.status in _RUNNING:
        return "pending"
    if level.status != "completed" or level.result is None:
        return "unavailable"
    if level.result.source == "placeholder":
        return "placeholder"
    return {"supports": "supports", "contradicts": "contradicts"}.get(state, "neutral")


def _integrate(job):
    ev = evidence_from_levels(_level_results(job))
    prediction = predict(ev, PARAMS)
    context = _template_context(ev, prediction)
    statuses = {level.key: level.status for level in job.levels}
    refining = frozenset(level.key for level in job.levels if level.refining)
    running = [key for key in ("primary", "tertiary") if not ev[key].get("ran") and statuses.get(key) in _RUNNING]
    missing = [key for key in ("primary", "tertiary") if not ev[key].get("ran") and key not in running]
    function = prediction["function"]
    if prediction["route"] == "fold":
        function = _brief(function, 110)
    score = prediction["score"]
    confidence_range = _confidence_range(ev, prediction, statuses, PARAMS, refining)
    return Verdict(
        source="live",
        function=function,
        description=_description(ev, prediction, missing, running),
        confidence_tier=prediction["band"],
        confidence_score=None if score is None else round(min(max(score, 0.0), 1.0), 2),
        confidence_range=confidence_range,
        curated_function=_curated_function(ev, prediction),
        facts=_facts(ev, prediction, context),
        go_terms=_go_terms(context),
        level_support=[
            LevelSupport(key=level.key, state=_support(level, prediction["support"].get(level.key, "neutral")))
            for level in job.levels
        ],
        rationale=_rationale(ev, prediction, context, PARAMS, statuses, confidence_range, refining),
    )


def _simple_support(level: LevelReport) -> SupportState:
    if level.status in _RUNNING:
        return "pending"
    if level.status != "completed" or level.result is None:
        return "unavailable"
    return "placeholder" if level.result.source == "placeholder" else "neutral"


def _placeholder_verdict(job: AnalysisJob, support: list[LevelSupport]) -> Verdict:
    """Mock mode: the known function of the built-in examples, clearly marked."""
    reported = sum(1 for item in support if item.state not in ("unavailable", "pending"))
    coverage_note = f"{reported} of {len(support)} structural levels returned results."
    example = find_example(job.query.sequence)
    if example is not None:
        return Verdict(
            source="placeholder",
            function=example.function,
            description=example.description,
            confidence_tier="high",
            confidence_score=0.9,
            go_terms=[term.model_copy() for term in example.go_terms],
            level_support=support,
            rationale=[
                "Placeholder verdict: every level returned placeholder data, so the known function of this "
                "built-in example is shown.",
                coverage_note,
            ],
        )
    return Verdict(
        source="placeholder",
        function="Function not yet determined",
        description="Every level returned placeholder data, so no real prediction can be made.",
        confidence_tier="undetermined",
        confidence_score=None,
        go_terms=[],
        level_support=support,
        rationale=["Placeholder verdict: no real analysis results were available.", coverage_note],
    )


def build_verdict(job: AnalysisJob) -> Verdict:
    """Combine the level results into the final prediction. Never raises."""
    simple = [LevelSupport(key=level.key, state=_simple_support(level)) for level in job.levels]
    any_live = any(item.state == "neutral" for item in simple)
    any_placeholder = any(item.state == "placeholder" for item in simple)
    if not any_live and any_placeholder:
        return _placeholder_verdict(job, simple)
    try:
        return _integrate(job)
    except Exception as error:  # a verdict must always be produced
        logger.exception("Could not combine the evidence for job %s", job.id)
        return Verdict(
            source="live",
            function="Function not determined",
            description="The level results could not be combined into a prediction.",
            confidence_tier="undetermined",
            confidence_score=None,
            go_terms=[],
            level_support=simple,
            rationale=[f"Evidence integration failed: {_brief(str(error) or error.__class__.__name__, 200)}"],
        )
