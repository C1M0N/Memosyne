"""
Memosyne - LLM-based terminology and quiz processing toolkit

Version: 0.6.2 (Refactored)

Quick Start:
    >>> from memosyne import reanimate, lithoform
    >>>
    >>> # 处理术语 (Reanimater)
    >>> result = reanimate(
    ...     input_csv="221.csv",
    ...     start_memo_index=221,
    ...     model="gpt-4o-mini"
    ... )
    >>>
    >>> # 解析 Quiz (Lithoformer)
    >>> result = lithoform(
    ...     input_md="quiz.md",
    ...     model="gpt-4o-mini"
    ... )
"""

__version__ = "0.6.2"
__author__ = "Memosyne Team"

# 导出主要 API（新名称 + 兼容旧名称）
from .api import (
    reanimate,
    lithoform,
    process_terms,  # 旧名兼容
    parse_quiz,     # 旧名兼容
    mms,            # 旧别名兼容
    exparser,       # 旧别名兼容
)

__all__ = [
    # 新 API 函数名
    "reanimate",
    "lithoform",
    # 旧名称（向后兼容）
    "process_terms",
    "parse_quiz",
    "mms",
    "exparser",
    # 元信息
    "__version__",
    "__author__",
]
