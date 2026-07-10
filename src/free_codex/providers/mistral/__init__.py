"""Mistral La Plateforme provider exports."""

from free_codex.providers.defaults import MISTRAL_DEFAULT_BASE

from .client import MistralProvider

__all__ = ["MISTRAL_DEFAULT_BASE", "MistralProvider"]
