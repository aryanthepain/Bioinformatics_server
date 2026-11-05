"""Quaternary structure: the team's quaternary_pipeline package (six stages).

Runs the package behind the team notebook "Quaternary_Structure.ipynb"
(quaternary_pipeline.py and the quaternary/ folder, copied unchanged from the
main branch into UI/backend). Nothing in that package is modified. This module
only decides what the pipeline analyses, runs its six stages one by one so the
interface can show progress and Cancel works, and translates the pipeline's
QuaternaryStructureOutput into the shared LevelResult shape.

What is analysed
  The pipeline is built around UniProt accessions: with an accession it reads
  the curated subunit annotation (UniProtKB), Complex Portal, the protein's PDB
  entries and their PDBe PISA interfaces, SWISS-MODEL Repository templates,
  IntAct and AlphaFold DB. The app only receives a sequence, so this level uses
  the closest Swiss-Prot homologue found by the primary level, provided the
  primary notebook's own homology test passed for it (identity > 30% and query
  coverage >= 80%). Otherwise the pipeline receives the raw sequence, its
  documented path for novel sequences. The interface always says which of the
  two was analysed.

Settings (as in the notebook unless noted)
  * QuaternaryConfig(cache_backend="json", timeout=30.0, offline_mode=False);
    the pipeline's cache lives in backend/data/quaternary_cache (the notebook
    used .quaternary_cache in the working folder) and PFP_CACHE=off turns it off;
  * the stages run in the order of QuaternaryEngine.analyze(), on a session made
    by QuaternaryEngine.create_session(), exactly as analyze_quaternary() does;
  * Stage 5 (predictive multimer) runs with enable_multimer=False, so it only
    proposes hypotheses. No AlphaFold-Multimer runner is connected; and on a
    machine with a CUDA GPU the package's opt-in path returns heuristic
    ipTM/pTM values labelled as an AlphaFold-Multimer run, which must not be
    shown as results.

Plumbing only
  * every stage runs in a helper thread, so Cancel and a time limit
    (PFP_QUATERNARY_TIMEOUT, default 10 minutes) work while a database is slow;
  * the app does not cache this level (backend/data/cache): the pipeline caches
    every successful database answer itself, so repeats are fast, and a query
    that failed is tried again next time instead of being remembered.

Display choices (they never change a result)
  * PISA interface residues are listed in the PDB entry's own numbering rather
    than drawn on the residue map, because that numbering can differ from the
    positions in the submitted sequence;
  * a database query that raised an error is reported as failed (the pipeline's
    audit table records it as "no hit");
  * the curated UniProt subunit text is shown next to the pipeline's call.
"""

import importlib.util
import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from ..config import CACHE_ENABLED, QUATERNARY_CACHE_DIR, QUATERNARY_TIMEOUT_SECONDS
from ..jobs import LevelSkipped, StageContext
from ..schemas import (
    EvidenceItem,
    Headline,
    LevelResult,
    Link,
    Metric,
    Note,
    Polarity,
    Table,
    TableColumn,
)
from .primary import _hit_details

T = TypeVar("T")

# The notebook's QuaternaryConfig(timeout=30.0): seconds allowed per web request.
REQUEST_TIMEOUT_SECONDS = 30.0

MINUS = "−"  # a true minus sign, for typography

# The pipeline's audit names, and the source names its stages use for errors.
_ERROR_SOURCE = {
    "UniProtKB": "uniprot",
    "Complex Portal": "complex_portal",
    "RCSB PDB": "rcsb",
    "PDBe PISA": "pisa",
    "SWISS-MODEL": "swissmodel",
    "IntAct": "intact",
    "AlphaFold DB": "alphafold",
    "AlphaFold-Multimer": "multimer",
}

_SOURCE_LABEL = {
    "uniprot": "UniProtKB",
    "complex_portal": "Complex Portal",
    "rcsb": "RCSB PDB",
    "pisa": "PDBe PISA",
    "swissmodel": "SWISS-MODEL",
    "intact": "IntAct",
    "alphafold": "AlphaFold DB",
    "esmfold": "ESMFold fallback",
    "multimer": "AlphaFold-Multimer",
}

_HIT_NOUN = {
    "UniProtKB": ("entry", "entries"),
    "Complex Portal": ("complex", "complexes"),
    "RCSB PDB": ("PDB entry", "PDB entries"),
    "PDBe PISA": ("interface", "interfaces"),
    "SWISS-MODEL": ("structure", "structures"),
    "IntAct": ("partner", "partners"),
    "AlphaFold DB": ("model", "models"),
    "AlphaFold-Multimer": ("prediction", "predictions"),
}

