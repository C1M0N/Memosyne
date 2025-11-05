"""Unified app configuration models (Shared Kernel).

Typed models used by AppConfig service to aggregate settings from DB.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class FeatureFlags(BaseModel):
    enable_translation: bool = Field(default=True)
    enable_parsing: bool = Field(default=True)
    enable_concurrent: bool = Field(default=False)
    openai_tier: int = Field(default=1, ge=1, le=5, description="OpenAI API Tier (1-5)")
    anthropic_tier: int = Field(default=1, ge=1, le=5, description="Anthropic API Tier (1-5)")


class RuntimeTuning(BaseModel):
    max_concurrent: int | str = Field(default=10)
    max_retries: int = Field(default=1, ge=0, le=10)

    @field_validator('max_concurrent')
    @classmethod
    def validate_max_concurrent(cls, v):
        """验证并发数：允许整数(1-100)或字符串"auto" """
        if isinstance(v, str):
            if v.lower() == "auto":
                return "auto"  # 规范化为小写
            else:
                raise ValueError('字符串值必须为 "auto"')
        elif isinstance(v, int):
            if v < 1 or v > 100:
                raise ValueError('并发数必须在1-100之间')
            return v
        else:
            raise ValueError('并发数必须为整数或 "auto"')


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
    is_display: bool = False  # 是否在下拉菜单中显示
