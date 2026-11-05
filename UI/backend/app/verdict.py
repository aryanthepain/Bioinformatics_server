"""The integration step: combine the four level results into one predicted function.

Same logic as the notebook "Function_Prediction_Integration.ipynb" (sections 4 and 6
are copied here unchanged), so the website and the notebook give identical answers.

Function is predicted by transferring the annotation of a related, characterised
protein, so the confidence is

    P(function correct) = P(homologous to the template) x P(function conserved at this distance)

  Route (first that applies)          predicted function             P(homology)        P(conserved)
  1. sequence: DIAMOND hit passed     the hit's protein name         0.99 (>= 40% id)   0.95 (>= 60%)
     the primary thresholds and is                                   0.90 (30-40%)      0.80 (40-60%)
     characterised                                                                      0.55 (30-40%)
  2. domain: Pfam E-value < 1e-10     "X family member"              0.95               0.50
  3. fold: significant Foldseek       "Structural similarity to X"   Foldseek prob      0.25
     match of a reliable model
     (mean QMEAN >= 0.6)

The other levels are consistency checks, added on the log-odds scale:
  tertiary   reliable model with a significant match +0.5; without one -1.0
  secondary  agreement with experimental PDB structures >= 75% +0.4; < 60% -1.0
  quaternary template assembly CONFIRMED/SUPPORTED +0.4; CONFLICTING -0.5
             (halved below 40% identity)
Agreement is rewarded less than contradiction is penalised: agreement between
dependent levels is expected, a contradiction is informative.

Score = sigmoid(logit(base) + adjustments); bands: high >= 0.80, moderate >= 0.50.
Literature: Tian & Skolnick 2003 (J Mol Biol 333:863), Rost 1999 (Protein Eng 12:85),
Rost 2002 (J Mol Biol 318:595), Aloy et al. 2003 (J Mol Biol 332:989), van Kempen
et al. 2024 (Nat Biotechnol 42:243). The score is a literature-anchored estimate,
not a calibrated probability.

When every level returned placeholder data (mock mode), the built-in examples
still show their known function, clearly marked as a placeholder.
"""

import logging
import math
import re

from .examples import find_example
from .schemas import AnalysisJob, GoTerm, LevelReport, LevelSupport, SupportState, Verdict

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


def _passed(level, prefix):
    """The primary notebook's own verdict: its evidence line is positive when the test passed."""
    return any(item.get("polarity") == "positive" and str(item.get("text", "")).startswith(prefix)
               for item in level.get("evidence", []))


def _parse_swissprot_title(title):
    """'sp|P69905|HBA_HUMAN Hemoglobin subunit alpha OS=Homo sapiens OX=9606 ...' -> parts."""
    token, _, rest = title.partition(" ")
    parts = token.split("|")
    accession = parts[1] if len(parts) > 2 else token
    entry = parts[2] if len(parts) > 2 else token
    protein = rest.split(" OS=")[0].strip()
    organism = re.search(r"OS=(.*?)(?: OX=|$)", rest)
    return accession, entry, protein, organism.group(1).strip() if organism else ""


def primary_evidence(level):
    """DIAMOND best Swiss-Prot hit and the best Pfam domain (HMMER) from the primary level."""
    if not _live(level):
        return {"ran": False}
    raw = level.get("raw") or {}
    diamond, hmmer = raw.get("diamond") or {}, raw.get("hmmer") or {}
    hit = None
    if diamond.get("title") and (_num(diamond.get("identity")) or 0) > 0:
        accession, entry, protein, organism = _parse_swissprot_title(str(diamond["title"]))
        hit = {
            "accession": accession, "entry": entry, "protein": protein, "organism": organism,
            "identity": _num(diamond.get("identity")), "coverage": _num(diamond.get("query_coverage")),
            "evalue": _num(diamond.get("e_value")),
            "passed": _passed(level, "DIAMOND:"),  # identity > 30% and coverage >= 80%
        }
    domain = None
    if _passed(level, "HMMER:") and hmmer.get("domain") not in (None, "None"):
        accession = str(hmmer.get("accession") or "")
        same = [d for d in hmmer.get("domains", []) or [] if d.get("accession") == accession and _num(d.get("e_value")) is not None]
        best = min(same, key=lambda d: float(d["e_value"])) if same else {}
        domain = {
            "name": str(hmmer["domain"]), "accession": accession.split(".")[0],
            "description": str(best.get("description") or hmmer["domain"]), "evalue": _num(hmmer.get("e_value")),
        }
    return {"ran": True, "hit": hit, "domain": domain}


