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
        prompt_tokens: 提示词 Token 数
        completion_tokens: 补全 Token 数
        total_tokens: 总 Token 数
    """

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

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


__all__ = ["TokenUsage", "ProcessResult"]