_OLIGOMER = {
    2: "dimer",
    3: "trimer",
    4: "tetramer",
    5: "pentamer",
    6: "hexamer",
    7: "heptamer",
    8: "octamer",
    9: "nonamer",
    10: "decamer",
    12: "dodecamer",
    14: "tetradecamer",
}


# --- Setup checks ---------------------------------------------------------------


def missing_setup() -> list[str]:
    """What still needs installing before the module can run (empty = ready)."""
    missing: list[str] = []
    if importlib.util.find_spec("quaternary_pipeline") is None or importlib.util.find_spec("quaternary") is None:
        missing.append("the team's quaternary_pipeline package (copy it from the main branch into UI/backend)")
    for module, label in (("pandas", "pandas"), ("pydantic", "pydantic"), ("requests", "requests")):
        if importlib.util.find_spec(module) is None:
            missing.append(label)
    return missing


# --- Which protein the pipeline analyses -------------------------------------------


@dataclass(frozen=True)
class Homologue:
    """The primary level's best Swiss-Prot hit."""

    accession: str
    entry: str
    protein: str
    organism: str
    gene: str
    identity: float
    coverage: float
    passed: bool  # the primary notebook's DIAMOND test (identity > 30% and coverage >= 80%)


def primary_homologue(result: LevelResult | None) -> Homologue | None:
    """The best Swiss-Prot hit in a live primary result, or None if there is none.

    The pass/fail decision is the primary notebook's own: its DIAMOND evidence
    line ("DIAMOND: ...") is positive exactly when both thresholds were met.
    """
    if result is None or result.source != "live" or not isinstance(result.raw, dict):
        return None
    diamond = result.raw.get("diamond")
    if not isinstance(diamond, dict) or str(diamond.get("best_hit", "None")) == "None":
        return None
    details = _hit_details(diamond)
    try:
        identity = float(diamond.get("identity") or 0.0)
        coverage = float(diamond.get("query_coverage") or 0.0)
    except (TypeError, ValueError):
        return None
    passed = any(item.polarity == "positive" and item.text.startswith("DIAMOND:") for item in result.evidence)
    return Homologue(
        accession=details["accession"].strip().upper(),
        entry=details["entry"],
        protein=details["protein"],
        organism=details["organism"],
        gene=details["gene"],
        identity=identity,
        coverage=coverage,
        passed=passed,
    )


@dataclass(frozen=True)
class Target:
    value: str  # a UniProt accession, or the sequence itself
    mode: str  # "homologue" or "sequence"
    reason: str  # one sentence for the interface


def choose_target(sequence: str, primary_result: LevelResult | None) -> tuple[Target, Homologue | None]:
    """The homologue's accession when the primary test passed, otherwise the sequence."""
    from quaternary.clients import UniProtClient  # the pipeline's own accession check

    homologue = primary_homologue(primary_result)
    if homologue is not None and homologue.passed and UniProtClient.is_valid_accession(homologue.accession):
        reason = (
            f"The closest Swiss-Prot homologue, {homologue.accession} "
            f"({homologue.identity:.2f}% identity over {homologue.coverage:.2f}% of the sequence), was analysed."
        )
        return Target(value=homologue.accession, mode="homologue", reason=reason), homologue

    if homologue is not None and homologue.passed:
        reason = f"The primary level's best hit ({homologue.entry}) has no valid UniProt accession"
    elif homologue is not None:
        reason = (
            f"The best Swiss-Prot hit ({homologue.entry}, {homologue.identity:.2f}% identity, "
            f"{homologue.coverage:.2f}% coverage) did not pass the primary thresholds (identity > 30% and "
            "coverage ≥ 80%)"
        )
    elif primary_result is None:
        reason = "The primary level did not finish (it failed, was skipped or was cancelled)"
    elif primary_result.source != "live":
        reason = "The primary level returned placeholder data"
    else:
        reason = "The primary level found no Swiss-Prot hit"
    reason += ", so the pipeline analysed the sequence itself."
    return Target(value=sequence, mode="sequence", reason=reason), homologue


