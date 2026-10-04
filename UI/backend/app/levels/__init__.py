"""Registry of the four structural levels, in the order they run.

This is the ONE place where a real analysis module replaces a placeholder.
A module only needs this signature:

    def analyze(sequence: str, ctx: StageContext) -> LevelResult

See docs/LEVEL_CONTRACT.md for details.

Setting PFP_PLACEHOLDER_LEVELS (e.g. "tertiary") forces placeholder data for
those levels even when a real module exists, which is handy for fast
interface work.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from ..config import LEVEL_NAMES, MOCK_FAIL_LEVEL, PLACEHOLDER_LEVELS
from ..jobs import StageContext
from ..schemas import LevelKey, LevelResult
from . import placeholders, primary, tertiary

logger = logging.getLogger(__name__)

LevelRunner = Callable[[str, StageContext], LevelResult]


@dataclass(frozen=True)
class LevelSpec:
    key: LevelKey
    title: str
    tools: tuple[str, ...]
    run: LevelRunner
    live: bool = False
    # Set for real modules whose results may be cached on disk (see app/cache.py).
    cache_version: str | None = None


def _spec(
    key: LevelKey,
    title: str,
    tools: tuple[str, ...],
    placeholder: LevelRunner,
    live: LevelRunner | None = None,
    cache_version: str | None = None,
) -> LevelSpec:
    if live is not None and key not in PLACEHOLDER_LEVELS:
        return LevelSpec(key, title, tools, live, live=True, cache_version=cache_version)
    return LevelSpec(key, title, tools, placeholder)


LEVELS: tuple[LevelSpec, ...] = (
    _spec(
        "primary",
        "Primary structure",
        ("DIAMOND", "HMMER / Pfam", "ESM-2", "ProtParam"),
        placeholders.primary,
        live=primary.analyze,
        cache_version=primary.CACHE_VERSION,
    ),
    _spec(
        "secondary",
        "Secondary structure",
        ("JPred 4", "ProtBert-BFD-SS3", "RCSB PDB / PDBe"),
        placeholders.secondary,
    ),
    _spec(
        "tertiary",
        "Tertiary structure",
        ("Swiss-Model", "Foldseek", "ProtParam"),
        placeholders.tertiary,
        live=tertiary.analyze,
        cache_version=tertiary.CACHE_VERSION,
    ),
    _spec(
        "quaternary",
        "Quaternary structure",
        (),  # filled in when the quaternary module is connected
        placeholders.quaternary,
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
