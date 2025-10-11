"""
Prompts 模块 - LLM 提示词管理

将所有 Prompt 集中管理，便于修改和维护
"""
from .reanimater_prompts import (
    REANIMATER_SYSTEM_PROMPT,
    REANIMATER_USER_TEMPLATE,
)
from .lithoformer_prompts import (
    LITHOFORMER_SYSTEM_PROMPT,
    LITHOFORMER_USER_TEMPLATE,
)

__all__ = [
    "REANIMATER_SYSTEM_PROMPT",
    "REANIMATER_USER_TEMPLATE",
    "LITHOFORMER_SYSTEM_PROMPT",
    "LITHOFORMER_USER_TEMPLATE",
]
