"""FastAPI application entry point.

Start the server from the backend folder with:

    uv run uvicorn app.main:app --reload --port 8000

Interactive API documentation is then available at http://127.0.0.1:8000/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from . import runner
from .api import router
from .config import API_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    runner.startup()
    yield
    await runner.shutdown()


app = FastAPI(
    title="Protein Function Predictor API",
    version=API_VERSION,
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Visiting the bare server address opens the API documentation."""
    return RedirectResponse(url="/docs")
