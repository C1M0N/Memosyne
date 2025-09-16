# term_processor.py
from typing import List
from term_data import InRow, TermList
from openai_helper import OpenAIHelper

ALLOWED_POS = {"n.","vt.","vi.","adj.","adv.","P.","O.","abbr."}

def _memo_id(start: int, i: int) -> str:
  # start=2700, i从0计，首条返回 M002701
  return f"M{(start + i + 1):06d}"

def _wmpair(word: str, zh: str) -> str:
  return f"{word.strip()} - {zh.strip()}"

def _force_pos_for_phrase(word: str, pos: str) -> str:
  if " " in word and pos != "abbr.":
    return "P."
  return pos if pos in ALLOWED_POS else ("P." if " " in word else "O.")

def _clean_rarity(val: str) -> str:
  return "RARE" if (val or "").strip().upper() == "RARE" else ""

def _align_pp(ppfix: str, ppmeans: str) -> tuple[str, str]:
  fx = " ".join((ppfix or "").replace("-", " ").split()).lower()
  # token 内多词用下划线；token 间用空格
  mm = " ".join((ppmeans or "").replace("-", "_").split()).lower()
  return fx, mm

class TermProcessor:
  def __init__(self, openai_helper: OpenAIHelper, term_list: TermList,
      start_memo_index: int, batch_id: str, batch_note: str):
    self.llm = openai_helper
    self.terms = term_list
    self.start = start_memo_index
    self.batch_id = batch_id
    self.batch_note = f"「{(batch_note or '').strip()}」" if batch_note else ""

  def process(self, rows: List[InRow], model_name: str) -> List[dict]:
    out: List[dict] = []
    for i, row in enumerate(rows):
      info = self.llm.fetch_term_info(row.Word, row.ZhDef)

      ipa = (info.get("IPA") or "").strip()
      pos = (info.get("POS") or "").strip()
      pos = _force_pos_for_phrase(row.Word, pos)
      if pos != "abbr." and not ipa:
        # 严格要求 IPA（除 abbr. 外），这里不强行造，留空让你一眼可见
        pass

      rarity = _clean_rarity(info.get("Rarity") or "")
      endef = (info.get("EnDef") or "").strip()

      ppfix, ppmeans = _align_pp(info.get("PPfix") or "", info.get("PPmeans") or "")

      tag_en = (info.get("TagEN") or "").strip()
      tag_cn = self.terms.to_cn(tag_en)  # 不在清单内→空

      out.append({
        "WMpair": _wmpair(row.Word, row.ZhDef),
        "MemoID": _memo_id(self.start, i),
        "Word": row.Word,
        "ZhDef": row.ZhDef,
        "IPA": ipa,
        "POS": pos,
        "Tag": tag_cn,
        "Rarity": rarity,
        "EnDef": endef,
        "PPfix": ppfix,
        "PPmeans": ppmeans,
        "BatchID": self.batch_id,
        "BatchNote": self.batch_note,
      })
    return out