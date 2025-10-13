"""
Shared CLI Utilities

Following DDD principles:
- Cross-cutting CLI concerns (prompts, validation)
- Reusable across bounded contexts
"""
from .prompts import ask

__all__ = ["ask"]
