"""
Reanimator 并发处理用例 (v0.16.0)

提供并发模式的术语处理能力，适用于 TUI 等需要高性能的场景。
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import (
    apply_business_rules,
    get_chinese_tag,
    generate_memo_id,
)
from .ports import LLMPort, TermListPort

# 导入核心模型
from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress


class ConcurrentProcessTermsUseCase:
    """
    并发处理术语用例 (v0.16.0)

    Workflow:
    1. 接收术语输入列表
    2. 使用 asyncio 并发调用 LLM 解析术语
    3. 按索引排序结果
    4. 返回处理结果

    Features:
    - 支持 max_concurrent 限制并发数
    - 使用 Semaphore 控制并发数量
    - 内存缓冲 + 排序保证顺序
    - 进度条按完成数更新
    - Token 统计实时累加
    """

    def __init__(
        self,
        llm: LLMPort,
        term_list: TermListPort,
        start_memo_index: int,
        batch_id: str,
        batch_note: str = "",
        max_concurrent: int = 3,
    ):
        """
        Args:
            llm: LLM 端口（由 Infrastructure 层注入）
            term_list: 术语表端口（由 Infrastructure 层注入）
            start_memo_index: 起始 Memo 编号（如 2700 表示从 M002701 开始）
            batch_id: 批次 ID（如 "251007A015"）
            batch_note: 批次备注（可选）
            max_concurrent: 最大并发数（默认 3）
        """
        self.llm = llm
        self.term_list = term_list
        self.start_memo = start_memo_index
        self.batch_id = batch_id
        self.batch_note = f"「{batch_note.strip()}」" if batch_note else ""
        self.max_concurrent = max_concurrent

        # 创建自定义线程池，支持并发调用
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix="ReanimatorWorker",
        )

        self.logger = logging.getLogger("memosyne.reanimator.concurrent")

    def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
    ) -> ProcessResult[TermOutput]:
        """
        执行并发处理：处理术语列表

        Args:
            terms: 术语输入（可迭代对象）
            show_progress: 是否显示进度条

        Returns:
            ProcessResult[TermOutput] - 包含结果列表和 token 统计
        """
        # 转换为列表以获取总数
        terms_list = list(terms)
        total = len(terms_list)

        # 使用 asyncio 运行并发处理
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        results = loop.run_until_complete(
            self._process_concurrent(terms_list, total, show_progress)
        )

        return results

    async def _process_concurrent(
        self,
        terms: list[TermInput],
        total: int,
        show_progress: bool,
    ) -> ProcessResult[TermOutput]:
        """
        异步并发处理术语列表

        Args:
            terms: 术语列表
            total: 总数
            show_progress: 是否显示进度

        Returns:
            ProcessResult[TermOutput]
        """
        # 创建 Semaphore 限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # 用于存储结果（索引 -> TermOutput）
        results_dict: dict[int, TermOutput] = {}

        # Token 统计（需要线程安全）
        total_tokens = TokenUsage()
        tokens_lock = asyncio.Lock()

        # 进度条
        with Progress(
            total=total,
            desc="Processing [Tokens: 0]",
            unit="term",
            enabled=show_progress,
        ) as progress:

            # 创建所有任务
            tasks = [
                self._process_single_term(
                    index=index,
                    term=term,
                    semaphore=semaphore,
                    results_dict=results_dict,
                    total_tokens=total_tokens,
                    tokens_lock=tokens_lock,
                    progress=progress,
                )
                for index, term in enumerate(terms)
            ]

            # 并发执行所有任务
            await asyncio.gather(*tasks)

        # 按索引排序结果
        sorted_results = [results_dict[i] for i in range(total) if i in results_dict]

        return ProcessResult(
            items=sorted_results,
            success_count=len(sorted_results),
            total_count=total,
            token_usage=total_tokens,
        )

    async def _process_single_term(
        self,
        index: int,
        term: TermInput,
        semaphore: asyncio.Semaphore,
        results_dict: dict[int, TermOutput],
        total_tokens: TokenUsage,
        tokens_lock: asyncio.Lock,
        progress: Progress,
    ) -> None:
        """
        处理单个术语（异步）

        Args:
            index: 术语索引
            term: 术语输入
            semaphore: 信号量（控制并发）
            results_dict: 结果字典
            total_tokens: Token 统计
            tokens_lock: Token 统计锁
            progress: 进度条
        """
        async with semaphore:
            try:
                # 在线程池中执行同步 LLM 调用
                loop = asyncio.get_event_loop()
                llm_dict, token_dict = await loop.run_in_executor(
                    self._executor,
                    self.llm.process_term,
                    term.word,
                    term.zh_def,
                )

                # 转换为领域模型（自动验证）
                llm_response = LLMResponse(**llm_dict)

                # 应用业务规则（领域服务）
                llm_response = apply_business_rules(term.word, llm_response)

                # 映射英文标签到中文（领域服务）
                tag_cn = get_chinese_tag(llm_response.tag_en, self.term_list.mapping)

                # 生成 Memo ID（领域服务）
                memo_id = generate_memo_id(self.start_memo, index)

                # 组装输出（领域模型工厂方法）
                output = TermOutput.from_input_and_llm(
                    term_input=term,
                    llm_response=llm_response,
                    memo_id=memo_id,
                    tag_cn=tag_cn,
                    batch_id=self.batch_id,
                    batch_note=self.batch_note,
                )

                # 存储结果
                results_dict[index] = output

                # 更新 Token 统计（线程安全）
                async with tokens_lock:
                    tokens = TokenUsage(**token_dict)
                    total_tokens.input_tokens += tokens.input_tokens
                    total_tokens.output_tokens += tokens.output_tokens

                    # 更新进度条
                    progress.advance(
                        desc=f"Processing [Tokens: {total_tokens.total_tokens:,}]"
                    )

            except Exception as exc:
                self.logger.error(f"处理术语失败 [index={index}]: {term.word} - {exc}")
                # 不抛出异常，允许其他任务继续
                progress.advance(desc=f"Processing [Error: {term.word}]")

    def __del__(self):
        """清理线程池"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
