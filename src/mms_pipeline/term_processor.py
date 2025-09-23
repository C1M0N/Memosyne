# term_processor.py
import re
from typing import List
from tqdm import tqdm

from term_data import InRow, TermList
from openai_helper import OpenAIHelper, SKIP

ALLOWED_POS = {"n.","vt.","vi.","adj.","adv.","P.","O.","abbr."}
_IPA_HINT = re.compile(r"[\u0250-\u02AFˈˌːɚɝɾ]")  # IPA 常见符号

def _normalize_ipa(s: str) -> str:
  s = (s or "").strip()
  if not s:
    return s
  if s.startswith("[") and s.endswith("]"):
    inner = " ".join(s[1:-1].split())
    return f"/{inner}/" if inner else ""
  if s.startswith("/") and s.endswith("/"):
    inner = " ".join(s[1:-1].split())
    return f"/{inner}/" if inner else ""
  if _IPA_HINT.search(s):
    inner = " ".join(s.split())
    return f"/{inner}/" if inner else ""
  return s

def _invalid_ipa(s: str) -> bool:
  s = (s or "").strip()
  return (not s) or (not (s.startswith("/") and s.endswith("/"))) or len(s) < 3

def _memo_id(start: int, i: int) -> str:
  return f"M{(start + i + 1):06d}"

def _wmpair(word: str, zh: str) -> str:
  return f"{word.strip()} - {zh.strip()}"

_ABBR_TOKEN = re.compile(r"""(?ix)
  ^(
     (?:[A-Z]\.){2,}[A-Z]?        # A.V. / A.V.N.
    |[A-Z](?:-[A-Z])+             # S-P / G-A-B-A
    |[A-Z0-9]{2,}(?:[-/][A-Z0-9]{1,})+  # Na+/K+ / 5-HT / GABA-A
    |[A-Z]{2,}[0-9]*              # ATP / MRI / EEG
  )$
""")

def _looks_abbr(word: str, ipa_input: str) -> bool:
  w = (word or "").strip()
  if not w:
    return False
  first = w.split()[0].strip("()[]{}:;,.!")
  if _ABBR_TOKEN.match(first):
    return True
  # “给了全称就判 abbr.”：如果输入 IPA 看起来像英文短语（不是 /.../ 且不含 IPA 符号）
  if ipa_input:
    txt = ipa_input.strip()
    if not (txt.startswith("/") and txt.endswith("/")) and not _IPA_HINT.search(txt) and re.search(r"[A-Za-z]", txt):
      return True
  return False

def _force_pos(word: str, pos: str, is_abbr: bool) -> str:
  if is_abbr:
    return "abbr."
  if " " in (word or ""):
    return "P."
  return pos if pos in ALLOWED_POS else "O."

def _is_skip_or_empty(v: str | None) -> bool:
  return (not v) or (v.strip() == "") or (v.strip() == SKIP)

