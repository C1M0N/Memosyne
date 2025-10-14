"""
Lithoformer Application Ports - Port interfaces (Dependency Inversion)
"""
from typing import Protocol, runtime_checkable
from pathlib import Path

from ..domain.models import QuizItem


@runtime_checkable
class LLMPort(Protocol):
    """LLM calling capability (implemented by Infrastructure)"""

    def parse_question(self, payload: dict[str, str]) -> tuple[dict, dict]:
        """
        Analyse a single quiz question using LLM

        Args:
            payload: Dict containing context/question/answer texts

        Returns:
            (question_dict, token_usage_dict)

        Raises:
            LLMError: LLM call failed
        """
        ...


@runtime_checkable
class FileRepositoryPort(Protocol):
    """File storage capability (implemented by Infrastructure)"""

    def read_markdown(self, path: Path) -> str:
        """Read markdown file"""
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write text file"""
        ...


@runtime_checkable
class FormatterPort(Protocol):
    """Quiz formatter capability"""

    def format(
        self,
        items: list[QuizItem],
        title_main: str,
        title_sub: str = ""
    ) -> str:
        """Format quiz items to output text"""
        ...
