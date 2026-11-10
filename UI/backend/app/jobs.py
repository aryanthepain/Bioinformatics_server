"""In-memory storage for analysis jobs, safe to use from several threads.

Analysis modules run in worker threads (so slow work never freezes the web
server), while the API reads job state from the main thread. Every read and
write therefore goes through a lock, and readers always receive a private
copy of the job.
"""

import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timezone

from .config import MAX_STORED_JOBS
from .schemas import (
    AnalysisJob,
    JobStatus,
    LevelKey,
    LevelReport,
    LevelResult,
    QueryInfo,
    StepStatus,
    Verdict,
)

TERMINAL_JOB_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})
UNFINISHED_STEP_STATUSES: frozenset[str] = frozenset({"pending", "running"})


class AnalysisCancelled(Exception):
    """Raised inside a running level when the user cancels the analysis."""


class LevelSkipped(Exception):
    """Raised by a level that cannot run for this input (the message says why)."""


class JobNotFound(KeyError):
    """The requested job id does not exist (or was removed after a restart)."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _find_level(job: AnalysisJob, key: LevelKey) -> LevelReport:
    for level in job.levels:
        if level.key == key:
            return level
    raise KeyError(f"Job {job.id} has no level called {key!r}.")


class JobStore:
    def __init__(self, max_jobs: int = MAX_STORED_JOBS) -> None:
        self._lock = threading.Lock()
        self._jobs: OrderedDict[str, AnalysisJob] = OrderedDict()
        self._cancel_events: dict[str, threading.Event] = {}
        self._max_jobs = max_jobs

    # --- Creating and reading ------------------------------------------------

    def create(self, query: QueryInfo, levels: list[LevelReport]) -> AnalysisJob:
        now = utc_now()
        job = AnalysisJob(
            id=uuid.uuid4().hex[:12],
            status="queued",
            created_at=now,
            updated_at=now,
            query=query,
            levels=levels,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._cancel_events[job.id] = threading.Event()
            self._evict_old_jobs()
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> AnalysisJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            return job.model_copy(deep=True)

    def cancel_event(self, job_id: str) -> threading.Event:
        with self._lock:
            event = self._cancel_events.get(job_id)
            if event is None:
                raise JobNotFound(job_id)
            return event

    # --- Cancellation ----------------------------------------------------------

    def request_cancel(self, job_id: str) -> AnalysisJob:
        """Ask a job to stop. The runner notices and marks it cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFound(job_id)
            if job.status not in TERMINAL_JOB_STATUSES:
                self._cancel_events[job_id].set()
            return job.model_copy(deep=True)

    def cancel_all(self) -> None:
        """Ask every unfinished job to stop (used when the server shuts down)."""
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.status not in TERMINAL_JOB_STATUSES:
                    self._cancel_events[job_id].set()

    # --- Updates used by the runner -------------------------------------------

    def set_job_status(self, job_id: str, status: JobStatus) -> None:
        def apply(job: AnalysisJob) -> None:
            job.status = status

        self._update(job_id, apply)

    def start_level(self, job_id: str, key: LevelKey) -> None:
        def apply(job: AnalysisJob) -> None:
            level = _find_level(job, key)
            level.status = "running"
            level.started_at = utc_now()
            level.message = None

        self._update(job_id, apply)

    def report_level(self, job_id: str, key: LevelKey, message: str) -> None:
        def apply(job: AnalysisJob) -> None:
            _find_level(job, key).message = message

        self._update(job_id, apply)

    def finish_level(
        self,
        job_id: str,
        key: LevelKey,
        status: StepStatus,
        result: LevelResult | None = None,
        message: str | None = None,
    ) -> None:
        def apply(job: AnalysisJob) -> None:
            level = _find_level(job, key)
            level.status = status
            level.result = result
            level.message = message
            level.finished_at = utc_now()

        self._update(job_id, apply)

    def start_refining(self, job_id: str, key: LevelKey, message: str) -> None:
        """A completed level starts its background step; its result stays visible."""

        def apply(job: AnalysisJob) -> None:
            level = _find_level(job, key)
            level.refining = True
            level.message = message

        self._update(job_id, apply)

    def finish_refining(
        self,
        job_id: str,
        key: LevelKey,
        result: LevelResult | None,
        message: str | None = None,
    ) -> None:
        """The background step ended: replace the result (None keeps the current one)."""

        def apply(job: AnalysisJob) -> None:
            level = _find_level(job, key)
            level.refining = False
            level.message = message
            if result is not None:
                level.result = result
                level.finished_at = utc_now()

        self._update(job_id, apply)

    def set_verdict_status(self, job_id: str, status: StepStatus) -> None:
        def apply(job: AnalysisJob) -> None:
            job.verdict_status = status

        self._update(job_id, apply)

    def publish_verdict(self, job_id: str, verdict: Verdict) -> None:
        """A provisional verdict, shown while slower levels are still running."""

        def apply(job: AnalysisJob) -> None:
            job.verdict = verdict
            job.verdict_status = "running"

        self._update(job_id, apply)

    def stop_unfinished(self, job_id: str, message: str) -> None:
        """Mark the levels that are still waiting or running as stopped."""

        def apply(job: AnalysisJob) -> None:
            now = utc_now()
            for level in job.levels:
                if level.status in UNFINISHED_STEP_STATUSES:
                    if level.status == "running":
                        level.finished_at = now
                    level.status = "cancelled"
                    level.message = message
                elif level.refining:
                    level.refining = False  # its result stays; the background step was stopped
                    level.message = "Its background step was stopped before it finished."

        self._update(job_id, apply)

    def complete(self, job_id: str, verdict: Verdict) -> None:
        def apply(job: AnalysisJob) -> None:
            for level in job.levels:
                level.refining = False
            job.verdict = verdict
            job.verdict_status = "completed"
            job.status = "completed"
            job.finished_at = utc_now()

        self._update(job_id, apply)

    def mark_cancelled(self, job_id: str) -> None:
        def apply(job: AnalysisJob) -> None:
            now = utc_now()
            for level in job.levels:
                level.refining = False
                if level.status in UNFINISHED_STEP_STATUSES:
                    if level.status == "running":
                        level.finished_at = now
                    level.status = "cancelled"
                    level.message = "Cancelled."
            if job.verdict_status in UNFINISHED_STEP_STATUSES:
                job.verdict_status = "cancelled"
            job.status = "cancelled"
            job.finished_at = now

        self._update(job_id, apply)

    def fail(self, job_id: str, error: str) -> None:
        def apply(job: AnalysisJob) -> None:
            now = utc_now()
            for level in job.levels:
                level.refining = False
                if level.status == "running":
                    level.status = "failed"
                    level.message = error
                    level.finished_at = now
                elif level.status == "pending":
                    level.status = "cancelled"
                    level.message = "Not run because the analysis stopped."
            if job.verdict_status in UNFINISHED_STEP_STATUSES:
                job.verdict_status = "failed"
            job.status = "failed"
            job.error = error
            job.finished_at = now

        self._update(job_id, apply)

    # --- Internals -----------------------------------------------------------------

    def _update(self, job_id: str, apply: Callable[[AnalysisJob], None]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return  # the job was removed; nothing to update
            if job.status in TERMINAL_JOB_STATUSES:
                return  # finished jobs never change (e.g. a level answering after Cancel)
            apply(job)
            job.updated_at = utc_now()

    def _evict_old_jobs(self) -> None:
        """Keep memory bounded by dropping the oldest finished jobs."""
        while len(self._jobs) > self._max_jobs:
            oldest_finished = next(
                (job_id for job_id, job in self._jobs.items() if job.status in TERMINAL_JOB_STATUSES),
                None,
            )
            if oldest_finished is None:
                return
            del self._jobs[oldest_finished]
            self._cancel_events.pop(oldest_finished, None)


class StageContext:
    """Handed to every analysis module so it can report progress and stop early.

    Modules call:
      ctx.report("Waiting for Foldseek... 40 s")   # shown live in the interface
      ctx.sleep(20)                              # a wait that stops on cancel
      ctx.check_cancelled()                      # between long steps
    """

    def __init__(
        self,
        store: JobStore,
        job_id: str,
        level_key: LevelKey,
        cancel_event: threading.Event,
    ) -> None:
        self._store = store
        self._job_id = job_id
        self._level_key = level_key
        self._cancel_event = cancel_event

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise AnalysisCancelled()

    def report(self, message: str) -> None:
        self.check_cancelled()
        self._store.report_level(self._job_id, self._level_key, message)

    def sleep(self, seconds: float) -> None:
        if self._cancel_event.wait(timeout=max(0.0, seconds)):
            raise AnalysisCancelled()

    def level_result(self, key: LevelKey) -> LevelResult | None:
        """The result of another level of this analysis, if that level completed.

        Levels run in registry order, so a level can read the results of the
        levels before it (the quaternary level reads the primary level's
        Swiss-Prot homologue). Returns None if that level did not complete,
        or if the job is unknown (as in the check scripts).
        """
        try:
            job = self._store.get(self._job_id)
        except JobNotFound:
            return None
        for level in job.levels:
            if level.key == key:
                return level.result if level.status == "completed" else None
        return None


# The single store used by the whole application.
store = JobStore()
