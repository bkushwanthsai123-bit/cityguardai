"""Provider abstraction and factory for incident-report generation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import settings
from ..schemas import DetectionResult, IncidentReport

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract incident-report generator."""

    @abstractmethod
    def generate_report(
        self, result: DetectionResult, context: dict
    ) -> IncidentReport:
        """Generate a validated IncidentReport for a detection result."""
        raise NotImplementedError


def get_provider() -> AIProvider:
    """Return a provider based on settings.LLM_PROVIDER (default ollama)."""
    provider = (settings.LLM_PROVIDER or "ollama").lower()
    if provider == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider()
    logger.warning("Unknown LLM_PROVIDER %r; defaulting to ollama", provider)
    from .ollama_provider import OllamaProvider

    return OllamaProvider()
