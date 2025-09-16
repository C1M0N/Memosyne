import re
from typing import Dict

RE_TWO_CN = re.compile(r"^[\u4E00-\u9FFF]{2}$")
RE_HAS_SPACE = re.compile(r"\s")

ALLOWED_POS = {"n.","vt.","vi.","adj.","adv.","P.","O.","abbr."}

def norm_ppfix(s: str) -> str:
  t = (s or "").lower()
  t = re.sub(r"[-_/]+", " ", t)
  t = re.sub(r"[^a-z\s]+", " ", t)
  t = re.sub(r"\s+", " ", t).strip()
  return t

def align_pp(ppfix_raw: str, means_raw: str) -> tuple[str, str]:
  """PPmeans：ASCII，token 间空格；token 内词组用下划线；并与 PPfix 对齐。"""
  fix_tokens = [t for t in norm_ppfix(ppfix_raw).split(" ") if t]
  raw = (means_raw or "").lower()
  raw = re.sub(r"[^\x20-\x7E]+", " ", raw)   # ASCII
  raw = re.sub(r"[-/]+", "_", raw)
  raw = re.sub(r"\s*_\s*", "_", raw)
  raw = re.sub(r"\s+", " ", raw).strip()

  parts = []
  for sep in [";", ",", "|"]:
    tmp = [x.strip() for x in raw.split(sep) if x.strip()]
    if len(tmp) == len(fix_tokens) and len(tmp) > 0:
      parts = tmp
      break
  if not parts:
    parts = [x for x in raw.split(" ") if x]

  if len(parts) > len(fix_tokens) and fix_tokens:
    # 多出的并到最后一个 token
    merged = parts[:len(fix_tokens)-1] + ["_".join(parts[len(fix_tokens)-1:])]
    parts = merged
  while len(parts) < len(fix_tokens):
    parts.append("")

  parts = [re.sub(r"\s+", "_", t) for t in parts]
  return " ".join(fix_tokens), " ".join(parts)

def postprocess_record(
    raw_llm: Dict,
    word: str,
    zh: str,
    catalog: Dict,
    enforce_phrase_pos: bool = True
) -> Dict:
  cnTags = catalog.get("cnTags", [])
  en2cn = catalog.get("en2cn", {})

  ipa = (raw_llm.get("IPA") or "").strip()
  pos = (raw_llm.get("POS") or "").strip()
  tag_raw = (raw_llm.get("Tag") or "").strip()
  rarity = (raw_llm.get("Rarity") or "").strip()
  endef = (raw_llm.get("EnDef") or "").strip()
  ppfix = (raw_llm.get("PPfix") or "").strip()
  ppmeans = (raw_llm.get("PPmeans") or "").strip()

  # Tag：白名单或英文映射，其他清空
  tag = ""
  if tag_raw in cnTags:
    tag = tag_raw
  else:
    mapped = en2cn.get(tag_raw.lower())
    if mapped in cnTags:
      tag = mapped
  if not RE_TWO_CN.match(tag or ""):
    tag = ""

  # POS：含空格则强制 P.（不覆盖 abbr.，因为由 agent 决定）
  if enforce_phrase_pos and RE_HAS_SPACE.search(word):
    pos = "P."
  if pos not in ALLOWED_POS:
    pos = "P." if RE_HAS_SPACE.search(word) else "O."

  # Rarity：合法化
  rarity = "RARE" if rarity == "RARE" else ""

  # IPA：除 abbr. 外必须有（若空，留空给人工检查；你也可选择抛错或二次重试）
  if pos != "abbr." and not ipa:
    ipa = ipa  # 保留为空（提示已在 System 里硬性要求）

  # 形态：对齐与下划线规则
  ppfix_norm, ppmeans_norm = align_pp(ppfix, ppmeans)

  return {
    "Word": word,
    "ZhDef": zh,
    "IPA": ipa,
    "POS": pos,
    "Tag": tag,
    "Rarity": rarity,
    "EnDef": endef,
    "PPfix": ppfix_norm,
    "PPmeans": ppmeans_norm
  }