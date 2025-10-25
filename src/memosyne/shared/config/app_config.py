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
