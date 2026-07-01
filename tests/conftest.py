"""Shared pytest fixtures.

Sets up an isolated SQLite database and a FastAPI ``TestClient`` with the
YOLO detector and the LLM provider mocked, so the suite runs fully offline
without real model weights or a running Ollama server.

The environment is configured at import time (before any ``app`` module is
imported) because ``app.config`` reads settings once via an ``lru_cache`` and
``app.database`` builds its engine at import.
"""

from __future__ import annotations

import atexit
import io
import os
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Configure environment BEFORE importing any app module.
# ---------------------------------------------------------------------------
_TMP_DB = tempfile.NamedTemporaryFile(prefix="smartcity_test_", suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DB_URL"] = "sqlite:///" + _TMP_DB.name
# Point at a path that does not exist so nothing accidentally loads weights.
os.environ.setdefault("MODEL_PATH", "ml/weights/does_not_exist.pt")
# Keep the LLM provider pointed at a dead host; tests mock around it anyway.
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:59999")
# Write uploads to a throwaway directory, not the repo.
_TMP_UPLOADS = tempfile.mkdtemp(prefix="smartcity_uploads_")
os.environ.setdefault("UPLOAD_DIR", _TMP_UPLOADS)


@atexit.register
def _cleanup_tmp_db() -> None:
    try:
        os.unlink(_TMP_DB.name)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Test doubles for the detector and LLM provider.
# ---------------------------------------------------------------------------
class _FakeDetector:
    """Detector stand-in that returns a canned result without loading YOLO."""

    def __init__(self, result):
        self._result = result
        self.loaded = True

    def load(self):  # noqa: D401 - mirror real signature (lifespan calls this)
        self.loaded = True
        return self

    def detect(self, image_bytes, imgsz=None):  # noqa: D401 - mirror real signature
        self.last_imgsz = imgsz
        return self._result

    def annotate(self, image_bytes, imgsz=None):  # noqa: D401 - mirror real signature
        # Return small valid JPEG-ish bytes; router only saves them to disk.
        return b"\xff\xd8\xff\xe0annotated\xff\xd9"

    def annotate_video(self, video_path, imgsz=None, max_frames=200, **kwargs):
        summary = {
            "frames_processed": 3,
            "frames_with_garbage": 3,
            "class_counts": {"Waste": 3},
            "capped_at_max_frames": False,
            "max_frames": max_frames,
        }
        return b"GIF89a-annotated", summary


class _FakeProvider:
    """Provider stand-in that defers all numbers to the deterministic rules."""

    def generate_report(self, result, context):
        from app.llm import rules

        return rules.build_report(result, context or {})


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_image_bytes() -> bytes:
    """A tiny valid PNG generated in-memory via Pillow."""
    PIL = pytest.importorskip("PIL")
    from PIL import Image  # noqa: F401  (ensures submodule import)

    img = Image.new("RGB", (640, 480), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fake_detection_result():
    """A deterministic ``DetectionResult``: one Waste box at 25% area.

    score = 100 * (1.0 * 0.25) + 5 * 1 = 30 -> medium / P3 / 24h /
    Solid Waste Management.
    """
    from app.schemas import Detection, DetectionResult

    det = Detection(
        class_name="Waste",
        confidence=0.91,
        bbox=[0.0, 0.0, 500.0, 500.0],
        area_fraction=0.25,
    )
    return DetectionResult(
        detections=[det],
        image_width=1000,
        image_height=1000,
        inference_ms=12.5,
    )


@pytest.fixture
def client(fake_detection_result):
    """FastAPI ``TestClient`` with a fresh schema and mocked detector/provider."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import app.main as main_module
    import app.detector as detector_module
    import app.llm.base as base_module
    from app.database import Base, engine, init_db

    fake_detector = _FakeDetector(fake_detection_result)
    fake_provider = _FakeProvider()

    # Patch the Detector class so the lifespan startup does not download weights.
    detector_module.Detector = lambda *a, **k: fake_detector  # type: ignore[assignment]
    if hasattr(main_module, "Detector"):
        main_module.Detector = lambda *a, **k: fake_detector  # type: ignore[attr-defined]

    # Patch the provider factory wherever it may be referenced.
    base_module.get_provider = lambda *a, **k: fake_provider  # type: ignore[assignment]
    if hasattr(main_module, "get_provider"):
        main_module.get_provider = lambda *a, **k: fake_provider  # type: ignore[attr-defined]

    # Start from a clean schema for per-test isolation.
    Base.metadata.drop_all(bind=engine)
    init_db()

    with TestClient(main_module.app) as test_client:
        # Belt-and-suspenders: ensure request handlers read the fakes.
        main_module.app.state.detector = fake_detector
        main_module.app.state.provider = fake_provider
        yield test_client
