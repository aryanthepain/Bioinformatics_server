"""Runs analysis jobs in the background.

How a job runs:
  1. It waits for a free slot (at most MAX_CONCURRENT_JOBS run at once).
  2. All structural levels start at the same time, each in a worker thread, so
     slow or blocking code never freezes the server. A level first waits for
     the levels in its `after` (quaternary waits for primary), and an
     `exclusive` level (primary: DIAMOND, HMMER, ESM-2 on the local CPU) runs
     for one job at a time.
  3. A level that fails is marked "failed" and the others carry on; a level
     that cannot run is marked "skipped".
  4. Quick results: the results page opens as soon as any level has a result
     (the frontend shows each level as it finishes). Once the essential level
     (primary) is done and either every non-background level has finished or
     QUICK_RESULT_SECONDS have passed (default 0: straight away), a provisional
     verdict is published. It is recomputed each time a level changes (finishes,
     or a background step starts or ends), and becomes final when all are done.
  5. Cancel while no level has a result stops the job. Once a level has a result
     ("Stop & finish now"), it stops the remaining levels and finalises the
     verdict with the levels that finished.
  6. A level with a background `refine` step (the primary level's EBI BLASTp and
     InterProScan) shows its result first, then runs that step and replaces the
     result; the verdict is recomputed when it finishes. Levels waiting for it
     (quaternary) start as soon as the first result is there.

Results of slow real modules are cached on disk (app/cache.py), so analysing
the same sequence again skips the wait.
"""

import asyncio
import logging
import threading

from . import cache
from .config import MAX_CONCURRENT_JOBS, MOCK_DELAY_SCALE, QUICK_RESULT_SECONDS
from .jobs import AnalysisCancelled, LevelSkipped, StageContext, store
from .levels import LEVELS, LevelSpec
from .schemas import AnalysisJob, LevelKey, LevelResult
from .verdict import build_verdict

logger = logging.getLogger(__name__)

# Short pause before the final verdict appears, so the final step is visible in
# the placeholder demo. Scaled by PFP_MOCK_DELAY_SCALE.
_INTEGRATION_PAUSE_SECONDS = 0.6

# How often the supervisor checks for "Stop & finish now", so stopping is prompt
# even while a level is stuck in a slow web request.
_STOP_CHECK_SECONDS = 1.0

# Level states after which a level will not change any more.
_DONE_STATES = frozenset({"completed", "failed", "skipped", "cancelled"})

_slots: asyncio.Semaphore | None = None
_exclusive: dict[LevelKey, asyncio.Semaphore] = {}
_tasks: set[asyncio.Task[None]] = set()


def _get_slots() -> asyncio.Semaphore:
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    return _slots


def _exclusive_lock(key: LevelKey) -> asyncio.Semaphore:
    lock = _exclusive.get(key)
    if lock is None:
        lock = _exclusive[key] = asyncio.Semaphore(1)
    return lock


def _describe(error: BaseException) -> str:
    text = str(error).strip() or error.__class__.__name__
    return text if len(text) <= 300 else text[:297] + "..."


def _keep(task: asyncio.Task[None]) -> None:
    """Hold a reference to a background task until it ends (asyncio only keeps weak ones)."""
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def startup() -> None:
    """Called when the server starts (inside its event loop)."""
    global _slots
    _slots = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    _exclusive.clear()


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
    _keep(asyncio.get_running_loop().create_task(_run(job_id), name=f"analysis-{job_id}"))


async def _run_level(
    job_id: str,
    spec: LevelSpec,
    sequence: str,
    cancel_event: threading.Event,
    finished: dict[LevelKey, asyncio.Event],
) -> None:
    """Run one level and record its outcome. Never raises (except when the server stops)."""
    event = cancel_event
    try:
        for key in spec.after:
            if not finished[key].is_set():
                store.report_level(job_id, spec.key, f"Starts when the {key} level has finished.")
            await finished[key].wait()
        if event.is_set():
            return

        store.start_level(job_id, spec.key)
        result: LevelResult | None = None
        if spec.cache_version is not None:
            result = await asyncio.to_thread(cache.load, spec.key, spec.cache_version, sequence)
            if result is not None:
                logger.info("Using the cached %s result for job %s", spec.key, job_id)
                store.finish_level(job_id, spec.key, "completed", result=result)

        if result is None:
            if spec.exclusive:
                lock = _exclusive_lock(spec.key)
                if lock.locked():
                    store.report_level(job_id, spec.key, "Waiting for another analysis to finish this step…")
                async with lock:
                    if event.is_set():
                        return
                    result = await _execute(job_id, spec, sequence, event)
            else:
                result = await _execute(job_id, spec, sequence, event)

        if result is not None:
            finished[spec.key].set()  # levels waiting for this one can start now
            await _refine(job_id, spec, sequence, event, result)
    except asyncio.CancelledError:
        raise
    except Exception as error:  # a level must never take the job down with it
        logger.exception("The %s level crashed for job %s", spec.key, job_id)
        if not event.is_set():
            store.finish_level(job_id, spec.key, "failed", message=_describe(error))
    finally:
        finished[spec.key].set()


