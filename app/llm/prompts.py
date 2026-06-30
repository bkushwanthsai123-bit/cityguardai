"""Prompt construction for the LLM incident-report layer."""

from __future__ import annotations

import json

from ..schemas import DetectionResult

SYSTEM_PROMPT = (
    "You are an assistant for a Smart City illegal garbage dumping detection "
    "system. Given object-detection results from a street image, write a concise "
    "municipal incident report. Respond with STRICT JSON ONLY (no prose, no "
    "markdown fences) matching this exact schema:\n"
    '{\n'
    '  "title": str,\n'
    '  "description": str,\n'
    '  "severity": "low" | "medium" | "high" | "critical",\n'
    '  "severity_score": int (0-100),\n'
    '  "priority": "P1" | "P2" | "P3" | "P4",\n'
    '  "department": str,\n'
    '  "recommended_action": str,\n'
    '  "sla_hours": int\n'
    '}\n'
    "Focus on a clear, actionable title; a factual description; and a specific "
    "recommended_action. The system will recompute the numeric and routing "
    "fields, so prioritise accurate text."
)

# One few-shot example to anchor the JSON format.
FEW_SHOT_USER = (
    "Detections: 2 garbage_pile (conf 0.82, 0.77), 1 overflowing_bin (conf 0.65). "
    "Image 1280x720. Location: MG Road, Bengaluru."
)
FEW_SHOT_ASSISTANT = json.dumps(
    {
        "title": "Large garbage pile beside overflowing bin on MG Road",
        "description": (
            "Two sizeable garbage piles and an overflowing public bin detected on "
            "MG Road, posing a sanitation and public-health hazard."
        ),
        "severity": "high",
        "severity_score": 68,
        "priority": "P2",
        "department": "Solid Waste Management",
        "recommended_action": (
            "Dispatch a Solid Waste Management cleanup crew within 12 hours and "
            "service the overflowing bin."
        ),
        "sla_hours": 12,
    }
)


def _summarize(result: DetectionResult) -> str:
    """Produce a compact human-readable detection summary."""
    if not result.detections:
        return "No objects detected."
    counts: dict[str, int] = {}
    for d in result.detections:
        counts[d.class_name] = counts.get(d.class_name, 0) + 1
    parts = [f"{n} {name}" for name, n in sorted(counts.items())]
    return ", ".join(parts)


def build_user_prompt(result: DetectionResult, context: dict) -> str:
    """Build the user turn describing detections and geo context."""
    summary = _summarize(result)
    loc_bits = []
    if context.get("address"):
        loc_bits.append(f"Address: {context['address']}")
    if context.get("lat") is not None and context.get("lon") is not None:
        loc_bits.append(f"Coords: {context['lat']:.5f},{context['lon']:.5f}")
    location = (" " + "; ".join(loc_bits)) if loc_bits else ""
    return (
        f"Detections: {summary}. "
        f"Image {result.image_width}x{result.image_height}, "
        f"{len(result.detections)} object(s).{location} "
        "Return STRICT JSON only."
    )


def build_messages(result: DetectionResult, context: dict) -> list[dict]:
    """Build the chat-format message list for Ollama /api/chat."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": FEW_SHOT_USER},
        {"role": "assistant", "content": FEW_SHOT_ASSISTANT},
        {"role": "user", "content": build_user_prompt(result, context)},
    ]
