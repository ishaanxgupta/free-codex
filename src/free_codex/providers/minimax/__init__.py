"""MiniMax provider exports."""

from free_codex.providers.defaults import MINIMAX_DEFAULT_BASE

from .client import MiniMaxProvider

__all__ = [
    "MINIMAX_DEFAULT_BASE",
    "MiniMaxProvider",
]