# --- Running the pipeline ------------------------------------------------------------


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _bounded(call: Callable[[], T], ctx: StageContext, deadline: float, message: str) -> T:
    """Run one pipeline stage in a helper thread, so Cancel and the time limit still work.

    A stage that is stuck in a slow web request is abandoned (the thread ends
    on its own once the request times out) instead of holding up the analysis.
    """
    outcome: dict[str, Any] = {}

    def target() -> None:
        try:
            outcome["value"] = call()
        except BaseException as error:  # handed back to the caller below
            outcome["error"] = error

    worker = threading.Thread(target=target, name="quaternary-stage", daemon=True)
    started = time.monotonic()
    last_report = started
    worker.start()
    while True:
        worker.join(timeout=0.5)
        if not worker.is_alive():
            break
        ctx.check_cancelled()
        now = time.monotonic()
        if now > deadline:
            raise TimeoutError(
                f"The quaternary pipeline did not finish within {QUATERNARY_TIMEOUT_SECONDS / 60:.0f} minutes "
                f"({message.rstrip('…')})."
            )
        if now - last_report >= 2.0:
            ctx.report(f"{message} · {_clock(now - started)}")
            last_report = now
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def run_pipeline(target: str, ctx: StageContext, offline: bool = False) -> tuple[Any, Any]:
    """Run the pipeline's six stages on an accession or a sequence.

    Returns (QuaternaryStructureOutput, the session with its stage results).
    offline=True uses the package's bundled test data instead of the internet
    (only scripts/check_quaternary.py --offline does this).
    """
    from quaternary.config import QuaternaryConfig
    from quaternary.engine import QuaternaryEngine

    config = QuaternaryConfig(
        cache_enabled=CACHE_ENABLED and not offline,
        cache_backend="json",
        cache_dir=QUATERNARY_CACHE_DIR,
        timeout=REQUEST_TIMEOUT_SECONDS,
        offline_mode=offline,
    )
    engine = QuaternaryEngine(config)
    session = engine.create_session(target)

    # The order of QuaternaryEngine.analyze(); Stage 5 without the multimer opt-in.
    stages: list[tuple[str, Callable[[], Any]]] = [
        (
            "Stage 1 of 6 · UniProtKB subunit annotation and Complex Portal…",
            session.run_stage_1_sequence_and_accession,
        ),
        ("Stage 2 of 6 · experimental assemblies in the RCSB PDB…", session.run_stage_2_experimental_assemblies),
        ("Stage 3 of 6 · interface thermodynamics from PDBe PISA…", session.run_stage_3_thermodynamic_qualification),
        (
            "Stage 4 of 6 · SWISS-MODEL templates, IntAct partners, AlphaFold DB…",
            session.run_stage_4_homology_and_partners,
        ),
        (
            "Stage 5 of 6 · multimer hypotheses (AlphaFold-Multimer is not run)…",
            lambda: session.run_stage_5_predictive_multimer(enable_multimer=False, hypothesis=None),
        ),
        ("Stage 6 of 6 · synthesis and functional inference…", session.run_stage_6_synthesis),
    ]
    deadline = time.monotonic() + QUATERNARY_TIMEOUT_SECONDS
    output = None
    for message, stage in stages:
        ctx.report(message)
        output = _bounded(stage, ctx, deadline, message)
    if output is None:
        raise RuntimeError("The quaternary pipeline finished without a result.")
    return output, session


# --- Small display helpers --------------------------------------------------------------


def _value(item: Any) -> str:
    """An enum's value, or the item itself, as text."""
    return str(getattr(item, "value", item))


