"""Lithoformer Infrastructure - LLM Adapter"""
from typing import Any
from ...core.interfaces import LLMProvider, LLMError


class LithoformerLLMAdapter:
    """Lithoformer LLM Adapter (implements LLMPort)"""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def parse_quiz(self, markdown: str) -> tuple[dict[str, Any], dict[str, int]]:
        """Parse quiz markdown using LLM"""
        try:
            from ...schemas.quiz_schema import get_quiz_schema

            llm_response, token_usage = self.provider.complete_structured(
                system_prompt="You are a quiz parser. Parse the markdown quiz into structured format.",
                user_prompt=markdown,
                schema=get_quiz_schema(),
                schema_name="QuizResponse"
            )

            token_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

            return llm_response, token_dict
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM call failed: {e}") from e

    @classmethod
    def from_provider(cls, provider: LLMProvider) -> "LithoformerLLMAdapter":
        return cls(provider=provider)
