"""
Reanimator 配置模型 (v0.16.0)

Typed models used by ReanimatorConfigService to aggregate settings from DB.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class ReanimatorFeature(BaseModel):
    """Reanimator 功能开关"""
    enable_concurrent: bool = Field(default=False, description="启用并发处理模式")


class ReanimatorConfig(BaseModel):
    """Reanimator 配置"""
    reanimator_input_dir: str = Field(default="misc/input/reanimator", description="输入目录")
    reanimator_output_dir: str = Field(default="misc/output/reanimator", description="输出目录")
    default_model: str = Field(default="OpenAI::gpt-4o", description="默认模型")
    term_list_path: str = Field(default="db/term_list_v1.csv", description="术语表路径")
    max_concurrent: int = Field(default=3, ge=1, le=20, description="最大并发数")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")


class ReanimatorPaths(BaseModel):
    """Reanimator 路径配置"""
    input_dir: Path | None = Field(default=None)
    output_dir: Path | None = Field(default=None)


class ReanimatorConfigBundle(BaseModel):
    """Reanimator 完整配置包"""
    config: ReanimatorConfig = Field(default_factory=ReanimatorConfig)
    feature: ReanimatorFeature = Field(default_factory=ReanimatorFeature)
    paths: ReanimatorPaths = Field(default_factory=ReanimatorPaths)
