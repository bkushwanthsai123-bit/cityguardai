"""Ollama-backed incident-report provider with deterministic enforcement."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from ..config import settings
from ..schemas import DetectionResult, IncidentReport
from . import prompts, rules
from .base import AIProvider

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 60.0
_PING_TIMEOUT = 2.0


class OllamaProvider(AIProvider):
    """Calls Ollama in JSON mode; rules own all numeric/routing fields."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
    ) -> None:
        self.host = (host or settings.OLLAMA_HOST).rstrip("/")
        self.model = model or settings.LLM_MODEL

    def ping(self) -> bool:
        """Best-effort reachability check; never raises."""
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=_PING_TIMEOUT)
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.debug("Ollama ping failed: %s", exc)
            return False

    def _chat(self, messages: list[dict]) -> str:
        """Call Ollama /api/chat in JSON mode and return the content string."""
        payload = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "stream": False,
        }
        resp = httpx.post(
            f"{self.host}/api/chat", json=payload, timeout=_REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def _parse(self, content: str, result: DetectionResult) -> IncidentReport:
        """Parse + validate JSON content into an IncidentReport."""
        raw = json.loads(content)
        # Backfill numeric/routing fields so validation cannot fail on them;
        # rules.enforce will overwrite these regardless.
        score, band = rules.compute_severity(result)
        priority = rules.priority_for(band)
        raw.setdefault("severity", band)
        raw.setdefault("severity_score", score)
        raw.setdefault("priority", priority)
        raw.setdefault("department", rules.pick_department(result))
        raw.setdefault("recommended_action", "")
        raw.setdefault("sla_hours", rules.sla_for(priority))
        return IncidentReport.model_validate(raw)

    def generate_report(
        self, result: DetectionResult, context: dict
    ) -> IncidentReport:
        """Generate a report via Ollama; fall back to deterministic rules.

        Retries once on bad/invalid JSON. Falls back to rules.build_report on
        any transport error (Ollama unreachable). The numeric and routing
        fields are ALWAYS recomputed by rules.enforce.
        """
        messages = prompts.build_messages(result, context)

        last_err: Exception | None = None
        for attempt in (1, 2):
            try:
                content = self._chat(messages)
            except Exception as exc:  # noqa: BLE001 - transport failure -> fallback
                logger.warning(
                    "Ollama request failed (attempt %d): %s; using rules fallback",
                    attempt,
                    exc,
                )
                return rules.build_report(result, context)

            try:
                report = self._parse(content, result)
                return rules.enforce(report, result)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_err = exc
                logger.warning(
                    "Ollama returned invalid JSON (attempt %d): %s", attempt, exc
                )
                continue

        logger.error("Ollama JSON invalid after retry (%s); rules fallback", last_err)
        return rules.build_report(result, context)
