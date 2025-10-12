"""
OpenAI Provider - 重构版本

基于原 src/mms_pipeline/openai_helper.py
改进：继承抽象基类、结构化日志、可注入配置
"""
import json
from typing import Any
from openai import OpenAI, BadRequestError

from ..core.interfaces import BaseLLMProvider, LLMError
from ..models.result import TokenUsage
from ..prompts import REANIMATER_SYSTEM_PROMPT, REANIMATER_USER_TEMPLATE
from ..schemas import TERM_RESULT_SCHEMA


# Prompt 和 Schema 现在从独立模块导入


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider"""

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float | None = None,
        max_retries: int = 2
    ):
        self.client = OpenAI(api_key=api_key, max_retries=max_retries)
        super().__init__(model=model, temperature=temperature)

    @classmethod
    def from_settings(cls, settings) -> "OpenAIProvider":
        """从配置创建实例"""
        return cls(
            model=settings.default_openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.default_temperature,
        )

    def complete_prompt(self, word: str, zh_def: str) -> tuple[dict[str, Any], TokenUsage]:
        """调用 OpenAI API 生成术语信息"""
        user_message = REANIMATER_USER_TEMPLATE.format(word=word, zh_def=zh_def)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": REANIMATER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": TERM_RESULT_SCHEMA
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            response = self.client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            error_msg = str(e).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise LLMError(f"OpenAI API 错误：{e}") from e
        except Exception as e:
            raise LLMError(f"调用 OpenAI 时发生意外错误：{e}") from e

        try:
            content = response.choices[0].message.content
            result = json.loads(content)

            # 提取 token 使用信息
            usage = response.usage
            tokens = TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )

            return result, tokens
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise LLMError(f"解析 LLM 响应失败：{e}") from e

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> tuple[dict[str, Any], TokenUsage]:
        """调用 OpenAI API 生成结构化 JSON 响应"""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema
                }
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            response = self.client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            error_msg = str(e).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise LLMError(f"OpenAI API 错误：{e}") from e
        except Exception as e:
            raise LLMError(f"调用 OpenAI 时发生意外错误：{e}") from e

        try:
            content = response.choices[0].message.content
            result = json.loads(content)

            # 提取 token 使用信息
            usage = response.usage
            tokens = TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )

            return result, tokens
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise LLMError(f"解析 LLM 响应失败：{e}") from e

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("OpenAI API Key 未设置")
