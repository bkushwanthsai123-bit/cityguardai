"""Incident CRUD and filtering endpoints."""

from __future__ import annotations

import logging
from datetime import datetime

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident
from ..schemas import IncidentOut, IncidentUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    department: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[IncidentOut]:
    """List incidents with optional filters, newest first."""
    stmt = select(Incident)
    if department is not None:
        stmt = stmt.where(Incident.department == department)
    if severity is not None:
        stmt = stmt.where(Incident.severity == severity)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if priority is not None:
        stmt = stmt.where(Incident.priority == priority)
    if date_from is not None:
        stmt = stmt.where(Incident.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Incident.created_at <= date_to)
    if min_lat is not None:
        stmt = stmt.where(Incident.lat >= min_lat)
    if max_lat is not None:
        stmt = stmt.where(Incident.lat <= max_lat)
    if min_lon is not None:
        stmt = stmt.where(Incident.lon >= min_lon)
    if max_lon is not None:
        stmt = stmt.where(Incident.lon <= max_lon)

    stmt = stmt.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [IncidentOut.model_validate(r) for r in rows]


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: int, db: Session = Depends(get_db)
) -> IncidentOut:
    """Fetch a single incident by id."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentOut.model_validate(incident)


@router.get("/{incident_id}/annotated")
def get_incident_annotated(
    incident_id: int, db: Session = Depends(get_db)
) -> FileResponse:
    """Serve the incident's annotated media (boxes drawn) — a .jpg or .gif.

    This is generated once when the incident is created (image or video), so
    the dashboard can display it without re-running inference.
    """
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    path = incident.annotated_path
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="No annotated media for this incident")
    media_type = "image/gif" if path.lower().endswith(".gif") else "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
) -> IncidentOut:
    """Update an incident's status."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = payload.status
    db.commit()
    db.refresh(incident)
    return IncidentOut.model_validate(incident)


@router.delete("/{incident_id}")
def delete_incident(
    incident_id: int, db: Session = Depends(get_db)
) -> dict:
    """Delete an incident by id."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    db.delete(incident)
    db.commit()
    return {"deleted": True}
