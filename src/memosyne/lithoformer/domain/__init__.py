"""
Lithoformer Domain Layer

The innermost layer following strict dependency rules.
"""
from .models import QuizOptions, QuizItem, QuizResponse
from .services import (
    is_quiz_item_valid,
    filter_valid_items,
    infer_titles_from_filename,
    detect_quiz_type,
    count_questions_by_type,
)
from .exceptions import (
    LithoformerDomainError,
    InvalidQuizError,
    QuizValidationError,
    QuizParsingError,
)

__all__ = [
    # Models
    "QuizOptions",
    "QuizItem",
    "QuizResponse",
    # Services
    "is_quiz_item_valid",
    "filter_valid_items",
    "infer_titles_from_filename",
    "detect_quiz_type",
    "count_questions_by_type",
    # Exceptions
    "LithoformerDomainError",
    "InvalidQuizError",
    "QuizValidationError",
    "QuizParsingError",
]
