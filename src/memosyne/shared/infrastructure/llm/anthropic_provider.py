"""
Anthropic Provider - Shared Infrastructure Layer

DDD 原则：
- Shared Kernel 不包含业务逻辑
- 提供通用的 LLM 调用能力
- 业务相关的 prompts/schemas 由子域自行管理

基于原 src/mms_pipeline/anthropic_helper.py
改进：继承抽象基类、移除业务特定逻辑
"""
import json
from typing import Any
from anthropic import Anthropic, APIError

from ....core.interfaces import BaseLLMProvider, LLMError
from ....core.models import TokenUsage


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM Provider"""

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float | None = None,
        max_tokens: int | None = None  # None 则使用模型最大输出
    ):
        self.client = Anthropic(api_key=api_key)
        super().__init__(model=model, temperature=temperature)
        # Anthropic API 要求必须提供 max_tokens（与 OpenAI 不同）
        # 设置为足够大的值，让 API 自己决定实际能用多少
        # Claude 3.5 Sonnet 最大输出约 8192 tokens，但设置更大值也安全
        self.max_tokens = max_tokens if max_tokens is not None else 16384

    @classmethod
    def from_settings(cls, settings) -> "AnthropicProvider":
        """从配置创建实例"""
        return cls(
            model=settings.default_anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.default_temperature,
        )

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> tuple[dict[str, Any], TokenUsage]:
        """调用 Anthropic API 生成结构化 JSON 响应（使用 Tool Use）"""
        tool = {
            "name": schema_name,
            "description": f"Structured response format: {schema_name}",
            "input_schema": schema,
        }

        kwargs: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": self.max_tokens,
            "tools": [tool],
            "tool_choice": {"type": "tool", "name": schema_name},
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            resp = self.client.messages.create(**kwargs)
        except APIError as e:
            if "tool_choice" in str(e):
                kwargs.pop("tool_choice", None)
                resp = self.client.messages.create(**kwargs)
            else:
                raise LLMError(f"Anthropic API 错误：{e}") from e
        except Exception as e:
            raise LLMError(f"调用 Anthropic 时发生意外错误：{e}") from e

        # 提取 token 使用信息
        usage = resp.usage
        tokens = TokenUsage(
            prompt_tokens=usage.input_tokens if usage else 0,
            completion_tokens=usage.output_tokens if usage else 0,
            total_tokens=(usage.input_tokens + usage.output_tokens) if usage else 0,
        )

        # 解析 tool_use 区块
        for block in (resp.content or []):
            btype = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")
            bname = getattr(block, "name", None) if hasattr(block, "name") else block.get("name")
            if btype == "tool_use" and bname == schema_name:
                binput = getattr(block, "input", None) if hasattr(block, "input") else block.get("input")
                if isinstance(binput, dict):
                    return binput, tokens

        # 容错：尝试从文本提取 JSON
        text_parts = []
        for block in (resp.content or []):
            if hasattr(block, "type") and block.type == "text" and hasattr(block, "text"):
                text_parts.append(block.text or "")
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text") or "")
        text = "".join(text_parts).strip()

        try:
            return json.loads(text), tokens
        except json.JSONDecodeError:
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1 and e > s:
                return json.loads(text[s:e+1]), tokens
            raise LLMError("Claude 未返回可解析的结构化结果")

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("Anthropic API Key 未设置")
