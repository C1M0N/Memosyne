"""
Reanimator Sub-domain

A complete Ports & Adapters architecture for term processing.

Structure:
- domain/ - Business logic (zero dependencies)
- application/ - Use cases and ports (depends on domain)
- infrastructure/ - Adapters (implements ports)
- cli/ - Command-line interface (depends on all layers)

Usage:
    >>> from memosyne.reanimator.application import ProcessTermsUseCase
    >>> from memosyne.reanimator.infrastructure import ReanimatorLLMAdapter
    >>> from memosyne.reanimator.domain import TermInput
"""
# Domain layer exports
from .domain import (
    TermInput,
    LLMResponse,
    TermOutput,
    MemoID,
    apply_business_rules,
    get_chinese_tag,
    generate_memo_id,
)

# Application layer exports
from .application import (
    LLMPort,
    TermRepositoryPort,
    TermListPort,
    ProcessTermsUseCase,
)

# Infrastructure layer exports
from .infrastructure import (
    ReanimatorLLMAdapter,
    CSVTermAdapter,
    TermListAdapter,
)

__all__ = [
    # Domain
    "TermInput",
    "LLMResponse",
    "TermOutput",
    "MemoID",
    "apply_business_rules",
    "get_chinese_tag",
    "generate_memo_id",
    # Application
    "LLMPort",
    "TermRepositoryPort",
    "TermListPort",
    "ProcessTermsUseCase",
    # Infrastructure
    "ReanimatorLLMAdapter",
    "CSVTermAdapter",
    "TermListAdapter",
]
