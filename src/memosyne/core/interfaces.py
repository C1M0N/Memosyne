"""
核心抽象接口 - 使用 Protocol 定义契约

重构收益：
- ✅ 依赖倒置：高层模块依赖抽象而非具体实现
- ✅ 可测试性：可轻松创建 Mock 对象
- ✅ 可扩展性：新增 LLM 提供商只需实现协议
- ✅ 类型安全：IDE 能检查方法签名
"""
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


# ============================================================
# LLM Provider 接口（使用 Protocol - 鸭子类型）
# ============================================================
@runtime_checkable
class LLMProvider(Protocol):
    """
    LLM 提供商协议

    任何实现了 complete_prompt 和 complete_structured 方法的类都满足此协议，
    无需显式继承（结构化子类型，Structural Subtyping）
    """

    def complete_prompt(self, word: str, zh_def: str) -> dict[str, Any]:
        """
        调用 LLM 生成术语信息

        Args:
            word: 英文词条
            zh_def: 中文释义

        Returns:
            包含 IPA, POS, EnDef 等字段的字典

        Raises:
            LLMError: LLM 调用失败时抛出
        """
        ...

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> dict[str, Any]:
        """
        调用 LLM 生成结构化 JSON 响应

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            schema: JSON Schema 定义（OpenAPI 3.0 格式）
            schema_name: Schema 名称（用于标识，默认 "Response"）

        Returns:
            解析后的 JSON 字典

        Raises:
            LLMError: LLM 调用失败时抛出
        """
        ...


# ============================================================
# LLM Provider 基类（使用 ABC - 显式继承）
# ============================================================
class BaseLLMProvider(ABC):
    """
    LLM 提供商抽象基类

    相比 Protocol，ABC 提供：
    - 共享实现（公共方法）
    - 强制显式继承
    - 初始化验证

    选择建议：
    - 如果需要共享代码 → 使用 ABC
    - 如果只需要接口约束 → 使用 Protocol
    """

    def __init__(self, model: str, temperature: float | None = None):
        self.model = model
        self.temperature = temperature
        self._validate_config()

    @abstractmethod
    def complete_prompt(self, word: str, zh_def: str) -> dict[str, Any]:
        """调用 LLM 生成术语信息（子类必须实现）"""
        pass

    @abstractmethod
    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> dict[str, Any]:
        """调用 LLM 生成结构化 JSON 响应（子类必须实现）"""
        pass

    def _validate_config(self) -> None:
        """验证配置（子类可重写）"""
        if not self.model:
            raise ValueError("model 不能为空")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r})"


# ============================================================
# Repository 接口
# ============================================================
class TermListRepository(Protocol):
    """术语表仓储协议"""

    def load(self) -> dict[str, str]:
        """加载术语表（英文 -> 两字中文）"""
        ...

    def get_chinese_tag(self, english_tag: str) -> str:
        """获取中文标签"""
        ...


class CSVRepository(Protocol):
    """CSV 数据仓储协议"""

    def read_terms(self, path: str) -> list[dict]:
        """读取术语 CSV"""
        ...

    def write_terms(self, path: str, terms: list[dict]) -> None:
        """写出术语 CSV"""
        ...


# ============================================================
# 自定义异常
# ============================================================
class MemosymeError(Exception):
    """Memosyne 基础异常"""
    pass


class LLMError(MemosymeError):
    """LLM 调用异常"""
    pass


class ConfigError(MemosymeError):
    """配置错误"""
    pass


class ValidationError(MemosymeError):
    """数据验证异常"""
    pass


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 示例 1: 使用 Protocol（鸭子类型）
    class MockLLM:
        """Mock LLM - 不需要显式继承 LLMProvider"""
        def complete_prompt(self, word: str, zh_def: str) -> dict[str, Any]:
            return {"IPA": "/test/", "POS": "n.", "word": word, "zh_def": zh_def}

        def complete_structured(
            self,
            system_prompt: str,
            user_prompt: str,
            schema: dict[str, Any],
            schema_name: str = "Response"
        ) -> dict[str, Any]:
            return {"result": "mock", "schema": schema_name}

    mock = MockLLM()
    assert isinstance(mock, LLMProvider)  # True!

    # 示例 2: 使用 ABC（显式继承）
    class ExampleProvider(BaseLLMProvider):
        def complete_prompt(self, word: str, zh_def: str) -> dict[str, Any]:
            return {"model": self.model, "word": word, "zh_def": zh_def}

        def complete_structured(
            self,
            system_prompt: str,
            user_prompt: str,
            schema: dict[str, Any],
            schema_name: str = "Response"
        ) -> dict[str, Any]:
            return {"model": self.model, "schema": schema_name}

    provider = ExampleProvider(model="gpt-4o-mini")
    print(provider)  # ExampleProvider(model='gpt-4o-mini')

    # 示例 3: 类型检查
    def process_with_llm(llm: LLMProvider, word: str) -> dict[str, Any]:
        """接受任何实现了 LLMProvider 协议的对象"""
        return llm.complete_prompt(word, "测试")

    # 两种实现都可以传入
    process_with_llm(mock, "test")
    process_with_llm(provider, "test")
