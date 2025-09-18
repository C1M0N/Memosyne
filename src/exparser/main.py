# src/quiz_agent/main.py
import os
from pathlib import Path

from openai_quiz_helper import OpenAIQuizHelper
from formatter import format_items_to_shouldbe


def ask(prompt: str, required: bool = True) -> str:
  while True:
    v = input(prompt).strip()
    if v or not required:
      return v
    print("不能为空，请重输。")


# ---------- 路径解析：自动找到项目根(data/ 所在处) ----------
def _find_project_root() -> Path:
  here = Path(__file__).resolve()
  for p in [here.parent, *here.parents]:
    if (p / "data").is_dir():
      return p
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


def _resolve_input_md(user_input: str) -> Path:
  """
  输入Markdown：留空 -> data/input/Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md
  只给文件名 -> 默认到 data/input/ 下找
  """
  s = (user_input or "").strip()
  if not s:
    return ROOT / "data" / "input" / "Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md"
  p = Path(s)
  if p.is_absolute() or any(ch in s for ch in ("/", "\\")):
    return p
  return ROOT / "data" / "input" / s


def _resolve_output_path(user_input: str) -> Path:
  """
  输出：留空 -> data/output/ShouldBe.txt；
  如果给的是目录 -> 自动拼 'ShouldBe.txt' 并防覆盖；
  如果给的是具体文件名 -> 直接使用并防覆盖。
  """
  s = (user_input or "").strip()
  default_dir = ROOT / "data" / "output"
  default_name = "ShouldBe.txt"

  if not s:
    default_dir.mkdir(parents=True, exist_ok=True)
    return _unique_path(default_dir / default_name)

  p = Path(s)
  if p.suffix.lower() != ".txt":
    p.mkdir(parents=True, exist_ok=True)
    return _unique_path(p / default_name)

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


def _infer_titles_from_filename(path: Path) -> tuple[str, str]:
  """
  从文件名推断：
    'Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md'
    -> ('Chapter 3 Quiz', 'Assessment and Classification of Mental Disorders')
  其他情况：尽量拆成 '... Quiz' + '-' 之后的部分；否则整段作为 main，sub 为空。
  """
  name = path.stem  # 不含扩展名
  # 常见模式："... Quiz- Subtitle"
  if "Quiz" in name:
    # 先按 'Quiz' 切
    left, _, right = name.partition("Quiz")
    main = (left + "Quiz").strip()
    # 再看是否有 '-' 引导的副标题
    if "-" in right:
      _, _, sub = right.partition("-")
      sub = sub.strip()
    else:
      sub = right.strip().lstrip(":：-").strip()
    if main:
      return main, sub
  # 兜底
  return name.strip(), ""


def main():
  _load_dotenv_simple(_find_project_root() / ".env")
  print("=== Quiz Agent | 终端向导 ===")

  model = ask("模型ID（例如 gpt-4o-mini / GPT-5-mini）：")
  in_raw = ask("输入Markdown文件路径（默认 data/input/...）：", required=False)
  out_raw = ask("输出TXT文件路径（默认 data/output/ShouldBe.txt）：", required=False)

  input_path = _resolve_input_md(in_raw)
  output_path = _resolve_output_path(out_raw)

  # 推断标题（可根据需要改成也询问用户）
  title_main, title_sub = _infer_titles_from_filename(input_path)

  # 展示解析后的实际路径，便于定位问题
  print(f"[Paths] input = {input_path}")
  print(f"[Paths] output = {output_path}")
  print(f"[Title] main = {title_main} | sub = {title_sub}")

  # 读取 Markdown
  try:
    md_text = input_path.read_text(encoding="utf-8")
  except Exception as e:
    print(f"读取输入失败：{e}")
    return

  # OpenAI
  try:
    helper = OpenAIQuizHelper(model=model, temperature=None)
  except Exception as e:
    print(f"OpenAI 初始化失败：{e}")
    return

  # 解析 → 格式化
  try:
    items = helper.parse_md_to_items(md_text)
  except Exception as e:
    print(f"解析失败：{e}")
    return

  out_text = format_items_to_shouldbe(items, title_main, title_sub)

  # 写出
  try:
    output_path.write_text(out_text, encoding="utf-8")
  except Exception as e:
    print(f"写出失败：{e}")
    return

  print(f"✅ 完成：{output_path}")


if __name__ == "__main__":
  main()