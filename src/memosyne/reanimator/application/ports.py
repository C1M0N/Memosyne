"""
Reanimator Application Ports - 端口接口（依赖倒置）

端口 = 接口抽象，定义应用层需要的外部能力。
适配器（Infrastructure 层）负责实现这些端口。

依赖规则：
- Application 层定义端口（Protocol）
- Infrastructure 层实现端口（Adapter）
- 依赖箭头：Infrastructure → Application（而非相反）

这实现了依赖倒置原则（DIP）：高层模块不依赖低层模块，都依赖抽象。
"""
from typing import Protocol, runtime_checkable
from pathlib import Path

from ..domain.models import TermInput, TermOutput


# ============================================================
# LLM Port - LLM 调用能力
# ============================================================
@runtime_checkable
class LLMPort(Protocol):
    """LLM 调用端口（由 Infrastructure 层实现）

    职责：
    - 发送 Prompt 到 LLM
    - 接收结构化响应
    - 处理错误和重试

    实现者：
    - ReanimatorLLMAdapter (infrastructure/llm_adapter.py)
    """

    def process_term(self, word: str, zh_def: str) -> tuple[dict, dict]:
        """
        处理单个术语，调用 LLM 生成术语信息

        Args:
            word: 英文词条
            zh_def: 中文释义

        Returns:
            (llm_response_dict, token_usage_dict)
            - llm_response_dict: LLM 返回的术语信息（字典格式）
            - token_usage_dict: Token 使用统计

        Raises:
            LLMError: LLM 调用失败（网络错误、API 错误等）

        Example:
            >>> adapter = ReanimatorLLMAdapter(...)
            >>> resp, tokens = adapter.process_term("neuron", "神经元")
            >>> resp["POS"]
            'n.'
            >>> tokens["total_tokens"]
            150
        """
        ...


# ============================================================
# Term Repository Port - 术语存储能力
# ============================================================
@runtime_checkable
class TermRepositoryPort(Protocol):
    """术语仓储端口（由 Infrastructure 层实现）

    职责：
    - 读取输入术语（CSV）
    - 写出处理结果（CSV）

    实现者：
    - CSVTermAdapter (infrastructure/csv_adapter.py)
    """

    def read_input(self, path: Path) -> list[TermInput]:
        """
        读取输入术语

        Args:
            path: 输入文件路径（CSV）

        Returns:
            术语输入列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误

        Example:
            >>> repo = CSVTermAdapter()
            >>> terms = repo.read_input(Path("input.csv"))
            >>> terms[0].word
            'neuroscience'
        """
        ...

    def write_output(self, path: Path, terms: list[TermOutput]) -> None:
        """
        写出处理结果

        Args:
            path: 输出文件路径（CSV）
            terms: 术语输出列表

        Raises:
            OSError: 文件写入失败

        Example:
            >>> repo = CSVTermAdapter()
            >>> repo.write_output(Path("output.csv"), results)
        """
        ...


# ============================================================
# Term List Port - 术语表能力
# ============================================================
@runtime_checkable
class TermListPort(Protocol):
    """术语表端口（由 Infrastructure 层实现）

    职责：
    - 提供英文标签 → 中文标签的映射

    实现者：
    - TermListAdapter (infrastructure/term_list_adapter.py)
    """

    @property
    def mapping(self) -> dict[str, str]:
        """
        获取术语表映射（英文 → 中文）

        Returns:
            映射字典（如 {"psychology": "心理", "neuroscience": "神经"}）

        Example:
            >>> adapter = TermListAdapter()
            >>> adapter.mapping["psychology"]
            '心理'
        """
        ...


# ============================================================
# 使用示例（Mock 实现用于测试）
# ============================================================
if __name__ == "__main__":
    # 演示如何使用端口接口（实际使用时由 Infrastructure 层提供实现）

    class MockLLMAdapter:
        """Mock LLM Adapter（仅用于演示）"""
        def process_term(self, word: str, zh_def: str) -> tuple[dict, dict]:
            return {
                "IPA": "/test/",
                "POS": "n.",
                "EnDef": "Test definition",
                "Example": "Test example"
            }, {"total_tokens": 100}

    class MockTermRepository:
        """Mock Term Repository（仅用于演示）"""
        def read_input(self, path: Path) -> list[TermInput]:
            return [TermInput(word="test", zh_def="测试")]

        def write_output(self, path: Path, terms: list[TermOutput]) -> None:
            print(f"Writing {len(terms)} terms to {path}")

    class MockTermList:
        """Mock Term List（仅用于演示）"""
        @property
        def mapping(self) -> dict[str, str]:
            return {"psychology": "心理"}

    # 验证 Protocol
    llm: LLMPort = MockLLMAdapter()
    repo: TermRepositoryPort = MockTermRepository()
    term_list: TermListPort = MockTermList()

    print("✅ 端口接口定义正确")
    print(f"   LLM Port: {isinstance(llm, LLMPort)}")
    print(f"   Repository Port: {isinstance(repo, TermRepositoryPort)}")
    print(f"   TermList Port: {isinstance(term_list, TermListPort)}")