async def _execute(job_id: str, spec: LevelSpec, sequence: str, event: threading.Event) -> LevelResult | None:
    """Run the level; return its result if it completed."""
    context = StageContext(store, job_id, spec.key, event)
    try:
        result = await asyncio.to_thread(spec.run, sequence, context)
    except AnalysisCancelled:
        return None  # the job is being cancelled or stopped; the supervisor records it
    except LevelSkipped as skip:
        if not event.is_set():
            store.finish_level(job_id, spec.key, "skipped", message=_describe(skip))
        return None
    except Exception as error:  # one level failing must not stop the others
        logger.exception("The %s level failed for job %s", spec.key, job_id)
        if not event.is_set():
            store.finish_level(job_id, spec.key, "failed", message=_describe(error))
        return None
    if event.is_set():
        return None  # finished after Cancel: the job no longer accepts results
    store.finish_level(job_id, spec.key, "completed", result=result)
    if spec.cache_version is not None:
        await asyncio.to_thread(cache.store, spec.key, spec.cache_version, sequence, result)
    return result


async def _refine(job_id: str, spec: LevelSpec, sequence: str, event: threading.Event, result: LevelResult) -> None:
    """The level's optional background step; its result stays visible meanwhile. Never raises.

    Runs outside the exclusive lock (it waits for remote services, not the local CPU).
    If it fails, the result shown so far is kept.
    """
    if spec.refine is None or spec.needs_refinement is None or event.is_set():
        return
    try:
        if not spec.needs_refinement(result):
            return
        store.start_refining(job_id, spec.key, "Starting the remote analyses…")
        context = StageContext(store, job_id, spec.key, event)
        refined = await asyncio.to_thread(spec.refine, sequence, result, context)
    except asyncio.CancelledError:
        raise
    except AnalysisCancelled:
        return  # stopped: the supervisor records it and keeps the result shown so far
    except Exception as error:
        logger.exception("The background step of the %s level failed for job %s", spec.key, job_id)
        if not event.is_set():
            store.finish_refining(job_id, spec.key, None, message=f"Background step failed: {_describe(error)}")
        return
    if event.is_set():
        return
    store.finish_refining(job_id, spec.key, refined)
    if spec.cache_version is not None:
        try:
            await asyncio.to_thread(cache.store, spec.key, spec.cache_version, sequence, refined)
        except Exception:
            logger.exception("Could not cache the refined %s result", spec.key)


def _has_results(job_id: str) -> bool:
    """At least one level finished with a result, so stopping still leaves something to show."""
    return any(level.status == "completed" and level.result is not None for level in store.get(job_id).levels)


def _level_state(job: AnalysisJob) -> tuple[object, ...]:
    """What the verdict depends on: each level's status, background step and result time."""
    return tuple((level.key, level.status, level.refining, level.finished_at) for level in job.levels)


def _ready_for_quick_result(job_id: str, now: float, deadline: float) -> bool:
    """Essential levels done, and either all foreground levels done or the time budget used."""
    status = {level.key: level.status for level in store.get(job_id).levels}
    if not all(status[spec.key] in _DONE_STATES for spec in LEVELS if spec.essential):
        return False
    foreground_done = all(status[spec.key] in _DONE_STATES for spec in LEVELS if not spec.background)
    return foreground_done or now >= deadline


async def _run(job_id: str) -> None:
    try:
        cancel_event = store.cancel_event(job_id)
        async with _get_slots():
            if cancel_event.is_set():
                store.mark_cancelled(job_id)
                return

            store.set_job_status(job_id, "running")
            sequence = store.get(job_id).query.sequence
            loop = asyncio.get_running_loop()
            deadline = loop.time() + QUICK_RESULT_SECONDS

            finished: dict[LevelKey, asyncio.Event] = {spec.key: asyncio.Event() for spec in LEVELS}
            pending: set[asyncio.Task[None]] = set()
            for spec in LEVELS:
                task = loop.create_task(
                    _run_level(job_id, spec, sequence, cancel_event, finished),
                    name=f"analysis-{job_id}-{spec.key}",
                )
                _keep(task)
                pending.add(task)

            published = False
            published_state: tuple[object, ...] = ()
            while pending:
                now = loop.time()
                timeout = _STOP_CHECK_SECONDS
                if not published and now < deadline:
                    timeout = min(timeout, deadline - now)
                _, pending = await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)

                if cancel_event.is_set():
                    if _has_results(job_id):
                        # "Stop & finish now": keep what finished and finalise.
                        store.stop_unfinished(job_id, "Stopped before it finished.")
                        store.complete(job_id, build_verdict(store.get(job_id)))
                    else:
                        store.mark_cancelled(job_id)
                    return

                if not pending:
                    break
                if not published and not _ready_for_quick_result(job_id, loop.time(), deadline):
                    continue
                # Recompute the provisional verdict whenever a level changes: it finishes, or a
                # background step starts, ends or replaces a result.
                job = store.get(job_id)
                state = _level_state(job)
                if state != published_state:
                    store.publish_verdict(job_id, build_verdict(job))
                    published_state = state
                    if not published:
                        published = True
                        logger.info("Published the provisional verdict for job %s", job_id)

            store.set_verdict_status(job_id, "running")
            await asyncio.sleep(_INTEGRATION_PAUSE_SECONDS * MOCK_DELAY_SCALE)
            if cancel_event.is_set():
                if _has_results(job_id):
                    store.complete(job_id, build_verdict(store.get(job_id)))
                else:
                    store.mark_cancelled(job_id)
                return
            store.complete(job_id, build_verdict(store.get(job_id)))

    except asyncio.CancelledError:
        store.mark_cancelled(job_id)
        raise
    except Exception as error:
        logger.exception("Analysis %s failed unexpectedly", job_id)
        store.fail(job_id, _describe(error))