def _looks_like_definition(s: str) -> bool:
  if not s:
    return True
  t = s.strip().lower()
  return bool(re.search(r"\b(is|are|means?|refers? to|defined as)\b", t)) and len(t.split()) <= 16

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
    allowed = self.terms.en_vocab()

    bar = tqdm(rows, desc="LLM", total=len(rows), ncols=80, ascii=True)
    for i, row in enumerate(bar):
      # A) 缩写判定
      is_abbr = _looks_abbr(row.Word, row.IPA)

      # B) 跳过计划（仅三字段可跳）
      need_ipa = (not row.IPA) and (not is_abbr)
      need_endef = not bool(row.EnDef)
      need_example = not bool(row.Example)

      data = self.llm.fetch_main(
        word=row.Word, zh=row.ZhDef, allowed_tag_en=allowed,
        skip_ipa=(not need_ipa),
        skip_endef=(not need_endef),
        skip_example=(not need_example),
      )

      # 用输入覆盖被跳过的字段
      if not need_ipa:     data["IPA"] = row.IPA
      if not need_endef:   data["EnDef"] = row.EnDef
      if not need_example: data["Example"] = row.Example

      # C) POS 归一
      pos = _force_pos(row.Word, (data.get("POS") or "").strip(), is_abbr)
      data["POS"] = pos

      # D) 清理 skip 标记
      for k in ("IPA","EnDef","Example","PPfix","PPmeans","TagEN"):
        v = (data.get(k) or "").strip()
        data[k] = "" if v == SKIP else v

      # E) IPA 规则
      if pos == "abbr.":
        # abbr.：按你的要求，IPA 允许空（不强求模型给全称）
        data["IPA"] = row.IPA or ""  # 若你输入给了“全称文本”，也不当作 IPA 使用
      else:
        data["IPA"] = _normalize_ipa(data.get("IPA",""))

      # F) 例句不要像定义体；缺失兜底
      miss_ipa = (pos != "abbr.") and _invalid_ipa(data.get("IPA"))
      miss_endef = _is_skip_or_empty(data.get("EnDef"))
      miss_example = _is_skip_or_empty(data.get("Example")) or _looks_like_definition(data.get("Example",""))

      if miss_ipa or miss_endef or miss_example:
        data2 = self.llm.fetch_main(
          word=row.Word, zh=row.ZhDef, allowed_tag_en=allowed,
          skip_ipa=(not miss_ipa),
          skip_endef=(not miss_endef),
          skip_example=(not miss_example),
        )
        if miss_ipa:
          data["IPA"] = _normalize_ipa((data2.get("IPA") or "").strip())
        if miss_endef:
          data["EnDef"] = (data2.get("EnDef") or "").strip()
        if miss_example:
          data["Example"] = (data2.get("Example") or "").strip()

      # G) 单字段兜底
      if pos != "abbr." and _invalid_ipa(data.get("IPA")):
        data["IPA"] = _normalize_ipa(self.llm.fetch_single("IPA", row.Word, row.ZhDef))
      if _is_skip_or_empty(data.get("EnDef")):
        data["EnDef"] = self.llm.fetch_single("EnDef", row.Word, row.ZhDef)
      if _is_skip_or_empty(data.get("Example")) or _looks_like_definition(data.get("Example","")):
        data["Example"] = self.llm.fetch_single("Example", row.Word, row.ZhDef)

      # H) 最终校验
      if pos != "abbr.":
        if _invalid_ipa(data.get("IPA")):
          raise ValueError(f"[IPA不规范] Word='{row.Word}' 期望 /.../，实际='{data.get('IPA')}'")
      if _is_skip_or_empty(data.get("EnDef")):
        raise ValueError(f"[缺失不可接受] Word='{row.Word}' 的 EnDef 仍为空")
      if _is_skip_or_empty(data.get("Example")):
        raise ValueError(f"[缺失不可接受] Word='{row.Word}' 的 Example 仍为空")

      # I) Tag 映射为两字中文
      tag_cn = self.terms.to_cn((data.get("TagEN") or "").strip())
      # PP 规整
      ppfix = " ".join((data.get("PPfix") or "").lower().replace("-", " ").split())
      ppmeans = " ".join((data.get("PPmeans") or "").lower().split())

      out.append({
        "WMpair": _wmpair(row.Word, row.ZhDef),
        "MemoID": _memo_id(self.start, i),
        "Word": row.Word,
        "ZhDef": row.ZhDef,
        "IPA": (data.get("IPA","") if pos != "abbr." else ""),
        "POS": pos,
        "Tag": tag_cn,  # 两字中文；映射不到为空
        "Rarity": (data.get("Rarity") or "").strip(),
        "EnDef": data.get("EnDef",""),
        "Example": data.get("Example",""),
        "PPfix": ppfix,
        "PPmeans": ppmeans,
        "BatchID": self.batch_id,
        "BatchNote": self.batch_note,
      })

      used = self.llm.usage_summary()
      bar.set_postfix_str(f"tok={used['total']} (p{used['prompt']}/c{used['completion']})")

    return out