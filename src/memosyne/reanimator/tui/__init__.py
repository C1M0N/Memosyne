"""Reanimator TUI package."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = ["ReanimatorApp", "main"]

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .app import ReanimatorApp, main


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("memosyne.reanimator.tui.app")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
