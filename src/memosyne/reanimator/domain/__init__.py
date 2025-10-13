"""
Reanimator Domain Layer

The innermost layer following strict dependency rules:
- Zero external dependencies (only Python stdlib and Pydantic)
- Encapsulates business concepts (Terms, Memo IDs, POS tags)
- Encapsulates business rules (POS correction, tag mapping)
- Independently testable (no mocks needed)
"""
from .models import TermInput, LLMResponse, TermOutput, MemoID
from .services import (
    apply_business_rules,
    get_chinese_tag,
    generate_memo_id,
    validate_word_format,
    should_force_phrase_pos,
)
from .exceptions import (
    ReanimatorDomainError,
    InvalidTermError,
    InvalidMemoIDError,
    TermValidationError,
    POSCorrectionError,
)

__all__ = [
    # Models
    "TermInput",
    "LLMResponse",
    "TermOutput",
    "MemoID",
    # Services
    "apply_business_rules",
    "get_chinese_tag",
    "generate_memo_id",
    "validate_word_format",
    "should_force_phrase_pos",
    # Exceptions
    "ReanimatorDomainError",
    "InvalidTermError",
    "InvalidMemoIDError",
    "TermValidationError",
    "POSCorrectionError",
]
