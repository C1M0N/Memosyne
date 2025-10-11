"""
处理结果数据模型

统一的处理结果封装，包含 token 统计和元数据
"""
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

# 泛型类型变量（TermOutput 或 QuizItem）
T = TypeVar("T")


class TokenUsage(BaseModel):
    """Token 使用统计"""

    prompt_tokens: int = Field(default=0, description="输入 tokens")
    completion_tokens: int = Field(default=0, description="输出 tokens")
    total_tokens: int = Field(default=0, description="总 tokens")

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """累加 token 统计"""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def __str__(self) -> str:
        """格式化显示"""
        return f"Tokens: {self.total_tokens:,} (in={self.prompt_tokens:,}, out={self.completion_tokens:,})"


class ProcessResult(BaseModel, Generic[T]):
    """
    处理结果封装

    泛型参数 T 可以是 TermOutput 或 QuizItem
    """

    items: list[T] = Field(default_factory=list, description="处理结果列表")
    success_count: int = Field(default=0, description="成功数量")
    total_count: int = Field(default=0, description="总数量")
    token_usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 使用统计")

    @property
    def failure_count(self) -> int:
        """失败数量"""
        return self.total_count - self.success_count

    @property
    def success_rate(self) -> float:
        """成功率（0-1）"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def __str__(self) -> str:
        """格式化显示"""
        return (
            f"ProcessResult(items={len(self.items)}, "
            f"success={self.success_count}/{self.total_count}, "
            f"tokens={self.token_usage.total_tokens:,})"
        )


# 为了向后兼容，也可以直接返回列表
# 但新代码建议使用 ProcessResult
