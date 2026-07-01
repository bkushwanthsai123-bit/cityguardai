"""REST API tests against ``app.main:app`` with detector + LLM mocked."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")


# Columns that IncidentOut must expose (contract-locked shape).
INCIDENT_OUT_FIELDS = {
    "id",
    "created_at",
    "image_path",
    "detections",
    "num_detections",
    "classes",
    "lat",
    "lon",
    "address",
    "title",
    "description",
    "severity",
    "severity_score",
    "priority",
    "department",
    "recommended_action",
    "sla_hours",
    "status",
}


def _create_incident(client, sample_image_bytes, lat=12.97, lon=77.59, address="MG Road"):
    """Helper: POST /detect and return the created IncidentOut dict."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}
    data = {}
    if lat is not None:
        data["lat"] = str(lat)
    if lon is not None:
        data["lon"] = str(lon)
    if address is not None:
        data["address"] = address
    resp = client.post("/detect", files=files, data=data)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "model_loaded", "db_ok", "ollama_ok"):
        assert key in body
    assert body["db_ok"] is True


def test_detect_creates_incident_consistent_with_rules(
    client, sample_image_bytes, fake_detection_result
):
    from app.llm import rules

    body = _create_incident(client, sample_image_bytes)

    # Shape.
    assert INCIDENT_OUT_FIELDS.issubset(body.keys())
    assert isinstance(body["id"], int)
    assert body["status"] == "open"
    assert body["num_detections"] == 1
    assert body["classes"] == ["Waste"]
    assert body["lat"] == pytest.approx(12.97)
    assert body["lon"] == pytest.approx(77.59)
    assert body["address"] == "MG Road"

    # Numbers must match the deterministic rules (rules own the numbers).
    score, band = rules.compute_severity(fake_detection_result)
    assert body["severity_score"] == score
    assert 0 <= body["severity_score"] <= 100
    assert body["severity"] == band
    assert body["priority"] == rules.priority_for(band)
    assert body["sla_hours"] == rules.sla_for(body["priority"])
    assert body["department"] == rules.pick_department(fake_detection_result)
    # Concretely: a single Waste box at 25% area is medium / P3 / 24h.
    assert body["severity"] == "medium"
    assert body["priority"] == "P3"
    assert body["sla_hours"] == 24
    assert body["department"] == "Solid Waste Management"


def test_list_incidents_with_filters(client, sample_image_bytes):
    a = _create_incident(client, sample_image_bytes)
    _create_incident(client, sample_image_bytes)

    # No filter -> at least our two.
    resp = client.get("/incidents")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) >= 2

    # Filter by department.
    resp = client.get("/incidents", params={"department": "Solid Waste Management"})
    assert resp.status_code == 200
    assert all(r["department"] == "Solid Waste Management" for r in resp.json())

    # Filter by severity.
    resp = client.get("/incidents", params={"severity": "medium"})
    assert resp.status_code == 200
    assert all(r["severity"] == "medium" for r in resp.json())

    # Filter by status.
    resp = client.get("/incidents", params={"status": "open"})
    assert resp.status_code == 200
    assert all(r["status"] == "open" for r in resp.json())

    # Filter by priority.
    resp = client.get("/incidents", params={"priority": a["priority"]})
    assert resp.status_code == 200
    assert all(r["priority"] == a["priority"] for r in resp.json())

    # Pagination params are accepted.
    resp = client.get("/incidents", params={"limit": 1, "offset": 0})
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_get_incident_by_id(client, sample_image_bytes):
    created = _create_incident(client, sample_image_bytes)
    resp = client.get("/incidents/" + str(created["id"]))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_incident_404(client):
    resp = client.get("/incidents/99999999")
    assert resp.status_code == 404


