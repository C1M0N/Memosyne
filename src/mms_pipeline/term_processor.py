# term_processor.py
from typing import List
from term_data import InRow, TermList
from openai_helper import OpenAIHelper
from time import perf_counter
from tqdm import tqdm  # 项目要求：必须使用 tqdm


def _iter_with_progress(rows, desc: str = "LLM"):
  """只用 tqdm 显示进度条。"""
  total = len(rows)
  bar_fmt = "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
  it = enumerate(
    tqdm(rows, desc=desc, total=total, ncols=80, ascii=True, bar_format=bar_fmt, leave=True),
    start=0
  )
  for i, row in it:
    yield i, row


class TermProcessor:
  def __init__(self, openai_helper: OpenAIHelper, term_list: TermList,
      start_memo_index: int, batch_id: str, batch_note: str):
    self.llm = openai_helper
    self.terms = term_list
    self.start = start_memo_index
    self.batch_id = batch_id
    self.batch_note = f"「{(batch_note or '').strip()}」" if batch_note else ""

  def _memo_id(self, i: int) -> str:
    # start=2700, i 从 0 计，首条返回 M002701
    return f"M{(self.start + i + 1):06d}"

  def _wmpair(self, word: str, zh: str) -> str:
    return f"{word.strip()} - {zh.strip()}"

  def _post_fixups(self, word: str, info: dict) -> dict:
    """
    仅保留与 schema 无重叠的业务兜底：
    1) 词组（含空格）→ 强制 POS='P.'（但 abbr. 例外）
    2) POS='abbr.' → IPA 必须为空
    3) PPfix/PPmeans 轻度正规化（小写、空白折叠）
    """
    pos = (info.get("POS") or "").strip()
    if " " in word and pos != "abbr.":
      info["POS"] = "P."

    if info.get("POS") == "abbr." and (info.get("IPA") or "").strip():
      info["IPA"] = ""  # 与业务规则一致：缩写不标 IPA

    info["PPfix"] = " ".join((info.get("PPfix") or "").lower().split())
    info["PPmeans"] = " ".join((info.get("PPmeans") or "").lower().split())
    return info

  def process(self, rows: List[InRow], model_name: str) -> List[dict]:
    out: List[dict] = []
    for i, row in _iter_with_progress(rows, desc="LLM"):
      # LLM 严格按 schema 返回
      info = self.llm.fetch_term_info(row.Word, row.ZhDef)

      # 仅做业务兜底与映射
      info = self._post_fixups(row.Word, info)
      tag_cn = self.terms.to_cn(info.get("TagEN") or "")

      out.append({
        "WMpair": self._wmpair(row.Word, row.ZhDef),
        "MemoID": self._memo_id(i),
        "Word": row.Word,
        "ZhDef": row.ZhDef,
        "IPA": info.get("IPA", ""),
        "POS": info.get("POS", ""),
        "Tag": tag_cn,
        "Rarity": info.get("Rarity", ""),
        "EnDef": info.get("EnDef", ""),
        "PPfix": info.get("PPfix", ""),
        "PPmeans": info.get("PPmeans", ""),
        "BatchID": self.batch_id,
        "BatchNote": self.batch_note,
      })
    return out