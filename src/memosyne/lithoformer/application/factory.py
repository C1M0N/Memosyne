"""UseCaseFactory - Centralized assembly for Lithoformer pipelines.

Assembles provider, adapter and appropriate use case (sequential/concurrent)
based on FeatureConfig. Keeps UI thin and testable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from ...shared.config import Settings
from ...shared.infrastructure.llm import OpenAIProvider, AnthropicProvider
from ...core.interfaces import LLMProvider, StatsRepository
from ...core.models import Configuration
from ..domain.models import FeatureConfig
from ..infrastructure import LithoformerLLMAdapter
from .use_cases import ParseQuizUseCase


class UseCaseFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_provider(self, provider: str, model_id: str) -> LLMProvider:
        provider_norm = provider.lower().strip()
        if provider_norm == "anthropic":
            if not self.settings.anthropic_api_key:
                raise RuntimeError("未配置 ANTHROPIC_API_KEY")
            return AnthropicProvider(
                model=model_id,
                api_key=self.settings.anthropic_api_key,
                temperature=self.settings.default_temperature,
            )
        # default to openai
        return OpenAIProvider(
            model=model_id,
            api_key=self.settings.openai_api_key,
            temperature=self.settings.default_temperature,
        )

    def build_adapter(self, provider: LLMProvider, feature_config: FeatureConfig) -> LithoformerLLMAdapter:
        return LithoformerLLMAdapter.from_provider(provider, feature_config=feature_config)

    def build_use_case(
        self,
        *,
        provider: str,
        model_id: str,
        feature_config: FeatureConfig,
        stats_repo: StatsRepository | None,
        output_filename: str,
    ) -> Tuple[ParseQuizUseCase, str]:
        """Return configured use case and model identifier string.

        Returns:
            (use_case, model_identifier)
        """
        llm_provider = self.build_provider(provider, model_id)
        adapter = self.build_adapter(llm_provider, feature_config)
        model_identifier = Configuration.format_model(provider, model_id)
        use_case = ParseQuizUseCase(
            llm=adapter,
            stats_repo=stats_repo,
            feature_config=feature_config,
            model_identifier=model_identifier,
            output_filename=output_filename,
        )
        return use_case, model_identifier

