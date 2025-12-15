"""Concurrent Reanimator use case (aligned with Lithoformer)."""
from __future__ import annotations

import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable
from time import perf_counter

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import apply_business_rules, map_field_label, generate_word_id
from .ports import LLMPort, TermListPort

from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress
from ...core.interfaces import LLMError
import logging


class ConcurrentProcessTermsUseCase:
    def __init__(
        self,
        *,
        llm: LLMPort,
        term_list: TermListPort,
        start_word_index: int,
        batch_id: str,
        batch_note: str = "",
        max_concurrent: int = 3,
        max_retries: int = 3,
        retry_config: dict | None = None,
    ) -> None:
        self.llm = llm
        self.term_list = term_list
        self.start_word_index = start_word_index
        self.batch_id = batch_id
        self.batch_note = batch_note.strip()
        self.max_concurrent = max_concurrent
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="ReanimatorWorker")
        self.max_retries = max_retries
        self.retry_config = retry_config or {
            "rate_limit_max_retries": 100,
            "rate_limit_base_delay": 15,
            "rate_limit_max_wait": 120,
            "other_error_retry_delay": 2,
        }

    async def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
        progress_callback: Callable[
            [int, int, TokenUsage, dict | None, int | None, float | None, str, float | None],
            None,
        ]
        | None = None,
    ) -> ProcessResult[TermOutput]:
        """异步执行术语处理（适用于 Textual TUI 环境）"""
        term_list = list(terms)
        total = len(term_list)
        return await self._process(term_list, total, show_progress, progress_callback)

    async def _process(
        self,
        terms: list[TermInput],
        total: int,
        show_progress: bool,
        progress_callback: Callable[
            [int, int, TokenUsage, dict | None, int | None, float | None, str, float | None],
            None,
        ]
        | None,
    ) -> ProcessResult[TermOutput]:
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results: dict[int, TermOutput] = {}
        total_tokens = TokenUsage()
        tokens_lock = asyncio.Lock()
        completed_lock = asyncio.Lock()
        completed = {"count": 0}
        success_count = {"count": 0}

        with Progress(total=total, desc="Processing", unit="term", enabled=show_progress) as progress:
            tasks = [
                self._process_single_term(
                    i,
                    term,
                    semaphore,
                    results,
                    total_tokens,
                    tokens_lock,
                    progress,
                    progress_callback,
                    total,
                    completed,
                    completed_lock,
                    success_count,
                )
                for i, term in enumerate(terms)
            ]
            await asyncio.gather(*tasks)

        ordered = [results[i] for i in range(total) if i in results]
        return ProcessResult(items=ordered, success_count=success_count["count"], total_count=total, token_usage=total_tokens)

    async def _process_single_term(
        self,
        index: int,
        term: TermInput,
        semaphore: asyncio.Semaphore,
        results: dict[int, TermOutput],
        total_tokens: TokenUsage,
        tokens_lock: asyncio.Lock,
        progress: Progress,
        progress_callback: Callable[
            [int, int, TokenUsage, dict | None, int | None, float | None, str, float | None],
            None,
        ]
        | None,
        total_count: int,
        completed_counter: dict,
        completed_lock: asyncio.Lock,
        success_counter: dict,
    ) -> None:
        async with semaphore:
            loop = asyncio.get_event_loop()
            requested_fields = term.requested_optional_fields()

            if progress_callback:
                progress_callback(
                    completed_counter["count"],
                    total_count,
                    total_tokens,
                    None,
                    index,
                    None,
                    "start",
                    None,
                )

            rate_limit_retry = 0
            retry_count = 0
            success = False
            term_elapsed: float | None = None
            last_rate_limit_info: dict | None = None

            while True:
                try:
                    term_start = perf_counter()
                    raw_response, token_dict, rate_limit_info = await loop.run_in_executor(
                        self._executor,
                        self.llm.process_term,
                        term.word_en,
                        term.mean_zh,
                        self.batch_note,
                        requested_fields,
                    )
                    llm_payload = apply_business_rules(term.word_en, LLMResponse(**raw_response))
                    term_elapsed = perf_counter() - term_start
                    word_id = generate_word_id(self.start_word_index, index)
                    field_label = term.field or map_field_label(llm_payload.field_en, self.term_list.mapping)

                    output = TermOutput.compose(
                        term_input=term,
                        llm_response=llm_payload,
                        field_zh=field_label,
                        batch_id=self.batch_id,
                        word_id=word_id,
                        batch_note=term.batch_note or self.batch_note,
                    )

                    async with tokens_lock:
                        total_tokens.prompt_tokens += token_dict.get("prompt_tokens", 0)
                        total_tokens.completion_tokens += token_dict.get("completion_tokens", 0)
                        total_tokens.total_tokens += token_dict.get("total_tokens", 0)
                    last_rate_limit_info = rate_limit_info
                    success = True
                    results[index] = output
                    async with completed_lock:
                        success_counter["count"] += 1
                    break
                except LLMError as exc:
                    err_text = str(exc).lower()
                    if "429" in err_text or "rate" in err_text:
                        rate_limit_retry += 1
                        max_rl = self.retry_config.get("rate_limit_max_retries", 100)
                        if rate_limit_retry > max_rl:
                            break

                        base_delay = self.retry_config.get("rate_limit_base_delay", 15)
                        max_wait = self.retry_config.get("rate_limit_max_wait", 120)
                        exponential = base_delay * (2 ** (rate_limit_retry - 1))
                        jitter = random.uniform(0, exponential * 0.5)
                        wait_time = min(exponential + jitter, max_wait)
                        wait_int = int(wait_time)

                        logging.getLogger("memosyne.reanimator.application").warning(
                            "Word #%s 遇到 429，第 %d/%d 次重试，将等待 %ds",
                            term.word_id or term.word_en,
                            rate_limit_retry,
                            max_rl,
                            wait_int,
                        )

                        for remaining in range(wait_int, 0, -1):
                            if progress_callback:
                                progress_callback(
                                    completed_counter["count"],
                                    total_count,
                                    total_tokens,
                                    {"retry_after": remaining},
                                    index,
                                    None,
                                    "waiting_429",
                                    float(remaining),
                                )
                            await asyncio.sleep(1)
                        continue

                    retry_count += 1
                    if retry_count <= self.max_retries:
                        await asyncio.sleep(self.retry_config.get("other_error_retry_delay", 2))
                        continue
                    break
                except Exception:
                    break

            async with completed_lock:
                completed_counter["count"] += 1
                completed_now = completed_counter["count"]
            progress.advance(desc=f"Processing [Tokens: {total_tokens.total_tokens:,}]")
            if progress_callback:
                progress_callback(
                    completed_now,
                    total_count,
                    total_tokens,
                    last_rate_limit_info,
                    index,
                    term_elapsed,
                    "done" if success else "error",
                    None,
                )
