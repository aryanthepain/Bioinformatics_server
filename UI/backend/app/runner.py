"""Runs analysis jobs in the background.

How a job runs:
  1. It waits for a free slot (only MAX_CONCURRENT_JOBS run at once).
  2. Each structural level runs in a worker thread, so slow or blocking
     code (model inference, waiting for JPred) never freezes the server.
  3. A level that fails is marked "failed" and the job carries on with
     the remaining levels; a level that cannot run is marked "skipped".
  4. The integration step combines whatever results exist into a verdict.

Results of slow real modules are cached on disk (app/cache.py), so analysing
the same sequence again skips the wait.
"""

import asyncio
import logging

from . import cache
from .config import MAX_CONCURRENT_JOBS, MOCK_DELAY_SCALE
from .jobs import AnalysisCancelled, LevelSkipped, StageContext, store
from .levels import LEVELS
from .verdict import build_verdict

logger = logging.getLogger(__name__)

# Short pause before the verdict appears, so the final step is visible in the
# placeholder demo. Scaled by PFP_MOCK_DELAY_SCALE; remove once real modules
# are connected.
_INTEGRATION_PAUSE_SECONDS = 0.6

_slots: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task[None]] = set()


def _get_slots() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    return _slots


def _describe(error: BaseException) -> str:
    text = str(error).strip() or error.__class__.__name__
    return text if len(text) <= 300 else text[:297] + "..."


def startup() -> None:
    """Called when the server starts (inside its event loop)."""
    global _slots
    _slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)


async def shutdown() -> None:
    """Called when the server stops: ask running jobs to stop, then wait briefly."""
    store.cancel_all()
    pending = [task for task in _tasks if not task.done()]
    if not pending:
        return
    _, still_running = await asyncio.wait(pending, timeout=5)
    for task in still_running:
        task.cancel()


def schedule(job_id: str) -> None:
    """Start a job in the background. Must be called from inside the event loop."""
    task = asyncio.get_running_loop().create_task(_run(job_id), name=f"analysis-{job_id}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _run(job_id: str) -> None:
    try:
        cancel_event = store.cancel_event(job_id)
        async with _get_slots():
            if cancel_event.is_set():
                store.mark_cancelled(job_id)
                return

            store.set_job_status(job_id, "running")
            sequence = store.get(job_id).query.sequence

            for spec in LEVELS:
                if cancel_event.is_set():
                    store.mark_cancelled(job_id)
                    return

                store.start_level(job_id, spec.key)
                if spec.cache_version is not None:
                    cached = await asyncio.to_thread(cache.load, spec.key, spec.cache_version, sequence)
                    if cached is not None:
                        logger.info("Using the cached %s result for job %s", spec.key, job_id)
                        store.finish_level(job_id, spec.key, "completed", result=cached)
                        continue

                context = StageContext(store, job_id, spec.key, cancel_event)
                try:
                    result = await asyncio.to_thread(spec.run, sequence, context)
                except AnalysisCancelled:
                    store.mark_cancelled(job_id)
                    return
                except LevelSkipped as skip:
                    store.finish_level(job_id, spec.key, "skipped", message=_describe(skip))
                    continue
                except Exception as error:  # one level failing must not stop the others
                    logger.exception("The %s level failed for job %s", spec.key, job_id)
                    store.finish_level(job_id, spec.key, "failed", message=_describe(error))
                    continue
                store.finish_level(job_id, spec.key, "completed", result=result)
                if spec.cache_version is not None:
                    await asyncio.to_thread(cache.store, spec.key, spec.cache_version, sequence, result)

            if cancel_event.is_set():
                store.mark_cancelled(job_id)
                return

            store.set_verdict_status(job_id, "running")
            await asyncio.sleep(_INTEGRATION_PAUSE_SECONDS * MOCK_DELAY_SCALE)
            if cancel_event.is_set():
                store.mark_cancelled(job_id)
                return
            verdict = build_verdict(store.get(job_id))
            store.complete(job_id, verdict)

    except asyncio.CancelledError:
        store.mark_cancelled(job_id)
        raise
    except Exception as error:
        logger.exception("Analysis %s failed unexpectedly", job_id)
        store.fail(job_id, _describe(error))
