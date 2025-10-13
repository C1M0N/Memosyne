"""
Lithoformer Application Use Cases
"""
from tqdm import tqdm

from ..domain.models import QuizResponse, QuizItem
from ..domain.services import is_quiz_item_valid
from .ports import LLMPort

# 导入核心模型
from ...core.models import ProcessResult, TokenUsage


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
        # Call LLM (through port)
        llm_dict, token_dict = self.llm.parse_quiz(markdown)

        # Convert to domain model
        response = QuizResponse(**llm_dict)

        # Convert token dict to TokenUsage
        tokens = TokenUsage(**token_dict)

        items = response.items or []
        total = len(items)
        valid_items: list[QuizItem] = []

        progress = None
        if show_progress and total > 0:
            progress = tqdm(
                total=total,
                desc=f"Validating quiz items [Tokens: {tokens.total_tokens:,}]",
                ncols=100,
                ascii=True,
                mininterval=0.0,
                smoothing=0.0,
                unit="item",
            )
            progress.update(0)

        try:
            for item in items:
                if is_quiz_item_valid(item):
                    valid_items.append(item)
                if progress is not None:
                    progress.update(1)
        finally:
            if progress is not None:
                progress.close()

        return ProcessResult(
            items=valid_items,
            success_count=len(valid_items),
            total_count=len(response.items),
            token_usage=tokens,
        )
