"""Reanimator synchronous use case."""
from __future__ import annotations

from time import perf_counter, sleep
from typing import Callable, Iterable
import random

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import apply_business_rules, map_field_label, generate_word_id
from .ports import LLMPort, TermListPort

from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress
from ...core.interfaces import LLMError
import logging


class ProcessTermsUseCase:
    def __init__(
        self,
        *,
        llm: LLMPort,
        term_list: TermListPort,
        start_word_index: int,
        batch_id: str,
        batch_note: str = "",
        max_retries: int = 3,
        retry_config: dict | None = None,
    ) -> None:
        self.llm = llm
        self.term_list = term_list
        self.start_word_index = start_word_index
        self.batch_id = batch_id
        self.batch_note = batch_note.strip()
        self.max_retries = max_retries
        self.retry_config = retry_config or {
            "rate_limit_max_retries": 100,
            "rate_limit_base_delay": 15,
            "rate_limit_max_wait": 120,
            "other_error_retry_delay": 2,
        }

    def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
        progress_callback: Callable[
            [int, int, TokenUsage, dict | None, int | None, float | None, str, float | None],
            None,
        ]
        | None = None,
    ) -> ProcessResult[TermOutput]:
        results: list[TermOutput] = []
        total_tokens = TokenUsage()
        total = len(terms) if hasattr(terms, "__len__") else None
        completed = 0
        success_count = 0

        with Progress(total=total, desc="Processing", unit="term", enabled=show_progress) as progress:
            for index, term_input in enumerate(terms):
                if progress_callback:
                    progress_callback(
                        completed,
                        total or (index + 1),
                        total_tokens,
                        None,
                        index,
                        None,
                        "start",
                        None,
                    )

                requested_fields = term_input.requested_optional_fields()
                rate_limit_retry = 0
                retry_count = 0
                term_elapsed: float | None = None
                last_rate_limit_info: dict | None = None
                success = False

                while True:
                    try:
                        term_start = perf_counter()
                        raw_response, token_dict, rate_limit_info = self.llm.process_term(
                            term_input.word_en,
                            term_input.mean_zh,
                            self.batch_note,
                            requested_fields,
                        )
                        llm_payload = apply_business_rules(term_input.word_en, LLMResponse(**raw_response))
                        term_elapsed = perf_counter() - term_start
                        tokens = TokenUsage(**token_dict)
                        total_tokens = total_tokens + tokens
                        last_rate_limit_info = rate_limit_info
                        success = True
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
                                term_input.word_id or term_input.word_en,
                                rate_limit_retry,
                                max_rl,
                                wait_int,
                            )

                            if progress_callback:
                                progress_callback(
                                    completed,
                                    total or (index + 1),
                                    total_tokens,
                                    {"retry_after": wait_int},
                                    index,
                                    None,
                                    "waiting_429",
                                    float(wait_int),
                                )

                            for remaining in range(wait_int, 0, -1):
                                if progress_callback:
                                    progress_callback(
                                        completed,
                                        total or (index + 1),
                                        total_tokens,
                                        {"retry_after": remaining},
                                        index,
                                        None,
                                        "waiting_429",
                                        float(remaining),
                                    )
                                sleep(1)
                            continue

                        retry_count += 1
                        if retry_count <= self.max_retries:
                            sleep(self.retry_config.get("other_error_retry_delay", 2))
                            continue
                        break
                    except Exception:
                        break

                completed += 1
                progress.advance(desc=f"Processing [Tokens: {total_tokens.total_tokens:,}]")
                if progress_callback:
                    progress_callback(
                        completed,
                        total or (index + 1),
                        total_tokens,
                        last_rate_limit_info,
                        index,
                        term_elapsed,
                        "done" if success else "error",
                        None,
                    )

                if success:
                    word_id = generate_word_id(self.start_word_index, index)
                    field_label = term_input.field
                    if not field_label:
                        field_label = map_field_label(llm_payload.field_en, self.term_list.mapping)

                    output = TermOutput.compose(
                        term_input=term_input,
                        llm_response=llm_payload,
                        field_zh=field_label,
                        batch_id=self.batch_id,
                        word_id=word_id,
                        batch_note=term_input.batch_note or self.batch_note,
                    )
                    results.append(output)
                    success_count += 1

        return ProcessResult(
            items=results,
            success_count=success_count,
            total_count=len(terms) if hasattr(terms, "__len__") else len(results),
            token_usage=total_tokens,
        )
