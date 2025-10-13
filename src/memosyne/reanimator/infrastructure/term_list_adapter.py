"""
Reanimator Infrastructure - TermList Adapter

术语表适配器：实现 Application 层的 TermListPort 接口

职责：
- 加载术语表（英文 -> 中文）
- 提供标签映射查询
- 委托给现有的 TermListRepo
"""
from pathlib import Path

from ...shared.infrastructure.storage.term_list_repository import TermListRepo


class TermListAdapter:
    """
    术语表适配器（实现 TermListPort）

    封装 TermListRepo，提供符合端口接口的方法。
    """

    def __init__(self, term_list_path: Path):
        """
        Args:
            term_list_path: 术语表文件路径
        """
        self._repo = TermListRepo()
        self._repo.load(term_list_path)

    @property
    def mapping(self) -> dict[str, str]:
        """
        获取术语表映射（实现 TermListPort.mapping）

        Returns:
            映射字典（英文 -> 两字中文）
        """
        return self._repo.mapping

    @classmethod
    def from_path(cls, term_list_path: Path) -> "TermListAdapter":
        """
        工厂方法：从路径创建适配器

        Args:
            term_list_path: 术语表文件路径

        Returns:
            TermListAdapter 实例

        Raises:
            FileNotFoundError: 术语表文件不存在
        """
        return cls(term_list_path=term_list_path)

    @classmethod
    def from_settings(cls, settings) -> "TermListAdapter":
        """
        工厂方法：从 Settings 创建适配器

        Args:
            settings: Settings 对象

        Returns:
            TermListAdapter 实例
        """
        return cls(term_list_path=settings.term_list_path)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    print("""
    TermListAdapter 使用示例：

    # 1. 从路径创建
    from pathlib import Path
    adapter = TermListAdapter.from_path(Path("db/term_list_v1.csv"))
    print(f"加载了 {len(adapter.mapping)} 个术语映射")

    # 2. 查询映射
    tag_cn = adapter.mapping.get("psychology", "")
    print(f"psychology -> {tag_cn}")

    # 3. 从 Settings 创建
    from memosyne.config import get_settings
    settings = get_settings()
    adapter2 = TermListAdapter.from_settings(settings)

    # 4. 注入到用例
    from memosyne.reanimator.application import ProcessTermsUseCase

    use_case = ProcessTermsUseCase(
        llm=llm_adapter,
        term_list=adapter,  # 实现了 TermListPort
        start_memo_index=2700,
        batch_id="251007A015"
    )
    """)
