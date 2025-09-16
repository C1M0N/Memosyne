import os
import csv
import pandas as pd
from typing import List, Dict

def read_input_csv(path: str) -> List[Dict]:
  df = pd.read_csv(path, encoding="utf-8")
  # 兼容 BOM 或变体列名
  cols = {c.strip().replace("\ufeff", ""): c for c in df.columns}
  word_col = next((k for k in cols if k.lower() in ["word", " word", "word "]), None)
  zh_col   = next((k for k in cols if k.lower() in ["zhdef", "zh", "zh_def"]), None)
  if not word_col or not zh_col:
    raise ValueError("Input CSV must include 'Word' and 'ZhDef' columns.")
  df = df.rename(columns={cols[word_col]: "Word", cols[zh_col]: "ZhDef"})
  # 标准化空白
  df["Word"] = df["Word"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
  df["ZhDef"] = df["ZhDef"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
  return df.to_dict(orient="records")

def ensure_dir(path: str) -> None:
  os.makedirs(path, exist_ok=True)

def unique_path(dirpath: str, filename: str) -> str:
  """防重名：如存在则 _2/_3 递增"""
  ensure_dir(dirpath)
  stem, ext = os.path.splitext(filename)
  candidate = os.path.join(dirpath, filename)
  k = 2
  while os.path.exists(candidate):
    candidate = os.path.join(dirpath, f"{stem}_{k}{ext}")
    k += 1
  return candidate

COLUMNS = [
  "WMpair","MemoID","Word","ZhDef","IPA","POS","Tag","Rarity",
  "EnDef","PPfix","PPmeans","BatchID","BatchNote"
]

def write_output_csv(rows: List[Dict], outdir: str, filename: str) -> str:
  path = unique_path(outdir, filename)
  # 固定列顺序，仅保留指定列
  os.makedirs(outdir, exist_ok=True)
  with open(path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
      # 填补缺失列为空
      row = {c: r.get(c, "") for c in COLUMNS}
      writer.writerow(row)
  return path