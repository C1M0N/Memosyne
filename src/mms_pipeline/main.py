# src/mms_pipeline/main.py
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from term_data import read_input_csv, write_output_csv, TermList
from openai_helper import OpenAIHelper
from term_processor import TermProcessor


# ========== 基础交互 ==========
def ask(prompt: str, required: bool = True) -> str:
  while True:
    v = input(prompt).strip()
    if v or not required:
      return v
    print("不能为空，请重输。")


# ========== 项目根与路径工具 ==========
def _find_project_root() -> Path:
  here = Path(__file__).resolve()
  for p in [here.parent, *here.parents]:
    if (p / "data").is_dir():
      return p
  return here.parents[2]


ROOT = _find_project_root()
DATA_IN = ROOT / "data" / "input" / "memo"
DATA_OUT = ROOT / "data" / "output" / "memo"
TERMLIST_PATH = ROOT / "db" / "term_list_v1.csv"


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


def _load_dotenv_simple(path: Path):
  if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
      line = line.strip()
      if not line or line.startswith("#") or "=" not in line:
        continue
      k, v = line.split("=", 1)
      os.environ.setdefault(k.strip(), v.strip())


# ========== 引擎与展示名 ==========
def _resolve_model(user: str) -> tuple[str, str]:
  """
  返回 (model_id, model_display)
  - 4  -> gpt-4o-mini / 4oMini
  - 5  -> gpt-5-mini / 5Mini
  - 其他：按原样作为 model_id，并生成一个展示名（尽量紧凑、驼峰）
  """
  u = (user or "").strip()
  if u == "4":
    return "gpt-4o-mini", "4oMini"
  if u == "5":
    return "gpt-5-mini", "5Mini"

  mid = u  # 用户提供完整模型ID
  # 展示名生成：优先匹配常见模式；否则把连字符转驼峰，并保留尾部 Mini/Mini字样
  lut = {
    "gpt-4o-mini": "4oMini",
    "gpt-5-mini": "5Mini",
  }
  if mid in lut:
    return mid, lut[mid]

  # 通用：去掉前缀 gpt-，把 - 分段再驼峰，保留数字/字母；末尾 -mini -> Mini
  parts = mid.replace("gpt-", "", 1).split("-")
  disp = "".join(p[:1].upper() + p[1:] for p in parts if p)
  disp = disp.replace("Mini", "Mini")  # 若已包含 Mini 维持
  return mid, disp or "Model"


# ========== 输入CSV与起始Memo ==========
def _resolve_input_and_memo(user_path: str) -> tuple[Path, int]:
  """
  - 纯数字：视为 data/input/{num}.csv，且起始Memo=num
  - 含“.csv”或带路径分隔符：按文件路径读取，并额外询问起始Memo
  - 留空：使用 data/input/n8n.csv，并额外询问起始Memo
  """
  s = (user_path or "").strip()
  if s.isdigit():
    memo = int(s)
    p = DATA_IN / f"{s}.csv"
    return p, memo

  if (".csv" in s) or any(ch in s for ch in ("/", "\\")):
    p = Path(s)
    if not p.is_absolute():
      # 相对路径优先 data/input/，找不到再按相对
      cand = DATA_IN / s
      p = cand if cand.exists() else Path(s)
    memo_str = ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）：")
    try:
      memo = int(memo_str)
    except ValueError:
      raise ValueError("起始Memo编号必须为整数。")
    return p, memo

  # 留空：默认 n8n.csv 并询问起始Memo
  p = DATA_IN / "short.csv"
  memo_str = ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）：")
  try:
    memo = int(memo_str)
  except ValueError:
    raise ValueError("起始Memo编号必须为整数。")
  return p, memo


# ========== BatchID 生成 ==========
def _today_ny_ymd() -> datetime:
  # 使用 America/New_York 时区
  return datetime.now(ZoneInfo("America/New_York"))


