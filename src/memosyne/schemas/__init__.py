"""
Schemas 模块 - JSON Schema 定义

用于 LLM 结构化输出的 Schema 定义
"""
from .term_schema import TERM_RESULT_SCHEMA
from .quiz_schema import QUIZ_SCHEMA

__all__ = [
    "TERM_RESULT_SCHEMA",
    "QUIZ_SCHEMA",
]
