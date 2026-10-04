"""FastAPI application entry point.

Development (two servers, see the README):

    uv run uvicorn app.main:app --reload --port 8000

Hosting: once the frontend has been built (UI/frontend/dist exists), this
same server also serves the website, so the whole app runs as ONE service:

    cd frontend && npm run build
    cd ../backend && uv run uvicorn app.main:app --port 8000

The interactive API documentation is always available at /docs.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import runner
from .api import router
from .config import API_VERSION

# UI/frontend/dist, created by "npm run build" (and by the build step when hosted).
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

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

if FRONTEND_DIST.is_dir():
    # Serve the built website. Mounted last, so /api and /docs keep priority.
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        """Without a built website, the bare address opens the API documentation."""
        return RedirectResponse(url="/docs")