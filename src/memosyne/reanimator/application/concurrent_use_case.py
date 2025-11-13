"""Concurrent Reanimator use case (aligned with Lithoformer)."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import apply_business_rules, map_field_label, generate_word_id
from .ports import LLMPort, TermListPort

from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress


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
    ) -> None:
        self.llm = llm
        self.term_list = term_list
        self.start_word_index = start_word_index
        self.batch_id = batch_id
        self.batch_note = batch_note.strip()
        self.max_concurrent = max_concurrent
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="ReanimatorWorker")

    def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
        progress_callback: Callable[[int, int, TokenUsage, dict | None], None] | None = None,
    ) -> ProcessResult[TermOutput]:
        term_list = list(terms)
        total = len(term_list)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._process(term_list, total, show_progress, progress_callback))
        finally:
            loop.close()

    async def _process(
        self,
        terms: list[TermInput],
        total: int,
        show_progress: bool,
        progress_callback: Callable[[int, int, TokenUsage, dict | None], None] | None,
    ) -> ProcessResult[TermOutput]:
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results: dict[int, TermOutput] = {}
        total_tokens = TokenUsage()
        tokens_lock = asyncio.Lock()

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
                )
                for i, term in enumerate(terms)
            ]
            await asyncio.gather(*tasks)

        ordered = [results[i] for i in range(total) if i in results]
        return ProcessResult(items=ordered, success_count=len(ordered), total_count=total, token_usage=total_tokens)

    async def _process_single_term(
        self,
        index: int,
        term: TermInput,
        semaphore: asyncio.Semaphore,
        results: dict[int, TermOutput],
        total_tokens: TokenUsage,
        tokens_lock: asyncio.Lock,
        progress: Progress,
        progress_callback: Callable[[int, int, TokenUsage, dict | None], None] | None,
        total_count: int,
    ) -> None:
        async with semaphore:
            loop = asyncio.get_event_loop()
            requested_fields = term.requested_optional_fields()
            raw_response, token_dict, rate_limit_info = await loop.run_in_executor(
                self._executor,
                self.llm.process_term,
                term.word_en,
                term.mean_zh,
                self.batch_note,
                requested_fields,
            )
            llm_payload = apply_business_rules(term.word_en, LLMResponse(**raw_response))

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
                progress.advance(desc=f"Processing [Tokens: {total_tokens.total_tokens:,}]")
                if progress_callback:
                    progress_callback(
                        index + 1,
                        total_count,
                        total_tokens,
                        rate_limit_info,
                    )

            results[index] = output
