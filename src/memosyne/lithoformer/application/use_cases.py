"""
Lithoformer Application Use Cases
"""

from ..domain.models import QuizResponse, QuizItem
from ..domain.services import is_quiz_item_valid
from .ports import LLMPort

# 导入核心模型
from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress, indeterminate_progress


class ParseQuizUseCase:
    """
    Parse Quiz Use Case (main business workflow)

    Workflow:
    1. Receive markdown content
    2. Call LLM to parse quiz
    3. Filter valid items
    4. Return processing result
    """

    def __init__(self, llm: LLMPort):
        """
        Args:
            llm: LLM port (injected by Infrastructure)
        """
        self.llm = llm

    def execute(
        self,
        markdown: str,
        show_progress: bool = True,
    ) -> ProcessResult[QuizItem]:
        """
        Execute use case: parse quiz markdown

        Args:
            markdown: Quiz markdown content
            show_progress: Whether to show progress

        Returns:
            ProcessResult[QuizItem]

        Raises:
            LLMError: LLM call failed
        """
        with indeterminate_progress("Calling LLM...", enabled=show_progress):
            llm_dict, token_dict = self.llm.parse_quiz(markdown)

        # Convert to domain model
        response = QuizResponse(**llm_dict)

        # Convert token dict to TokenUsage
        tokens = TokenUsage(**token_dict)

        items = response.items or []
        total = len(items)
        valid_items: list[QuizItem] = []

        with Progress(
            total=total if total else None,
            desc="Validating quiz items [Tokens: 0]",
            unit="item",
            enabled=show_progress,
        ) as progress:
            for index, item in enumerate(items, start=1):
                if is_quiz_item_valid(item):
                    valid_items.append(item)
                total_display = total if total else index
                progress.advance(
                    desc=f"Validating quiz items [{index}/{total_display}] [Tokens: {tokens.total_tokens:,}]"
                )

        return ProcessResult(
            items=valid_items,
            success_count=len(valid_items),
            total_count=len(response.items),
            token_usage=tokens,
        )
