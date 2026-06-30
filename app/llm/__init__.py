"""LLM layer: provider abstraction, deterministic rules, and prompts."""

from __future__ import annotations

from .base import AIProvider, get_provider

__all__ = ["AIProvider", "get_provider"]