def _next_run_letter(out_dir: Path, yymmdd: str) -> str:
  """
  扫描 data/output/ 下当日已有文件，生成下一个批次字母（A..Z）
  文件名前缀形如：YYMMDD[A-Z]
  """
  used = set()
  if out_dir.exists():
    for p in out_dir.iterdir():
      name = p.name
      if len(name) >= 7 and name[:6] == yymmdd:
        ch = name[6]
        if "A" <= ch <= "Z":
          used.add(ch)
  # 下一个字母
  for code in range(ord("A"), ord("Z") + 1):
    c = chr(code)
    if c not in used:
      return c
  raise RuntimeError("当日批次超过 26 次（A..Z 已用尽）。")


def _make_batch_id(out_dir: Path, items_count: int) -> str:
  """
  BatchID = YYMMDD + RunLetter + NNN
  - NNN 为本批词条数，3 位左零填充
  """
  d = _today_ny_ymd()
  yymmdd = d.strftime("%y%m%d")
  run_letter = _next_run_letter(out_dir, yymmdd)
  nnn = f"{items_count:03d}"
  return f"{yymmdd}{run_letter}{nnn}"


# ========== 输出文件名 ==========
def _output_path(batch_id: str, model_display: str) -> Path:
  DATA_OUT.mkdir(parents=True, exist_ok=True)
  filename = f"{batch_id}.csv"
  return _unique_path(DATA_OUT / filename)


# ========== .env 加载 ==========
def _init_openai(model_id: str) -> OpenAIHelper:
  try:
    helper = OpenAIHelper(model=model_id)
  except Exception as e:
    raise RuntimeError(f"OpenAI 初始化失败：{e}")
  return helper


# ========== 主流程 ==========
def main():
  _load_dotenv_simple(_find_project_root() / ".env")
  print("=== MMS Slim | 终端向导 ===")

  # 仅 3 个输入
  model_in = ask("引擎（4 = gpt-4o-mini，5 = gpt-5-mini，或输入完整模型ID）：")
  path_in = ask("输入CSV路径（纯数字=按 {num}.csv；含 .csv/路径=直接使用；留空=使用 n8n.csv）：", required=False)
  note_in = ask("批注（BatchNote，可空）：", required=False)

  # 解析模型
  model_id, model_display = _resolve_model(model_in)

  # 解析输入文件与起始Memo
  try:
    input_path, start_memo = _resolve_input_and_memo(path_in)
  except Exception as e:
    print(f"路径/起始Memo 解析失败：{e}")
    return

  # 显示关键信息
  print(f"[Engine] model_id = {model_id}, display = {model_display}")
  print(f"[Input ] path = {input_path}")
  print(f"[Start ] memo = {start_memo}")
  print(f"[Term  ] path = {TERMLIST_PATH}")

  # 读取输入
  try:
    entries = read_input_csv(str(input_path))
  except Exception as e:
    print(f"读取输入失败：{e}")
    return

  # 加载术语表（固定路径）
  term_list = TermList()
  try:
    term_list.load_from_csv(str(TERMLIST_PATH))
  except Exception as e:
    print(f"读取术语表失败：{e}")
    return

  # 自动生成 BatchID（基于今日日期 + 当日批次字母 + 本批词数）
  try:
    batch_id = _make_batch_id(DATA_OUT, items_count=len(entries))
  except Exception as e:
    print(f"BatchID 生成失败：{e}")
    return

  # 输出路径（默认目录 + 自动文件名 + 防覆盖）
  output_path = _output_path(batch_id, model_display)

  # OpenAI
  try:
    helper = _init_openai(model_id)
  except Exception as e:
    print(e)
    return

  # 处理
  processor = TermProcessor(
    openai_helper=helper,
    term_list=term_list,
    start_memo_index=start_memo,
    batch_id=batch_id,
    batch_note=note_in,
  )
  out_rows = processor.process(entries, model_name=model_display)

  # 写出
  try:
    write_output_csv(str(output_path), out_rows)
  except Exception as e:
    print(f"写出失败：{e}")
    return

  print(f"✅ 完成：{output_path}")


if __name__ == "__main__":
  main()