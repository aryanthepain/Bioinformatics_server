"""A small on-disk cache for slow analysis modules.

Real modules can take many minutes (EBI, Foldseek). Their results are
saved as backend/data/cache/<level>/<version>/<sha256 of sequence>.json, so
analysing the same sequence again is instant, which is ideal for demos.

  * Delete the backend/data/cache folder to clear it.
  * Set PFP_CACHE=off to bypass it.
  * A module's cache version changes whenever its logic changes, so results
    from older code are never reused.

Only live results are cached; placeholders are instant anyway.
"""

import hashlib
import logging
import os
import tempfile
from pathlib import Path

from .config import CACHE_DIR, CACHE_ENABLED
from .schemas import LevelResult

logger = logging.getLogger(__name__)


def _path(level: str, version: str, sequence: str) -> Path:
    digest = hashlib.sha256(sequence.encode("utf-8")).hexdigest()
    return CACHE_DIR / level / version / f"{digest}.json"


def load(level: str, version: str, sequence: str) -> LevelResult | None:
    """Return the cached result, or None if there is none (or it is unreadable)."""
    if not CACHE_ENABLED:
        return None
    path = _path(level, version, sequence)
    if not path.is_file():
        return None
    try:
        return LevelResult.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as error:  # damaged or outdated file: ignore it and recompute
        logger.warning("Ignoring unreadable cache file %s (%s)", path, error.__class__.__name__)
        return None


def store(level: str, version: str, sequence: str, result: LevelResult) -> None:
    """Save a live result. Problems are logged, never raised."""
    if not CACHE_ENABLED or result.source != "live":
        return
    path = _path(level, version, sequence)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file, then rename: a crash never leaves half a file.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            handle.write(result.model_dump_json())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except OSError as error:
        logger.warning("Could not write cache file %s (%s)", path, error)
