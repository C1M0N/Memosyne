"""
Reanimator Infrastructure - CSV Adapter

CSV 适配器：实现 Application 层的 TermRepositoryPort 接口

职责：
- 读取输入术语 CSV
- 写出处理结果 CSV
- 委托给现有的 CSVTermRepository
"""
from pathlib import Path

from ..domain.models import TermInput, TermOutput
from ...shared.infrastructure.storage.csv_repository import CSVTermRepository


class CSVTermAdapter:
    """
    CSV 术语适配器（实现 TermRepositoryPort）

    封装 CSVTermRepository，提供符合端口接口的方法。
    """

    def __init__(self):
        """初始化适配器"""
        # CSVTermRepository 是无状态的，直接使用类方法
        pass

    def read_input(self, path: Path) -> list[TermInput]:
        """
        读取输入术语（实现 TermRepositoryPort.read_input）

        Args:
            path: 输入文件路径

        Returns:
            术语输入列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        # 委托给 CSVTermRepository
        return CSVTermRepository.read_input(path)

    def write_output(self, path: Path, terms: list[TermOutput]) -> None:
        """
        写出处理结果（实现 TermRepositoryPort.write_output）

        Args:
            path: 输出文件路径
            terms: 术语输出列表

        Raises:
            OSError: 文件写入失败
        """
        # 委托给 CSVTermRepository
        CSVTermRepository.write_output(path, terms)

    @classmethod
    def create(cls) -> "CSVTermAdapter":
        """
        工厂方法：创建适配器实例

        Returns:
            CSVTermAdapter 实例
        """
        return cls()


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    print("""
    CSVTermAdapter 使用示例：

    # 1. 创建适配器
    adapter = CSVTermAdapter.create()

    # 2. 读取输入
    from pathlib import Path
    terms = adapter.read_input(Path("data/input/reanimator/221.csv"))
    print(f"读取到 {len(terms)} 个术语")

    # 3. 写出结果
    # (假设已经处理完成)
    adapter.write_output(Path("data/output/reanimator/result.csv"), results)

    # 4. 注入到用例
    from memosyne.reanimator.application import ProcessTermsUseCase

    # CSV Adapter 主要在 CLI 层使用（读写文件）
    # Use Case 不直接依赖它，由 CLI 负责调用
    """)