def secondary_evidence(level):
    """Best agreement between the predicted secondary structure and experimental PDB structures."""
    if not _live(level):
        return {"ran": False}
    raw = level.get("raw") or {}
    rows = [
        r for r in raw.get("experimental_comparison") or []
        if _num(r.get("SS_Agreement_%")) is not None and _num(r.get("Comparable_Residues")) is not None
    ]
    best = max(rows, key=lambda r: (float(r["Comparable_Residues"]) >= 20, float(r["SS_Agreement_%"]))) if rows else None
    return {
        "ran": True,
        "predictor_agreement": _num(raw.get("predictor_agreement_percent")),
        "best": None if best is None else {
            "entity": str(best.get("PDB_entity")), "identity": _num(best.get("Sequence_Identity_%")),
            "residues": int(float(best["Comparable_Residues"])), "agreement": float(best["SS_Agreement_%"]),
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
    """Model quality (mean local QMEAN) and the best Foldseek match of the SWISS-MODEL model."""
    if not _live(level):
        return {"ran": False}
    raw = level.get("raw") or {}
    qmean = next((_num(m.get("value")) for m in level.get("metrics", []) if m.get("label") == "Mean local quality"), None)
    best = None
    for database, hit in (raw.get("foldseek_top_hits") or {}).items():
        evalue = _num((hit or {}).get("eval"))
        if evalue is None:
            continue
        token, _, description = str(hit.get("target", "")).partition(" ")
        candidate = {
            "database": database, "target": _pretty_target(database, token), "description": description.strip(),
            "evalue": evalue, "prob": _num(hit.get("prob")), "seq_id": _num(hit.get("seqId")),
        }
        if best is None or evalue < best["evalue"]:
            best = candidate
    return {"ran": True, "qmean": qmean, "best": best}


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
    # Route 1 - sequence homology (DIAMOND hit that passed the primary thresholds)
    "seq_hom_40": 0.99,       # P(homologous) when identity >= 40%
    "seq_hom_30": 0.90,       # P(homologous) when identity is 30-40% (twilight zone, Rost 1999)
    "cons_60": 0.95,          # P(function conserved) at >= 60% identity (Tian & Skolnick 2003)
    "cons_40": 0.80,          # ... at 40-60% identity (first three EC digits reliable)
    "cons_30": 0.55,          # ... at 30-40% identity (function diverges, Rost 2002)
    # Route 2 - Pfam domain (HMMER independent E-value < 1e-10)
    "dom_hom": 0.95,          # P(the domain is a true family member)
    "dom_cons": 0.50,         # P(the family's function applies to this protein)
    # Route 3 - fold only (Foldseek)
    "fold_cons": 0.25,        # P(function conserved | same fold only) (Aloy et al. 2003)
    "fold_evalue": 1e-3,      # a structural match counts if E <= this ...
    "fold_prob": 0.5,         # ... and Foldseek's homology probability >= this
    "qmean_min": 0.6,         # the 3D model is trusted only if mean local QMEAN >= this
    # Consistency checks (log-odds adjustments)
    "d_ter_agree": 0.5,       # reliable model with a significant structural match
    "d_ter_contra": -1.0,     # reliable model but no significant structural match
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
    best = tertiary.get("best") if tertiary.get("ran") else None
    return bool(best) and best["evalue"] <= P["fold_evalue"] and (best["prob"] is None or best["prob"] >= P["fold_prob"])


def model_is_reliable(tertiary, P):
    return tertiary.get("ran") and tertiary.get("qmean") is not None and tertiary["qmean"] >= P["qmean_min"]


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
        function = f"{family_label(domain['description'])} (Pfam {domain['accession']})"
        p_hom, p_cons = P["dom_hom"], P["dom_cons"]
        basis = f"Pfam domain {domain['description']} ({domain['accession']}, E = {domain['evalue']:.1e})"
    elif fold_is_significant(ter, P) and model_is_reliable(ter, P):
        best = ter["best"]
        route, specificity = "fold", "fold only"
        function = f"Structural similarity to {best['target']}" + (f" ({best['description']})" if best["description"] else "")
        p_hom, p_cons = (best["prob"] if best["prob"] is not None else 0.5), P["fold_cons"]
        basis = f"Foldseek match {best['target']} in {best['database']} (E = {best['evalue']:.1e}, prob = {p_hom:.2f})"
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
        if not model_is_reliable(ter, P):
            steps.append(("tertiary", f"model unreliable (mean QMEAN {ter.get('qmean')}); not used", 0.0))
        elif fold_is_significant(ter, P):
            b = ter["best"]
            steps.append(("tertiary", f"reliable model matches {b['target']} (E = {b['evalue']:.1e})", P["d_ter_agree"]))
            support["tertiary"] = "supports"
        else:
            steps.append(("tertiary", "reliable model but no significant structural match", P["d_ter_contra"]))
            support["tertiary"] = "contradicts"

    if sec.get("ran"):
        best = sec.get("best")
        if best is None or best["residues"] < P["ss_min_res"]:
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
_ROUTE_TEXT = {
    "sequence": "Route 1 of 3, sequence homology",
    "domain": "Route 2 of 3, Pfam domain",
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


def _description(ev, prediction, context, missing):
    route = prediction["route"]
    prim, ter = ev["primary"], ev["tertiary"]
    hit = prim.get("hit") if prim.get("ran") else None
    domain = prim.get("domain") if prim.get("ran") else None
    if route == "sequence":
        where = f", {hit['organism']}" if hit["organism"] else ""
        text = (
            f"Closest characterised Swiss-Prot protein: {hit['protein']} ({hit['accession']}{where}), "
            f"{hit['identity']:.1f}% identity over {hit['coverage']:.1f}% of the query, so its function is "
            "transferred at the level of the specific protein."
        )
        if domain is not None:
            text += f" Pfam domain: {domain['description']} ({domain['accession']})."
        if context is not None:
            if context.get("formula") and context["status"] in ("CONFIRMED", "SUPPORTED"):
                text += f" Oligomeric state of {hit['accession']}: {context['formula']} ({context['status']})."
            for name, identifier, stoichiometry in context["complexes"][:2]:
                if name:
                    details = ", ".join(str(part) for part in (identifier, stoichiometry) if part)
                    text += f" Member of the {name}" + (f" ({details})." if details else ".")
        return text
    if route == "domain":
        if hit is not None and hit["passed"]:
            opening = f"The closest Swiss-Prot protein ({hit['entry']}) is itself uncharacterised"
        elif hit is not None:
            opening = (
                f"No Swiss-Prot protein passed the homology test (best hit {hit['entry']}: "
                f"{hit['identity']:.1f}% identity, {hit['coverage']:.1f}% coverage)"
            )
        else:
            opening = "No Swiss-Prot protein passed the homology test"
        return (
            f"{opening}, but the sequence contains the {domain['description']} domain ({domain['accession']}, "
            f"E-value {domain['evalue']:.1e}), so a family-level function is predicted; members of a family "
            "can differ in their exact function."
        )
    if route == "fold":
        best = ter["best"]
        probability = f", homology probability {best['prob']:.2f}" if best["prob"] is not None else ""
        return (
            "Neither a characterised Swiss-Prot homologue nor a Pfam domain supported a function, but the "
            f"reliable 3D model matches {best['target']} in {best['database']} (E-value {best['evalue']:.1e}"
            f"{probability}). Similar folds can carry different functions, so treat this as a hint."
        )
    text = "No Swiss-Prot homologue, Pfam domain or significant structural match from a reliable model supported a function."
    if missing:
        text += f" The {' and '.join(missing)} level{'s' if len(missing) > 1 else ''} gave no result, so part of that evidence was missing."
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


def _rationale(ev, prediction, context, P):
    route = prediction["route"]
    if route is None:
        lines = [
            "No route applied: no characterised Swiss-Prot homologue or Pfam domain passed the primary tests, "
            "and no significant structural match came from a reliable 3D model."
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
            lines.append(f"{key.capitalize()} level: no real (live) result, so it was not used.")
    if prediction["score"] is not None:
        total = sum(delta for _, _, delta in prediction["steps"])
        lines.append(
            f"Confidence {prediction['score']:.2f} = sigmoid({total:.2f}): {prediction['band']} "
            f"(high ≥ {P['high']:.2f}, moderate ≥ {P['moderate']:.2f}). Agreement between levels is rewarded less "
            "than contradiction is penalised; the score is a literature-anchored estimate, not a calibrated probability."
        )
    if context is not None and context["go_mf"]:
        lines.append(
            f"GO terms: molecular-function annotations of {context['analysed']} in UniProtKB, read by the "
            "quaternary level (activity terms first)."
        )
    return lines


def _support(level, state):
    if level.status != "completed" or level.result is None:
        return "unavailable"
    if level.result.source == "placeholder":
        return "placeholder"
    return {"supports": "supports", "contradicts": "contradicts"}.get(state, "neutral")


def _integrate(job):
    ev = evidence_from_levels(_level_results(job))
    prediction = predict(ev, PARAMS)
    context = _template_context(ev, prediction)
    missing = [key for key in ("primary", "tertiary") if not ev[key].get("ran")]
    function = prediction["function"]
    if prediction["route"] == "fold":
        function = _brief(function, 110)
    score = prediction["score"]
    return Verdict(
        source="live",
        function=function,
        description=_description(ev, prediction, context, missing),
        confidence_tier=prediction["band"],
        confidence_score=None if score is None else round(min(max(score, 0.0), 1.0), 2),
        go_terms=_go_terms(context),
        level_support=[
            LevelSupport(key=level.key, state=_support(level, prediction["support"].get(level.key, "neutral")))
            for level in job.levels
        ],
        rationale=_rationale(ev, prediction, context, PARAMS),
    )


def _simple_support(level: LevelReport) -> SupportState:
    if level.status != "completed" or level.result is None:
        return "unavailable"
    return "placeholder" if level.result.source == "placeholder" else "neutral"


def _placeholder_verdict(job: AnalysisJob, support: list[LevelSupport]) -> Verdict:
    """Mock mode: the known function of the built-in examples, clearly marked."""
    reported = sum(1 for item in support if item.state != "unavailable")
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
