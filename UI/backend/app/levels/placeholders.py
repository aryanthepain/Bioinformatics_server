"""Placeholder results for all four structural levels.

These stand in for the real analysis modules until they are connected, and
each one mirrors what its notebook actually produces, so the interface
already has the right shape:

  primary     DIAMOND homologues, HMMER/Pfam domains, ESM-2, ProtParam
  secondary   JPred + ProtBert per-residue predictions, PDB comparison
  tertiary    Swiss-Model model, Foldseek matches, ProtParam, model
              geometry and wet-lab recommendations
  quaternary  generic (the module is still being written)

They are deterministic (same sequence → same placeholder), consistent
(every level shares one domain layout and one set of ProtParam values) and
honest (every result is marked source="placeholder").

Each function has the exact signature a real module must have:

    def analyze(sequence: str, ctx: StageContext) -> LevelResult
"""

import hashlib
import random
from dataclasses import dataclass

from ..config import JPRED_MAX_LENGTH, MOCK_DELAY_SCALE, MOCK_FAIL_LEVEL
from ..examples import find_example
from ..jobs import LevelSkipped, StageContext
from ..schemas import (
    EvidenceItem,
    Headline,
    LegendItem,
    LevelKey,
    LevelResult,
    Metric,
    Note,
    Segment,
    Table,
    TableColumn,
    Tone,
    Track,
)

MINUS = "\u2212"  # a true minus sign, for typography

# --- Shared helpers ------------------------------------------------------------


