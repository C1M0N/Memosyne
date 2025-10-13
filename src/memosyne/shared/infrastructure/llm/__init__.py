"""
Shared LLM Infrastructure

Provides LLM provider implementations (OpenAI, Anthropic) that can be
reused across different bounded contexts (Reanimator, Lithoformer).

Following DDD principles:
- Infrastructure layer depends on Domain abstractions
- Implements core.interfaces.LLMProvider protocol
- No business logic, only technical adapters
"""
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider

__all__ = [
    "OpenAIProvider",
    "AnthropicProvider",
]
