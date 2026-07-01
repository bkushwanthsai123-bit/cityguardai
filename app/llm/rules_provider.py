"""Deterministic, LLM-free incident-report provider.

Wraps the rule engine (``rules.build_report``) as an ``AIProvider`` so the
system can run with zero external dependencies (no Ollama, no network). Select
it with ``LLM_PROVIDER=rules``. Useful for offline demos, CI, and as a
guaranteed fallback backend.
"""

from __future__ import annotations

from . import rules
from .base import AIProvider
from ..schemas import DetectionResult, IncidentReport


class RulesProvider(AIProvider):
    """Generate incident reports purely from the deterministic rule engine."""

    def generate_report(
        self, result: DetectionResult, context: dict
    ) -> IncidentReport:
        return rules.build_report(result, context)

    def ping(self) -> bool:  # parity with OllamaProvider for /health
        """Always available -- no external dependency."""
        return True
