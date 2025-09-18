# formatter.py
import re

# ---- patterns ----
_PIC_RE = re.compile(r"§Pic\.(\d+)§")
_ANS_SUMMARY_RE = re.compile(r":\s*[A-F](\s*,\s*[A-F])+\.*\s*$", re.IGNORECASE)
_CURLY_RE = re.compile(r"\{\{[^}]*\}\}")         # {{...}}
_UNDER_RE = re.compile(r"_{3,}")                 # ____ (3+ underscores)
_LOWER_OPT_LINE = re.compile(r"^\s*[a-d]\.\s+.+$", re.IGNORECASE)  # a. something
_NAKED_LETTER  = re.compile(r"^\s*[A-D]\.\s*$")   # 'A.' 只有字母和点
_GRADE_ARTIFACT = re.compile(r"^\s*(Correct\s*answer:|Incorrect\s*answer:)\s*$", re.IGNORECASE)
_NOT_SELECTED  = re.compile(r",\s*Not Selected\s*$", re.IGNORECASE)
_SEQ_ONLY_LINE = re.compile(r"^\s*[A-F](\s*,\s*[A-F])+\s*\.?\s*$", re.IGNORECASE)  # B, A, C, D

def _inject_pic_linebreaks(stem: str) -> str:
  def repl(m): return f"<br>§Pic.{m.group(1)}§<br>"
  return _PIC_RE.sub(repl, stem)

def _normalize_linebreaks_to_br(s: str) -> str:
  return s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")

def _sanitize_stem(stem: str) -> str:
  """去题干里的垃圾行/伪选项/空行"""
  stem = _normalize_linebreaks_to_br(stem)
  parts = [p for p in stem.split("<br>")]
  cleaned = []
  for raw in parts:
    line = _NOT_SELECTED.sub("", raw).strip()
    if not line:
      continue
    if _GRADE_ARTIFACT.match(line):
      continue
    if _NAKED_LETTER.match(line):         # 空的 'A.' 行
      continue
    if _LOWER_OPT_LINE.match(line) and line[:1].islower():  # 小写 a./b./c./d. 伪选项行
      continue
    cleaned.append(raw.strip())
  out = "<br>".join(cleaned)
  while "<br><br>" in out:
    out = out.replace("<br><br>", "<br>")
  return out

def _strip_option_prefix(text: str) -> str:
  """选项文本去头部前缀：A./(A)/•/く 等，保留纯句子"""
  t = text.strip()
  t = re.sub(r"^\s*[\(\[]?\s*[A-Fa-f]\s*[\.\)]\s*", "", t)  # A. / (A) / A)
  t = re.sub(r"^[•\-\–\—\·\*]\s*", "", t)                   # bullet
  t = re.sub(r"^[く]+\s*", "", t)                            # 奇怪前缀
  t = _NOT_SELECTED.sub("", t).strip()
  return t

def _normalize_sequence(text: str) -> str:
  """'B, A, C, D' / '• B,A, C ,D' -> 'B,A,C,D'"""
  letters = re.findall(r"[A-Fa-f]", text)
  return ",".join(c.upper() for c in letters)

def _replace_cloze(stem: str, answers: list[str]) -> str:
  """优先替 {{...}}，否则替 ____"""
  if not answers:
    return stem
  spans = list(_CURLY_RE.finditer(stem))
  if spans:
    out, last = [], 0
    for i, sp in enumerate(spans):
      out.append(stem[last:sp.start()])
      val = answers[i] if i < len(answers) else ""
      out.append(f"{{{{{val}}}}}")
      last = sp.end()
    out.append(stem[last:])
    return "".join(out)
  us = list(_UNDER_RE.finditer(stem))
  if us:
    out, last = [], 0
    for i, sp in enumerate(us):
      out.append(stem[last:sp.start()])
      val = answers[i] if i < len(answers) else ""
      out.append(f"{{{{{val}}}}}")
      last = sp.end()
    out.append(stem[last:])
    return "".join(out)
  return stem

def _restore_underscores(stem: str) -> str:
  """CLOZE 误判兜底：把 {{...}} 全还原为 _______"""
  return _CURLY_RE.sub("_______", stem)

def _has_any_option_text(opts: dict) -> bool:
  return any((opts.get(k) or "").strip() for k in ["A","B","C","D","E","F"])

def _collapse_br(s: str) -> str:
  while "<br><br>" in s:
    s = s.replace("<br><br>", "<br>")
  return s

def _remove_option_texts_from_stem(stem: str, opts: dict) -> str:
  """把题干中“恰好和某个选项文本相同”的行移除，避免重复"""
  option_texts = set((opts.get(k) or "").strip() for k in ["A","B","C","D","E","F"] if (opts.get(k) or "").strip())
  if not option_texts:
    return stem
  parts = [p.strip() for p in stem.split("<br>")]
  kept = [p for p in parts if p not in option_texts]
  return "<br>".join(kept)

