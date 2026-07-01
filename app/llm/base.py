"""Provider abstraction and factory for incident-report generation.

Vendor-agnostic: providers register themselves in ``_REGISTRY`` under a name,
and ``get_provider()`` instantiates the one named by ``settings.LLM_PROVIDER``.
Adding a new backend (OpenAI, Anthropic, vLLM, ...) is a matter of writing an
``AIProvider`` subclass and calling ``register_provider("name", factory)`` --
no changes to callers. Two backends ship today: ``ollama`` (local LLM) and
``rules`` (deterministic, no LLM required).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict

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


# name -> zero-arg factory returning an AIProvider. Populated by register_provider.
_REGISTRY: Dict[str, Callable[[], AIProvider]] = {}


def register_provider(name: str, factory: Callable[[], AIProvider]) -> None:
    """Register a provider factory under a lowercase name."""
    _REGISTRY[name.lower()] = factory


def _build_ollama() -> AIProvider:
    from .ollama_provider import OllamaProvider

    return OllamaProvider()


def _build_rules() -> AIProvider:
    from .rules_provider import RulesProvider

    return RulesProvider()


register_provider("ollama", _build_ollama)
register_provider("rules", _build_rules)


def get_provider() -> AIProvider:
    """Return the provider named by settings.LLM_PROVIDER (default ollama).

    Unknown names fall back to ``ollama`` with a warning so a typo can't take
    the service down; ``ollama`` itself degrades to deterministic rules if the
    LLM is unreachable.
    """
    name = (settings.LLM_PROVIDER or "ollama").lower()
    factory = _REGISTRY.get(name)
    if factory is None:
        logger.warning(
            "Unknown LLM_PROVIDER %r; known=%s; defaulting to 'ollama'",
            name, sorted(_REGISTRY),
        )
        factory = _REGISTRY["ollama"]
    return factory()
