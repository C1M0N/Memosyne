"""
CSV Repository - CSV 数据读写

基于原 src/mms_pipeline/term_data.py
改进：使用 Pydantic 模型、更好的错误处理
"""
import csv
from pathlib import Path
from typing import Iterable

from ....reanimator.domain.models import TermInput, TermOutput


# 列名同义词映射
_WORD_KEYS = {
    "word", "headword", "term", "english", "en",
    "词", "词条", "单词", "英文", "英语"
}
_ZH_KEYS = {
    "zhdef", "zh", "cn",
    "中文", "释义", "中文释义", "定义", "义项", "解释"
}


def _norm_key(s: str) -> str:
    """规范化列名"""
    if s is None:
        return ""
    s = s.replace("\ufeff", "").strip().lower()
    s = s.replace("\u3000", " ")  # 全角空格
    return s


def _pick_first(d: dict[str, str], candidates: Iterable[str]) -> str:
    """从字典中选择第一个存在的键"""
    for k in candidates:
        if k in d and d[k]:
            return d[k]
    return ""


class CSVTermRepository:
    """CSV 术语仓储"""

    @staticmethod
    def read_input(path: Path | str) -> list[TermInput]:
        """
        读取输入 CSV

        Args:
            path: CSV 文件路径

        Returns:
            TermInput 列表

        Raises:
            ValueError: 文件格式错误或缺少必需列
        """
        path = Path(path)
        terms: list[TermInput] = []

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            # 分隔符嗅探
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)
            raw_fieldnames = reader.fieldnames or []

            # 规范化表头
            norm_field_map = {fn: _norm_key(fn) for fn in raw_fieldnames}

            for row in reader:
                # 构造规范化字典
                clean = {}
                for orig_key, val in row.items():
                    nk = norm_field_map.get(orig_key, _norm_key(orig_key))
                    clean[nk] = (val or "").strip()

                # 提取 Word / ZhDef
                word = _pick_first(clean, ["word"] + list(_WORD_KEYS))
                zh = _pick_first(clean, ["zhdef"] + list(_ZH_KEYS))

                if word and zh:
                    # 使用 Pydantic 验证（会自动去空白、检查有效性）
                    terms.append(TermInput(word=word, zh_def=zh))

        if not terms:
            raise ValueError(
                f"输入CSV没有有效的 Word/ZhDef 行。\n"
                f"检测到的表头：{raw_fieldnames}\n"
                f"支持的列名：word/term/headword（英文）或 中文/释义（中文）"
            )

        return terms

    @staticmethod
    def write_output(path: Path | str, terms: Iterable[TermOutput]) -> None:
        """
        写出术语 CSV（无表头，按固定顺序）

        Args:
            path: 输出文件路径
            terms: TermOutput 列表
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for term in terms:
                writer.writerow(term.to_csv_row())
