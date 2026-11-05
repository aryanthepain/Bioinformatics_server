"""Load the machine-learning models when the server starts (PFP_PRELOAD_MODELS=on).

Normally ESM-2 (primary level) and ProtBert (secondary level) are loaded during
the first analysis. On a hosted server it is better to load them at start-up:
the first visitor does not wait for them, and the memory they occupy keeps an
Oracle Cloud Always Free machine from being treated as idle (Oracle reclaims
free machines whose CPU, network and memory use all stay below 20% for a week).

Loading runs in a background thread, so the website is available immediately.
Any problem is only logged: the model then loads during the first analysis, as
it does locally.
"""

import logging
import threading
from collections.abc import Callable

from .config import PRELOAD_MODELS
from .levels import LIVE_LEVELS, primary, secondary

logger = logging.getLogger(__name__)


class _Silent:
    """Stands in for a StageContext: model loading only reports progress."""

    def report(self, message: str) -> None:
        pass


def _load_esm2() -> None:
    primary.get_pipeline(_Silent())  # type: ignore[arg-type]


def _load_protbert() -> None:
    with secondary._protbert_lock:
        if secondary._protbert is None:
            secondary._protbert = secondary._ProtBert()


def _run() -> None:
    models: list[tuple[str, Callable[[], None]]] = []
    if "primary" in LIVE_LEVELS and not primary.missing_setup():
        models.append(("ESM-2", _load_esm2))
    if "secondary" in LIVE_LEVELS and not secondary.missing_setup():
        models.append(("ProtBert-BFD-SS3", _load_protbert))
    for name, load in models:
        try:
            load()
            logger.info("Preloaded the %s model.", name)
        except Exception as error:  # it will load during the first analysis instead
            logger.warning("Could not preload the %s model (%s); it will load during the first analysis.", name, error)


def start() -> None:
    """Start loading the models in the background, if PFP_PRELOAD_MODELS is on."""
    if PRELOAD_MODELS:
        threading.Thread(target=_run, name="model-preload", daemon=True).start()
