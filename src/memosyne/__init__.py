"""
Memosyne - LLM-based terminology and quiz processing toolkit

Version: 2.0.0 (Refactored)

Quick Start:
    >>> from memosyne import process_terms, parse_quiz
    >>>
    >>> # 处理术语
    >>> result = process_terms(
    ...     input_csv="221.csv",
    ...     start_memo_index=221,
    ...     model="gpt-4o-mini"
    ... )
    >>>
    >>> # 解析 Quiz
    >>> result = parse_quiz(
    ...     input_md="quiz.md",
    ...     model="gpt-4o-mini"
    ... )
"""

__version__ = "2.0.0"
__author__ = "Memosyne Team"

# 导出主要 API
from .api import process_terms, parse_quiz, mms, exparser

__all__ = [
    "process_terms",
    "parse_quiz",
    "mms",
    "exparser",
    "__version__",
    "__author__",
]
