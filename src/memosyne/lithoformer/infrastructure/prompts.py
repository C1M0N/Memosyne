"""
Lithoformer Prompts - Quiz parsing instructions loaded from stat.db.

The prompt sections are stored in the `lithoformer_prompts` table. This module
retrieves the latest version on demand and assembles the system prompt per
schema type.
"""

from functools import lru_cache
from typing import Dict

from ...shared.config import get_settings
from ...shared.infrastructure.config_db import get_stats_repository


LITHOFORMER_USER_TEMPLATE = """以下提供单道题目及其标准答案，请按照系统说明生成结构化 JSON。

{context}

```Question
{question}
```

```Answer
{answer}
```
"""


@lru_cache(maxsize=1)
def _load_prompt_sections() -> Dict[str, str]:
    """Fetch prompt sections (latest version) from stat.db."""
    settings = get_settings()
    stats_repo = get_stats_repository(settings.db_dir / "stat.db")
    return stats_repo.get_prompt_sections()


def get_dynamic_system_prompt(schema_type: str) -> str:
    """
    根据schema类型动态生成system prompt

    Args:
        schema_type: schema类型，可选值：
            - "full": 翻译 + 解析
            - "no_translation": 仅解析（移除翻译指令）
            - "no_analysis": 仅翻译（移除解析指令）
            - "minimal": 基础解析（移除翻译和解析指令）

    Returns:
        动态生成的system prompt
    """
    prompts = _load_prompt_sections()

    sections: list[str] = [prompts["base_prompt"]]

    if schema_type in ("full", "no_analysis"):
        sections.append(prompts["translation_section"])

    if schema_type in ("full", "no_translation"):
        sections.append(prompts["analysis_section"])
        sections.append(prompts["analysis_examples"])
    elif schema_type in ("no_analysis", "minimal"):
        sections.append(prompts["no_analysis_instruction"])

    sections.append(prompts["footer"])

    return "\n".join(sections)


def get_dynamic_user_prompt(context: str, question: str, answer: str) -> str:
    """
    生成user prompt（所有类型通用）

    Args:
        context: 备注或上下文
        question: 题目内容
        answer: 答案内容

    Returns:
        格式化的user prompt
    """
    return LITHOFORMER_USER_TEMPLATE.format(
        context=context,
        question=question,
        answer=answer,
    )
