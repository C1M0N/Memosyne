# term_processor.py
from typing import List
from term_data import InRow, TermList
from openai_helper import OpenAIHelper
import sys
from time import perf_counter
try:
  from tqdm import tqdm  # optional; if missing we fallback to a simple progress bar
except Exception:  # ImportError or any env issue
  tqdm = None

ALLOWED_POS = {"n.","vt.","vi.","adj.","adv.","P.","O.","abbr."}

def _render_progress(i: int, total: int, start_ts: float, bar_len: int = 30):
  if total <= 0:
    return
  # clamp
  i = max(0, min(i, total))
  ratio = i / total
  filled = int(bar_len * ratio)
  left = bar_len - filled
  elapsed = perf_counter() - start_ts
  eta = (elapsed / i * (total - i)) if i else 0.0
  sys.stdout.write(
    "\r[{done}{todo}] {cur}/{tot}  {pct:>5.1f}%  ETA {eta:.1f}s".format(
      done="=" * filled,
      todo="." * left,
      cur=i,
      tot=total,
      pct=ratio * 100,
      eta=eta,
    )
  )
  sys.stdout.flush()

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

    if tqdm is not None:
      bar_fmt = "{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
      iterator = enumerate(tqdm(rows, desc="LLM", total=len(rows), ncols=80, ascii=True, bar_format=bar_fmt, leave=True), start=0)
      for i, row in iterator:
        info = self.llm.fetch_term_info(row.Word, row.ZhDef)

        ipa = (info.get("IPA") or "").strip()
        pos = (info.get("POS") or "").strip()
        pos = _force_pos_for_phrase(row.Word, pos)
        if pos != "abbr." and not ipa:
          pass  # keep empty to surface issues

        rarity = _clean_rarity(info.get("Rarity") or "")
        endef = (info.get("EnDef") or "").strip()

        ppfix, ppmeans = _align_pp(info.get("PPfix") or "", info.get("PPmeans") or "")

        tag_en = (info.get("TagEN") or "").strip()
        tag_cn = self.terms.to_cn(tag_en)

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
    else:
      total = len(rows)
      start_ts = perf_counter()
      _render_progress(0, total, start_ts)

      for i, row in enumerate(rows, start=0):
        info = self.llm.fetch_term_info(row.Word, row.ZhDef)

        ipa = (info.get("IPA") or "").strip()
        pos = (info.get("POS") or "").strip()
        pos = _force_pos_for_phrase(row.Word, pos)
        if pos != "abbr." and not ipa:
          pass

        rarity = _clean_rarity(info.get("Rarity") or "")
        endef = (info.get("EnDef") or "").strip()

        ppfix, ppmeans = _align_pp(info.get("PPfix") or "", info.get("PPmeans") or "")

        tag_en = (info.get("TagEN") or "").strip()
        tag_cn = self.terms.to_cn(tag_en)

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

        _render_progress(i + 1, total, start_ts)

      sys.stdout.write("\n")
      sys.stdout.flush()

    return out