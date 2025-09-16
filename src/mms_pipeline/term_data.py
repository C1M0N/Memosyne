# term_data.py
import csv
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class InRow:
  Word: str
  ZhDef: str

def read_input_csv(path: str) -> List[InRow]:
  rows: List[InRow] = []
  with open(path, "r", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
      w = (row.get("Word") or "").strip()
      z = (row.get("ZhDef") or "").strip()
      if w and z:
        rows.append(InRow(w, z))
  if not rows:
    raise ValueError("输入CSV没有有效的 Word/ZhDef 行。")
  return rows

class TermList:
  """一次性加载术语表（英文→两字中文）。不在每次请求传入大列表。"""
  def __init__(self):
    self.map: Dict[str, str] = {}  # en -> 两字中文

  def load_from_csv(self, path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
      r = csv.reader(f)
      header = next(r, None)
      for row in r:
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
      if en in t:
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