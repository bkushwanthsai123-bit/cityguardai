"""Detection endpoints: run YOLO -> LLM report -> persist incident."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..detector import Detector
from ..llm.base import AIProvider, get_provider
from ..models import Incident
from ..schemas import DetectionResult, IncidentOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["detection"])

# Frame budget for the persisted annotated GIF, so a long clip can't stall the
# request on CPU. Purely visual; detection accuracy is unaffected.
_GIF_MAX_FRAMES = 60


def _get_detector(request: Request) -> Detector:
    """Fetch the warm-loaded detector from app.state."""
    detector = getattr(request.app.state, "detector", None)
    if detector is None or not detector.loaded:
        raise HTTPException(status_code=503, detail="Detector not loaded")
    return detector


def _get_provider(request: Request) -> AIProvider:
    """Fetch the LLM provider from app.state, creating one if absent."""
    provider = getattr(request.app.state, "provider", None)
    if provider is None:
        provider = get_provider()
    return provider


def _save_upload(image_bytes: bytes, filename: str | None) -> str:
    """Persist an uploaded image to UPLOAD_DIR and return its path."""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "").suffix or ".jpg"
    out_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
    out_path.write_bytes(image_bytes)
    return str(out_path)


def _persist_incident(
    db: Session,
    image_path: str,
    result: DetectionResult,
    report,
    lat: float | None,
    lon: float | None,
    address: str | None,
    *,
    annotated_path: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> Incident:
    """Build and persist an Incident from a detection result + LLM report.

    ``title``/``description`` override the report's when provided (used by the
    video path to note how the incident was aggregated). ``annotated_path``
    points to media with boxes/labels drawn on it (annotated .jpg or .gif).
    """
    classes = sorted({d.class_name for d in result.detections})
    incident = Incident(
        image_path=image_path,
        annotated_path=annotated_path,
        detections=[d.model_dump() for d in result.detections],
        num_detections=len(result.detections),
        classes=classes,
        lat=lat,
        lon=lon,
        address=address,
        title=title or report.title,
        description=description or report.description,
        severity=report.severity,
        severity_score=report.severity_score,
        priority=report.priority,
        department=report.department,
        recommended_action=report.recommended_action,
        sla_hours=report.sla_hours,
        status="open",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    logger.info(
        "Incident %s created: %d detection(s), severity=%s",
        incident.id,
        incident.num_detections,
        incident.severity,
    )
    return incident


def process_image(
    image_bytes: bytes,
    filename: str | None,
    detector: Detector,
    provider: AIProvider,
    db: Session,
    lat: float | None = None,
    lon: float | None = None,
    address: str | None = None,
    imgsz: int | None = None,
) -> Incident:
    """Run detection + report generation and persist an Incident row."""
    image_path = _save_upload(image_bytes, filename)
    result: DetectionResult = detector.detect(image_bytes, imgsz=imgsz)

    # Render boxes/labels onto the image for display (best-effort).
    annotated_path: str | None = None
    try:
        annotated_bytes = detector.annotate(image_bytes, imgsz=imgsz)
        annotated_path = _save_upload(annotated_bytes, "annotated.jpg")
    except Exception as exc:  # noqa: BLE001 - annotation is best-effort
        logger.warning("Image annotation failed: %s", exc)

    context = {"lat": lat, "lon": lon, "address": address}
    report = provider.generate_report(result, context)
    return _persist_incident(
        db, image_path, result, report, lat, lon, address,
        annotated_path=annotated_path,
    )


def _sample_video_frames(
    video_path: str, max_frames: int
) -> list[tuple[int, bytes]]:
    """Sample up to ``max_frames`` frames evenly across a video.

    Returns a list of ``(frame_index, jpeg_bytes)``. Uses OpenCV; if the frame
    count is unknown, falls back to reading sequentially with a fixed stride.
    """
    import cv2  # imported lazily; heavy native dependency

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not read video file")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, total // max_frames) if total > 0 else 15

    frames: list[tuple[int, bytes]] = []
    idx = 0
    try:
        while len(frames) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                encoded, buf = cv2.imencode(".jpg", frame)
                if encoded:
                    frames.append((idx, buf.tobytes()))
            idx += 1
    finally:
        cap.release()
    return frames


def process_video(
    video_bytes: bytes,
    filename: str | None,
    detector: Detector,
    provider: AIProvider,
    db: Session,
    lat: float | None = None,
    lon: float | None = None,
    address: str | None = None,
    imgsz: int | None = None,
    max_frames: int = 24,
) -> Incident:
    """Sample frames from a video, detect per frame, and persist one incident.

    The frame with the most detections (tie-broken by total confidence) becomes
    the representative image; the incident is built from that frame's result and
    annotated with how many sampled frames contained garbage.
    """
    video_path = _save_upload(video_bytes, filename)
    frames = _sample_video_frames(video_path, max_frames)
    if not frames:
        raise HTTPException(status_code=400, detail="No frames decoded from video")

    best_key: tuple[int, float] = (-1, -1.0)
    best_result: DetectionResult | None = None
    best_jpeg: bytes | None = None
    frames_with_garbage = 0

    for _idx, jpeg in frames:
        result = detector.detect(jpeg, imgsz=imgsz)
        n = len(result.detections)
        if n:
            frames_with_garbage += 1
        key = (n, sum(d.confidence for d in result.detections))
        if key > best_key:
            best_key, best_result, best_jpeg = key, result, jpeg

    assert best_result is not None and best_jpeg is not None
    frame_path = _save_upload(best_jpeg, "frame.jpg")

    # Render an annotated animated GIF of the clip for display (best-effort).
    # Bounded frame budget so a long clip can't stall the request on CPU.
    annotated_path: str | None = None
    try:
        # Omit imgsz so the GIF uses the detector's fast per-frame size (640);
        # the accurate imgsz is already used by the detection loop above.
        gif_bytes, _summary = detector.annotate_video(
            video_path, max_frames=_GIF_MAX_FRAMES
        )
        annotated_path = _save_upload(gif_bytes, "annotated.gif")
    except Exception as exc:  # noqa: BLE001 - annotation is best-effort
        logger.warning("Video annotation failed: %s", exc)

    context = {"lat": lat, "lon": lon, "address": address}
    report = provider.generate_report(best_result, context)

    note = (
        f"Video analysis: {len(frames)} frames sampled, "
        f"{frames_with_garbage} contained garbage. "
        f"Peak frame had {len(best_result.detections)} detection(s). "
    )
    return _persist_incident(
        db,
        frame_path,
        best_result,
        report,
        lat,
        lon,
        address,
        annotated_path=annotated_path,
        description=note + report.description,
    )


def _validate_imgsz(imgsz: int | None) -> int | None:
    """Validate a per-request inference size (None uses the configured default)."""
    if imgsz is None:
        return None
    if imgsz < 320 or imgsz > 4096:
        raise HTTPException(
            status_code=422, detail="imgsz must be between 320 and 4096"
        )
    return imgsz


@router.post("/detect", response_model=IncidentOut)
async def detect(
    request: Request,
    file: UploadFile = File(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    address: str | None = Form(None),
    imgsz: int | None = Form(None),
    db: Session = Depends(get_db),
) -> IncidentOut:
    """Detect garbage in an uploaded image and store an incident.

    ``imgsz`` optionally overrides the inference image size for this request;
    larger values (e.g. 1280, 1600) recover more small objects on high-res
    photos at the cost of latency. Defaults to the configured ``IMGSZ``.
    """
    detector = _get_detector(request)
    provider = _get_provider(request)
    imgsz = _validate_imgsz(imgsz)
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    incident = process_image(
        image_bytes, file.filename, detector, provider, db, lat, lon, address, imgsz
    )
    return IncidentOut.model_validate(incident)


@router.post("/detect/annotated")
async def detect_annotated(
    request: Request,
    file: UploadFile = File(...),
    imgsz: int | None = Form(None),
) -> Response:
    """Return the uploaded image with detection boxes/masks drawn (JPEG).

    Visual-only: runs the detector and streams back the annotated image. Does
    NOT persist an incident (use ``/detect`` for that).
    """
    detector = _get_detector(request)
    imgsz = _validate_imgsz(imgsz)
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    annotated = detector.annotate(image_bytes, imgsz=imgsz)
    return Response(content=annotated, media_type="image/jpeg")


@router.post("/detect/video/annotated")
async def detect_video_annotated(
    request: Request,
    file: UploadFile = File(...),
    imgsz: int | None = Form(None),
    max_frames: int = Form(200),
) -> Response:
    """Return the uploaded video with detection boxes/masks drawn as a GIF.

    Visual-only: samples frames, draws detections on each, and streams back an
    animated GIF. Does NOT persist an incident (use ``/detect/video`` for that).
    """
    detector = _get_detector(request)
    imgsz = _validate_imgsz(imgsz)
    if max_frames < 1 or max_frames > 600:
        raise HTTPException(status_code=422, detail="max_frames must be between 1 and 600")
    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    video_path = _save_upload(video_bytes, file.filename)
    try:
        gif_bytes, summary = detector.annotate_video(
            video_path, imgsz=imgsz, max_frames=max_frames
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    headers = {
        "X-Frames-Processed": str(summary["frames_processed"]),
        "X-Frames-With-Garbage": str(summary["frames_with_garbage"]),
        "X-Capped": str(summary["capped_at_max_frames"]),
    }
    return Response(content=gif_bytes, media_type="image/gif", headers=headers)


@router.post("/detect/video", response_model=IncidentOut)
async def detect_video(
    request: Request,
    file: UploadFile = File(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    address: str | None = Form(None),
    imgsz: int | None = Form(None),
    max_frames: int = Form(24),
    db: Session = Depends(get_db),
) -> IncidentOut:
    """Detect garbage in an uploaded video and store a single aggregated incident.

    Frames are sampled evenly (``max_frames``, capped 1-120), each run through
    the detector; the frame with the most detections represents the incident.
    """
    detector = _get_detector(request)
    provider = _get_provider(request)
    imgsz = _validate_imgsz(imgsz)
    if max_frames < 1 or max_frames > 120:
        raise HTTPException(
            status_code=422, detail="max_frames must be between 1 and 120"
        )
    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    incident = process_video(
        video_bytes,
        file.filename,
        detector,
        provider,
        db,
        lat,
        lon,
        address,
        imgsz,
        max_frames,
    )
    return IncidentOut.model_validate(incident)


@router.post("/detect/batch", response_model=list[IncidentOut])
async def detect_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    imgsz: int | None = Form(None),
    db: Session = Depends(get_db),
) -> list[IncidentOut]:
    """Detect garbage across multiple images and store incidents."""
    detector = _get_detector(request)
    provider = _get_provider(request)
    imgsz = _validate_imgsz(imgsz)
    out: list[IncidentOut] = []
    for file in files:
        image_bytes = await file.read()
        if not image_bytes:
            logger.warning("Skipping empty upload %r", file.filename)
            continue
        incident = process_image(
            image_bytes, file.filename, detector, provider, db, imgsz=imgsz
        )
        out.append(IncidentOut.model_validate(incident))
    return out