def _brief(text: str, limit: int = 220) -> str:
    collapsed = " ".join(str(text).split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _number(value: Any) -> float | None:
    """A finite number, or None (for missing values, text, NaN and infinity)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _signed(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace("-", MINUS)


def _plural(count: int, nouns: tuple[str, str]) -> str:
    return f"{count} {nouns[0] if count == 1 else nouns[1]}"


def assembly_name(assembly_type: str, subunits: int) -> str:
    """'Monomer', 'Homotetramer', 'Heterotetramer', 'Homo-24-mer' or 'Uncharacterized'."""
    if assembly_type == "MONOMER":
        return "Monomer"
    if assembly_type in ("HOMOMER", "HETEROMER"):
        prefix = "Homo" if assembly_type == "HOMOMER" else "Hetero"
        word = _OLIGOMER.get(subunits)
        return f"{prefix}{word}" if word else f"{prefix}-{subunits}-mer"
    return "Uncharacterized"


def _residue_ranges(residues: list[int], limit: int = 10) -> str:
    """[27, 28, 29, 40] -> '27–29, 40' (at most `limit` ranges, then a count)."""
    numbers = sorted({int(residue) for residue in residues})
    if not numbers:
        return "—"
    ranges: list[tuple[int, int]] = []
    for number in numbers:
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], number)
        else:
            ranges.append((number, number))
    shown = [f"{start}–{end}" if start != end else str(start) for start, end in ranges[:limit]]
    if len(ranges) > limit:
        shown.append(f"… (+{len(ranges) - limit} more)")
    return ", ".join(shown)


def _stage_errors(session: Any) -> dict[str, list[str]]:
    """Errors recorded by the pipeline's stages, by source (e.g. 'uniprot')."""
    errors: dict[str, list[str]] = {}
    for number in sorted(session.stages):
        provenance = session.stages[number].provenance or {}
        for entry in provenance.get("errors", []) or []:
            if isinstance(entry, dict):
                source = str(entry.get("source", "unknown"))
                errors.setdefault(source, []).append(_brief(str(entry.get("error", "")), 160))
    return errors


def _stage_data(session: Any, number: int) -> dict[str, Any]:
    stage = session.stages.get(number)
    data = getattr(stage, "data", None)
    return data if isinstance(data, dict) else {}


# --- Translating the results for the interface --------------------------------------------


def _to_level_result(
    sequence: str,
    target: Target,
    homologue: Homologue | None,
    output: Any,
    session: Any,
) -> LevelResult:
    accession = target.value if target.mode == "homologue" else None
    uniprot = _stage_data(session, 1).get("uniprot") or {}
    stage2 = _stage_data(session, 2)
    stage3 = _stage_data(session, 3)
    stage4 = _stage_data(session, 4)
    errors = _stage_errors(session)

    self_assembly = output.target_self_assembly
    stoichiometry = output.stoichiometry
    formula = str((self_assembly.formula if self_assembly else stoichiometry.formula) or "UNCHARACTERIZED")
    assembly_type = _value(self_assembly.assembly_type if self_assembly else stoichiometry.assembly_type)
    subunits = int((self_assembly.subunit_count if self_assembly else stoichiometry.total_subunits) or 1)
    symmetry = (self_assembly.symmetry if self_assembly else stoichiometry.symmetry) or None
    status = _value(self_assembly.confidence_status if self_assembly else output.status)
    name = assembly_name(assembly_type, subunits)
    characterized = name != "Uncharacterized"

    pisa = stage3.get("pisa_validation") or {}
    pisa_pdb = str(stage3.get("evaluated_pdb_id") or pisa.get("pdb_id") or "").upper()
    # The PISA client answers a missing entry with placeholder values and status "unknown".
    pisa_found = bool(pisa) and not (str(pisa.get("status", "")).lower() == "unknown" and not pisa.get("interfaces"))
    pisa_state = str(stage3.get("pisa_thermodynamic_state") or "UNKNOWN")
    delta_g = _number(pisa.get("dissociation_energy_kcal_mol")) if pisa_found else None
    total_bsa = _number(stage3.get("total_buried_surface_area_angstrom2")) if pisa_found else None
    interfaces = list(output.interfaces)
    complexes = list(output.functional_complexes)
    provenance = output.confidence_provenance
    swiss = provenance.swissmodel if provenance else None
    alphafold = provenance.alphafold_db if provenance else None
    inferred = output.inferred_function
    candidates = [row for row in stage2.get("candidate_scoring", []) or [] if isinstance(row, dict)]
    models = [row for row in stage4.get("homology_models", []) or [] if isinstance(row, dict)]
    subunit_text = str(uniprot.get("subunit_text") or "")
    has_subunit_text = bool(subunit_text) and subunit_text != "No subunit annotation found."

    # --- Headline and summary
    headline_value = f"{name} ({formula})" if characterized else name
    headline_label = f"quaternary assembly of {accession}" if accession else "quaternary assembly"

    if characterized:
        article = "an" if name[0] in "AEIOU" else "a"
        finding = f"forms {article} {name.lower()} ({formula}); evidence status: {status.lower()}"
    else:
        finding = f"has no characterised quaternary structure (evidence status: {status.lower()})"
    if homologue is not None and target.mode == "homologue":
        described = homologue.protein or homologue.entry
        summary = (
            f"{described} ({accession}), the closest Swiss-Prot homologue ({homologue.identity:.2f}% identity "
            f"over {homologue.coverage:.2f}% of the sequence), {finding}."
        )
    else:
        summary = f"{target.reason} The sequence {finding}."
    if complexes:
        first = complexes[0]
        portal = f"Complex Portal {first.complex_portal_id}" if first.complex_portal_id else "Complex Portal"
        summary += f" It is part of the {first.name} ({portal})."

    # --- Key figures (up to four)
    metrics: list[Metric] = [
        Metric(
            label="Evidence status",
            value=status,
            hint=(
                "The pipeline's tier: CONFIRMED = a PISA-stable experimental assembly; SUPPORTED = PDB entries "
                "or homology templates; PREDICTED = weaker evidence; INSUFFICIENT EVIDENCE = nothing found."
            ),
        ),
        Metric(
            label="ΔG dissociation (PISA)",
            value=f"{_signed(delta_g, 2)} kcal/mol" if delta_g is not None else "—",
            hint="Free energy needed to pull the assembly apart; positive values mean a stable assembly.",
        ),
        Metric(
            label="Buried surface area",
            value=f"{total_bsa:,.0f} Å²" if total_bsa else "—",
            hint="Surface buried between the subunits of the PISA assembly.",
        ),
        Metric(label="Analysed", value=accession or "Sequence only"),
    ]

    analysed_group = "Analysed protein · UniProtKB"
    if homologue is not None and target.mode == "homologue":
        metrics += [
            Metric(label="UniProt accession", value=homologue.accession, group=analysed_group),
            Metric(label="Entry", value=homologue.entry, group=analysed_group),
            Metric(label="Protein", value=homologue.protein or "—", group=analysed_group),
            Metric(
                label="Organism",
                value=homologue.organism or str(uniprot.get("organism") or "—"),
                group=analysed_group,
            ),
            Metric(label="Identity to the query", value=f"{homologue.identity:.2f}%", group=analysed_group),
            Metric(label="Coverage of the query", value=f"{homologue.coverage:.2f}%", group=analysed_group),
        ]
    else:
        metrics.append(Metric(label="Input", value=f"Raw sequence ({len(sequence)} residues)", group=analysed_group))

    call_group = "Assembly · pipeline call"
    metrics += [
        Metric(label="Stoichiometry", value=formula, group=call_group),
        Metric(label="Subunits", value=str(subunits) if characterized else "—", group=call_group),
        Metric(label="Assembly type", value=assembly_type, group=call_group),
        Metric(label="Symmetry", value=str(symmetry) if symmetry else "—", group=call_group),
    ]

    pisa_group = f"Interface thermodynamics · PDBe PISA{f' · {pisa_pdb}' if pisa_pdb else ''}"
    if pisa_found:
        metrics += [
            Metric(label="PDB entry", value=f"{pisa_pdb} (assembly {pisa.get('assembly_id', '1')})", group=pisa_group),
            Metric(label="Thermodynamic state", value=pisa_state, group=pisa_group),
            Metric(label="Chains in assembly", value=str(pisa.get("macromolecular_size", "—")), group=pisa_group),
            Metric(label="Composition", value=str(pisa.get("composition") or "—"), group=pisa_group),
            Metric(label="Interfaces", value=str(len(interfaces)), group=pisa_group),
        ]
    else:
        metrics.append(
            Metric(
                label="PISA data",
                value=f"none for {pisa_pdb}" if pisa_pdb else "no PDB entry to analyse",
                group=pisa_group,
            )
        )

    swiss_group = "Homology models · SWISS-MODEL Repository"
    gmqe = _number(getattr(swiss, "gmqe", None))
    qsqe = _number(getattr(swiss, "qmqe", None))
    template_coverage = _number(getattr(swiss, "coverage", None))
    metrics += [
        Metric(label="Structures listed", value=str(len(models)), group=swiss_group),
        Metric(
            label="Best GMQE",
            value=f"{gmqe:.3f}" if gmqe else "—",
            hint="Global model quality estimate (0–1).",
            group=swiss_group,
        ),
        Metric(
            label="Best QSQE",
            value=f"{qsqe:.3f}" if qsqe else "not reported",
            hint="Quaternary structure quality estimate (0–1) of the template interface.",
            group=swiss_group,
        ),
        Metric(
            label="Template coverage",
            value=f"{100 * template_coverage:.1f}%" if template_coverage else "—",
            group=swiss_group,
        ),
    ]

    plddt = _number(getattr(alphafold, "global_plddt", None))
    metrics.append(
        Metric(
            label="Mean pLDDT",
            value=f"{plddt:.2f}" if plddt is not None else "—",
            hint="Confidence of the single-chain AlphaFold model; it says nothing about the assembly.",
            group="Monomer fold · AlphaFold DB",
        )
    )

    if inferred is not None:
        inference_group = "Functional inference · quaternary pipeline"
        metrics += [
            Metric(label="Molecular function", value=str(inferred.molecular_function), group=inference_group),
            Metric(label="Biological process", value=str(inferred.biological_process), group=inference_group),
            Metric(label="Archetype", value=str(inferred.archetype_name or "none matched"), group=inference_group),
            Metric(
                label="Pipeline confidence",
                value=f"{float(inferred.confidence):.2f} ({_value(inferred.status)})",
                hint="The pipeline's own score for its functional inference.",
                group=inference_group,
            ),
        ]

    run_group = "Pipeline run"
    metrics += [
        Metric(
            label="Stages succeeded",
            value=", ".join(str(number) for number in output.stages_completed) or "—",
            hint="Stage 6 always completes; stages without data count as unsuccessful.",
            group=run_group,
        ),
        Metric(label="AlphaFold-Multimer", value="not run (no GPU runner connected)", group=run_group),
    ]

    # --- Evidence: the pipeline's database audit, with failed queries marked as such
    evidence: list[EvidenceItem] = []
    records = list(output.evidence_coverage.records) if output.evidence_coverage else []
    for record in records:
        database = str(record.database)
        state = _value(record.query_status)
        failures = errors.get(_ERROR_SOURCE.get(database, ""), [])
        nouns = _HIT_NOUN.get(database, ("hit", "hits"))
        polarity: Polarity
        if failures:
            polarity, text = "neutral", f"{database}: query failed ({failures[0]})."
        elif state == "QUERY_SUCCESS_WITH_HIT":
            polarity = "positive"
            text = f"{database}: {_plural(int(record.hit_count), nouns)}. {record.rationale or ''}".strip()
        elif state == "QUERY_SUCCESS_NO_HIT":
            polarity, text = "neutral", f"{database}: nothing found. {record.rationale or ''}".strip()
        elif state == "PREDICTION_NOT_EXECUTED":
            polarity, text = "neutral", f"{database}: not run (no GPU runner connected)."
        else:
            polarity, text = "neutral", f"{database}: {state.replace('_', ' ').lower()}."
        evidence.append(EvidenceItem(polarity=polarity, text=text))
    if pisa_found and delta_g is not None:
        if pisa_state == "STABLE":
            evidence.append(
                EvidenceItem(
                    polarity="positive",
                    text=(
                        f"PDBe PISA: the assembly of PDB {pisa_pdb} is stable "
                        f"(ΔG dissociation {_signed(delta_g, 2)} kcal/mol)."
                    ),
                )
            )
        elif pisa_state == "DISSOCIATED":
            evidence.append(
                EvidenceItem(
                    polarity="negative",
                    text=(
                        f"PDBe PISA: the assembly of PDB {pisa_pdb} is not stable (ΔG dissociation "
                        f"{_signed(delta_g, 2)} kcal/mol); it may be a crystal-packing artefact."
                    ),
                )
            )
    for conflict in output.conflicts:
        evidence.append(
            EvidenceItem(
                polarity="negative",
                text=(
                    f"Conflict: {conflict.source_a} ({conflict.stoichiometry_a}) vs {conflict.source_b} "
                    f"({conflict.stoichiometry_b}). {_brief(conflict.rationale, 200)}"
                ),
            )
        )

    # --- Notes
    notes: list[Note] = []
    if homologue is not None and target.mode == "homologue":
        notes.append(
            Note(
                kind="caution",
                title=f"These results describe {accession}",
                text=(
                    f"The pipeline looked up {accession} ({homologue.protein or homologue.entry}"
                    f"{', ' + homologue.organism if homologue.organism else ''}), the closest Swiss-Prot entry to the "
                    f"submitted sequence ({homologue.identity:.2f}% identity). Close homologues usually share their "
                    "oligomeric state, but this becomes less certain as sequence identity falls, so treat the "
                    "assembly as a prediction for the submitted protein."
                ),
            )
        )
    else:
        notes.append(
            Note(
                kind="caution",
                title="Analysed without a homologue",
                text=(
                    f"{target.reason} Lookups that need a UniProt accession (UniProtKB, Complex Portal, "
                    "SWISS-MODEL Repository, IntAct, AlphaFold DB) were therefore not possible."
                ),
            )
        )
    if has_subunit_text:
        entry_label = str(uniprot.get("accession") or accession or "").strip()
        source = f"UniProtKB {entry_label}" if entry_label else "UniProtKB"
        title = f"Curated subunit annotation ({source})"
        notes.append(Note(kind="observation", title=title, text=_brief(subunit_text, 500)))
    if inferred is not None:
        mechanism = str(inferred.oligomeric_mechanism_hypothesis or "").strip()
        text = f"{inferred.molecular_function} ({inferred.biological_process})."
        if mechanism:
            text += f" {mechanism.rstrip('.')}."
        if inferred.archetype_name:
            text += f" Archetype: {inferred.archetype_name}."
        notes.append(Note(kind="observation", title="Functional inference by the pipeline", text=text))
    if interfaces:
        notes.append(
            Note(
                kind="caution",
                title="Interface residues use PDB numbering",
                text=(
                    "The residue numbers in the interface table come from PDB entry "
                    f"{pisa_pdb or 'the evaluated entry'} "
                    "(its own chains and numbering), which can differ from positions in the submitted sequence, "
                    "so they are listed rather than drawn on the residue map."
                ),
            )
        )
    experimental_conflict = output.experimental_conflict
    if (
        experimental_conflict is not None
        and experimental_conflict.conflict_detected
        and experimental_conflict.conflict_rationale
    ):
        conflict_text = _brief(experimental_conflict.conflict_rationale, 400)
        notes.append(Note(kind="caution", title="Conflicting assembly evidence", text=conflict_text))
    if errors:
        listed = "; ".join(f"{_SOURCE_LABEL.get(source, source)}: {messages[0]}" for source, messages in errors.items())
        notes.append(Note(kind="caution", title="Some database queries failed", text=_brief(listed, 450)))

    # --- Tables
    tables: list[Table] = []
    if candidates:
        evaluated = str(stage2.get("evaluated_pdb_id") or "").upper()

        def resolution(row: dict[str, Any]) -> str:
            value = _number(row.get("resolution"))
            return f"{value:.2f} Å" if value else "—"

        def score(row: dict[str, Any]) -> str:
            value = _number(row.get("assembly_score"))
            return f"{value:.1f} / 9" if value is not None else "—"

        tables.append(
            Table(
                key="experimental-assemblies",
                title="Experimental structures (RCSB PDB)",
                caption=(
                    "PDB entries from the UniProt record (first six), ranked by the pipeline's assembly score "
                    "(coverage + resolution + assembly weights, out of 9); the top entry is analysed with PISA."
                ),
                columns=[
                    TableColumn(key="entry", label="PDB entry", mono=True),
                    TableColumn(key="method", label="Method"),
                    TableColumn(key="resolution", label="Resolution", align="right"),
                    TableColumn(key="score", label="Score", align="right"),
                    TableColumn(key="pisa", label="PISA", align="right"),
                ],
                rows=[
                    {
                        "entry": str(row.get("pdb_id", "—")),
                        "method": str(row.get("method") or "—"),
                        "resolution": resolution(row),
                        "score": score(row),
                        "pisa": "analysed" if str(row.get("pdb_id", "")).upper() == evaluated else "—",
                    }
                    for row in candidates
                ],
            )
        )
    if interfaces:
        largest = sorted(interfaces, key=lambda item: -(_number(item.buried_surface_area_angstrom2) or 0.0))
        shown = largest[:20]
        caption = f"Pairwise interfaces of PDB {pisa_pdb} (PDBe PISA); residues of the first chain, in PDB numbering"
        if len(largest) > len(shown):
            caption += f"; the {len(shown)} largest of {len(largest)}"
        tables.append(
            Table(
                key="pisa-interfaces",
                title="Interfaces (PDBe PISA)",
                caption=caption,
                columns=[
                    TableColumn(key="chains", label="Chains", mono=True),
                    TableColumn(key="area", label="Buried area", align="right"),
                    TableColumn(key="energy", label="ΔiG", align="right"),
                    TableColumn(key="hbonds", label="H-bonds", align="right"),
                    TableColumn(key="salt", label="Salt bridges", align="right"),
                    TableColumn(key="residues", label="Interface residues (chain 1)", mono=True),
                ],
                rows=[
                    {
                        "chains": f"{item.chain_1} – {item.chain_2}",
                        "area": f"{(_number(item.buried_surface_area_angstrom2) or 0.0):,.1f} Å²",
                        "energy": (
                            f"{_signed(item.solvation_free_energy_kcal_mol, 2)} kcal/mol"
                            if _number(item.solvation_free_energy_kcal_mol) is not None
                            else "—"
                        ),
                        "hbonds": str(item.hydrogen_bonds_count),
                        "salt": str(item.salt_bridges_count),
                        "residues": _residue_ranges(list(item.interface_residues_chain_1)),
                    }
                    for item in shown
                ],
            )
        )
    if complexes:
        rows = []
        for item in complexes:
            partners = []
            for index, partner in enumerate(item.partner_uniprot_accessions):
                partner_name = item.partner_names[index] if index < len(item.partner_names) else ""
                partners.append(f"{partner} ({partner_name})" if partner_name else str(partner))
            rows.append(
                {
                    "name": str(item.name),
                    "identifier": str(item.complex_portal_id or "—"),
                    "stoichiometry": str(item.stoichiometry or "—"),
                    "partners": ", ".join(partners) or "—",
                }
            )
        tables.append(
            Table(
                key="functional-complexes",
                title="Functional complexes (Complex Portal)",
                caption="Curated complexes that contain the analysed protein, with their other components",
                columns=[
                    TableColumn(key="name", label="Complex"),
                    TableColumn(key="identifier", label="ID", mono=True),
                    TableColumn(key="stoichiometry", label="Stoichiometry", mono=True),
                    TableColumn(key="partners", label="Other components"),
                ],
                rows=rows,
            )
        )
    if records:
        audit_rows = []
        for record in records:
            database = str(record.database)
            failures = errors.get(_ERROR_SOURCE.get(database, ""), [])
            state = "query failed" if failures else _value(record.query_status).replace("_", " ").lower()
            audit_rows.append(
                {
                    "database": database,
                    "status": state,
                    "hits": str(record.hit_count),
                    "note": failures[0] if failures else str(record.rationale or "—"),
                }
            )
        tables.append(
            Table(
                key="database-coverage",
                title="Databases queried",
                caption="The pipeline's evidence audit; queries that raised an error are shown as failed",
                columns=[
                    TableColumn(key="database", label="Database"),
                    TableColumn(key="status", label="Status"),
                    TableColumn(key="hits", label="Hits", align="right"),
                    TableColumn(key="note", label="Note"),
                ],
                rows=audit_rows,
            )
        )

    # --- Links (each URL once)
    links: list[Link] = []
    seen: set[str] = set()

    def add_link(label: str, url: str) -> None:
        if url not in seen:
            seen.add(url)
            links.append(Link(label=label, url=url))

    if accession:
        add_link(f"UniProt {accession}", f"https://www.uniprot.org/uniprotkb/{accession}/entry")
    if pisa_pdb and re.fullmatch(r"[0-9][A-Z0-9]{3}", pisa_pdb):
        add_link(f"PDB {pisa_pdb}", f"https://www.rcsb.org/structure/{pisa_pdb}")
        add_link(f"PDBe {pisa_pdb}", f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pisa_pdb.lower()}")
    for item in complexes:
        if item.complex_portal_id and re.fullmatch(r"CPX-\d+", str(item.complex_portal_id)):
            identifier = str(item.complex_portal_id)
            add_link(f"Complex Portal {identifier}", f"https://www.ebi.ac.uk/complexportal/complex/{identifier}")
    if accession and models:
        add_link(f"SWISS-MODEL Repository {accession}", f"https://swissmodel.expasy.org/repository/uniprot/{accession}")
    if accession and plddt is not None:
        add_link(f"AlphaFold DB {accession}", f"https://alphafold.ebi.ac.uk/entry/{accession}")

    # --- Raw output: the pipeline's QuaternaryStructureOutput, plus how it was run
    raw: dict[str, Any] = {
        "analysed_target": target.value,
        "input": target.mode,
        "input_reason": target.reason,
        "homologue": (
            {
                "accession": homologue.accession,
                "entry": homologue.entry,
                "protein": homologue.protein,
                "organism": homologue.organism,
                "identity_percent": homologue.identity,
                "query_coverage_percent": homologue.coverage,
                "passed_primary_thresholds": homologue.passed,
            }
            if homologue is not None
            else None
        ),
        "uniprot": (
            {
                "accession": str(uniprot.get("accession", "")),
                "gene_name": uniprot.get("gene_name"),
                "organism": uniprot.get("organism"),
                "subunit_text": subunit_text,
                "go_terms": [
                    {"id": str(term.get("id", "")), "name": str(term.get("name", ""))}
                    for term in uniprot.get("go_terms", []) or []
                    if isinstance(term, dict)
                ],
            }
            if uniprot
            else None
        ),
        "stages": [
            {
                "number": number,
                "name": session.stages[number].stage_name,
                "status": _value(session.stages[number].status),
                "errors": [
                    {"source": str(entry.get("source", "")), "error": str(entry.get("error", ""))}
                    for entry in (session.stages[number].provenance or {}).get("errors", []) or []
                    if isinstance(entry, dict)
                ],
            }
            for number in sorted(session.stages)
        ],
        "pipeline_output": output.model_dump(mode="json"),
    }

    return LevelResult(
        source="live",
        headline=Headline(value=headline_value, label=headline_label),
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=[],
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )


# --- The entry point used by the app ----------------------------------------------------------


def analyze_target(
    sequence: str,
    target: Target,
    homologue: Homologue | None,
    ctx: StageContext,
    offline: bool = False,
) -> LevelResult:
    """Run the pipeline on the chosen target and translate its result.

    Shared by analyze() below and scripts/check_quaternary.py.
    """
    output, session = run_pipeline(target.value, ctx, offline=offline)

    # Every other lookup starts from the UniProt entry: if it could not be read
    # (e.g. no internet), "uncharacterized" would be misleading, so the level fails.
    uniprot_errors = _stage_errors(session).get("uniprot", [])
    if target.mode == "homologue" and uniprot_errors:
        raise RuntimeError(f"Could not read the UniProt entry {target.value} ({uniprot_errors[0]}).")
    return _to_level_result(sequence, target, homologue, output, session)


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Run the team's quaternary pipeline and return the result for the interface.

    Needs the primary level to run first (the registry order guarantees it).
    """
    missing = missing_setup()
    if missing:
        raise LevelSkipped(
            "Quaternary-structure analysis is not set up yet (missing: "
            + ", ".join(missing)
            + "). See the README, then restart the backend."
        )
    target, homologue = choose_target(sequence, ctx.level_result("primary"))
    ctx.report(f"Analysing {target.value if target.mode == 'homologue' else 'the sequence itself'}…")
    return analyze_target(sequence, target, homologue, ctx)