def test_patch_status(client, sample_image_bytes):
    created = _create_incident(client, sample_image_bytes)
    resp = client.patch(
        "/incidents/" + str(created["id"]), json={"status": "in_progress"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    resp = client.patch(
        "/incidents/" + str(created["id"]), json={"status": "resolved"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_patch_status_404(client):
    resp = client.patch("/incidents/99999999", json={"status": "resolved"})
    assert resp.status_code == 404


def test_delete_incident(client, sample_image_bytes):
    created = _create_incident(client, sample_image_bytes)
    resp = client.delete("/incidents/" + str(created["id"]))
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Now gone.
    resp = client.get("/incidents/" + str(created["id"]))
    assert resp.status_code == 404


def test_analytics_summary(client, sample_image_bytes):
    _create_incident(client, sample_image_bytes)
    resp = client.get("/analytics/summary")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("total", "by_severity", "by_department", "by_status", "by_priority", "trend"):
        assert key in body
    assert body["total"] >= 1
    assert isinstance(body["by_severity"], dict)
    assert isinstance(body["by_department"], dict)
    assert isinstance(body["by_status"], dict)
    assert isinstance(body["by_priority"], dict)
    assert isinstance(body["trend"], list)


def test_analytics_hotspots(client, sample_image_bytes):
    _create_incident(client, sample_image_bytes, lat=12.9716, lon=77.5946)
    resp = client.get("/analytics/hotspots")
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    for row in rows:
        for key in ("lat", "lon", "count", "top_severity"):
            assert key in row


def test_detect_passes_imgsz_override_to_detector(client, sample_image_bytes):
    """A per-request imgsz form field reaches Detector.detect(imgsz=...)."""
    import app.main as main_module

    files = {"file": ("test.png", sample_image_bytes, "image/png")}
    resp = client.post("/detect", files=files, data={"imgsz": "1600"})
    assert resp.status_code == 200, resp.text
    assert main_module.app.state.detector.last_imgsz == 1600


def test_detect_without_imgsz_defaults_to_none(client, sample_image_bytes):
    """Omitting imgsz leaves the override as None (detector uses its default)."""
    import app.main as main_module

    files = {"file": ("test.png", sample_image_bytes, "image/png")}
    resp = client.post("/detect", files=files)
    assert resp.status_code == 200, resp.text
    assert main_module.app.state.detector.last_imgsz is None


def test_detect_rejects_out_of_range_imgsz(client, sample_image_bytes):
    """imgsz outside [320, 4096] is rejected before touching the detector."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}
    resp = client.post("/detect", files=files, data={"imgsz": "100"})
    assert resp.status_code == 422


def _make_video_bytes(tmp_path, frames=8):
    """Write a tiny mp4 and return its bytes (skips if OpenCV is unavailable)."""
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    path = str(tmp_path / "clip.mp4")
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 5, (64, 64))
    for _ in range(frames):
        vw.write(np.zeros((64, 64, 3), dtype="uint8"))
    vw.release()
    with open(path, "rb") as fh:
        return fh.read()


def test_detect_video_creates_aggregated_incident(client, tmp_path):
    """POST /detect/video samples frames and stores one annotated incident."""
    video_bytes = _make_video_bytes(tmp_path)
    files = {"file": ("clip.mp4", video_bytes, "video/mp4")}
    resp = client.post("/detect/video", files=files, data={"max_frames": "6"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The fake detector returns one detection per frame, so the aggregated
    # incident carries that detection and the video-analysis annotation.
    assert body["description"].startswith("Video analysis:")
    assert body["num_detections"] == 1
    for key in INCIDENT_OUT_FIELDS:
        assert key in body


def test_detect_video_rejects_bad_max_frames(client, tmp_path):
    """max_frames outside [1, 120] is rejected."""
    video_bytes = _make_video_bytes(tmp_path)
    files = {"file": ("clip.mp4", video_bytes, "video/mp4")}
    resp = client.post("/detect/video", files=files, data={"max_frames": "999"})
    assert resp.status_code == 422


def test_detect_sets_annotated_path(client, sample_image_bytes):
    """POST /detect persists an annotated image path for display."""
    files = {"file": ("test.png", sample_image_bytes, "image/png")}
    resp = client.post("/detect", files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["annotated_path"]
    assert body["annotated_path"].endswith(".jpg")


def test_detect_video_sets_annotated_gif_path(client, tmp_path):
    """POST /detect/video persists an annotated GIF path for display."""
    video_bytes = _make_video_bytes(tmp_path)
    files = {"file": ("clip.mp4", video_bytes, "video/mp4")}
    resp = client.post("/detect/video", files=files, data={"max_frames": "6"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["annotated_path"]
    assert body["annotated_path"].endswith(".gif")
