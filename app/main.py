"""FastAPI application entrypoint with lifespan-managed model warm-load."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import engine, init_db
from .detector import Detector
from .llm.base import get_provider
from .routers import analytics, detect, incidents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB, warm-load YOLO, and build the LLM provider on startup."""
    logger.info("Starting Smart City garbage detection API")
    init_db()

    detector = Detector()
    try:
        detector.load()
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.error("Failed to load detector at startup: %s", exc)
    app.state.detector = detector

    try:
        app.state.provider = get_provider()
    except Exception as exc:  # noqa: BLE001 - provider is best-effort
        logger.error("Failed to build LLM provider: %s", exc)
        app.state.provider = None

    yield
    logger.info("Shutting down Smart City garbage detection API")


app = FastAPI(
    title="Smart City Garbage Detection API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect.router)
app.include_router(incidents.router)
app.include_router(analytics.router)

# Serve uploaded images so the frontend can render them.
import os

from .config import settings

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


def _db_ok() -> bool:
    """Run a trivial SELECT 1 to confirm DB connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - report unhealthy, do not raise
        logger.warning("DB health check failed: %s", exc)
        return False


def _ollama_ok() -> bool:
    """Best-effort Ollama ping with a short timeout."""
    provider = getattr(app.state, "provider", None)
    ping = getattr(provider, "ping", None)
    if callable(ping):
        try:
            return bool(ping())
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.debug("Ollama health check failed: %s", exc)
            return False
    return False


@app.get("/health")
def health() -> dict:
    """Liveness/readiness probe: model, DB, and Ollama status."""
    detector = getattr(app.state, "detector", None)
    model_loaded = bool(detector is not None and detector.loaded)
    return {
        "status": "ok",
        "model_loaded": model_loaded,
        "db_ok": _db_ok(),
        "ollama_ok": _ollama_ok(),
    }


@app.get("/")
def root() -> dict:
    """Service banner."""
    return {"service": "smart-city-garbage", "docs": "/docs"}
