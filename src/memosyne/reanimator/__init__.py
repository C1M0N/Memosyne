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
    WordID,
    apply_business_rules,
    map_field_label,
    generate_word_id,
    parse_word_index_from_filename,
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
    "WordID",
    "apply_business_rules",
    "map_field_label",
    "generate_word_id",
    "parse_word_index_from_filename",
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
