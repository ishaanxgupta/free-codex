"""Cerebras Inference (OpenAI-compatible) adapter."""

from free_codex.providers.defaults import CEREBRAS_DEFAULT_BASE

from .client import CerebrasProvider

__all__ = ["CEREBRAS_DEFAULT_BASE", "CerebrasProvider"]
