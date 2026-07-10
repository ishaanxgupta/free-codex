"""Mistral Codestral provider (codestral.mistral.ai) exports."""

from free_codex.providers.defaults import CODESTRAL_DEFAULT_BASE

from .client import CodestralProvider

__all__ = ["CODESTRAL_DEFAULT_BASE", "CodestralProvider"]
