"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Incident(Base):
    """A detected illegal garbage dumping incident."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False, index=True
    )
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # Media with YOLO boxes/labels drawn on it: annotated .jpg for images,
    # annotated .mp4 for videos. Nullable for pre-annotation incidents.
    annotated_path: Mapped[str | None] = mapped_column(String, nullable=True)

    detections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    num_detections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    classes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    lat: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False, index=True)
    department: Mapped[str] = mapped_column(String, nullable=False, index=True)
    recommended_action: Mapped[str] = mapped_column(String, nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String, default="open", nullable=False, index=True
    )
