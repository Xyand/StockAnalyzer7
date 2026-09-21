"""FastAPI application entry point.

Serves the JSON API under /api and the static single-page UI at /.
"""
from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import REPO_ROOT, get_settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)

FRONTEND_DIR = REPO_ROOT / "frontend"

@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logging.getLogger(__name__).info(
        "StockAnalyzer7 ready - provider=%s, data=%s",
        settings.market_data_provider,
        settings.data_dir,
    )
    yield


app = FastAPI(
    title="StockAnalyzer7",
    description=(
        "Portfolio analytics: year-over-year returns per holding, and fund "
        "look-through to your effective position in each base asset."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# The UI is served from the same origin, but allow localhost origins so the
# frontend can also be run from a separate dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
