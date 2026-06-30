"""Detection endpoints: run YOLO -> LLM report -> persist incident."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..detector import Detector
from ..llm.base import AIProvider, get_provider
from ..models import Incident
from ..schemas import DetectionResult, IncidentOut

logger = logging.getLogger(__name__)

router = APIRouter(tags=["detection"])


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


def process_image(
    image_bytes: bytes,
    filename: str | None,
    detector: Detector,
    provider: AIProvider,
    db: Session,
    lat: float | None = None,
    lon: float | None = None,
    address: str | None = None,
) -> Incident:
    """Run detection + report generation and persist an Incident row."""
    image_path = _save_upload(image_bytes, filename)
    result: DetectionResult = detector.detect(image_bytes)

    context = {"lat": lat, "lon": lon, "address": address}
    report = provider.generate_report(result, context)

    classes = sorted({d.class_name for d in result.detections})
    incident = Incident(
        image_path=image_path,
        detections=[d.model_dump() for d in result.detections],
        num_detections=len(result.detections),
        classes=classes,
        lat=lat,
        lon=lon,
        address=address,
        title=report.title,
        description=report.description,
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


@router.post("/detect", response_model=IncidentOut)
async def detect(
    request: Request,
    file: UploadFile = File(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    address: str | None = Form(None),
    db: Session = Depends(get_db),
) -> IncidentOut:
    """Detect garbage in an uploaded image and store an incident."""
    detector = _get_detector(request)
    provider = _get_provider(request)
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty upload")
    incident = process_image(
        image_bytes, file.filename, detector, provider, db, lat, lon, address
    )
    return IncidentOut.model_validate(incident)


@router.post("/detect/batch", response_model=list[IncidentOut])
async def detect_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[IncidentOut]:
    """Detect garbage across multiple images and store incidents."""
    detector = _get_detector(request)
    provider = _get_provider(request)
    out: list[IncidentOut] = []
    for file in files:
        image_bytes = await file.read()
        if not image_bytes:
            logger.warning("Skipping empty upload %r", file.filename)
            continue
        incident = process_image(
            image_bytes, file.filename, detector, provider, db
        )
        out.append(IncidentOut.model_validate(incident))
    return out
