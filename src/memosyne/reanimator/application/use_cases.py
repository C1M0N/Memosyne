"""Reanimator synchronous use case."""
from __future__ import annotations

from typing import Callable, Iterable

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import apply_business_rules, map_field_label, generate_word_id
from .ports import LLMPort, TermListPort

from ...core.models import ProcessResult, TokenUsage
from ...shared.utils import Progress


class ProcessTermsUseCase:
    def __init__(
        self,
        *,
        llm: LLMPort,
        term_list: TermListPort,
        start_word_index: int,
        batch_id: str,
        batch_note: str = "",
    ) -> None:
        self.llm = llm
        self.term_list = term_list
        self.start_word_index = start_word_index
        self.batch_id = batch_id
        self.batch_note = batch_note.strip()

    def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
        progress_callback: Callable[[int, int, TokenUsage, dict | None], None] | None = None,
    ) -> ProcessResult[TermOutput]:
        results: list[TermOutput] = []
        total_tokens = TokenUsage()
        total = len(terms) if hasattr(terms, "__len__") else None

        with Progress(total=total, desc="Processing", unit="term", enabled=show_progress) as progress:
            for index, term_input in enumerate(terms):
                requested_fields = term_input.requested_optional_fields()
                raw_response, token_dict, rate_limit_info = self.llm.process_term(
                    term_input.word_en,
                    term_input.mean_zh,
                    self.batch_note,
                    requested_fields,
                )
                llm_payload = apply_business_rules(term_input.word_en, LLMResponse(**raw_response))

                tokens = TokenUsage(**token_dict)
                total_tokens = total_tokens + tokens
                progress.advance(desc=f"Processing [Tokens: {total_tokens.total_tokens:,}]")
                if progress_callback:
                    progress_callback(
                        index + 1,
                        total or (index + 1),
                        total_tokens,
                        rate_limit_info,
                    )

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

        return ProcessResult(
            items=results,
            success_count=len(results),
            total_count=len(results),
            token_usage=total_tokens,
        )
