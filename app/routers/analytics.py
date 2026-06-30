"""Analytics endpoints: summary aggregates and geographic hotspots."""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Incident

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Severity ordering for picking a hotspot's top severity.
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _count_by(db: Session, column) -> dict[str, int]:
    """Return a {value: count} map grouped by a column."""
    rows = db.execute(
        select(column, func.count()).group_by(column)
    ).all()
    return {str(value): int(count) for value, count in rows}


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    """Aggregate counts by severity/department/status/priority plus a trend."""
    total = db.execute(select(func.count()).select_from(Incident)).scalar_one()

    trend_rows = db.execute(
        select(
            func.date(Incident.created_at).label("d"),
            func.count().label("c"),
        )
        .group_by("d")
        .order_by("d")
    ).all()
    trend = [{"date": str(d), "count": int(c)} for d, c in trend_rows]

    return {
        "total": int(total),
        "by_severity": _count_by(db, Incident.severity),
        "by_department": _count_by(db, Incident.department),
        "by_status": _count_by(db, Incident.status),
        "by_priority": _count_by(db, Incident.priority),
        "trend": trend,
    }


@router.get("/hotspots")
def hotspots(
    db: Session = Depends(get_db),
    precision: int = Query(3, ge=1, le=6),
) -> list[dict]:
    """Cluster incidents by rounded lat/lon and report counts + top severity."""
    stmt = select(Incident.lat, Incident.lon, Incident.severity).where(
        Incident.lat.is_not(None), Incident.lon.is_not(None)
    )
    rows = db.execute(stmt).all()

    buckets: dict[tuple[float, float], dict] = defaultdict(
        lambda: {"count": 0, "top_severity": "low"}
    )
    for lat, lon, severity in rows:
        key = (round(float(lat), precision), round(float(lon), precision))
        bucket = buckets[key]
        bucket["count"] += 1
        if _SEVERITY_RANK.get(severity, 0) > _SEVERITY_RANK.get(
            bucket["top_severity"], 0
        ):
            bucket["top_severity"] = severity

    result = [
        {
            "lat": key[0],
            "lon": key[1],
            "count": b["count"],
            "top_severity": b["top_severity"],
        }
        for key, b in buckets.items()
    ]
    result.sort(key=lambda h: h["count"], reverse=True)
    return result
