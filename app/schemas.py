"""Pydantic v2 schemas — field names are contract-locked."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
Priority = Literal["P1", "P2", "P3", "P4"]
Status = Literal["open", "in_progress", "resolved"]


class Detection(BaseModel):
    """A single object detection."""

    class_name: str
    confidence: float
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    area_fraction: float


class DetectionResult(BaseModel):
    """Raw detector output for one image."""

    detections: list[Detection]
    image_width: int
    image_height: int
    inference_ms: float


class IncidentReport(BaseModel):
    """Strict LLM-shaped incident report (numbers owned by rules)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    severity: Severity
    severity_score: int = Field(..., ge=0, le=100)
    priority: Priority
    department: str
    recommended_action: str
    sla_hours: int


class IncidentCreate(BaseModel):
    """Detection fields plus optional geo context for creating an incident."""

    detections: list[Detection]
    image_width: int
    image_height: int
    inference_ms: float
    lat: Optional[float] = None
    lon: Optional[float] = None
    address: Optional[str] = None


class IncidentUpdate(BaseModel):
    """Mutable fields on an incident."""

    status: Status


class IncidentOut(BaseModel):
    """Serialized incident row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    image_path: Optional[str] = None
    detections: list
    num_detections: int
    classes: list[str]
    lat: Optional[float] = None
    lon: Optional[float] = None
    address: Optional[str] = None
    title: str
    description: str
    severity: str
    severity_score: int
    priority: str
    department: str
    recommended_action: str
    sla_hours: int
    status: str
