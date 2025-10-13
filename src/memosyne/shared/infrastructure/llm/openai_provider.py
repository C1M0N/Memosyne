"""OpenAI Provider - Shared Infrastructure Layer

DDD 原则：
- Shared Kernel 不包含业务逻辑
- 提供通用的 LLM 调用能力
- 业务相关的 prompts/schemas 由子域自行管理

重构说明：
在上一版尝试切换到 ``client.responses.parse`` 之后，macOS 用户反馈
``OSError: [Errno 63] File name too long``。排查发现 OpenAI SDK 会把
``input`` 字段当作待上传文件路径，把整段 Markdown 题干错当成文件名。
本次修复回退到稳定的 ``chat.completions`` 调用方式，并保留健壮的 JSON
解析逻辑，以适配 SDK 行为差异。
"""
from __future__ import annotations

import json
from typing import Any

from openai import BadRequestError, OpenAI

from ....core.interfaces import BaseLLMProvider, LLMError
from ....core.models import TokenUsage


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

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> tuple[dict[str, Any], TokenUsage]:
        """调用 OpenAI API 生成结构化 JSON 响应"""
        schema_payload = {
            "name": schema_name,
            "strict": True,
            "schema": schema,
        }

        return self._request_via_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_payload=schema_payload,
        )

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("OpenAI API Key 未设置")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request_via_chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_payload: dict[str, Any],
        system_role: str = "system",
    ) -> tuple[dict[str, Any], TokenUsage]:
        """向 Chat Completions 请求结构化 JSON。"""

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": system_role, "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": schema_payload,
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            response = self.client.chat.completions.create(**kwargs)
            data = self._extract_chat_output(response)
            tokens = self._extract_token_usage(response)
            return data, tokens
        except BadRequestError as exc:
            error_msg = str(exc).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
                data = self._extract_chat_output(response)
                tokens = self._extract_token_usage(response)
                return data, tokens
            raise LLMError(f"OpenAI API 错误：{exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"调用 OpenAI 时发生意外错误：{exc}") from exc

    @staticmethod
    def _extract_chat_output(response: Any) -> dict[str, Any]:
        """Extract structured JSON from ``chat.completions`` output."""

        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError) as exc:  # noqa: BLE001
            raise LLMError(f"解析 LLM 响应失败：{exc}") from exc

        if isinstance(content, dict):
            parsed = content.get("parsed")
            if isinstance(parsed, dict):
                return parsed
            text_value = content.get("text")
            if isinstance(text_value, str):
                return OpenAIProvider._loads_json(text_value)

        if isinstance(content, list):
            text_segments: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    parsed = part.get("parsed")
                    if isinstance(parsed, dict):
                        return parsed
                    text_val = part.get("text") or part.get("value")
                else:
                    text_val = getattr(part, "text", None)
                    parsed = getattr(part, "parsed", None)
                    if isinstance(parsed, dict):
                        return parsed
                if isinstance(text_val, str):
                    text_segments.append(text_val)
            if text_segments:
                return OpenAIProvider._loads_json("".join(text_segments))

        if isinstance(content, str):
            return OpenAIProvider._loads_json(content)

        raise LLMError("OpenAI 响应格式未知，无法解析 JSON")

    @staticmethod
    def _loads_json(payload: str) -> dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LLMError(f"解析 LLM 响应失败：{exc}") from exc

    @staticmethod
    def _extract_token_usage(response: Any) -> TokenUsage:
        """从响应中提取 Token 使用量"""
        try:
            usage = response.usage
            return TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )
        except (AttributeError, TypeError):
            # 如果没有 usage 信息，返回全 0
            return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
