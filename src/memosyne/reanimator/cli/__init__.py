"""
Reanimator CLI Layer

The outermost layer that handles user interaction and dependency injection.

Entry point:
    python -m memosyne.reanimator.cli.main
"""
from .main import main

__all__ = ["main"]
