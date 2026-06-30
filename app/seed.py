"""Seed the database with demo incidents so the dashboard looks alive.

Run as a module:  python -m app.seed
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from .database import SessionLocal, init_db
from .llm import rules
from .models import Incident
from .schemas import Detection, DetectionResult

logger = logging.getLogger(__name__)

# Bengaluru city centre; demo incidents jitter around this point.
CENTER_LAT = 12.97
CENTER_LON = 77.59

_CLASSES = ["garbage_pile", "garbage_bag", "litter", "overflowing_bin"]
_STATUSES = ["open", "in_progress", "resolved"]
_ADDRESSES = [
    "MG Road", "Indiranagar 100ft Road", "Koramangala 5th Block",
    "Whitefield Main Road", "Jayanagar 4th Block", "Malleshwaram 8th Cross",
    "HSR Layout Sector 2", "BTM Layout 2nd Stage", "Marathahalli Bridge",
    "Electronic City Phase 1", "Yelahanka New Town", "Banashankari 2nd Stage",
    "Rajajinagar 1st Block", "Hebbal Flyover", "Bellandur Lake Road",
]


def _make_result(rng: random.Random) -> DetectionResult:
    """Build a synthetic detection result with 1-4 random boxes."""
    count = rng.randint(1, 4)
    detections: list[Detection] = []
    for _ in range(count):
        cls = rng.choice(_CLASSES)
        bw = rng.uniform(40, 320)
        bh = rng.uniform(40, 320)
        x1 = rng.uniform(0, 640 - bw)
        y1 = rng.uniform(0, 640 - bh)
        detections.append(
            Detection(
                class_name=cls,
                confidence=round(rng.uniform(0.3, 0.95), 3),
                bbox=[x1, y1, x1 + bw, y1 + bh],
                area_fraction=(bw * bh) / (640 * 640),
            )
        )
    return DetectionResult(
        detections=detections,
        image_width=640,
        image_height=640,
        inference_ms=round(rng.uniform(15, 90), 2),
    )


def seed(count: int = 15, seed_value: int = 42) -> int:
    """Insert `count` demo incidents. Returns the number inserted."""
    init_db()
    rng = random.Random(seed_value)
    inserted = 0

    with SessionLocal() as db:
        for i in range(count):
            result = _make_result(rng)
            address = _ADDRESSES[i % len(_ADDRESSES)]
            lat = CENTER_LAT + rng.uniform(-0.08, 0.08)
            lon = CENTER_LON + rng.uniform(-0.08, 0.08)
            context = {"lat": lat, "lon": lon, "address": address}
            report = rules.build_report(result, context)

            incident = Incident(
                created_at=datetime.now(timezone.utc)
                - timedelta(days=rng.randint(0, 14), hours=rng.randint(0, 23)),
                image_path=None,
                detections=[d.model_dump() for d in result.detections],
                num_detections=len(result.detections),
                classes=sorted({d.class_name for d in result.detections}),
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
                status=rng.choice(_STATUSES),
            )
            db.add(incident)
            inserted += 1
        db.commit()

    logger.info("Seeded %d demo incidents", inserted)
    return inserted


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    n = seed()
    print(f"Seeded {n} demo incidents.")


if __name__ == "__main__":
    main()
