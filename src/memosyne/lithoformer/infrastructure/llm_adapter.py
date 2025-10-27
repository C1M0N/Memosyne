"""
Lithoformer Infrastructure - LLM Adapter

LLM 适配器：实现 Application 层的 LLMPort 接口

职责：
- 封装 LLM Provider（OpenAI/Anthropic）
- 注入 Lithoformer 特定的 Prompts 和 Schemas
- 处理 LLM 调用和错误
- 支持动态配置（v0.11+）：根据功能开关动态生成schema和prompt

DDD 原则（Phase 4.6）：
- Prompts 和 Schemas 属于子域业务逻辑
- 不应放在 Shared Kernel 中
- Adapter 负责组装完整的请求
"""
from typing import Any

from ...core.interfaces import LLMProvider, LLMError
from .prompts import (
    LITHOFORMER_SYSTEM_PROMPT,
    LITHOFORMER_USER_TEMPLATE,
    get_dynamic_system_prompt,
    get_dynamic_user_prompt,
)
from .schemas import QUESTION_SCHEMA, get_dynamic_schema
from ..domain.models import FeatureConfig


class LithoformerLLMAdapter:
    """Lithoformer LLM Adapter (implements LLMPort)"""

    def __init__(self, provider: LLMProvider, feature_config: FeatureConfig | None = None):
        """
        Args:
            provider: LLM 提供商（OpenAI/Anthropic）
            feature_config: 功能配置（可选）。如果提供，将使用动态schema和prompt
        """
        self.provider = provider
        self.feature_config = feature_config

    def parse_question(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int], dict | None]:
        """
        解析并分析单个题目（实现 LLMPort.parse_question）

        Args:
            payload: 包含 context/question/answer/note 的字典

        Returns:
            (question_dict, token_usage_dict, rate_limit_info)
            - question_dict: 解析后的题目字典
            - token_usage_dict: token使用情况
            - rate_limit_info: rate limit信息（如果LLM provider提供）

        Raises:
            LLMError: LLM 调用失败
        """
        try:
            context = (payload.get("context") or "").strip()
            question = (payload.get("question") or "").strip()
            answer = (payload.get("answer") or "").strip()
            note = (payload.get("note") or "").strip()

            if not question:
                raise LLMError("题目内容为空，无法解析")

            # 根据feature_config选择schema和prompt
            if self.feature_config:
                # 使用动态schema和prompt
                schema_type = self.feature_config.get_schema_type()
                schema = get_dynamic_schema(schema_type)
                system_prompt = get_dynamic_system_prompt(schema_type)
            else:
                # 使用默认schema和prompt（向后兼容）
                schema = QUESTION_SCHEMA
                system_prompt = LITHOFORMER_SYSTEM_PROMPT

            user_prompt = LITHOFORMER_USER_TEMPLATE.format(
                context=context if context else "",
                question=question,
                answer=answer,
            )

            # 如果有备注，附加到user prompt后面
            if note:
                user_prompt += f"\n\n备注：{note}"

            # 调用底层 LLM Provider 的通用方法（现在返回3个值）
            llm_response, token_usage, rate_limit_info = self.provider.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema["schema"],
                schema_name=schema["name"]
            )

            if not isinstance(llm_response, dict):
                raise LLMError("LLM 返回的数据格式不正确")

            token_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

            return llm_response, token_dict, rate_limit_info

        except LLMError:
            # LLM 错误直接向上传播
            raise

        except Exception as e:
            # 其他错误包装为 LLMError
            raise LLMError(f"LLM 调用失败：{e}") from e

    @classmethod
    def from_provider(
        cls,
        provider: LLMProvider,
        feature_config: FeatureConfig | None = None
    ) -> "LithoformerLLMAdapter":
        """
        工厂方法：从 LLM Provider 创建适配器

        Args:
            provider: LLM 提供商
            feature_config: 功能配置（可选）

        Returns:
            LithoformerLLMAdapter 实例
        """
        return cls(provider=provider, feature_config=feature_config)
