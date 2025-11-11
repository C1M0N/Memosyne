"""
Lithoformer Application Use Cases
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Iterator, Literal, Sequence

from ..domain.models import QuizItem, FeatureConfig, OPTION_LETTERS
from ..domain.services import (
    is_quiz_item_valid,
    split_markdown_into_questions,
)
from .ports import LLMPort

# 导入核心模型和接口
from ...core.models import ProcessResult, TokenUsage
from ...core.interfaces import StatsRepository
from ...shared.utils import Progress, indeterminate_progress

# Logger
logger = logging.getLogger("memosyne.lithoformer.application")


# v1.9.1c: 字符计数工具函数
def _count_output_chars(d: dict) -> int:
    """递归计算字典中所有字符串的字符数（v1.9.1c: 用于output_char_count）

    只计算实际内容，不包含JSON格式化字符（缩进、换行、引号等）

    Args:
        d: 输出字典

    Returns:
        总字符数
    """
    total = 0
    for v in d.values():
        if isinstance(v, str):
            total += len(v)
        elif isinstance(v, dict):
            total += _count_output_chars(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    total += len(item)
                elif isinstance(item, dict):
                    total += _count_output_chars(item)
    return total


def _ensure_question_number(block: dict[str, str], index: int) -> str:
    """确保题目块中存在question_number字段。

    优先使用已有的question_number/number字段，若缺失则回退到index。
    """
    candidate = (block.get("question_number") or block.get("number") or "").strip()

    if not candidate:
        index_value = block.get("index")
        if isinstance(index_value, str) and index_value.strip().isdigit():
            candidate = index_value.strip()

    if not candidate:
        candidate = str(index if index > 0 else 1)

    block["question_number"] = candidate
    return candidate


def _extract_batch_id(output_filename: str | None) -> str:
    """从输出文件名中提取批次号（取第一个分段部分）。"""
    if not output_filename:
        return "default"

    stem = Path(output_filename).stem
    if not stem:
        return "default"

    # 分隔符可能包含下划线或连字符，仅取第一个片段作为批次号
    return re.split(r"[-_]", stem, maxsplit=1)[0]


@dataclass(slots=True)
class QuizProcessingEvent:
    """
    单题解析事件，供流式消费（如 TUI）使用。

    Attributes:
        index: 当前题目的序号（从 1 开始）
        total: 总题数
        status: 解析结果状态
            - success: 解析成功
            - invalid: 未通过业务规则校验
            - error: 解析失败
            - waiting_429: 遇到429错误，正在等待重试
            - processing: 正在处理中（LLM调用中）
        item: 解析成功时的 QuizItem
        block: 原始题目块内容（context/question/answer）
        tokens: 当前题目的 Token 消耗
        total_tokens: 截至当前的 Token 累计值
        error: 解析失败原因
        elapsed: 本题耗时（秒）
        retry_wait_remaining: 429等待剩余秒数（仅当status="waiting_429"时有值）
        rate_limit_info: rate limit信息（如果LLM provider提供）
    """

    index: int
    total: int
    status: Literal["success", "invalid", "error", "waiting_429", "processing"]
    item: QuizItem | None
    block: dict[str, str]
    tokens: TokenUsage
    total_tokens: TokenUsage
    error: str | None
    elapsed: float
    retry_wait_remaining: int | None = None  # 429等待剩余秒数
    rate_limit_info: dict | None = None  # rate limit信息


class ParseQuizUseCase:
    """
    Parse Quiz Use Case (main business workflow)

    Workflow:
    1. Receive markdown content
    2. Call LLM to parse quiz
    3. Filter valid items
    4. Return processing result
    5. Save processing stats (optional, v0.11+)
    """

    def __init__(
        self,
        llm: LLMPort,
        stats_repo: StatsRepository | None = None,
        feature_config: FeatureConfig | None = None,
        model_identifier: str = "",
        output_filename: str = "",
    ):
        """
        Args:
            llm: LLM port (injected by Infrastructure)
            stats_repo: 统计仓储（可选，用于保存性能数据）
            feature_config: 功能配置（可选，用于统计）
            model_identifier: 模型标识（格式：Provider::model）
            output_filename: 输出文件名
        """
        self.llm = llm
        self.stats_repo = stats_repo
        self.feature_config = feature_config
        self.model_identifier = model_identifier
        self.output_filename = output_filename

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
        note: str = "",
        show_spinner: bool = False,
    ) -> tuple[QuizProcessingEvent, TokenUsage]:
        """
        处理单个题目块，返回事件和累积 Token。

        提供给 TUI 等外部组件复用，以便插入自定义的进度控制。

        Args:
            block: 题目块字典（context, question, answer）
            index: 题目索引
            total_count: 总题目数
            total_tokens: 累积的token使用量
            note: 用户备注，会附加到user prompt后面
            show_spinner: 是否显示进度条
        """
        start_time = perf_counter()
        status: Literal["success", "invalid", "error"]
        item: QuizItem | None = None
        error_message: str | None = None
        token_usage = TokenUsage()
        rate_limit_info: dict | None = None

        try:
            with indeterminate_progress(
                f"Calling LLM for item #{index}...",
                enabled=show_spinner,
            ):
                item_dict, token_dict, rate_limit_info = self.llm.parse_question(
                    {
                        "context": block.get("context", ""),
                        "question": block.get("question", ""),
                        "answer": block.get("answer", ""),
                        "note": note,
                        "index": str(index),
                    }
                )

            token_usage = TokenUsage(**token_dict)
            new_total_tokens = total_tokens + token_usage

            candidate = QuizItem(**_normalize_question_dict(item_dict))

            if is_quiz_item_valid(candidate, self.feature_config):
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
            rate_limit_info=rate_limit_info,
        )

        # 保存统计数据（如果配置了stats_repo）
        if self.stats_repo and status == "success":
            self._save_stats(block, item_dict if status == "success" else {}, elapsed, token_usage, note)  # v1.9.1c: 传递note

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
            # 确保block中包含index与question_number（允许TUI/CLI共用）
            block["index"] = str(index)
            _ensure_question_number(block, index)
            event, total_tokens = self.process_block(
                block,
                index,
                total_count,
                total_tokens,
                show_spinner=show_spinner,
            )
            yield event

    def _save_stats(
        self,
        block: dict[str, str],
        output_dict: dict,
        processing_time: float,
        token_usage: TokenUsage,  # v1.9.1: 新增token_usage参数
        note: str = "",  # v1.9.1c: 新增note参数
    ) -> None:
        """
        保存处理统计数据到数据库（v1.9.0重构版）

        Args:
            block: 原始题目块
            output_dict: LLM输出字典
            processing_time: 处理时长（秒）
            token_usage: Token使用统计
            note: 用户备注（v1.9.1c新增）
        """
        if not self.stats_repo:
            return

        # 组装原始文本（v1.9.1c: 只计算原始内容，不包含标记文本）
        parts = []
        if block.get("context"):
            parts.append(block.get("context", ""))
        parts.append(block.get("question", ""))
        parts.append(block.get("answer", ""))
        original_text = "\n\n".join(parts)

        # 计算输出字符数（v1.9.1c: 只计算内容，不包含JSON格式字符）
        output_char_count = _count_output_chars(output_dict)

        # 组装输出文本（用于保存到bank）
        import json
        output_text = json.dumps(output_dict, ensure_ascii=False, indent=2)

        # 获取功能配置
        use_translation = self.feature_config.enable_translation if self.feature_config else True
        use_parsing = self.feature_config.enable_parsing if self.feature_config else True

        # 提取题型（如果有）
        # v1.9.1: 从"qtype"字段读取而不是"question_type"
        question_type = output_dict.get("qtype", None)

        # 统一question_number与batch_id（允许并发/CLI共用）
        index_hint = 0
        index_value = block.get("index")
        if isinstance(index_value, str) and index_value.isdigit():
            index_hint = int(index_value)
        question_number = _ensure_question_number(block, index_hint if index_hint > 0 else 1)
        batch_id = _extract_batch_id(self.output_filename)

        self.stats_repo.save_processing_log(
            question_number=question_number,
            batch_id=batch_id,
            model=self.model_identifier,
            input_char_count=len(original_text),
            use_translation=use_translation,
            use_parsing=use_parsing,
            note=note,  # v1.9.1c: 使用传入的note参数
            question_type=question_type,
            output_char_count=output_char_count,  # v1.9.1c: 使用计算好的字符数
            input_tokens=token_usage.input_tokens,  # v1.9.1: 从token_usage获取
            output_tokens=token_usage.output_tokens,  # v1.9.1: 从token_usage获取
            processing_time=processing_time,
            has_error=False,
        )

        # Phase 2: 自动保存到题库（如果题号不存在）
        # v1.9.2: 移除自动保存，改为由TUI层用户确认后保存
        # self._save_to_bank_if_new(
        #     question_number=question_number,
        #     batch_id=batch_id,
        #     original_text=original_text,
        #     output_text=output_text,
        #     use_translation=use_translation,
        #     use_parsing=use_parsing,
        # )

    def _save_to_bank_if_new(
        self,
        question_number: str,
        batch_id: str,
        original_text: str,
        output_text: str,
        use_translation: bool,
        use_parsing: bool,
    ) -> None:
        """保存到题库（如果题号不存在）

        Args:
            question_number: 题号
            batch_id: 批次ID
            original_text: 原始输入文本
            output_text: 输出文本
            use_translation: 是否使用翻译
            use_parsing: 是否使用解析
        """
        if not self.stats_repo or not question_number:
            return

        try:
            # 检查题号是否已存在
            if not self.stats_repo.check_bank_exists(question_number):
                self.stats_repo.save_to_bank(
                    question_number=question_number,
                    batch_id=batch_id,
                    model=self.model_identifier,
                    use_translation=use_translation,
                    use_parsing=use_parsing,
                    original_input=original_text[:50000],  # 限制长度
                    output=output_text[:50000],  # 限制长度
                    no_overwrite=False,  # 允许覆盖（但前面已检查不存在）
                )
        except Exception:
            # 题库保存失败不应影响主流程
            pass


def _normalize_question_dict(data: dict) -> dict:
    """Ensure LLM output conforms to domain expectations."""
    result = dict(data)

    # Normalize qtype / answer casing
    qtype = (result.get("qtype") or "").strip().upper()
    if qtype:
        result["qtype"] = qtype

    answer = (result.get("answer") or "").strip()
    if qtype == "MCQ":
        letters = re.findall(r"[A-Za-z]", answer)
        if letters:
            result["answer"] = "".join(ch.upper() for ch in letters)
        else:
            result["answer"] = answer.upper()
    else:
        result["answer"] = answer

    # Ensure options keys exist and strip whitespace
    options = result.get("options") or {}
    normalized_options = {}
    for key in OPTION_LETTERS:
        value = options.get(key, "")
        if value is None:
            value = ""
        normalized_options[key] = str(value).strip()
    # 保留原始额外键（如 LLM 新增的, 避免信息丢失）
    for key, value in options.items():
        if key not in normalized_options:
            normalized_options[key] = str(value or "").strip()
    result["options"] = normalized_options
    # 删除已弃用的步骤字段（ORDER 已移除）
    result.pop("steps", None)
    result.pop("steps_translation", None)

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
    elif isinstance(analysis, str):
        # LLM错误地返回了JSON字符串类型，尝试二次解析（双重保险）
        try:
            import json
            parsed_analysis = json.loads(analysis)
            if isinstance(parsed_analysis, dict):
                # 成功解析，递归应用normalize逻辑
                parsed_analysis["domain"] = (parsed_analysis.get("domain") or "").strip()
                parsed_analysis["rationale"] = (parsed_analysis.get("rationale") or "").strip()

                key_points = []
                for point in parsed_analysis.get("key_points") or []:
                    text = str(point).strip()
                    if text:
                        key_points.append(text)
                parsed_analysis["key_points"] = key_points

                distractors = []
                for dist in parsed_analysis.get("distractors") or []:
                    if not isinstance(dist, dict):
                        continue
                    option = (dist.get("option") or "").strip().upper()
                    reason = (dist.get("reason") or "").strip()
                    if option or reason:
                        distractors.append({"option": option, "reason": reason})
                parsed_analysis["distractors"] = distractors

                result["analysis"] = parsed_analysis
                logger.warning("LLM返回了字符串化的analysis，已成功二次解析并normalize")
            else:
                result["analysis"] = None
                logger.warning("二次解析analysis失败：解析结果不是对象")
        except (json.JSONDecodeError, TypeError) as e:
            result["analysis"] = None
            logger.warning(f"无法二次解析analysis字符串: {str(e)[:100]}")
    elif analysis is not None:
        # 其他非预期类型也设为None
        result["analysis"] = None
        logger.warning(f"LLM返回了非预期类型的analysis字段: {type(analysis).__name__}")

    # Ensure translations exist and align with base fields
    result["stem_translation"] = (result.get("stem_translation") or "").strip()

    options_translation = result.get("options_translation") or {}
    normalized_options_translation = {}
    for key in OPTION_LETTERS:
        normalized_options_translation[key] = str(options_translation.get(key, "") or "").strip()
    for key, value in options_translation.items():
        if key not in normalized_options_translation:
            normalized_options_translation[key] = str(value or "").strip()
    result["options_translation"] = normalized_options_translation

    cloze_trans = result.get("cloze_answers_translation") or []
    cloze = result.get("cloze_answers") or []
    if len(cloze_trans) < len(cloze):
        cloze_trans = list(cloze_trans) + [""] * (len(cloze) - len(cloze_trans))
    elif len(cloze_trans) > len(cloze):
        cloze_trans = cloze_trans[: len(cloze)]
    result["cloze_answers_translation"] = [str(text).strip() for text in cloze_trans]

    return result


class ConcurrentParseQuizUseCase:
    """
    并发解析Quiz Use Case (v0.11+)

    Workflow:
    1. 接收markdown内容
    2. 使用asyncio并发调用LLM解析题目
    3. 按题目编号排序结果
    4. 批量保存统计数据
    5. 返回处理结果

    Features:
    - 支持max_concurrent限制并发数
    - 失败重试（retry with exponential backoff）
    - 429错误使用指数退避（15秒起，每次翻倍，最长2分钟）
    - 添加随机抖动避免并发请求同时重试
    - 内存缓冲+排序保证顺序
    - 进度条按完成数更新
    """

    def __init__(
        self,
        llm: LLMPort,
        feature_config: FeatureConfig,
        stats_repo: StatsRepository | None = None,
        model_identifier: str = "",
        output_filename: str = "",
    ):
        """
        Args:
            llm: LLM port (injected by Infrastructure)
            feature_config: 功能配置（必填，用于获取并发数和重试次数）
            stats_repo: 统计仓储（可选）
            model_identifier: 模型标识
            output_filename: 输出文件名
        """
        from concurrent.futures import ThreadPoolExecutor

        self.llm = llm
        self.feature_config = feature_config
        self.stats_repo = stats_repo
        self.model_identifier = model_identifier
        self.output_filename = output_filename

        # 创建自定义线程池，支持真正的max_concurrent并发
        # （默认executor只有32个线程，无法支持更高并发）
        self._executor = ThreadPoolExecutor(
            max_workers=feature_config.max_concurrent,
            thread_name_prefix="LLMWorker",
        )

        # Tokens阈值优化：追踪正在处理的题目数（用于判断是否为最后一题）
        self._active_processing_count = 0
        self._count_lock = asyncio.Lock()

        # Rate limit manager引用（由外部设置）
        self._rate_limit_manager = None

    async def execute_async(
        self,
        markdown: str,
        *,
        question_numbers: Sequence[str | None] | None = None,
        show_progress: bool = True,
    ) -> ProcessResult[QuizItem]:
        """
        异步并发执行use case

        Args:
            markdown: Quiz markdown content
            show_progress: 是否显示进度
            on_event_callback: 每个题目处理完成时的回调函数（用于实时UI更新）

        Returns:
            ProcessResult[QuizItem]
        """
        import asyncio

        question_blocks = self._split_markdown(markdown)
        provided_numbers = list(question_numbers) if question_numbers is not None else None
        total_count = len(question_blocks)

        # 结果缓冲区（按index存储）
        results: dict[int, QuizProcessingEvent] = {}
        stats_buffer: list[dict] = []

        # 并发限制
        semaphore = asyncio.Semaphore(self.feature_config.max_concurrent)

        async def process_block_async(index: int, block: dict[str, str]):
            """异步处理单个题目块"""
            async with semaphore:
                event = await self._process_block_with_retry(
                    block=block,
                    index=index,
                    total_count=total_count,
                )
                results[index] = event

                # 如果成功且有stats_repo，加入统计缓冲
                if event.status == "success" and self.stats_repo and event.item:
                    stats_buffer.append(
                        self._build_stat_dict(block, event.item.model_dump(), event.elapsed, event.tokens)  # v1.9.1b: 添加tokens参数
                    )

        # 创建所有任务
        # question_number可由调用方提供，也允许在此回退
        tasks = []
        for index, block in enumerate(question_blocks, start=1):
            if provided_numbers and index - 1 < len(provided_numbers):
                candidate = provided_numbers[index - 1]
                if candidate:
                    block["question_number"] = candidate
            block["index"] = str(index)  # 保留index用于其他用途
            _ensure_question_number(block, index)
            tasks.append(process_block_async(index, block))

        # 并发执行
        await asyncio.gather(*tasks)

        # 批量保存统计（v1.9.0：使用循环调用新API）
        if self.stats_repo and stats_buffer:
            for stat_dict in stats_buffer:
                self.stats_repo.save_processing_log(**stat_dict)

        # 按index排序结果
        sorted_events = [results[i] for i in sorted(results.keys())]

        # 提取valid items
        valid_items = [event.item for event in sorted_events if event.item and event.status == "success"]

        # 计算总token
        total_tokens = TokenUsage()
        for event in sorted_events:
            total_tokens = total_tokens + event.tokens

        result = ProcessResult(
            items=valid_items,
            success_count=len(valid_items),
            total_count=total_count,
            token_usage=total_tokens,
        )

        # 将events存储为result的私有属性（用于TUI更新状态）
        result._events = sorted_events  # type: ignore

        return result

    async def stream_async(
        self,
        markdown: str,
        question_numbers: Sequence[str | None] | None = None,
    ):
        """
        并发流式事件接口：统一与顺序版的事件消费模式。

        Yields:
            QuizProcessingEvent（包括中间状态：processing, waiting_429等）
        """
        import asyncio

        question_blocks = self._split_markdown(markdown)
        provided_numbers = list(question_numbers) if question_numbers is not None else None
        total_count = len(question_blocks)

        semaphore = asyncio.Semaphore(self.feature_config.max_concurrent)
        event_queue: asyncio.Queue[QuizProcessingEvent] = asyncio.Queue()

        async def task_for(index: int, block: dict[str, str]):
            """处理单个题目，并将所有事件（包括中间状态）发送到queue"""
            async with semaphore:
                await self._process_block_with_retry(
                    block, index, total_count, event_queue, self._executor
                )

        # 创建所有任务并立即启动
        tasks = []
        for i, b in enumerate(question_blocks, start=1):
            if provided_numbers and i - 1 < len(provided_numbers):
                candidate = provided_numbers[i - 1]
                if candidate:
                    b["question_number"] = candidate
            b["index"] = str(i)  # 保留index用于其他用途
            _ensure_question_number(b, i)
            tasks.append(asyncio.create_task(task_for(i, b)))

        # 从queue中读取事件并yield给UI
        completed_count = 0
        while completed_count < total_count:
            event = await event_queue.get()
            yield event

            # 只有最终状态才计入完成数
            if event.status in ["success", "error", "invalid"]:
                completed_count += 1

        # 确保所有任务完成（应该已经完成了）
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_block_with_retry(
        self,
        block: dict[str, str],
        index: int,
        total_count: int,
        event_queue: asyncio.Queue,
        executor,
    ) -> None:
        """
        异步处理单个题目块（支持重试）

        注意：成功时会实时保存统计数据

        重试策略：
        - 429错误：无限重试（使用指数退避，最多100次），每秒发送倒计时事件
        - 其他错误：受max_retries限制

        Args:
            block: 题目块
            index: 题目索引
            total_count: 总题目数
            event_queue: 事件队列，用于发送中间状态和最终结果
            executor: 自定义ThreadPoolExecutor，支持真正的max_concurrent并发

        Returns:
            None（通过event_queue发送所有事件）
        """
        import asyncio
        from ...core.interfaces import LLMError
        from ...shared.infrastructure.app_config import SQLiteAppConfigService
        from ...shared.config import get_settings

        # 从数据库读取重试配置（不再硬编码）
        settings = get_settings()
        appcfg = SQLiteAppConfigService(settings.db_dir / "config.db")
        retry_config = appcfg.get_retry_config()

        max_retries = self.feature_config.max_retries
        retry_count = 0
        rate_limit_retry_count = 0  # 429错误单独计数
        max_rate_limit_retries = retry_config["rate_limit_max_retries"]  # 从数据库读取（默认100）
        # 单题处理超时时间（秒），默认180秒（3分钟）
        question_timeout_seconds = int(appcfg.get_config("question_timeout_seconds") or "1200")

        # 递增active_count（用于判断是否为最后一题）
        async with self._count_lock:
            self._active_processing_count += 1

        try:
            # 发送"processing"事件（开始处理）
            await event_queue.put(QuizProcessingEvent(
                index=index,
                total=total_count,
                status="processing",
                item=None,
                block=block,
                tokens=TokenUsage(),
                total_tokens=TokenUsage(),
                error=None,
                elapsed=0.0,
                retry_wait_remaining=None,
            ))

            while True:  # 无限循环，由内部逻辑控制退出
                try:
                    # Tokens阈值检查：如果tokens不足且不是最后一题，触发429重试
                    async with self._count_lock:
                        active_count = self._active_processing_count
                    is_last_pending = (active_count <= 1)

                    if not is_last_pending and self._rate_limit_manager:
                        # 不是最后一题，检查tokens阈值
                        current_info = self._rate_limit_manager.get_current_info()
                        if current_info:
                            remaining_tokens = current_info.get("remaining_tokens", float('inf'))
                            tokens_threshold = int(appcfg.get_config("tokens_threshold") or "5000")

                            if remaining_tokens < tokens_threshold:
                                # Tokens不足，模拟429错误，触发指数退避机制
                                raise LLMError(
                                    f"SIMULATED_429: tokens不足 (剩余{remaining_tokens} < 阈值{tokens_threshold})"
                                )
                    # 调用LLM（同步方法，需要在executor中运行）
                    # 注意：start_time必须在LLM调用之前记录，才能排除队列等待时间
                    loop = asyncio.get_event_loop()
                    start_time = perf_counter()  # 在executor调用前记录时间
                    parse_future = loop.run_in_executor(
                        executor,  # 使用自定义executor，支持max_concurrent并发
                        self.llm.parse_question,
                        {
                            "context": block.get("context", ""),
                            "question": block.get("question", ""),
                            "answer": block.get("answer", ""),
                            "note": "",
                            "index": str(index),
                        },
                    )
                    try:
                        item_dict, token_dict, rate_limit_info = await asyncio.wait_for(
                            parse_future,
                            timeout=question_timeout_seconds,
                        )
                    except asyncio.TimeoutError as timeout_exc:
                        raise TimeoutError(
                            f"LLM 处理超出 {question_timeout_seconds} 秒: {timeout_exc}"
                        ) from timeout_exc
                    elapsed = perf_counter() - start_time  # LLM调用后立即计算耗时

                    token_usage = TokenUsage(**token_dict)
                    candidate = QuizItem(**_normalize_question_dict(item_dict))

                    if is_quiz_item_valid(candidate, self.feature_config):
                        # 实时保存统计（异步环境下，实时保存比批量保存更合适）（v1.9.0：使用新API）
                        if self.stats_repo:
                            stat_dict = self._build_stat_dict(block, item_dict, elapsed, token_usage)  # v1.9.1: 传入token_usage
                            # 在asyncio环境中，使用线程池执行同步的数据库写入
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(
                                None,
                                lambda: self.stats_repo.save_processing_log(**stat_dict)
                            )

                            # Phase 2: 自动保存到题库（异步调用）
                            # v1.9.2: 移除自动保存，改为由TUI层用户确认后保存
                            # import json
                            # parts = []
                            # if block.get("context"):
                            #     parts.append(block.get("context", ""))
                            # parts.append(block.get("question", ""))
                            # parts.append(block.get("answer", ""))
                            # original_text = "\n\n".join(parts)
                            # output_text = json.dumps(item_dict, ensure_ascii=False, indent=2)
                            #
                            # await loop.run_in_executor(
                            #     None,
                            #     lambda: self._save_to_bank_if_new(
                            #         question_number=stat_dict["question_number"],
                            #         batch_id=stat_dict["batch_id"],
                            #         original_text=original_text,
                            #         output_text=output_text,
                            #         use_translation=stat_dict["use_translation"],
                            #         use_parsing=stat_dict["use_parsing"],
                            #     )
                            # )

                        # 发送成功事件
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="success",
                            item=candidate,
                            block=block,
                            tokens=token_usage,
                            total_tokens=token_usage,  # 在并发场景下，total_tokens由外层累加
                            error=None,
                            elapsed=elapsed,
                            retry_wait_remaining=None,
                            rate_limit_info=rate_limit_info,
                        ))
                        return  # 处理完成，退出
                    else:
                        # 发送invalid事件
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="invalid",
                            item=None,
                            block=block,
                            tokens=token_usage,
                            total_tokens=token_usage,
                            error="LLM 输出未通过业务规则校验",
                            elapsed=elapsed,
                            retry_wait_remaining=None,
                            rate_limit_info=rate_limit_info,
                        ))
                        return  # 处理完成，退出

                except LLMError as exc:
                    # 检查是否是429错误
                    if "429" in str(exc) or "rate" in str(exc).lower():
                        # 429错误：无限重试（最多100次，使用单独计数器）
                        rate_limit_retry_count += 1
                        if rate_limit_retry_count > max_rate_limit_retries:
                            # 429错误超过最大重试次数，elapsed设为0（因为没有成功的LLM调用）
                            await event_queue.put(QuizProcessingEvent(
                                index=index,
                                total=total_count,
                                status="error",
                                item=None,
                                block=block,
                                tokens=TokenUsage(),
                                total_tokens=TokenUsage(),
                                error=f"429错误重试{max_rate_limit_retries}次后仍然失败: {exc}",
                                elapsed=0.0,
                                retry_wait_remaining=None,
                            ))
                            return  # 处理失败，退出

                        # 指数退避 + 随机抖动（参考OpenAI最佳实践）
                        # 基础等待时间、最大等待时间从数据库读取（不再硬编码）
                        # 每次重试翻倍，并添加随机抖动避免同时重试
                        import random
                        base_delay = retry_config["rate_limit_base_delay"]  # 从数据库读取（默认15秒）
                        max_wait_time = retry_config["rate_limit_max_wait"]  # 从数据库读取（默认120秒）
                        exponential_delay = base_delay * (2 ** (rate_limit_retry_count - 1))
                        jitter = random.uniform(0, exponential_delay * 0.5)
                        wait_time = min(exponential_delay + jitter, max_wait_time)
                        wait_time_int = int(wait_time)  # 向下取整

                        # 检查是否是模拟的429（tokens不足触发）
                        is_simulated_429 = "SIMULATED_429" in str(exc)

                        # 只有真实的429错误才记录日志
                        if not is_simulated_429:
                            from logging import getLogger
                            logger = getLogger("memosyne.lithoformer.application")
                            logger.warning(
                                f"题目#{index} 遇到429 Rate Limit错误 (第{rate_limit_retry_count}次重试，不受max_retries限制)，"
                                f"等待{wait_time_int}秒后重试..."
                            )

                        # 倒计时：每秒发送一个"waiting_429"事件
                        for remaining in range(wait_time_int, 0, -1):
                            await event_queue.put(QuizProcessingEvent(
                                index=index,
                                total=total_count,
                                status="waiting_429",
                                item=None,
                                block=block,
                                tokens=TokenUsage(),
                                total_tokens=TokenUsage(),
                                error=None,
                                elapsed=0.0,
                                retry_wait_remaining=remaining,
                            ))
                            await asyncio.sleep(1)  # 等待1秒

                        # 倒计时结束，发送"processing"事件（重新开始处理）
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="processing",
                            item=None,
                            block=block,
                            tokens=TokenUsage(),
                            total_tokens=TokenUsage(),
                            error=None,
                            elapsed=0.0,
                            retry_wait_remaining=None,
                        ))
                        continue

                    # 其他LLM错误：受max_retries限制
                    retry_count += 1
                    if retry_count <= max_retries:
                        from logging import getLogger
                        logger = getLogger("memosyne.lithoformer.application")
                        logger.warning(
                            f"题目#{index} 遇到LLM错误: {exc} (第{retry_count}/{max_retries}次重试)"
                        )
                        # 从数据库读取重试延迟（不再硬编码，默认2秒）
                        await asyncio.sleep(retry_config["other_error_retry_delay"])
                        continue
                    else:
                        # 重试失败，elapsed设为0（因为没有成功的LLM调用）
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="error",
                            item=None,
                            block=block,
                            tokens=TokenUsage(),
                            total_tokens=TokenUsage(),
                            error=f"重试{max_retries}次后仍然失败: {exc}",
                            elapsed=0.0,
                            retry_wait_remaining=None,
                        ))
                        return  # 处理失败，退出

                except Exception as exc:
                    # 其他异常：受max_retries限制
                    retry_count += 1
                    if retry_count <= max_retries:
                        from logging import getLogger
                        logger = getLogger("memosyne.lithoformer.application")
                        logger.warning(
                            f"题目#{index} 遇到异常: {exc} (第{retry_count}/{max_retries}次重试)"
                        )
                        # 从数据库读取重试延迟（不再硬编码，默认2秒）
                        await asyncio.sleep(retry_config["other_error_retry_delay"])
                        continue
                    else:
                        # 重试失败，elapsed设为0（因为没有成功的LLM调用）
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="error",
                            item=None,
                            block=block,
                            tokens=TokenUsage(),
                            total_tokens=TokenUsage(),
                            error=f"重试{max_retries}次后仍然失败: {exc}",
                            elapsed=0.0,
                            retry_wait_remaining=None,
                        ))
                        return  # 处理失败，退出

        finally:
            # 递减active_count（无论成功或失败都要执行）
            async with self._count_lock:
                self._active_processing_count -= 1

    def _build_stat_dict(self, block: dict[str, str], output_dict: dict, processing_time: float, token_usage: TokenUsage) -> dict:
        """构建统计数据字典（v1.9.0：适配新API）

        Args:
            block: 题目块字典
            output_dict: LLM输出字典
            processing_time: 处理时长（秒）
            token_usage: Token使用统计（v1.9.1新增）
        """
        # 组装原始文本（v1.9.1c: 只计算原始内容，不包含标记文本）
        parts = []
        if block.get("context"):
            parts.append(block.get("context", ""))
        parts.append(block.get("question", ""))
        parts.append(block.get("answer", ""))
        original_text = "\n\n".join(parts)

        # 计算输出字符数（v1.9.1c: 只计算内容，不包含JSON格式字符）
        output_char_count = _count_output_chars(output_dict)

        # 提取题型（如果有）
        # v1.9.1: 从"qtype"字段读取而不是"question_type"
        question_type = output_dict.get("qtype", None)

        index_hint = 0
        index_value = block.get("index")
        if isinstance(index_value, str) and index_value.isdigit():
            index_hint = int(index_value)
        question_number = _ensure_question_number(block, index_hint if index_hint > 0 else 1)
        batch_id = _extract_batch_id(self.output_filename)

        return {
            "question_number": question_number,
            "batch_id": batch_id,
            "model": self.model_identifier,
            "input_char_count": len(original_text),
            "use_translation": self.feature_config.enable_translation,
            "use_parsing": self.feature_config.enable_parsing,
            "note": "",
            "question_type": question_type,
            "output_char_count": output_char_count,  # v1.9.1c: 使用计算好的字符数
            "input_tokens": token_usage.input_tokens,  # v1.9.1: 从token_usage获取
            "output_tokens": token_usage.output_tokens,  # v1.9.1: 从token_usage获取
            "processing_time": processing_time,
            "has_error": False,
        }

    def _save_to_bank_if_new(
        self,
        question_number: str,
        batch_id: str,
        original_text: str,
        output_text: str,
        use_translation: bool,
        use_parsing: bool,
    ) -> None:
        """保存到题库（如果题号不存在）（v1.9.1: 从ParseQuizUseCase复制）

        Args:
            question_number: 题号
            batch_id: 批次ID
            original_text: 原始输入文本
            output_text: 输出文本
            use_translation: 是否使用翻译
            use_parsing: 是否使用解析
        """
        if not self.stats_repo or not question_number:
            return

        try:
            # 检查题号是否已存在
            if not self.stats_repo.check_bank_exists(question_number):
                self.stats_repo.save_to_bank(
                    question_number=question_number,
                    batch_id=batch_id,
                    model=self.model_identifier,
                    use_translation=use_translation,
                    use_parsing=use_parsing,
                    original_input=original_text[:50000],  # 限制长度
                    output=output_text[:50000],  # 限制长度
                    no_overwrite=False,  # 允许覆盖（但前面已检查不存在）
                )
        except Exception:
            # 题库保存失败不应影响主流程
            pass

    def cleanup(self) -> None:
        """
        清理资源（关闭线程池）

        Note: 通常由TUI在处理完成后调用，或在异常时自动清理
        """
        if hasattr(self, "_executor") and self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    def __del__(self):
        """析构函数：确保线程池被关闭（fallback机制）"""
        try:
            self.cleanup()
        except Exception:
            pass  # 忽略析构时的异常

    @staticmethod
    def _split_markdown(markdown: str) -> list[dict[str, str]]:
        question_blocks = split_markdown_into_questions(markdown)
        if not question_blocks:
            raise ValueError("未在 Markdown 中解析到任何题目内容")
        return question_blocks
