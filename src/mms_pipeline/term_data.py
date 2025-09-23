# term_data.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import csv

@dataclass
class InRow:
  Word: str
  ZhDef: str
  IPA: str = ""
  EnDef: str = ""
  Example: str = ""

class TermList:
  """术语表：英文域名 -> 两字中文。CSV 至少有 en / cn 两列（不区分大小写）。"""
  def __init__(self):
    self.en2cn: dict[str, str] = {}

  def load_from_csv(self, file_path: str) -> None:
    encs: Tuple[str,...] = ("utf-8-sig","utf-8","gb18030","gbk","big5","cp950","latin-1")
    last: Exception | None = None
    for enc in encs:
      try:
        with open(file_path, "r", encoding=enc, newline="") as f:
          sample = f.read(4096); f.seek(0)
          try:
            dialect = csv.Sniffer().sniff(sample)
          except Exception:
            dialect = csv.excel
          reader = csv.DictReader(f, dialect=dialect)
          self.en2cn.clear()
          for r in reader:
            en = (r.get("en") or r.get("EN") or r.get("domain") or r.get("Domain") or "").strip()
            cn = (r.get("cn") or r.get("CN") or r.get("tag") or r.get("Tag") or "").strip()
            if en:
              self.en2cn[en.lower()] = cn
        print(f"[TermList] loaded {len(self.en2cn)} domains.")
        if not self.en2cn:
          raise ValueError("术语表为空或表头不匹配（需要 en/cn）")
        return
      except Exception as e:
        last = e
        continue
    raise last or RuntimeError("术语表读取失败")

  def to_cn(self, tag_en: str) -> str:
    if not tag_en:
      return ""
    return self.en2cn.get(tag_en.lower().strip(), "")

  def en_vocab(self) -> List[str]:
    return sorted(self.en2cn.keys())

# —— 输入 CSV（健壮编码）——
_CANDS: Tuple[str,...] = ("utf-8-sig","utf-8","gb18030","gbk","big5","cp950","shift_jis","latin-1")

def _try_read(path: str, enc: str) -> List[InRow]:
  rows: List[InRow] = []
  with open(path, "r", encoding=enc, newline="") as f:
    sample = f.read(4096); f.seek(0)
    try:
      dialect = csv.Sniffer().sniff(sample)
    except Exception:
      dialect = csv.excel
    reader = csv.DictReader(f, dialect=dialect)
    for r in reader:
      word = (r.get("Word") or r.get("word") or r.get("\ufeffWord") or "").strip()
      zh = (r.get("ZhDef") or r.get("zh") or "").strip()
      if not word:
        continue
      ipa = (r.get("IPA") or "").strip()
      endef = (r.get("EnDef") or "").strip()
      ex = (r.get("Example") or "").strip()
      rows.append(InRow(Word=word, ZhDef=zh, IPA=ipa, EnDef=endef, Example=ex))
  return rows

def read_input_csv(path: str) -> List[InRow]:
  last: Exception | None = None
  for enc in _CANDS:
    try:
      rows = _try_read(path, enc)
      print(f"[CSV] detected encoding: {enc}")
      return rows
    except Exception as e:
      last = e
      continue
  raise last or RuntimeError("输入 CSV 读取失败")

def write_output_csv(file_path: str, entries: List[dict]) -> None:
  """输出列顺序：WMpair MemoID Word ZhDef IPA POS Tag Rarity EnDef Example PPfix PPmeans BatchID BatchNote"""
  Path(file_path).parent.mkdir(parents=True, exist_ok=True)
  fields = [
    "WMpair","MemoID","Word","ZhDef","IPA","POS","Tag","Rarity",
    "EnDef","Example","PPfix","PPmeans","BatchID","BatchNote"
  ]
  with open(file_path, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for e in entries:
      w.writerow({k: e.get(k, "") for k in fields})