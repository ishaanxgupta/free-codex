"""Groq Cloud (OpenAI-compat) adapter."""

from free_codex.providers.defaults import GROQ_DEFAULT_BASE

from .client import GroqProvider

__all__ = ["GROQ_DEFAULT_BASE", "GroqProvider"]
