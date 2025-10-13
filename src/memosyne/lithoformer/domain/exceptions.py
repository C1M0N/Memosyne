"""
Lithoformer Domain Exceptions

Dependency rules:
- Zero external dependencies (only Python stdlib)
- Express business errors (not technical errors)
"""


class LithoformerDomainError(Exception):
    """Lithoformer domain exception base class"""
    pass


class InvalidQuizError(LithoformerDomainError):
    """Invalid quiz item"""

    def __init__(self, qtype: str, reason: str):
        self.qtype = qtype
        self.reason = reason
        super().__init__(f"Invalid quiz ({qtype}): {reason}")


class QuizValidationError(LithoformerDomainError):
    """Quiz validation failed"""

    def __init__(self, field: str, value: str, constraint: str):
        self.field = field
        self.value = value
        self.constraint = constraint
        super().__init__(
            f"Field '{field}' validation failed: value '{value}' violates '{constraint}'"
        )


class QuizParsingError(LithoformerDomainError):
    """Quiz parsing failed"""

    def __init__(self, content: str, reason: str):
        self.content = content[:100]  # Truncate
        self.reason = reason
        super().__init__(f"Quiz parsing failed: {reason}")
