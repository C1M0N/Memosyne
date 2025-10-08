"""
Term List Repository - 术语表仓储

基于原 src/mms_pipeline/term_data.py 中的 TermList 类
改进：类型提示、更好的错误处理
"""
import csv
from pathlib import Path


class TermListRepo:
    """术语表仓储（英文 -> 两字中文）"""

    def __init__(self):
        self.mapping: dict[str, str] = {}

    def load(self, path: Path | str) -> None:
        """
        从 CSV 加载术语表

        Args:
            path: 术语表 CSV 路径（两列：英文, 两字中文）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"术语表文件不存在：{path}")

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            # 分隔符嗅探
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.reader(f, dialect=dialect)
            next(reader, None)  # 跳过表头

            for row in reader:
                if len(row) < 2:
                    continue

                en = (row[0] or "").strip().lower()
                cn = (row[1] or "").strip()

                # 只保留两字中文
                if en and len(cn) == 2:
                    self.mapping[en] = cn

    def get_chinese_tag(self, english_tag: str) -> str:
        """
        获取中文标签（精确匹配或宽松包含匹配）

        Args:
            english_tag: 英文标签

        Returns:
            两字中文标签（找不到返回空字符串）

        Example:
            >>> repo = TermListRepo()
            >>> repo.mapping = {"psychology": "心理", "biology": "生物"}
            >>> repo.get_chinese_tag("psychology")
            '心理'
            >>> repo.get_chinese_tag("neurobiology")  # 宽松匹配
            '生物'
            >>> repo.get_chinese_tag("unknown")
            ''
        """
        tag = english_tag.strip().lower()

        if not tag:
            return ""

        # 1. 精确匹配
        if tag in self.mapping:
            return self.mapping[tag]

        # 2. 宽松包含匹配（如 "neurobiology" 匹配 "biology"）
        for en_key, cn_value in self.mapping.items():
            if en_key and en_key in tag:
                return cn_value

        return ""

    def __len__(self) -> int:
        """返回术语表条目数"""
        return len(self.mapping)

    def __contains__(self, key: str) -> bool:
        """检查英文标签是否存在"""
        return key.lower() in self.mapping
