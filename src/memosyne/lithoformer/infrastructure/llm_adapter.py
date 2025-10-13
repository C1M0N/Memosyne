"""
Lithoformer Infrastructure - LLM Adapter

LLM 适配器：实现 Application 层的 LLMPort 接口

职责：
- 封装 LLM Provider（OpenAI/Anthropic）
- 注入 Lithoformer 特定的 Prompts 和 Schemas
- 处理 LLM 调用和错误

DDD 原则（Phase 4.6）：
- Prompts 和 Schemas 属于子域业务逻辑
- 不应放在 Shared Kernel 中
- Adapter 负责组装完整的请求
"""
from typing import Any

from ...core.interfaces import LLMProvider, LLMError
from .prompts import LITHOFORMER_SYSTEM_PROMPT, LITHOFORMER_USER_TEMPLATE
from .schemas import QUIZ_SCHEMA


class LithoformerLLMAdapter:
    """Lithoformer LLM Adapter (implements LLMPort)"""

    def __init__(self, provider: LLMProvider):
        """
        Args:
            provider: LLM 提供商（OpenAI/Anthropic）
        """
        self.provider = provider

    def parse_quiz(self, markdown: str) -> tuple[dict[str, Any], dict[str, int]]:
        """
        解析 Quiz Markdown（实现 LLMPort.parse_quiz）

        Args:
            markdown: Quiz Markdown 文本

        Returns:
            (llm_response_dict, token_usage_dict)

        Raises:
            LLMError: LLM 调用失败
        """
        try:
            # 组装 Lithoformer 特定的 prompts
            system_prompt = LITHOFORMER_SYSTEM_PROMPT
            user_prompt = LITHOFORMER_USER_TEMPLATE.format(md=markdown)

            # 调用底层 LLM Provider 的通用方法
            llm_response, token_usage = self.provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=QUIZ_SCHEMA["schema"],
                schema_name=QUIZ_SCHEMA["name"]
            )

            # 转换 TokenUsage 对象为字典（适配端口接口）
            token_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

            return llm_response, token_dict

        except LLMError:
            # LLM 错误直接向上传播
            raise

        except Exception as e:
            # 其他错误包装为 LLMError
            raise LLMError(f"LLM 调用失败：{e}") from e

    @classmethod
    def from_provider(cls, provider: LLMProvider) -> "LithoformerLLMAdapter":
        """
        工厂方法：从 LLM Provider 创建适配器

        Args:
            provider: LLM 提供商

        Returns:
            LithoformerLLMAdapter 实例
        """
        return cls(provider=provider)
