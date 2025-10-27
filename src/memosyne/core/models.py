"""
Core Models - 核心共享数据模型

包含跨域共享的基础模型，如 Token 使用统计等
"""
from typing import TypeVar, Generic
from pydantic import BaseModel, Field


T = TypeVar("T")


class TokenUsage(BaseModel):
    """
    Token 使用统计

    Attributes:
        prompt_tokens: 提示词 Token 数（OpenAI命名）
        completion_tokens: 补全 Token 数（OpenAI命名）
        total_tokens: 总 Token 数

    注：input_tokens和output_tokens是别名（Anthropic命名）
    """

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    @property
    def input_tokens(self) -> int:
        """Anthropic风格别名：input_tokens = prompt_tokens"""
        return self.prompt_tokens

    @property
    def output_tokens(self) -> int:
        """Anthropic风格别名：output_tokens = completion_tokens"""
        return self.completion_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """支持 TokenUsage 相加"""
        if not isinstance(other, TokenUsage):
            raise TypeError(f"Cannot add TokenUsage with {type(other)}")
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def __repr__(self) -> str:
        return f"TokenUsage(prompt={self.prompt_tokens}, completion={self.completion_tokens}, total={self.total_tokens})"


class ProcessResult(BaseModel, Generic[T]):
    """
    处理结果容器（泛型）

    用于封装批量处理的结果，包含：
    - 成功处理的项目列表
    - 成功/失败计数
    - Token 使用统计
    """

    items: list[T] = Field(default_factory=list)
    success_count: int = Field(default=0, ge=0)
    total_count: int = Field(default=0, ge=0)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    def __repr__(self) -> str:
        return f"ProcessResult(success={self.success_count}/{self.total_count}, tokens={self.token_usage})"


class Configuration(BaseModel):
    """
    应用配置值对象

    用于封装应用的配置数据，包括路径配置和模型配置
    """

    # 路径配置
    lithoformer_input_dir: str = Field(default="", description="Lithoformer输入目录")
    lithoformer_output_dir: str = Field(default="", description="Lithoformer输出目录")

    # 模型配置（格式：Provider::model，如 OpenAI::gpt-4o-mini）
    default_model: str = Field(default="OpenAI::gpt-4o-mini", description="默认使用模型")

    # 预留配置项（7个）
    reserved_config_1: str = Field(default="", description="预留配置1")
    reserved_config_2: str = Field(default="", description="预留配置2")
    reserved_config_3: str = Field(default="", description="预留配置3")
    reserved_config_4: str = Field(default="", description="预留配置4")
    reserved_config_5: str = Field(default="", description="预留配置5")
    reserved_config_6: str = Field(default="", description="预留配置6")
    reserved_config_7: str = Field(default="", description="预留配置7")

    def parse_model(self) -> tuple[str, str]:
        """
        解析模型字符串，返回 (provider, model_name)

        格式：Provider::model（双冒号，首字母大写）

        Examples:
            >>> config = Configuration(default_model="OpenAI::gpt-4o-mini")
            >>> config.parse_model()
            ('openai', 'gpt-4o-mini')
        """
        if "::" in self.default_model:
            parts = self.default_model.split("::", 1)
            provider = parts[0].lower()  # 转换为小写
            model = parts[1]
            return provider, model
        # 向后兼容旧格式（单冒号）
        if ":" in self.default_model:
            parts = self.default_model.split(":", 1)
            provider = parts[0].lower()
            model = parts[1]
            return provider, model
        # 默认假设是OpenAI模型
        return "openai", self.default_model

    @staticmethod
    def format_model(provider: str, model: str) -> str:
        """
        格式化模型字符串

        Args:
            provider: 厂商名（如 'openai', 'anthropic'）
            model: 模型名（如 'gpt-4o-mini'）

        Returns:
            格式化的模型字符串（如 'OpenAI::gpt-4o-mini'）
        """
        provider_map = {
            "openai": "OpenAI",
            "anthropic": "Anthropic",
        }
        provider_formatted = provider_map.get(provider.lower(), provider.capitalize())
        return f"{provider_formatted}::{model}"


__all__ = ["TokenUsage", "ProcessResult", "Configuration"]
