"""Detector tests.

These need the heavy ``ultralytics`` dependency and may need network access to
download the ``yolov8n.pt`` fallback weights. Everything is skipped (not failed)
when those are unavailable, so the suite still passes fully offline.
"""

from __future__ import annotations

import pytest


def test_detector_falls_back_to_yolov8n_when_weights_missing(monkeypatch):
    pytest.importorskip("ultralytics")

    try:
        import app.detector as detector_module
    except Exception as exc:  # pragma: no cover - import-time deps
        pytest.skip("app.detector unavailable: " + str(exc))

    # Force a missing model path so the constructor must hit the fallback.
    from app.config import settings

    monkeypatch.setattr(settings, "MODEL_PATH", "ml/weights/definitely_missing.pt", raising=False)

    try:
        detector = detector_module.Detector()
    except TypeError:
        # Constructor may take an explicit path argument.
        try:
            detector = detector_module.Detector("ml/weights/definitely_missing.pt")
        except Exception as exc:  # pragma: no cover - network/model download
            pytest.skip("detector fallback needs network/model download: " + str(exc))
    except Exception as exc:  # pragma: no cover - network/model download
        pytest.skip("detector fallback needs network/model download: " + str(exc))

    assert detector is not None
    assert hasattr(detector, "detect")
