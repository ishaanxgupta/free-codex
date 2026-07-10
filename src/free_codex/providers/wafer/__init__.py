"""Wafer provider exports."""

from free_codex.providers.defaults import WAFER_DEFAULT_BASE

from .client import WaferProvider

__all__ = [
    "WAFER_DEFAULT_BASE",
    "WaferProvider",
]