def _rng(sequence: str, purpose: str) -> random.Random:
    """A random generator seeded by the sequence, so results are repeatable."""
    digest = hashlib.sha256(f"{purpose}:{sequence}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _pause(ctx: StageContext, message: str, seconds: float) -> None:
    """Show a progress message, then wait (scaled by PFP_MOCK_DELAY_SCALE)."""
    ctx.report(message)
    ctx.sleep(seconds * MOCK_DELAY_SCALE)


def _maybe_fail(level: LevelKey) -> None:
    if MOCK_FAIL_LEVEL == level:
        raise RuntimeError(f"Simulated failure (PFP_MOCK_FAIL_LEVEL={level}).")


def _evalue(mantissa: float, exponent: int) -> str:
    return f"{mantissa:.1f}e{MINUS}{exponent}"


def _signed(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace("-", MINUS)


def _percentages(counts: dict[str, int], total: int) -> dict[str, int]:
    """Whole-number percentages that always add up to exactly 100."""
    exact = {key: count * 100 / total for key, count in counts.items()}
    rounded = {key: int(value) for key, value in exact.items()}
    shortfall = 100 - sum(rounded.values())
    by_remainder = sorted(exact, key=lambda key: exact[key] - rounded[key], reverse=True)
    for key in by_remainder[:shortfall]:
        rounded[key] += 1
    return rounded


def _merge_runs(runs: list[tuple[Tone, int, int]]) -> list[tuple[Tone, int, int]]:
    """Join neighbouring runs that have the same tone."""
    merged: list[tuple[Tone, int, int]] = []
    for tone, start, end in runs:
        if merged and merged[-1][0] == tone and merged[-1][2] + 1 == start:
            merged[-1] = (tone, merged[-1][1], end)
        else:
            merged.append((tone, start, end))
    return merged


def _domain_regions(sequence: str) -> list[tuple[int, int]]:
    """One or two domain-like regions, shared by every level."""
    length = len(sequence)
    rng = _rng(sequence, "domains")

    def span(low_fraction: float, high_fraction: float) -> tuple[int, int]:
        start = max(1, round(length * low_fraction))
        end = min(length, round(length * high_fraction))
        return (start, max(start, end))

    if length < 300:
        return [span(rng.uniform(0.04, 0.12), rng.uniform(0.86, 0.96))]
    return [
        span(rng.uniform(0.02, 0.06), rng.uniform(0.20, 0.26)),
        span(rng.uniform(0.32, 0.38), rng.uniform(0.82, 0.92)),
    ]


@dataclass(frozen=True)
class _Physicochemical:
    molecular_weight_kda: float
    isoelectric_point: float
    gravy: float
    instability_index: float
    aromaticity: float


def _physicochemical(sequence: str) -> _Physicochemical:
    """One set of ProtParam values, shared by the primary and tertiary levels."""
    rng = _rng(sequence, "physicochemical")
    return _Physicochemical(
        molecular_weight_kda=len(sequence) * rng.uniform(0.108, 0.116),
        isoelectric_point=rng.uniform(4.6, 9.8),
        gravy=rng.uniform(-0.9, 0.15),
        instability_index=rng.uniform(22.0, 55.0),
        aromaticity=rng.uniform(0.06, 0.13),
    )


def _physicochemical_metrics(values: _Physicochemical, include_aromaticity: bool) -> list[Metric]:
    group = "Physicochemical profile · ProtParam"
    metrics = [
        Metric(label="Molecular weight", value=f"{values.molecular_weight_kda:.1f} kDa", group=group),
        Metric(label="Isoelectric point (pI)", value=f"{values.isoelectric_point:.2f}", group=group),
        Metric(
            label="GRAVY",
            value=_signed(values.gravy, 3),
            hint="Grand average of hydropathy. Below 0 means hydrophilic.",
            group=group,
        ),
        Metric(
            label="Instability index",
            value=f"{values.instability_index:.1f}",
            hint="Values below 40 suggest a stable protein.",
            group=group,
        ),
    ]
    if include_aromaticity:
        metrics.append(Metric(label="Aromaticity", value=f"{values.aromaticity:.3f}", group=group))
    return metrics


# --- Primary structure -----------------------------------------------------------


def primary(sequence: str, ctx: StageContext) -> LevelResult:
    rng = _rng(sequence, "primary")

    _pause(ctx, "Searching Swiss-Prot with DIAMOND…", 1.0)
    _maybe_fail("primary")
    _pause(ctx, "Scanning Pfam domains with HMMER…", 1.0)
    _pause(ctx, "Computing the ESM-2 embedding…", 1.0)

    # Homology hits, best first.
    hits: list[tuple[int, float, float, float, int, float]] = []
    identity = rng.uniform(55.0, 98.0)
    exponent = rng.randint(70, 140)
    bits = rng.uniform(300.0, 950.0)
    for rank in range(1, 6):
        coverage = rng.uniform(86.0, 100.0)
        hits.append((rank, identity, coverage, rng.uniform(1.0, 9.9), exponent, bits))
        identity = max(25.0, identity - rng.uniform(2.0, 7.0))
        exponent = max(5, exponent - rng.randint(4, 12))
        bits = max(50.0, bits - rng.uniform(15.0, 60.0))
    _, best_identity, best_coverage, best_mantissa, best_exponent, _ = hits[0]
    best_evalue = _evalue(best_mantissa, best_exponent)

    domains = _domain_regions(sequence)
    names = ["Placeholder domain"] if len(domains) == 1 else ["Placeholder domain A", "Placeholder domain B"]
    domain_evalues = [_evalue(rng.uniform(1.0, 9.9), rng.randint(20, 70)) for _ in domains]
    largest = max(range(len(domains)), key=lambda i: domains[i][1] - domains[i][0])
    domain_word = "domain" if len(domains) == 1 else "domains"

    return LevelResult(
        source="placeholder",
        headline=Headline(value=f"{best_identity:.0f}%", label="best Swiss-Prot hit identity"),
        summary=(
            f"A close Swiss-Prot homologue ({best_identity:.0f}% identity) and {len(domains)} "
            f"Pfam {domain_word} point to a well-characterised protein family."
        ),
        metrics=[
            Metric(label="Best-hit identity", value=f"{best_identity:.1f}%"),
            Metric(label="Query coverage", value=f"{best_coverage:.1f}%"),
            Metric(label="Best-hit E-value", value=best_evalue),
            Metric(label="Pfam domains", value=str(len(domains))),
            *_physicochemical_metrics(_physicochemical(sequence), include_aromaticity=True),
            Metric(label="Model", value="esm2_t6_8M_UR50D", group="Sequence embedding · ESM-2"),
            Metric(label="Dimensions", value="320", group="Sequence embedding · ESM-2"),
        ],
        evidence=[
            EvidenceItem(
                polarity="positive",
                text=(
                    f"DIAMOND: {best_identity:.1f}% identity over {best_coverage:.1f}% of the query "
                    f"(E-value {best_evalue}); contributes 50 of 50 points."
                ),
            ),
            EvidenceItem(
                polarity="positive",
                text=f"HMMER: {len(domains)} Pfam {domain_word} detected; contributes 40 of 40 points.",
            ),
            EvidenceItem(
                polarity="neutral",
                text="ESM-2: a 320-dimensional embedding was extracted for comparison with other proteins.",
            ),
        ],
        tracks=[
            Track(
                key="domains",
                label="Domains",
                caption="Primary · Pfam",
                style="blocks",
                segments=[
                    Segment(start=start, end=end, tone="accent" if index == largest else "ink", label=names[index])
                    for index, (start, end) in enumerate(domains)
                ],
            )
        ],
        tables=[
            Table(
                key="homologues",
                title="Closest Swiss-Prot homologues",
                caption="DIAMOND search against UniProtKB/Swiss-Prot",
                columns=[
                    TableColumn(key="rank", label="#", align="right"),
                    TableColumn(key="entry", label="Entry", mono=True),
                    TableColumn(key="identity", label="Identity", align="right"),
                    TableColumn(key="coverage", label="Coverage", align="right"),
                    TableColumn(key="evalue", label="E-value", align="right", mono=True),
                    TableColumn(key="bits", label="Bit score", align="right"),
                ],
                rows=[
                    {
                        "rank": str(rank),
                        "entry": f"[Swiss-Prot hit {rank}]",
                        "identity": f"{hit_identity:.1f}%",
                        "coverage": f"{hit_coverage:.1f}%",
                        "evalue": _evalue(mantissa, hit_exponent),
                        "bits": f"{hit_bits:.0f}",
                    }
                    for rank, hit_identity, hit_coverage, mantissa, hit_exponent, hit_bits in hits
                ],
            ),
            Table(
                key="pfam-domains",
                title="Pfam domains",
                caption="HMMER search against Pfam-A",
                columns=[
                    TableColumn(key="family", label="Family"),
                    TableColumn(key="accession", label="Accession", mono=True),
                    TableColumn(key="residues", label="Residues", align="right", mono=True),
                    TableColumn(key="evalue", label="E-value", align="right", mono=True),
                ],
                rows=[
                    {
                        "family": names[index],
                        "accession": "[PFxxxxx]",
                        "residues": f"{start}–{end}",
                        "evalue": domain_evalues[index],
                    }
                    for index, (start, end) in enumerate(domains)
                ],
            ),
        ],
    )


# --- Secondary structure ---------------------------------------------------------

_SS_RUN_LENGTHS: dict[str, tuple[int, int]] = {
    "helix": (6, 18),
    "strand": (4, 9),
    "coil": (3, 9),
    "uncertain": (2, 5),
}

_SS_LEGEND = [
    LegendItem(label="Helix", tone="helix"),
    LegendItem(label="Strand", tone="strand"),
    LegendItem(label="Coil", tone="coil"),
]


def _secondary_runs(sequence: str) -> list[tuple[Tone, int, int]]:
    """Consensus: alternating coil and structured runs covering every residue."""
    length = len(sequence)
    rng = _rng(sequence, "secondary-structure")
    runs: list[tuple[Tone, int, int]] = []
    position = 1
    structured_next = False  # proteins usually start with a coil

    while position <= length:
        state: Tone
        if structured_next:
            state = rng.choices(["helix", "strand", "uncertain"], weights=[0.5, 0.35, 0.15])[0]
        else:
            state = "coil"
        low, high = _SS_RUN_LENGTHS[state]
        end = min(length, position + rng.randint(low, high) - 1)
        runs.append((state, position, end))
        position = end + 1
        structured_next = not structured_next

    return _merge_runs(runs)


def _predictor_runs(
    sequence: str, consensus: list[tuple[Tone, int, int]]
) -> tuple[list[tuple[Tone, int, int]], list[tuple[Tone, int, int]]]:
    """JPred and ProtBert agree wherever the consensus is certain, and differ elsewhere."""
    rng = _rng(sequence, "predictors")
    jpred: list[tuple[Tone, int, int]] = []
    protbert: list[tuple[Tone, int, int]] = []
    for state, start, end in consensus:
        if state == "uncertain":
            structured: Tone = "helix" if rng.random() < 0.5 else "strand"
            if rng.random() < 0.5:
                jpred.append((structured, start, end))
                protbert.append(("coil", start, end))
            else:
                jpred.append(("coil", start, end))
                protbert.append((structured, start, end))
        else:
            jpred.append((state, start, end))
            protbert.append((state, start, end))
    return _merge_runs(jpred), _merge_runs(protbert)


def _composition(runs: list[tuple[Tone, int, int]], length: int, states: list[str]) -> dict[str, int]:
    counts = {state: 0 for state in states}
    for state, start, end in runs:
        counts[state] += end - start + 1
    return _percentages(counts, length)


def secondary(sequence: str, ctx: StageContext) -> LevelResult:
    length = len(sequence)
    if length > JPRED_MAX_LENGTH:
        raise LevelSkipped(
            f"JPred accepts at most {JPRED_MAX_LENGTH} residues, so secondary structure "
            f"was not predicted for this {length:,}-residue sequence."
        )

    rng = _rng(sequence, "secondary")

    _pause(ctx, "Submitting the sequence to JPred…", 1.0)
    _maybe_fail("secondary")
    for check in (1, 2, 3):
        _pause(ctx, f"Waiting for JPred results (check {check} of 3)…", 1.0)
    _pause(ctx, "Predicting with ProtBert-BFD-SS3…", 1.0)
    _pause(ctx, "Comparing with experimental structures from the PDB…", 1.0)

    consensus = _secondary_runs(sequence)
    jpred, protbert = _predictor_runs(sequence, consensus)
    shares = _composition(consensus, length, ["helix", "strand", "coil", "uncertain"])
    jpred_shares = _composition(jpred, length, ["helix", "strand", "coil"])
    protbert_shares = _composition(protbert, length, ["helix", "strand", "coil"])
    agreement = 100 - shares["uncertain"]

    if shares["helix"] >= 45 and shares["strand"] < 15:
        profile = "Mainly α-helical"
        profile_note = "Mostly helical proteins include many membrane proteins, globins and coiled coils."
    elif shares["strand"] >= 35 and shares["helix"] < 20:
        profile = "Mainly β-strand"
        profile_note = "Mostly β proteins include immunoglobulin-like domains and β-barrels."
    else:
        profile = "Mixed α/β"
        profile_note = "Mixed α/β profiles are common among enzymes and signalling domains."

    best_agreement = rng.randint(80, 93)
    structure_rows: list[dict[str, str]] = []
    structure_identity = rng.uniform(70.0, 99.0)
    structure_agreement = best_agreement
    for index in range(1, 4):
        aligned = max(1, min(length, round(length * rng.uniform(0.6, 0.98))))
        structure_rows.append(
            {
                "entry": f"[PDB ID {index}]",
                "chain": "A",
                "identity": f"{structure_identity:.1f}%",
                "aligned": str(aligned),
                "agreement": f"{structure_agreement}%",
            }
        )
        structure_identity = max(30.0, structure_identity - rng.uniform(4.0, 15.0))
        structure_agreement = max(50, structure_agreement - rng.randint(1, 6))

    evidence = [
        EvidenceItem(
            polarity="positive" if agreement >= 80 else "neutral",
            text=f"JPred and ProtBert agree on {agreement}% of residues.",
        ),
        EvidenceItem(
            polarity="positive",
            text=(
                "The closest experimentally solved structure matches the consensus at "
                f"{best_agreement}% of comparable residues."
            ),
        ),
    ]
    if shares["uncertain"] >= 15:
        evidence.append(
            EvidenceItem(
                polarity="negative",
                text=f"The predictors disagree on {shares['uncertain']}% of residues; treat those regions with caution.",
            )
        )

    experimental_group = "Experimental comparison · RCSB PDB / PDBe"
    predictor_group = "Individual predictors"

    return LevelResult(
        source="placeholder",
        headline=Headline(value=f"{agreement}%", label="predictor agreement"),
        summary=f"{profile} profile: {shares['helix']}% helix and {shares['strand']}% strand.",
        metrics=[
            Metric(label="α-helix", value=f"{shares['helix']}%"),
            Metric(label="β-strand", value=f"{shares['strand']}%"),
            Metric(label="Coil", value=f"{shares['coil']}%"),
            Metric(label="Predictors disagree", value=f"{shares['uncertain']}%"),
            Metric(label="Structures compared", value=str(len(structure_rows)), group=experimental_group),
            Metric(label="Best agreement", value=f"{best_agreement}%", group=experimental_group),
            Metric(
                label="JPred 4",
                value=f"{jpred_shares['helix']}% helix · {jpred_shares['strand']}% strand",
                group=predictor_group,
            ),
            Metric(
                label="ProtBert-BFD-SS3",
                value=f"{protbert_shares['helix']}% helix · {protbert_shares['strand']}% strand",
                group=predictor_group,
            ),
        ],
        evidence=evidence,
        notes=[Note(kind="observation", title=profile, text=profile_note)],
        tracks=[
            Track(
                key="secondary-structure",
                label="Secondary structure",
                caption="JPred ∩ ProtBert consensus",
                style="states",
                segments=[Segment(start=start, end=end, tone=state) for state, start, end in consensus],
                legend=[*_SS_LEGEND, LegendItem(label="Predictors disagree", tone="uncertain")],
            ),
            Track(
                key="jpred",
                label="JPred 4",
                caption="Secondary · prediction",
                style="states",
                segments=[Segment(start=start, end=end, tone=state) for state, start, end in jpred],
                legend=list(_SS_LEGEND),
                overview=False,
            ),
            Track(
                key="protbert",
                label="ProtBert-BFD-SS3",
                caption="Secondary · prediction",
                style="states",
                segments=[Segment(start=start, end=end, tone=state) for state, start, end in protbert],
                legend=list(_SS_LEGEND),
                overview=False,
            ),
        ],
        tables=[
            Table(
                key="experimental-structures",
                title="Experimentally solved structures",
                caption="RCSB PDB sequence search; secondary structure from PDBe",
                columns=[
                    TableColumn(key="entry", label="PDB entry", mono=True),
                    TableColumn(key="chain", label="Chain"),
                    TableColumn(key="identity", label="Identity", align="right"),
                    TableColumn(key="aligned", label="Aligned residues", align="right"),
                    TableColumn(key="agreement", label="SS agreement", align="right"),
                ],
                rows=structure_rows,
            )
        ],
    )


# --- Tertiary structure ----------------------------------------------------------

# Representative local-QMEAN score (0–1) for each quality band.
_QUALITY_SCORE: dict[str, float] = {
    "confidence-very-high": 0.88,
    "confidence-high": 0.72,
    "confidence-low": 0.52,
    "confidence-very-low": 0.32,
}


def _quality_runs(sequence: str) -> list[tuple[Tone, int, int]]:
    """High model quality inside domains, lower in linkers and at the termini."""
    length = len(sequence)
    runs: list[tuple[Tone, int, int]] = []
    cursor = 1

    for index, (start, end) in enumerate(_domain_regions(sequence)):
        if start > cursor:
            gap = start - cursor
            gap_tone: Tone
            if index == 0 and gap >= 10:
                gap_tone = "confidence-very-low"
            elif gap >= 8:
                gap_tone = "confidence-low"
            else:
                gap_tone = "confidence-high"
            runs.append((gap_tone, cursor, start - 1))

        if end - start + 1 >= 12:
            runs.append(("confidence-high", start, start + 2))
            runs.append(("confidence-very-high", start + 3, end - 3))
            runs.append(("confidence-high", end - 2, end))
        else:
            runs.append(("confidence-very-high", start, end))
        cursor = end + 1

    if cursor <= length:
        tail = length - cursor + 1
        runs.append(("confidence-very-low" if tail >= 10 else "confidence-low", cursor, length))

    return _merge_runs(runs)


def tertiary(sequence: str, ctx: StageContext) -> LevelResult:
    length = len(sequence)
    rng = _rng(sequence, "tertiary")

    _pause(ctx, "Submitting the sequence to Swiss-Model…", 1.0)
    _maybe_fail("tertiary")
    _pause(ctx, "Waiting for the Swiss-Model homology model…", 1.5)
    _pause(ctx, "Searching the PDB and AlphaFold DB with Foldseek…", 1.0)
    _pause(ctx, "Profiling the predicted model…", 0.5)

    # Model quality along the chain (Swiss-Model writes local QMEAN into the B-factor column).
    runs = _quality_runs(sequence)
    counts = {tone: 0 for tone in _QUALITY_SCORE}
    for tone, start, end in runs:
        counts[tone] += end - start + 1
    mean_quality = sum(_QUALITY_SCORE[tone] * count for tone, count in counts.items()) / length
    shares = _percentages(counts, length)
    low_share = shares["confidence-low"] + shares["confidence-very-low"]

    # Foldseek: the top match in each database, aligned over the domain region.
    domains = _domain_regions(sequence)
    matches: list[dict[str, str | float | int]] = []
    for database, name in (("pdb100", "PDB"), ("afdb50", "AlphaFold DB")):
        start = min(length, max(1, domains[0][0] + rng.randint(-3, 3)))
        end = min(length, max(1, domains[-1][1] + rng.randint(-3, 3)))
        if end < start:
            start, end = domains[0][0], domains[-1][1]
        matches.append(
            {
                "database": database,
                "name": name,
                "mantissa": rng.uniform(1.0, 9.9),
                "exponent": rng.randint(12, 45),
                "probability": rng.uniform(0.95, 1.0),
                "identity": rng.uniform(25.0, 95.0),
                "start": start,
                "end": end,
            }
        )

    def match_evalue(match: dict[str, str | float | int]) -> str:
        return _evalue(float(match["mantissa"]), int(match["exponent"]))

    best = min(matches, key=lambda match: float(match["mantissa"]) * 10.0 ** -int(match["exponent"]))
    best_evalue = match_evalue(best)

    # Model geometry, on the scale of the notebook's own output (~7.9 atoms per residue).
    atoms = round(length * rng.uniform(7.6, 8.1))
    size = length ** (1 / 3) * 7.0
    x_span, y_span, z_span = (size * rng.uniform(0.85, 1.15) for _ in range(3))
    dimensions = f"{x_span:.0f} × {y_span:.0f} × {z_span:.0f} Å"

    # Wet-lab recommendations, using exactly the notebook's rules.
    physchem = _physicochemical(sequence)
    if physchem.gravy < 0:
        solubility = (
            "Predicted to be hydrophilic (GRAVY below 0). Standard cytosolic extraction buffers "
            "such as Tris or PBS, without harsh detergents, should work."
        )
    else:
        solubility = (
            "Predicted to be hydrophobic (GRAVY of 0 or above). Consider mild detergents such as "
            "Triton X-100 or CHAPS during lysis."
        )
    if physchem.isoelectric_point < 7.4:
        purification = (
            f"With a pI of {physchem.isoelectric_point:.2f}, the protein is negatively charged at "
            "physiological pH (7.4). Use an anion-exchange column."
        )
    else:
        purification = (
            f"With a pI of {physchem.isoelectric_point:.2f}, the protein is positively charged at "
            "physiological pH (7.4). Use a cation-exchange column."
        )
    assay = (
        f"The predicted fold matches a known structure in the {best['name']} (E-value {best_evalue}). "
        "Review the literature on this fold for known binding partners or activity assays."
    )

    evidence = [
        EvidenceItem(
            polarity="positive",
            text=(
                f"Foldseek ({match['database']}): structural match with E-value {match_evalue(match)} "
                f"and probability {float(match['probability']):.2f}."
            ),
        )
        for match in matches
    ]
    evidence.append(
        EvidenceItem(polarity="neutral", text=f"Model of {atoms:,} atoms, about {dimensions}.")
    )
    if low_share >= 20:
        evidence.append(
            EvidenceItem(polarity="negative", text=f"{low_share}% of residues have low local model quality.")
        )

    physchem_metrics = _physicochemical_metrics(physchem, include_aromaticity=False)
    quality_group = "Model quality · local QMEAN"

    return LevelResult(
        source="placeholder",
        headline=Headline(value=best_evalue, label="best structural-match E-value"),
        summary=(
            "The predicted model matches known folds in both the PDB and AlphaFold DB; "
            f"the strongest match has an E-value of {best_evalue}."
        ),
        metrics=[
            Metric(label="Databases with a match", value=f"{len(matches)} of 2"),
            Metric(label="Model atoms", value=f"{atoms:,}"),
            Metric(label="Model size", value=dimensions),
            Metric(
                label="Mean model quality",
                value=f"{mean_quality:.2f}",
                hint="Average local QMEAN score (0–1) along the chain.",
            ),
            *physchem_metrics,
            Metric(label="High quality (≥ 0.8)", value=f"{shares['confidence-very-high']}% of residues", group=quality_group),
            Metric(label="Low quality (< 0.6)", value=f"{low_share}% of residues", group=quality_group),
        ],
        evidence=evidence,
        notes=[
            Note(kind="recommendation", title="Solubility", text=solubility),
            Note(kind="recommendation", title="Purification", text=purification),
            Note(kind="recommendation", title="Assay design", text=assay),
        ],
        tracks=[
            Track(
                key="model-quality",
                label="Model quality",
                caption="Tertiary · local QMEAN",
                style="states",
                segments=[Segment(start=start, end=end, tone=tone) for tone, start, end in runs],
                legend=[
                    LegendItem(label="QMEAN ≥ 0.8", tone="confidence-very-high"),
                    LegendItem(label="0.6–0.8", tone="confidence-high"),
                    LegendItem(label="0.4–0.6", tone="confidence-low"),
                    LegendItem(label="< 0.4", tone="confidence-very-low"),
                ],
            ),
            *[
                Track(
                    key=f"match-{match['database']}",
                    label=f"{match['name']} match",
                    caption=f"Foldseek · {match['database']}",
                    style="blocks",
                    segments=[
                        Segment(
                            start=int(match["start"]),
                            end=int(match["end"]),
                            tone="accent" if match is best else "ink",
                            label=f"[{match['name']} match]",
                        )
                    ],
                    overview=False,
                )
                for match in matches
            ],
        ],
        tables=[
            Table(
                key="structural-matches",
                title="Structural matches",
                caption="Foldseek search (3Di + amino acids) with the Swiss-Model model",
                columns=[
                    TableColumn(key="database", label="Database", mono=True),
                    TableColumn(key="match", label="Match"),
                    TableColumn(key="evalue", label="E-value", align="right", mono=True),
                    TableColumn(key="probability", label="Probability", align="right"),
                    TableColumn(key="identity", label="Identity", align="right"),
                    TableColumn(key="residues", label="Query residues", align="right", mono=True),
                ],
                rows=[
                    {
                        "database": str(match["database"]),
                        "match": f"[{match['name']} match]",
                        "evalue": match_evalue(match),
                        "probability": f"{float(match['probability']):.2f}",
                        "identity": f"{float(match['identity']):.1f}%",
                        "residues": f"{match['start']}–{match['end']}",
                    }
                    for match in matches
                ],
            )
        ],
    )


# --- Quaternary structure --------------------------------------------------------


def _interface_patches(sequence: str) -> list[tuple[int, int]]:
    """A few short candidate interface patches inside the domains."""
    rng = _rng(sequence, "interfaces")
    patches: list[tuple[int, int]] = []
    for start, end in _domain_regions(sequence):
        domain_length = end - start + 1
        for _ in range(1 if domain_length < 80 else 2):
            size = min(domain_length, rng.randint(5, 12))
            begin = rng.randint(start, end - size + 1)
            patches.append((begin, begin + size - 1))

    patches.sort()
    merged: list[tuple[int, int]] = []
    for start, end in patches:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def quaternary(sequence: str, ctx: StageContext) -> LevelResult:
    _pause(ctx, "Waiting for the quaternary-structure module…", 1.5)
    _maybe_fail("quaternary")

    example = find_example(sequence)
    assembly = example.assembly if example is not None else "Monomer"
    patches = _interface_patches(sequence)
    interface_residues = sum(end - start + 1 for start, end in patches)
    patch_word = "patch" if len(patches) == 1 else "patches"

    return LevelResult(
        source="placeholder",
        headline=Headline(value=assembly, label="predicted assembly"),
        summary=f"{len(patches)} candidate interface {patch_word} on the protein surface.",
        metrics=[
            Metric(label="Interface patches", value=str(len(patches))),
            Metric(label="Interface residues", value=str(interface_residues)),
            Metric(label="Likely partners", value="[partner proteins]", group="Interaction partners"),
        ],
        evidence=[
            EvidenceItem(
                polarity="neutral",
                text=f"{interface_residues} residues fall in candidate interface {patch_word}.",
            ),
        ],
        tracks=[
            Track(
                key="interfaces",
                label="Interface residues",
                caption="Quaternary · predicted",
                style="marks",
                segments=[Segment(start=start, end=end, tone="ink") for start, end in patches],
                legend=[LegendItem(label="Predicted interface", tone="ink")],
            )
        ],
        tables=[
            Table(
                key="interface-patches",
                title="Candidate interface patches",
                caption="Placeholder until the quaternary module is connected",
                columns=[
                    TableColumn(key="patch", label="#", align="right"),
                    TableColumn(key="residues", label="Residues", mono=True),
                    TableColumn(key="length", label="Length", align="right"),
                ],
                rows=[
                    {"patch": str(index), "residues": f"{start}–{end}", "length": str(end - start + 1)}
                    for index, (start, end) in enumerate(patches, start=1)
                ],
            )
        ],
    )
