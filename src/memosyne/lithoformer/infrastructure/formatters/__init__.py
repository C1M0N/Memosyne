"""
Lithoformer Formatters

Following DDD principles:
- Domain-specific formatters belong in Infrastructure layer
- Not in Shared Kernel (must be context-agnostic)
"""
from .quiz_formatter import QuizFormatter

__all__ = ["QuizFormatter"]