def _strip_steps_from_stem(stem: str, steps: list[str]) -> str:
  """ORDER：把题干里重复出现的步骤行剔除"""
  step_set = set(s.strip() for s in steps if s.strip())
  parts = [p.strip() for p in stem.split("<br>")]
  kept = [p for p in parts if p not in step_set and not _NAKED_LETTER.match(p)]
  return "<br>".join(kept)

def _extract_order_sequences_from_stem(stem: str) -> tuple[str, dict]:
  """
  若题干里含有“序列选项”行（如 'A. B,A,C,D' 或 'B, A, C, D'），
  提取到 options(A..F) 并从题干移除；返回 (新stem, options)
  """
  parts = [p.strip() for p in stem.split("<br>") if p.strip()]
  opts = {}
  kept = []
  next_label_ord = ord("A")
  for line in parts:
    m = re.match(r"^[A-F]\.\s*(.+)$", line, re.IGNORECASE)
    seq_text = None
    if m and _SEQ_ONLY_LINE.match(m.group(1)):
      seq_text = m.group(1)
    elif _SEQ_ONLY_LINE.match(line):
      seq_text = line
    if seq_text:
      if next_label_ord <= ord("F"):
        label = chr(next_label_ord)
        opts[label] = _normalize_sequence(seq_text)
        next_label_ord += 1
      # 不保留在 stem
      continue
    kept.append(line)
  new_stem = "<br>".join(kept)
  # 补齐空键
  for k in ["A","B","C","D","E","F"]:
    opts.setdefault(k, "")
  return new_stem, opts

# ---- main formatter ----
def format_items_to_shouldbe(items: list[dict], title_main: str, title_sub: str) -> str:
  blocks = []
  head = f"<b>{title_main}:<br>{title_sub}</b>"

  for it in items:
    qtype = (it.get("qtype") or "MCQ").upper()
    stem  = (it.get("stem") or "").strip()
    steps = it.get("steps") or []
    opts  = dict(it.get("options") or {})
    ans   = (it.get("answer") or "").strip().upper()
    cloz  = it.get("cloze_answers") or []

    # 统一换行 & 图片占位
    stem = _inject_pic_linebreaks(_normalize_linebreaks_to_br(stem))
    # 清理题干垃圾
    stem = _sanitize_stem(stem)

    # 跳过“答案总结句”伪题（仅当非 CLOZE & 无选项文本）
    if qtype != "CLOZE" and not _has_any_option_text(opts) and _ANS_SUMMARY_RE.search(stem):
      continue

    # —— CLOZE 误判兜底：有选项却是 CLOZE → 当 MCQ，且还原 {{...}} 为 _______ ——
    if qtype == "CLOZE" and _has_any_option_text(opts):
      qtype = "MCQ"
      stem = _restore_underscores(stem)

    if qtype == "CLOZE":
      # 正常 CLOZE：按答案覆盖
      stem_render = _replace_cloze(stem, cloz)
      block = f"{head}<br>{stem_render}"
      blocks.append(_collapse_br(block))
      continue

    if qtype == "ORDER":
      # 兜底：从 stem 提取序列选项（若 options 空）
      if not _has_any_option_text(opts):
        stem, recovered = _extract_order_sequences_from_stem(stem)
        # 合并（仅填充空位）
        for k in ["A","B","C","D","E","F"]:
          if not (opts.get(k) or "").strip():
            opts[k] = recovered.get(k, "")
      # 从 stem 剔除 steps（避免重复）
      stem = _strip_steps_from_stem(stem, steps)
      # 渲染
      lines = [head, f"[{stem}"]
      for s in steps:
        s = _NOT_SELECTED.sub("", s).rstrip()
        if s and not _NAKED_LETTER.match(s):
          lines.append(f" {s}")
      # 标准化 & 输出序列选项
      for letter in ["A","B","C","D","E","F"]:
        text = (opts.get(letter) or "").strip()
        if text:
          lines.append(f"{letter}. {_normalize_sequence(text)}")
      lines.append(f"]::({ans})")
      blocks.append(_collapse_br("<br>".join(lines)))
      continue

    # MCQ：图题若选项全空 → 回填 A..D = "A/B/C/D"
    if not _has_any_option_text(opts) and "§Pic." in stem:
      for k, v in zip(["A","B","C","D"], ["A","B","C","D"]):
        opts[k] = v

    # 规范化选项文本（去内层前缀）
    for k in list(opts.keys()):
      if opts.get(k):
        opts[k] = _strip_option_prefix(opts[k])

    # —— 去题干里的“重复选项句子” ——
    stem = _remove_option_texts_from_stem(stem, opts)

    # MCQ 渲染
    lines = [head, f"[{stem}"]
    for letter in ["A","B","C","D","E","F"]:
      text = (opts.get(letter) or "").strip()
      if text:
        lines.append(f"{letter}. {text}")
    lines.append(f"]::({ans})")
    blocks.append(_collapse_br("<br>".join(lines)))

  # 每题之间物理换行
  return "\n".join(blocks)