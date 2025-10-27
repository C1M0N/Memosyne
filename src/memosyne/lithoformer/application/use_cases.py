"""
Lithoformer Application Use Cases
"""

import asyncio
import re
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, Iterator, Literal

from ..domain.models import QuizItem, FeatureConfig
from ..domain.services import (
    is_quiz_item_valid,
    split_markdown_into_questions,
)
from .ports import LLMPort

# 导入核心模型和接口
from ...core.models import ProcessResult, TokenUsage
from ...core.interfaces import StatsRepository
from ...shared.utils import Progress, indeterminate_progress


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
        )

        # 保存统计数据（如果配置了stats_repo）
        if self.stats_repo and status == "success":
            self._save_stats(block, item_dict if status == "success" else {}, elapsed)

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

    def _save_stats(
        self,
        block: dict[str, str],
        output_dict: dict,
        processing_time: float,
    ) -> None:
        """
        保存处理统计数据到数据库

        Args:
            block: 原始题目块
            output_dict: LLM输出字典
            processing_time: 处理时长（秒）
        """
        if not self.stats_repo:
            return

        # 组装原始文本
        original_text = f"Question:\n{block.get('question', '')}\n\nAnswer:\n{block.get('answer', '')}"
        if block.get("context"):
            original_text = f"Context:\n{block.get('context', '')}\n\n" + original_text

        # 组装输出文本（JSON格式）
        import json
        output_text = json.dumps(output_dict, ensure_ascii=False, indent=2)

        # 获取功能配置
        use_translation = self.feature_config.enable_translation if self.feature_config else True
        use_parsing = self.feature_config.enable_parsing if self.feature_config else True

        # 保存统计
        self.stats_repo.save_stat(
            question_number=block.get("index", ""),
            model=self.model_identifier,
            input_char_count=len(original_text),
            output_char_count=len(output_text),
            use_translation=use_translation,
            use_parsing=use_parsing,
            original_text=original_text[:50000],  # 截断到最大长度
            output_text=output_text[:50000],  # 截断到最大长度
            output_filename=self.output_filename,
            processing_time=processing_time,
        )


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
        self.llm = llm
        self.feature_config = feature_config
        self.stats_repo = stats_repo
        self.model_identifier = model_identifier
        self.output_filename = output_filename

    async def execute_async(
        self,
        markdown: str,
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
        from collections import defaultdict

        question_blocks = self._split_markdown(markdown)
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
                        self._build_stat_dict(block, event.item.model_dump(), event.elapsed)
                    )

        # 创建所有任务
        tasks = [
            process_block_async(index, block)
            for index, block in enumerate(question_blocks, start=1)
        ]

        # 并发执行
        await asyncio.gather(*tasks)

        # 批量保存统计
        if self.stats_repo and stats_buffer:
            self.stats_repo.batch_save_stats(stats_buffer)

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

    async def stream_async(self, markdown: str):
        """
        并发流式事件接口：统一与顺序版的事件消费模式。

        Yields:
            QuizProcessingEvent（包括中间状态：processing, waiting_429等）
        """
        import asyncio

        question_blocks = self._split_markdown(markdown)
        total_count = len(question_blocks)

        semaphore = asyncio.Semaphore(self.feature_config.max_concurrent)
        event_queue: asyncio.Queue[QuizProcessingEvent] = asyncio.Queue()

        async def task_for(index: int, block: dict[str, str]):
            """处理单个题目，并将所有事件（包括中间状态）发送到queue"""
            async with semaphore:
                await self._process_block_with_retry(block, index, total_count, event_queue)

        # 创建所有任务
        tasks = [asyncio.create_task(task_for(i, b)) for i, b in enumerate(question_blocks, start=1)]

        # 从queue中读取事件并yield给UI
        completed_count = 0
        while completed_count < total_count:
            event = await event_queue.get()
            yield event

            # 只有最终状态才计入完成数
            if event.status in ["success", "error", "invalid"]:
                completed_count += 1

        # 等待所有任务完成（确保没有遗漏）
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_block_with_retry(
        self,
        block: dict[str, str],
        index: int,
        total_count: int,
        event_queue: asyncio.Queue,
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

        Returns:
            None（通过event_queue发送所有事件）
        """
        import asyncio
        from ...core.interfaces import LLMError

        max_retries = self.feature_config.max_retries
        retry_count = 0
        rate_limit_retry_count = 0  # 429错误单独计数
        max_rate_limit_retries = 100  # 429错误最多重试100次

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
                start_time = perf_counter()

                # 调用LLM（同步方法，需要在executor中运行）
                loop = asyncio.get_event_loop()
                item_dict, token_dict = await loop.run_in_executor(
                    None,
                    self.llm.parse_question,
                    {
                        "context": block.get("context", ""),
                        "question": block.get("question", ""),
                        "answer": block.get("answer", ""),
                        "note": "",
                        "index": str(index),
                    },
                )

                token_usage = TokenUsage(**token_dict)
                candidate = QuizItem(**_normalize_question_dict(item_dict))

                elapsed = perf_counter() - start_time

                if is_quiz_item_valid(candidate, self.feature_config):
                    # 实时保存统计（异步环境下，实时保存比批量保存更合适）
                    if self.stats_repo:
                        stat_dict = self._build_stat_dict(block, item_dict, elapsed)
                        # 在asyncio环境中，使用线程池执行同步的数据库写入
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            self.stats_repo.save_stat,
                            stat_dict["question_number"],
                            stat_dict["model"],
                            stat_dict["input_char_count"],
                            stat_dict["output_char_count"],
                            stat_dict["use_translation"],
                            stat_dict["use_parsing"],
                            stat_dict["original_text"],
                            stat_dict["output_text"],
                            stat_dict["output_filename"],
                            stat_dict["processing_time"],
                        )

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
                    ))
                    return  # 处理完成，退出

            except LLMError as exc:
                # 检查是否是429错误
                if "429" in str(exc) or "rate" in str(exc).lower():
                    # 429错误：无限重试（最多100次，使用单独计数器）
                    rate_limit_retry_count += 1
                    if rate_limit_retry_count > max_rate_limit_retries:
                        elapsed = perf_counter() - start_time
                        await event_queue.put(QuizProcessingEvent(
                            index=index,
                            total=total_count,
                            status="error",
                            item=None,
                            block=block,
                            tokens=TokenUsage(),
                            total_tokens=TokenUsage(),
                            error=f"429错误重试{max_rate_limit_retries}次后仍然失败: {exc}",
                            elapsed=elapsed,
                            retry_wait_remaining=None,
                        ))
                        return  # 处理失败，退出

                    # 指数退避 + 随机抖动（参考OpenAI最佳实践）
                    # 基础等待时间：15秒（OpenAI建议的最小暂停时间）
                    # 每次重试翻倍，并添加随机抖动避免同时重试
                    import random
                    base_delay = 15
                    exponential_delay = base_delay * (2 ** (rate_limit_retry_count - 1))
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    wait_time = min(exponential_delay + jitter, 120)  # 最多等待2分钟
                    wait_time_int = int(wait_time)  # 向下取整

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
                    await asyncio.sleep(2)  # 其他错误简单等待2秒
                    continue
                else:
                    elapsed = perf_counter() - start_time
                    await event_queue.put(QuizProcessingEvent(
                        index=index,
                        total=total_count,
                        status="error",
                        item=None,
                        block=block,
                        tokens=TokenUsage(),
                        total_tokens=TokenUsage(),
                        error=f"重试{max_retries}次后仍然失败: {exc}",
                        elapsed=elapsed,
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
                    await asyncio.sleep(2)
                    continue
                else:
                    elapsed = perf_counter() - start_time
                    await event_queue.put(QuizProcessingEvent(
                        index=index,
                        total=total_count,
                        status="error",
                        item=None,
                        block=block,
                        tokens=TokenUsage(),
                        total_tokens=TokenUsage(),
                        error=f"重试{max_retries}次后仍然失败: {exc}",
                        elapsed=elapsed,
                        retry_wait_remaining=None,
                    ))
                    return  # 处理失败，退出

    def _build_stat_dict(self, block: dict[str, str], output_dict: dict, processing_time: float) -> dict:
        """构建统计数据字典"""
        import json

        # 组装原始文本
        original_text = f"Question:\n{block.get('question', '')}\n\nAnswer:\n{block.get('answer', '')}"
        if block.get("context"):
            original_text = f"Context:\n{block.get('context', '')}\n\n" + original_text

        # 组装输出文本
        output_text = json.dumps(output_dict, ensure_ascii=False, indent=2)

        return {
            "question_number": block.get("index", ""),
            "model": self.model_identifier,
            "input_char_count": len(original_text),
            "output_char_count": len(output_text),
            "use_translation": self.feature_config.enable_translation,
            "use_parsing": self.feature_config.enable_parsing,
            "original_text": original_text[:50000],
            "output_text": output_text[:50000],
            "output_filename": self.output_filename,
            "processing_time": processing_time,
        }

    @staticmethod
    def _split_markdown(markdown: str) -> list[dict[str, str]]:
        question_blocks = split_markdown_into_questions(markdown)
        if not question_blocks:
            raise ValueError("未在 Markdown 中解析到任何题目内容")
        return question_blocks
