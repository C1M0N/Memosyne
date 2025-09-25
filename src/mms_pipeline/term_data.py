# term_data.py
import csv
from dataclasses import dataclass
from typing import List, Dict, Iterable

@dataclass
class InRow:
  Word: str
  ZhDef: str


# --- 关键：对列名做宽松规范化与同义词映射 ---
def _norm_key(s: str) -> str:
  """去除BOM/前后空白，转小写，去掉全角空格。"""
  if s is None:
    return ""
  s = s.replace("\ufeff", "").strip().lower()
  s = s.replace("\u3000", " ")  # 全角空格
  return s

# 可能的同义列名（全部转成小写后比较）
_WORD_KEYS = {
  "word", "headword", "term", "english", "en",
  "词", "词条", "单词", "英文", "英语"
}
_ZH_KEYS = {
  "zhdef", "zh", "cn",
  "中文", "释义", "中文释义", "定义", "义项", "解释"
}

def _pick_first(d: Dict[str, str], candidates: Iterable[str]) -> str:
  for k in candidates:
    if k in d and d[k]:
      return d[k]
  return ""

def read_input_csv(path: str) -> List[InRow]:
  """
  更稳健的 CSV 读取：
  - 自动识别分隔符（, ; \t）
  - 使用 utf-8-sig 删除BOM
  - 宽松匹配表头：大小写不敏感，去空格，支持多语言同义列名
  """
  rows: List[InRow] = []

  # 先读一小段做分隔符嗅探
  with open(path, "r", encoding="utf-8-sig", newline="") as f:
    sample = f.read(4096)
    f.seek(0)
    try:
      dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
      dialect = csv.excel  # 默认逗号

    reader = csv.DictReader(f, dialect=dialect)
    raw_fieldnames = reader.fieldnames or []

    # 规范化表头 -> 用于行数据key映射
    norm_field_map = {fn: _norm_key(fn) for fn in raw_fieldnames}
    # 反查：规范名 -> 原始名列表（很少用，但保留以便必要时调试）
    # rev = {}
    # for orig, norm in norm_field_map.items():
    #     rev.setdefault(norm, []).append(orig)

    for row in reader:
      # 按规范名构造一份 clean dict
      clean = {}
      for orig_key, val in row.items():
        nk = norm_field_map.get(orig_key, _norm_key(orig_key))
        clean[nk] = (val or "").strip()

      # 取 Word / ZhDef
      word = _pick_first(clean, ["word"] + list(_WORD_KEYS))
      zh   = _pick_first(clean, ["zhdef"] + list(_ZH_KEYS))

      if word and zh:
        rows.append(InRow(word, zh))

  if not rows:
    # 更友好的错误：打印检测到的表头，协助定位
    raise ValueError(
      "输入CSV没有有效的 Word/ZhDef 行。\n"
      "提示：请检查以下事项：\n"
      "  1) 表头是否存在（例：Word, ZhDef），支持同义：word/term/headword、中文/释义等；\n"
      "  2) 分隔符是否为逗号/分号/制表符（已自动嗅探，但如有不规则，请另存为标准CSV）；\n"
      "  3) 是否存在空格/BOM（已自动剥离）；\n"
      f"  4) 本文件检测到的原始表头：{raw_fieldnames}"
    )
  return rows


class TermList:
  """一次性加载术语表（英文→两字中文）。不在每次请求传入大列表。"""
  def __init__(self):
    self.map: Dict[str, str] = {}  # en -> 两字中文

  def load_from_csv(self, path: str) -> None:
    # 术语表通常两列：英文, 两字中文；这里也宽松一些
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
      sample = f.read(4096)
      f.seek(0)
      try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
      except csv.Error:
        dialect = csv.excel
      reader = csv.reader(f, dialect=dialect)
      header = next(reader, None)
      for row in reader:
        if len(row) < 2:
          continue
        en = (row[0] or "").strip().lower()
        cn = (row[1] or "").strip()
        if en and len(cn) == 2:
          self.map[en] = cn

  def to_cn(self, tag_en: str) -> str:
    t = (tag_en or "").strip().lower()
    if not t:
      return ""
    if t in self.map:
      return self.map[t]
    # 宽松包含匹配（neurobiology -> biology）
    for en, cn in self.map.items():
      if en and en in t:
        return cn
    return ""


def write_output_csv(path: str, rows: List[dict]) -> None:
  # 不写表头，直接行输出（按指定列顺序）
  with open(path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    for r in rows:
      w.writerow([
        r["WMpair"],
        r["MemoID"],
        r["Word"],
        r["ZhDef"],
        r["IPA"],
        r["POS"],
        r["Tag"],
        r["Rarity"],
        r["EnDef"],
        r["PPfix"],
        r["PPmeans"],
        r["BatchID"],
        r["BatchNote"],
      ])