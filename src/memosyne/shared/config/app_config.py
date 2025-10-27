"""Unified app configuration models (Shared Kernel).

Typed models used by AppConfig service to aggregate settings from DB.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field


class FeatureFlags(BaseModel):
    enable_translation: bool = Field(default=True)
    enable_parsing: bool = Field(default=True)
    enable_concurrent: bool = Field(default=False)
    feature_001: bool = Field(default=False)
    feature_002: bool = Field(default=False)
    feature_003: bool = Field(default=False)


class RuntimeTuning(BaseModel):
    max_concurrent: int = Field(default=10, ge=1, le=100)
    max_retries: int = Field(default=1, ge=0, le=10)


class AppConfigBundle(BaseModel):
    default_model: str = Field(default="OpenAI::gpt-4o-mini")
    feature: FeatureFlags = Field(default_factory=FeatureFlags)
    tuning: RuntimeTuning = Field(default_factory=RuntimeTuning)


class LithoformerPaths(BaseModel):
    input_dir: Path | None = Field(default=None)
    output_dir: Path | None = Field(default=None)


class LLMModelInfo(BaseModel):
    """LLM模型信息"""
    id: int
    provider: str  # openai, anthropic
    model_id: str  # gpt-4o, claude-sonnet-4.5
    display_name: str  # GPT-4o, Claude Sonnet 4.5
    alias: str | None = None
    price_input: float  # 每百万tokens的价格（美元）
    price_output: float  # 每百万tokens的价格（美元）
    # RPM限制
    rpm_limit_tier1: int | None = None
    rpm_limit_tier2: int | None = None
    rpm_limit_tier3: int | None = None
    rpm_limit_tier4: int | None = None
    rpm_limit_tier5: int | None = None
    # TPM限制（OpenAI使用）
    tpm_limit_tier1: int | None = None
    tpm_limit_tier2: int | None = None
    tpm_limit_tier3: int | None = None
    tpm_limit_tier4: int | None = None
    tpm_limit_tier5: int | None = None
    # ITPM限制（Anthropic使用）
    itpm_limit_tier1: int | None = None
    itpm_limit_tier2: int | None = None
    itpm_limit_tier3: int | None = None
    itpm_limit_tier4: int | None = None
    itpm_limit_tier5: int | None = None
    # OTPM限制（Anthropic使用）
    otpm_limit_tier1: int | None = None
    otpm_limit_tier2: int | None = None
    otpm_limit_tier3: int | None = None
    otpm_limit_tier4: int | None = None
    otpm_limit_tier5: int | None = None
    is_active: bool = True
    is_default: bool = False
