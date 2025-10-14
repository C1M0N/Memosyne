"""
Memosyne - LLM-based terminology and quiz processing toolkit

Version: 0.9.0

Quick Start:
    >>> from memosyne import reanimate, lithoform
    >>>
    >>> # 处理术语 (Reanimator)
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

__version__ = "0.9.0"
__author__ = "Memosyne Team"

# 导出主要 API
from .api import reanimate, lithoform

# 向后兼容别名
process_terms = reanimate  # v2.0 之前的名称
parse_quiz = lithoform     # v2.0 之前的名称

__all__ = [
    "reanimate",
    "lithoform",
    "process_terms",  # backward compatibility
    "parse_quiz",     # backward compatibility
    "__version__",
    "__author__",
]
