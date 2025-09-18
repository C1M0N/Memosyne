# src/quiz_agent/formatter.py

def format_items_to_shouldbe(items: list[dict], title_main: str, title_sub: str) -> str:
  """
  目标格式（和 ShouldBe.txt 一致的 HTML-like 样式）：
  <b>{title_main}:<br>{title_sub}</b><br>{stem}<br>A. ...<br>B. ...<br>...<br>]::(X)
  注意：整个文件可无换行符，使用 <br> 作为逻辑换行（和你的示例一致）。
  """
  blocks = []
  for it in items:
    stem = it.get("stem", "").strip()
    opts = it.get("options", {}) or {}
    ans  = (it.get("answer") or "").strip().upper()

    # 标题行
    head = f"<b>{title_main}:<br>{title_sub}</b>"

    # 题干 + 选项（存在的就输出）
    lines = [head, f"{stem}"]
    for letter in ["A", "B", "C", "D", "E", "F"]:
      if letter in opts and (opts[letter] or "").strip():
        lines.append(f"{letter}. {opts[letter].strip()}")

    # 答案（如果没有就留空括号）
    if not ans:
      ans = ""
    lines.append(f"]::({ans})")

    # 用 <br> 连接
    block = "<br>".join(lines)
    blocks.append(block)

  # 所有题目直接拼接（示例 ShouldBe.txt 是一整行只有 <br>，无物理换行）
  return "".join(blocks)