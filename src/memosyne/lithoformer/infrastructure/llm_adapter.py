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
from .schemas import QUESTION_SCHEMA


class LithoformerLLMAdapter:
    """Lithoformer LLM Adapter (implements LLMPort)"""

    def __init__(self, provider: LLMProvider):
        """
        Args:
            provider: LLM 提供商（OpenAI/Anthropic）
        """
        self.provider = provider

    def parse_question(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        """
        解析并分析单个题目（实现 LLMPort.parse_question）

        Args:
            payload: 包含 context/question/answer 的字典

        Returns:
            (question_dict, token_usage_dict)

        Raises:
            LLMError: LLM 调用失败
        """
        try:
            context = (payload.get("context") or "").strip()
            question = (payload.get("question") or "").strip()
            answer = (payload.get("answer") or "").strip()

            if not question:
                raise LLMError("题目内容为空，无法解析")

            user_prompt = LITHOFORMER_USER_TEMPLATE.format(
                context=context if context else "",
                question=question,
                answer=answer,
            )

            # 调用底层 LLM Provider 的通用方法
            llm_response, token_usage = self.provider.complete_structured(
                system_prompt=LITHOFORMER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=QUESTION_SCHEMA["schema"],
                schema_name=QUESTION_SCHEMA["name"]
            )

            if not isinstance(llm_response, dict):
                raise LLMError("LLM 返回的数据格式不正确")

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
