"""Lithoformer Infrastructure - Formatter Adapter"""
from ..domain.models import QuizItem
from .formatters.quiz_formatter import QuizFormatter


class FormatterAdapter:
    """Formatter adapter (implements FormatterPort)"""

    def __init__(self):
        self._formatter = QuizFormatter()

    def format(
        self,
        items: list[QuizItem],
        title_main: str,
        title_sub: str = ""
    ) -> str:
        """Format quiz items"""
        return self._formatter.format(items, title_main, title_sub)

    @classmethod
    def create(cls) -> "FormatterAdapter":
        return cls()
