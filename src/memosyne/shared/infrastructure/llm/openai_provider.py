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
        max_retries: int | None = None
    ):
        # 从数据库读取max_retries默认值（不再硬编码，默认2）
        if max_retries is None:
            from ...config import get_settings
            from ..app_config import SQLiteAppConfigService
            settings = get_settings()
            appcfg = SQLiteAppConfigService(settings.db_dir / "config.db")
            provider_config = appcfg.get_provider_config()
            max_retries = provider_config["openai_max_retries"]

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
    ) -> tuple[dict[str, Any], TokenUsage, dict | None]:
        """调用 OpenAI API 生成结构化 JSON 响应

        Returns:
            tuple: (response_data, token_usage, rate_limit_info)
                - response_data: 解析后的JSON数据
                - token_usage: token使用情况
                - rate_limit_info: rate limit信息（如果可用）
        """
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
    ) -> tuple[dict[str, Any], TokenUsage, dict | None]:
        """向 Chat Completions 请求结构化 JSON。

        Returns:
            tuple: (data, tokens, rate_limit_info)
        """

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
            # 使用with_raw_response()获取原始响应（包含headers）
            raw_response = self.client.chat.completions.with_raw_response.create(**kwargs)
            response = raw_response.parse()  # 解析为ChatCompletion对象

            data = self._extract_chat_output(response)
            tokens = self._extract_token_usage(response)
            rate_limit_info = self._extract_rate_limit_info(raw_response.headers)

            return data, tokens, rate_limit_info

        except BadRequestError as exc:
            error_msg = str(exc).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                raw_response = self.client.chat.completions.with_raw_response.create(**kwargs)
                response = raw_response.parse()

                data = self._extract_chat_output(response)
                tokens = self._extract_token_usage(response)
                rate_limit_info = self._extract_rate_limit_info(raw_response.headers)

                return data, tokens, rate_limit_info

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

    def _extract_rate_limit_info(self, headers) -> dict | None:
        """从响应headers中提取rate limit信息

        OpenAI API返回的headers格式：
        - x-ratelimit-remaining-requests: 剩余请求数
        - x-ratelimit-remaining-tokens: 剩余token数
        - x-ratelimit-limit-requests: 请求数限制
        - x-ratelimit-limit-tokens: token数限制

        Returns:
            dict | None: rate limit信息，如果headers不可用则返回None
        """
        try:
            import time
            from logging import getLogger

            logger = getLogger("memosyne.shared.infrastructure.llm.openai")

            # 从headers提取rate limit信息
            remaining_requests = headers.get("x-ratelimit-remaining-requests")
            remaining_tokens = headers.get("x-ratelimit-remaining-tokens")
            limit_requests = headers.get("x-ratelimit-limit-requests")
            limit_tokens = headers.get("x-ratelimit-limit-tokens")
            reset_tokens = headers.get("x-ratelimit-reset-tokens")

            # 如果任何一个关键值缺失，返回None
            if not all([remaining_requests, remaining_tokens, limit_requests, limit_tokens]):
                return None

            # 解析reset时间（格式："2.989s" -> 2秒）
            reset_tokens_seconds = None
            reset_timestamp = None
            if reset_tokens:
                try:
                    # 移除"s"后缀，转换为float并取整
                    reset_tokens_seconds = int(float(reset_tokens.rstrip('s')))
                    # 计算reset的绝对时间戳（消除网络延迟影响）
                    reset_timestamp = time.time() + reset_tokens_seconds
                except (ValueError, AttributeError):
                    reset_tokens_seconds = None
                    reset_timestamp = None

            return {
                "remaining_requests": int(remaining_requests),
                "limit_requests": int(limit_requests),
                "remaining_tokens": int(remaining_tokens),
                "limit_tokens": int(limit_tokens),
                "reset_tokens_seconds": reset_tokens_seconds,  # 原始秒数（用于debug）
                "reset_timestamp": reset_timestamp,  # 绝对时间戳（用于准确倒计时）
                "provider": "openai",
                "model": self.model,  # 添加model信息，用于4o-mini特殊处理
                "timestamp": time.time(),
            }

        except (AttributeError, TypeError, ValueError, KeyError):
            # 如果提取失败，返回None
            return None
