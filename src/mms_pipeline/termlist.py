import pandas as pd
from typing import List, Dict

def load_termlist(path: str) -> dict:
  df = pd.read_csv(path, encoding="utf-8")
  cols = [c.strip().replace("\ufeff", "") for c in df.columns]
  df.columns = cols

  # 尝试常见列名：中文两字（Tag/CN/中文…）与英文（Term/English…）
  cn_candidates = [c for c in cols if c.lower() in ["tag","cn","中文","标签","tagcn","tag_cn"]]
  en_candidates = [c for c in cols if c.lower() in ["term","english","en","英文","tagen","tag_en"]]
  cn_key = cn_candidates[0] if cn_candidates else None
  en_key = en_candidates[0] if en_candidates else None
  if not cn_key:
    raise ValueError("term_list_v1.csv must contain a Chinese two-char column like Tag/CN/中文.")

  cnTags: List[str] = []
  en2cn: Dict[str, str] = {}
  for _, row in df.iterrows():
    cn = str(row.get(cn_key, "")).strip()
    if len(cn) == 2:  # 两字中文
      if cn not in cnTags:
        cnTags.append(cn)
      if en_key:
        en_raw = str(row.get(en_key, "")).strip()
        if en_raw:
          for seg in [s.strip() for s in str(en_raw).replace("/", ";").replace(",", ";").split(";")]:
            if seg:
              en2cn[seg.lower()] = cn
  # 生成 gloss（供提示“理解”，不输出）
  prettyGloss = "; ".join([f"{cn}={en}" for en, cn in list(en2cn.items())[:200]])
  return {"cnTags": cnTags, "en2cn": en2cn, "prettyGloss": prettyGloss}