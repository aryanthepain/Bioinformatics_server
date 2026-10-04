"""HTTP routes. Every URL starts with /api so the frontend proxy can find it.

  GET  /api/health                     is the server up?
  GET  /api/examples                   example proteins for the input screen
  POST /api/analyses                   start an analysis (returns immediately)
  GET  /api/analyses/{job_id}          poll progress and results
  POST /api/analyses/{job_id}/cancel   stop a running analysis
"""

from fastapi import APIRouter, HTTPException

from . import runner
from .config import API_VERSION
from .examples import EXAMPLES
from .jobs import JobNotFound, store
from .levels import LEVELS, LIVE_LEVELS
from .schemas import (
    AnalysisJob,
    AnalysisRequest,
    ExampleSequence,
    HealthResponse,
    LevelReport,
    QueryInfo,
)
from .sequence import SequenceError, parse_sequence

router = APIRouter(prefix="/api")

_NOT_FOUND_MESSAGE = (
    "Analysis not found. Results are kept in memory, so they disappear when the server restarts."
)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=API_VERSION, live_levels=list(LIVE_LEVELS))


@router.get("/examples", response_model=list[ExampleSequence])
def list_examples() -> list[ExampleSequence]:
    return [example.as_schema() for example in EXAMPLES]


@router.post("/analyses", response_model=AnalysisJob, status_code=202)
async def create_analysis(request: AnalysisRequest) -> AnalysisJob:
    try:
        parsed = parse_sequence(request.sequence)
    except SequenceError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

    typed_name = (request.name or "").strip()
    name = typed_name or parsed.header or "Untitled sequence"

    job = store.create(
        query=QueryInfo(name=name[:80], sequence=parsed.sequence, length=len(parsed.sequence)),
        levels=[
            LevelReport(key=spec.key, title=spec.title, tools=list(spec.tools)) for spec in LEVELS
        ],
    )
    runner.schedule(job.id)
    return job


@router.get("/analyses/{job_id}", response_model=AnalysisJob)
def get_analysis(job_id: str) -> AnalysisJob:
    try:
        return store.get(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_MESSAGE) from None


@router.post("/analyses/{job_id}/cancel", response_model=AnalysisJob)
def cancel_analysis(job_id: str) -> AnalysisJob:
    try:
        return store.request_cancel(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_MESSAGE) from None
