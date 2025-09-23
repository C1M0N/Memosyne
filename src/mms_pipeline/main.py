# main.py
import os
from pathlib import Path
from dotenv import load_dotenv

from term_data import read_input_csv, write_output_csv, TermList
from openai_helper import OpenAIHelper
from term_processor import TermProcessor

def ask(tip: str, required: bool = True) -> str:
  while True:
    v = input(tip).strip()
    if v or not required:
      return v
    print("不能为空，请重输。")

def _project_root() -> Path:
  here = Path(__file__).resolve()
  for p in [here.parent, *here.parents]:
    if (p / "data").exists():
      return p
  return here.parent

ROOT = _project_root()
load_dotenv(ROOT / ".env", override=False)

def _unique(p: Path) -> Path:
  if not p.exists():
    return p
  stem, ext = p.stem, p.suffix
  k = 2
  while True:
    cand = p.with_name(f"{stem}_{k}{ext}")
    if not cand.exists():
      return cand
    k += 1

def _resolve_in(s: str) -> Path:
  s = (s or "").strip()
  if not s:
    return ROOT / "data" / "input" / "n8n.csv"
  p = Path(s)
  if p.is_absolute() or any(ch in s for ch in ("/","\\")):
    return p
  return ROOT / "data" / "input" / s

def _resolve_term(s: str) -> Path:
  s = (s or "").strip()
  if not s:
    return ROOT / "data" / "term_list_v1.csv"
  p = Path(s)
  if p.is_absolute() or any(ch in s for ch in ("/","\\")):
    return p
  return ROOT / "data" / s

def _resolve_out(s: str, batch_id: str, model_name: str) -> Path:
  default_dir = ROOT / "data" / "output"
  default_dir.mkdir(parents=True, exist_ok=True)
  filename = f"{batch_id}_MMS_V3_{model_name}.csv"
  if not s:
    return _unique(default_dir / filename)
  p = Path(s)
  if p.suffix.lower() != ".csv":
    p.mkdir(parents=True, exist_ok=True)
    return _unique(p / filename)
  p.parent.mkdir(parents=True, exist_ok=True)
  return _unique(p)

def main():
  print("=== MMS Slim | 终端向导 ===")
  model = ask("模型ID（例如 gpt-4o-mini / gpt-5-mini）：")
  model_name = ask("用于文件名展示的模型名（例如 4o-mini / 5-mini）：")

  inp = ask("输入CSV路径（默认 data/input/n8n.csv，可填文件名或完整路径）：", required=False)
  term = ask("术语表CSV路径（默认 data/term_list_v1.csv）：", required=False)
  start_memo = int(ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）："))
  batch_id = ask("BatchID（例：250916A058）：")
  batch_note = ask("批注（BatchNote，可空）：", required=False)
  outp = ask("输出路径（默认 data/output/；可给目录或完整文件名）：", required=False)
  temp_raw = ask("可选 temperature（留空=不传）：", required=False)
  temperature = None
  if temp_raw:
    try:
      temperature = float(temp_raw)
    except ValueError:
      print("⚠️ temperature 非数字，已忽略。")

  input_path = _resolve_in(inp)
  term_path = _resolve_term(term)
  out_path = _resolve_out(outp, batch_id, model_name)

  print(f"[Paths] input = {input_path}")
  print(f"[Paths] termlist = {term_path}")
  print(f"[Paths] output = {out_path}")

  try:
    rows = read_input_csv(str(input_path))
  except Exception as e:
    print(f"读取输入失败：{e}")
    return

  tl = TermList()
  try:
    tl.load_from_csv(str(term_path))
  except Exception as e:
    print(f"读取术语表失败：{e}")
    return

  try:
    helper = OpenAIHelper(model=model, api_key=os.getenv("OPENAI_API_KEY"), temperature=temperature)
  except Exception as e:
    print(f"OpenAI 初始化失败：{e}")
    return

  proc = TermProcessor(openai_helper=helper, term_list=tl,
                       start_memo_index=start_memo, batch_id=batch_id, batch_note=batch_note)
  try:
    out_rows = proc.process(rows, model_name=model_name)
  except Exception as e:
    print(f"处理失败：{e}")
    return

  try:
    write_output_csv(str(out_path), out_rows)
  except Exception as e:
    print(f"写出失败：{e}")
    return

  print(f"✅ 完成：{out_path}")

if __name__ == "__main__":
  main()