"""
Memosyne - LLM-based terminology and quiz processing toolkit

Version: 0.7.1

Quick Start:
    >>> from memosyne import reanimate, lithoform
    >>>
    >>> # 处理术语 (Reanimater)
    >>> result = reanimate(
    ...     input_csv="221.csv",
    ...     start_memo_index=221,
    ...     model="gpt-4o-mini"
    ... )
    >>> print(f"Token 使用: {result['token_usage']}")
    >>>
    >>> # 解析 Quiz (Lithoformer)
    >>> result = lithoform(
    ...     input_md="quiz.md",
    ...     model="gpt-4o-mini"
    ... )
    >>> print(f"Token 使用: {result['token_usage']}")
"""

__version__ = "0.7.1"
__author__ = "Memosyne Team"

# 导出主要 API
from .api import reanimate, lithoform

__all__ = [
    "reanimate",
    "lithoform",
    "__version__",
    "__author__",
]
