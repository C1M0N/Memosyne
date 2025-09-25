# src/mms_pipeline/main.py
import os
from pathlib import Path

from term_data import read_input_csv, write_output_csv, TermList
from openai_helper import OpenAIHelper
from term_processor import TermProcessor


def ask(prompt: str, required: bool = True) -> str:
  while True:
    v = input(prompt).strip()
    if v or not required:
      return v
    print("不能为空，请重输。")


# ---------- 路径解析：自动找到项目根(data/ 所在处) ----------
def _find_project_root() -> Path:
  here = Path(__file__).resolve()
  # 自下而上寻找包含 data/ 的目录
  for p in [here.parent, *here.parents]:
    if (p / "data").is_dir():
      return p
  # 兜底：回退到上两级
  return here.parents[2]


ROOT = _find_project_root()


def _unique_path(p: Path) -> Path:
  if not p.exists():
    return p
  stem, ext = p.stem, p.suffix
  k = 2
  while True:
    cand = p.with_name(f"{stem}_{k}{ext}")
    if not cand.exists():
      return cand
    k += 1


def _resolve_input_csv(user_input: str) -> Path:
  """输入CSV：留空或只给文件名 -> 默认 data/input/"""
  s = (user_input or "").strip()
  if not s:
    cand = ROOT / "data" / "input" / "memo" / "short.csv"
    return cand
  p = Path(s)
  if p.is_absolute() or any(ch in s for ch in ("/", "\\")):
    return p
  # 只有文件名：默认到 data/input/ 下找
  return ROOT / "data" / "input" / "memo" / s


def _resolve_termlist_csv(user_input: str) -> Path:
  """术语表：留空 -> data/term_list_v1.csv；只给文件名会在多个目录尝试"""
  s = (user_input or "").strip()
  if not s:
    return ROOT / "db" / "term_list_v1.csv"
  p = Path(s)
  if p.is_absolute() or any(ch in s for ch in ("/", "\\")):
    return p
  # 尝试 data/, data/input/, data/db/
  for sub in ("data", "data/input", "data/db"):
    cand = ROOT / sub / s
    if cand.exists():
      return cand
  return ROOT / "db" / s


def _resolve_output_path(user_input: str, batch_id: str, model_name: str) -> Path:
  """输出：留空 -> data/output/BatchID_MMS_V3_模型名.csv；目录则自动拼文件名并防覆盖"""
  s = (user_input or "").strip()
  default_dir = ROOT / "data" / "output" / "memo"
  filename = f"{batch_id}_MMS_V3_{model_name}.csv"

  if not s:
    default_dir.mkdir(parents=True, exist_ok=True)
    return _unique_path(default_dir / filename)

  p = Path(s)
  # 如果给的是目录
  if p.suffix.lower() != ".csv":
    p.mkdir(parents=True, exist_ok=True)
    return _unique_path(p / filename)

  # 给的是具体文件名
  p.parent.mkdir(parents=True, exist_ok=True)
  return _unique_path(p)

def _load_dotenv_simple(path: Path):
  if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
      line = line.strip()
      if not line or line.startswith("#") or "=" not in line:
        continue
      k, v = line.split("=", 1)
      os.environ.setdefault(k.strip(), v.strip())


def main():
  _load_dotenv_simple(_find_project_root() / ".env")
  print("=== MMS Slim | 终端向导 ===")

  model = ask("模型ID（例如 gpt-4o-mini / GPT-5-mini）：")
  model_name = ask("用于文件名展示的模型名（例如 GPT-5-mini）：")

  in_raw = ask("输入CSV路径（默认 data/input/n8n.csv，可填文件名或完整路径）：", required=False)
  term_raw = ask("术语表CSV路径（默认 data/term_list_v1.csv）：", required=False)

  # 先收集与文件名有关的参数，再解析输出路径
  start_memo_str = ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）：")
  batch_id = ask("BatchID（例：250916A058）：")
  batch_note = ask("批注（BatchNote，可空）：", required=False)
  out_raw = ask("输出路径（默认 data/output/；可给目录或完整文件名）：", required=False)

  try:
    start_memo = int(start_memo_str)
  except ValueError:
    print("起始Memo编号必须为整数。")
    return

  input_path = _resolve_input_csv(in_raw)
  termlist_path = _resolve_termlist_csv(term_raw)
  output_path = _resolve_output_path(out_raw, batch_id=batch_id, model_name=model_name)

  # 展示解析后的实际路径，便于定位问题
  print(f"[Paths] input = {input_path}")
  print(f"[Paths] termlist = {termlist_path}")
  print(f"[Paths] output = {output_path}")

  # 加载输入
  try:
    entries = read_input_csv(str(input_path))
  except Exception as e:
    print(f"读取输入失败：{e}")
    return

  # 加载术语表（一次）
  term_list = TermList()
  try:
    term_list.load_from_csv(str(termlist_path))
  except Exception as e:
    print(f"读取术语表失败：{e}")
    return

  # OpenAI
  try:
    helper = OpenAIHelper(model=model)
  except Exception as e:
    print(f"OpenAI 初始化失败：{e}")
    return

  # 处理
  processor = TermProcessor(
    openai_helper=helper,
    term_list=term_list,
    start_memo_index=start_memo,
    batch_id=batch_id,
    batch_note=batch_note,
  )
  out_rows = processor.process(entries, model_name=model_name)

  # 写出
  try:
    write_output_csv(str(output_path), out_rows)
  except Exception as e:
    print(f"写出失败：{e}")
    return

  print(f"✅ 完成：{output_path}")


if __name__ == "__main__":
  main()