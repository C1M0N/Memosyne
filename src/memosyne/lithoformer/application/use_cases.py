"""
Lithoformer Application Use Cases
"""

from ..domain.models import QuizItem
from ..domain.services import (
    is_quiz_item_valid,
    split_markdown_into_questions,
)
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
        question_blocks = split_markdown_into_questions(markdown)
        if not question_blocks:
            raise ValueError("未在 Markdown 中解析到任何题目内容")

        valid_items: list[QuizItem] = []
        total_tokens = TokenUsage()

        with Progress(
            total=len(question_blocks),
            desc="Validating quiz items [Tokens: 0]",
            unit="item",
            enabled=show_progress,
        ) as progress:
            for index, block in enumerate(question_blocks, start=1):
                with indeterminate_progress(
                    f"Calling LLM for item #{index}...",
                    enabled=show_progress,
                ):
                    item_dict, token_dict = self.llm.parse_question({
                        "context": block.get("context", ""),
                        "question": block.get("question", ""),
                        "answer": block.get("answer", ""),
                        "index": str(index),
                    })

                tokens = TokenUsage(**token_dict)
                total_tokens = total_tokens + tokens

                item = QuizItem(**_normalize_question_dict(item_dict))

                if is_quiz_item_valid(item):
                    valid_items.append(item)
                    if show_progress and progress and item.analysis:
                        progress.set_postfix(领域=item.analysis.domain)
                total_display = len(question_blocks)
                progress.advance(
                    desc=(
                        f"Validating quiz items [{index}/{total_display}] "
                        f"[Tokens: {total_tokens.total_tokens:,}]"
                    )
                )

        return ProcessResult(
            items=valid_items,
            success_count=len(valid_items),
            total_count=len(question_blocks),
            token_usage=total_tokens,
        )


def _normalize_question_dict(data: dict) -> dict:
    """Ensure LLM output conforms to domain expectations."""
    result = dict(data)

    # Normalize qtype / answer casing
    qtype = (result.get("qtype") or "").strip().upper()
    if qtype:
        result["qtype"] = qtype

    answer = (result.get("answer") or "").strip()
    result["answer"] = answer.upper()

    # Ensure options keys exist and strip whitespace
    options = result.get("options") or {}
    for key in ["A", "B", "C", "D", "E", "F"]:
        value = options.get(key, "")
        if value is None:
            value = ""
        options[key] = str(value).strip()
    result["options"] = options

    # Normalize analysis block
    analysis = result.get("analysis")
    if isinstance(analysis, dict):
        analysis["domain"] = (analysis.get("domain") or "").strip()
        analysis["rationale"] = (analysis.get("rationale") or "").strip()

        key_points = []
        for point in analysis.get("key_points") or []:
            text = str(point).strip()
            if text:
                key_points.append(text)
        analysis["key_points"] = key_points

        distractors = []
        for dist in analysis.get("distractors") or []:
            if not isinstance(dist, dict):
                continue
            option = (dist.get("option") or "").strip().upper()
            reason = (dist.get("reason") or "").strip()
            if option or reason:
                distractors.append({"option": option, "reason": reason})
        analysis["distractors"] = distractors

        result["analysis"] = analysis

    return result
