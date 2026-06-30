"""Deterministic scoring/routing rules. The numbers always come from here."""

from __future__ import annotations

from ..schemas import DetectionResult, IncidentReport

# Class severity weights, keyed by the detection model's waste classes.
CLASS_WEIGHTS: dict[str, float] = {
    "Waste": 1.0,
    "Glass": 0.8,
    "Metal": 0.6,
    "Plastic": 0.6,
    "Paper": 0.4,
}

# Department routing per class.
DEPARTMENT_BY_CLASS: dict[str, str] = {
    "Waste": "Solid Waste Management",
    "Glass": "Solid Waste Management",
    "Metal": "Solid Waste Management",
    "Plastic": "Sanitation Department",
    "Paper": "Street Cleaning / Public Health",
}

DEFAULT_DEPARTMENT = "Solid Waste Management"

SLA_BY_PRIORITY: dict[str, int] = {"P1": 4, "P2": 12, "P3": 24, "P4": 72}


def compute_severity(result: DetectionResult) -> tuple[int, str]:
    """Return (severity_score 0-100, band) from detections.

    score = min(100, round(100 * sum(weight * area_fraction) + 5 * count_bonus))
    count_bonus = min(detection_count, 5).
    """
    weighted = sum(
        CLASS_WEIGHTS.get(d.class_name, 0.0) * max(0.0, d.area_fraction)
        for d in result.detections
    )
    count_bonus = min(len(result.detections), 5)
    score = min(100, round(100 * weighted + 5 * count_bonus))
    score = max(0, int(score))
    return score, band_for(score)


def band_for(score: int) -> str:
    """Map a 0-100 score onto a severity band."""
    if score <= 25:
        return "low"
    if score <= 50:
        return "medium"
    if score <= 75:
        return "high"
    return "critical"


def pick_department(result: DetectionResult) -> str:
    """Route to the department of the highest-weight class present."""
    best_class: str | None = None
    best_weight = -1.0
    for d in result.detections:
        w = CLASS_WEIGHTS.get(d.class_name, 0.0)
        if w > best_weight:
            best_weight = w
            best_class = d.class_name
    if best_class is None:
        return DEFAULT_DEPARTMENT
    return DEPARTMENT_BY_CLASS.get(best_class, DEFAULT_DEPARTMENT)


def priority_for(band: str) -> str:
    """Map a severity band onto an operational priority."""
    return {
        "critical": "P1",
        "high": "P2",
        "medium": "P3",
        "low": "P4",
    }.get(band, "P4")


def sla_for(priority: str) -> int:
    """Return the SLA in hours for a priority."""
    return SLA_BY_PRIORITY.get(priority, 72)


def enforce(report: IncidentReport, result: DetectionResult) -> IncidentReport:
    """Clamp/override the numeric + routing fields of an LLM report.

    The LLM may only supply title/description/recommended_action; everything
    else is recomputed deterministically so values can never drift.
    """
    score, band = compute_severity(result)
    priority = priority_for(band)
    return report.model_copy(
        update={
            "severity": band,
            "severity_score": score,
            "priority": priority,
            "department": pick_department(result),
            "sla_hours": sla_for(priority),
        }
    )


def build_report(result: DetectionResult, context: dict) -> IncidentReport:
    """Full deterministic fallback report (no LLM)."""
    score, band = compute_severity(result)
    priority = priority_for(band)
    department = pick_department(result)
    classes = sorted({d.class_name for d in result.detections})
    count = len(result.detections)

    if count == 0:
        title = "No garbage detected"
        description = "No illegal dumping objects were detected in the image."
        action = "No action required. Verify camera coverage if expected."
    else:
        label = ", ".join(classes) if classes else "garbage"
        title = f"{band.capitalize()} severity: {label}"
        description = (
            f"Detected {count} object(s) ({label}) indicating illegal garbage "
            f"dumping. Estimated severity {score}/100 ({band})."
        )
        action = (
            f"Dispatch {department} for cleanup within {sla_for(priority)} hours "
            f"({priority})."
        )

    addr = context.get("address")
    if addr:
        description = f"{description} Location: {addr}."

    return IncidentReport(
        title=title,
        description=description,
        severity=band,
        severity_score=score,
        priority=priority,
        department=department,
        recommended_action=action,
        sla_hours=sla_for(priority),
    )
