"""Registry of the four structural levels, in the order they run.

This is the ONE place where a real analysis module replaces a placeholder.
A module only needs this signature:

    def analyze(sequence: str, ctx: StageContext) -> LevelResult

See docs/LEVEL_CONTRACT.md for details.

Setting PFP_PLACEHOLDER_LEVELS (e.g. "tertiary") forces placeholder data for
those levels even when a real module exists, which is handy for fast
interface work.

The levels run at the same time (see app/runner.py), except that a level
waits for the levels listed in its `after` (tertiary and quaternary analyse the
Swiss-Prot match that the primary level found). The order below is the display order.

A level may also have a background `refine` step that runs after its result is
shown and then replaces it (the primary level's remote EBI BLASTp and
InterProScan, the secondary level's comparison with experimental PDB structures);
`needs_refinement` says whether a result still needs it.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from ..config import LEVEL_NAMES, MOCK_FAIL_LEVEL, PLACEHOLDER_LEVELS
from ..jobs import StageContext
from ..schemas import LevelKey, LevelResult
from . import placeholders, primary, quaternary, secondary, tertiary

logger = logging.getLogger(__name__)

LevelRunner = Callable[[str, StageContext], LevelResult]
LevelRefiner = Callable[[str, LevelResult, StageContext], LevelResult]


@dataclass(frozen=True)
class LevelSpec:
    key: LevelKey
    title: str
    tools: tuple[str, ...]
    run: LevelRunner
    live: bool = False
    # Set for real modules whose results may be cached on disk (see app/cache.py).
    cache_version: str | None = None
    # Levels that must finish before this one starts.
    after: tuple[LevelKey, ...] = ()
    # CPU- and memory-heavy: only one analysis at a time runs this level.
    exclusive: bool = False
    # The results page waits for this level (it carries the predicted function).
    essential: bool = False
    # Usually slow (remote queues): the results page opens without waiting for it.
    background: bool = False
    # Optional background step after the result is shown, and when it is needed.
    refine: LevelRefiner | None = None
    needs_refinement: Callable[[LevelResult], bool] | None = None


def _spec(
    key: LevelKey,
    title: str,
    tools: tuple[str, ...],
    placeholder: LevelRunner,
    live: LevelRunner | None = None,
    cache_version: str | None = None,
    after: tuple[LevelKey, ...] = (),
    exclusive: bool = False,
    essential: bool = False,
    background: bool = False,
    refine: LevelRefiner | None = None,
    needs_refinement: Callable[[LevelResult], bool] | None = None,
) -> LevelSpec:
    flags = {"after": after, "essential": essential, "background": background}
    if live is not None and key not in PLACEHOLDER_LEVELS:
        return LevelSpec(
            key, title, tools, live, live=True, cache_version=cache_version, exclusive=exclusive,
            refine=refine, needs_refinement=needs_refinement, **flags,
        )
    return LevelSpec(key, title, tools, placeholder, **flags)


LEVELS: tuple[LevelSpec, ...] = (
    _spec(
        "primary",
        "Primary structure",
        ("DIAMOND", "HMMER / Pfam", "ESM-2", "ProtParam", "UniProt")
        + (("EBI BLASTp", "InterProScan") if primary.ebi_enabled() else ()),
        placeholders.primary,
        live=primary.analyze,
        cache_version=primary.CACHE_VERSION,
        exclusive=True,  # DIAMOND, HMMER and ESM-2 on the local CPU
        essential=True,
        refine=primary.refine,  # EBI BLASTp and InterProScan, after the local result is shown
        needs_refinement=primary.needs_refinement,
    ),
    _spec(
        "secondary",
        "Secondary structure",
        ("S4PRED", "ESM-2 SS3", "PSIPRED", "GOR IV", "Chou–Fasman", "RCSB PDB / PDBe"),
        placeholders.secondary,
        live=secondary.analyze,
        cache_version=secondary.CACHE_VERSION,
        exclusive=True,  # five predictors on the local CPU, models shared between analyses
        refine=secondary.refine,  # the comparison with experimental PDB structures, after the result is shown
        needs_refinement=secondary.needs_refinement,
    ),
    _spec(
        "tertiary",
        "Tertiary structure",
        ("AlphaFold DB", "Foldseek", "ProtParam", "pydssp", "UniProt"),
        placeholders.tertiary,
        live=tertiary.analyze,
        cache_version=tertiary.CACHE_VERSION,
        after=("primary",),  # analyses the AlphaFold DB structure of the primary level's closest match
        background=True,
    ),
    _spec(
        "quaternary",
        "Quaternary structure",
        ("UniProt", "Complex Portal", "RCSB PDB", "PDBe PISA", "SWISS-MODEL", "IntAct", "AlphaFold DB"),
        placeholders.quaternary,
        live=quaternary.analyze,
        # No cache_version: the pipeline caches its own database answers (see quaternary.py).
        after=("primary",),
    ),
)

# The levels that currently run a real module.
LIVE_LEVELS: tuple[LevelKey, ...] = tuple(spec.key for spec in LEVELS if spec.live)

if MOCK_FAIL_LEVEL is not None and MOCK_FAIL_LEVEL not in LEVEL_NAMES:
    logger.warning(
        "PFP_MOCK_FAIL_LEVEL=%r is not a level name; expected one of %s.",
        MOCK_FAIL_LEVEL,
        ", ".join(LEVEL_NAMES),
    )
