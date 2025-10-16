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
        title_sub: str = "",
        *,
        batch_code: str = "",
        question_start: int | None = None,
        question_prefix: str = "L",
    ) -> str:
        """Format quiz items"""
        return self._formatter.format(
            items,
            title_main,
            title_sub,
            batch_code=batch_code,
            question_start=question_start,
            question_prefix=question_prefix,
        )

    @classmethod
    def create(cls) -> "FormatterAdapter":
        return cls()
