"""
Lithoformer Application Use Cases
"""

import re
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, Iterator, Literal

from ..domain.models import QuizItem
from ..domain.services import (
    is_quiz_item_valid,
    split_markdown_into_questions,
)
from .ports import LLMPort

# 导入核心模型
from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress, indeterminate_progress


@dataclass(slots=True)
class QuizProcessingEvent:
    """
    单题解析事件，供流式消费（如 TUI）使用。

    Attributes:
        index: 当前题目的序号（从 1 开始）
        total: 总题数
        status: 解析结果状态
        item: 解析成功时的 QuizItem
        block: 原始题目块内容（context/question/answer）
        tokens: 当前题目的 Token 消耗
        total_tokens: 截至当前的 Token 累计值
        error: 解析失败原因
        elapsed: 本题耗时（秒）
    """

    index: int
    total: int
    status: Literal["success", "invalid", "error"]
    item: QuizItem | None
    block: dict[str, str]
    tokens: TokenUsage
    total_tokens: TokenUsage
    error: str | None
    elapsed: float


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
        question_blocks = self._split_markdown(markdown)
        total_count = len(question_blocks)
        valid_items: list[QuizItem] = []
        token_snapshot = TokenUsage()

        with Progress(
            total=total_count,
            desc="Validating quiz items [Tokens: 0]",
            unit="item",
            enabled=show_progress,
        ) as progress:
            for event in self._stream_blocks(
                question_blocks,
                show_spinner=show_progress,
            ):
                token_snapshot = event.total_tokens
                desc = (
                    f"Validating quiz items "
                    f"[{event.index}/{event.total}] "
                    f"[Tokens: {event.total_tokens.total_tokens:,}]"
                )
                if show_progress and progress:
                    progress.advance(desc=desc)

                if event.status == "success" and event.item:
                    valid_items.append(event.item)
                    if show_progress and progress and event.item.analysis:
                        progress.set_postfix(领域=event.item.analysis.domain)
                elif event.status != "success" and show_progress and progress:
                    progress.set_postfix(错误=event.error or "解析失败")

        return ProcessResult(
            items=valid_items,
            success_count=len(valid_items),
            total_count=total_count,
            token_usage=token_snapshot,
        )

    def stream(self, markdown: str) -> Iterable[QuizProcessingEvent]:
        """
        逐题解析 Markdown，生成流式事件。

        用于 TUI 等需要实时反馈的场景。

        Args:
            markdown: Quiz markdown content

        Yields:
            QuizProcessingEvent
        """
        question_blocks = self._split_markdown(markdown)
        yield from self._stream_blocks(question_blocks)

    @staticmethod
    def _split_markdown(markdown: str) -> list[dict[str, str]]:
        question_blocks = split_markdown_into_questions(markdown)
        if not question_blocks:
            raise ValueError("未在 Markdown 中解析到任何题目内容")
        return question_blocks

    def process_block(
        self,
        block: dict[str, str],
        index: int,
        total_count: int,
        total_tokens: TokenUsage,
        *,
        show_spinner: bool = False,
    ) -> tuple[QuizProcessingEvent, TokenUsage]:
        """
        处理单个题目块，返回事件和累积 Token。

        提供给 TUI 等外部组件复用，以便插入自定义的进度控制。
        """
        start_time = perf_counter()
        status: Literal["success", "invalid", "error"]
        item: QuizItem | None = None
        error_message: str | None = None
        token_usage = TokenUsage()

        try:
            with indeterminate_progress(
                f"Calling LLM for item #{index}...",
                enabled=show_spinner,
            ):
                item_dict, token_dict = self.llm.parse_question(
                    {
                        "context": block.get("context", ""),
                        "question": block.get("question", ""),
                        "answer": block.get("answer", ""),
                        "index": str(index),
                    }
                )

            token_usage = TokenUsage(**token_dict)
            new_total_tokens = total_tokens + token_usage

            candidate = QuizItem(**_normalize_question_dict(item_dict))

            if is_quiz_item_valid(candidate):
                status = "success"
                item = candidate
            else:
                status = "invalid"
                error_message = "LLM 输出未通过业务规则校验"
        except Exception as exc:  # 捕获 LLMError 和其它异常
            status = "error"
            error_message = str(exc)
            new_total_tokens = total_tokens

        elapsed = perf_counter() - start_time

        event = QuizProcessingEvent(
            index=index,
            total=total_count,
            status=status,
            item=item,
            block=block,
            tokens=token_usage,
            total_tokens=new_total_tokens,
            error=error_message,
            elapsed=elapsed,
        )
        return event, new_total_tokens

    def _stream_blocks(
        self,
        blocks: list[dict[str, str]],
        *,
        show_spinner: bool = False,
    ) -> Iterator[QuizProcessingEvent]:
        """
        核心迭代逻辑，供 execute() 和 stream() 复用。
        """
        total_tokens = TokenUsage()
        total_count = len(blocks)

        for index, block in enumerate(blocks, start=1):
            event, total_tokens = self.process_block(
                block,
                index,
                total_count,
                total_tokens,
                show_spinner=show_spinner,
            )
            yield event


def _normalize_question_dict(data: dict) -> dict:
    """Ensure LLM output conforms to domain expectations."""
    result = dict(data)

    # Normalize qtype / answer casing
    qtype = (result.get("qtype") or "").strip().upper()
    if qtype:
        result["qtype"] = qtype

    answer = (result.get("answer") or "").strip()
    if qtype == "MCQ":
        letters = re.findall(r"[A-Fa-f]", answer)
        if letters:
            result["answer"] = "".join(ch.upper() for ch in letters)
        else:
            result["answer"] = answer.upper()
    elif qtype == "ORDER":
        result["answer"] = answer.upper()
    else:
        result["answer"] = answer

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

    # Ensure translations exist and align with base fields
    result["stem_translation"] = (result.get("stem_translation") or "").strip()

    steps = result.get("steps") or []
    steps_trans = result.get("steps_translation") or []
    if len(steps_trans) < len(steps):
        steps_trans = list(steps_trans) + [""] * (len(steps) - len(steps_trans))
    elif len(steps_trans) > len(steps):
        steps_trans = steps_trans[: len(steps)]
    result["steps_translation"] = [str(step).strip() for step in steps_trans]

    options_translation = result.get("options_translation") or {}
    normalized_options_translation = {}
    for key in ["A", "B", "C", "D", "E", "F"]:
        normalized_options_translation[key] = str(options_translation.get(key, "") or "").strip()
    result["options_translation"] = normalized_options_translation

    cloze_trans = result.get("cloze_answers_translation") or []
    cloze = result.get("cloze_answers") or []
    if len(cloze_trans) < len(cloze):
        cloze_trans = list(cloze_trans) + [""] * (len(cloze) - len(cloze_trans))
    elif len(cloze_trans) > len(cloze):
        cloze_trans = cloze_trans[: len(cloze)]
    result["cloze_answers_translation"] = [str(text).strip() for text in cloze_trans]

    return result
