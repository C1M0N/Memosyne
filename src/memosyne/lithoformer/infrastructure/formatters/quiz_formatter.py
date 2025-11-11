"""
Quiz 格式化工具

将解析后的 QuizItem 列表格式化为 ShouldBe.txt 格式
"""
import re
from ...domain.models import QuizItem, OPTION_LETTERS


# ============================================================
# 正则表达式模式
# ============================================================
_PIC_RE = re.compile(r"§Pic\.(\d+)§")
_ANS_SUMMARY_RE = re.compile(r":\s*[A-Z](\s*,\s*[A-Z])+\.*\s*$", re.IGNORECASE)
_CURLY_RE = re.compile(r"\{\{[^}]*\}\}")  # {{...}}
_UNDER_RE = re.compile(r"_{3,}")  # ____ (3+ underscores)
_LOWER_OPT_LINE = re.compile(r"^\s*[a-z]\.\s+.+$", re.IGNORECASE)  # a. something
_NAKED_LETTER = re.compile(r"^\s*[A-Z]\.\s*$")  # 'A.' 只有字母和点
_GRADE_ARTIFACT = re.compile(r"^\s*(Correct\s*answer:|Incorrect\s*answer:)\s*$", re.IGNORECASE)
_NOT_SELECTED = re.compile(r",\s*Not Selected\s*$", re.IGNORECASE)


# ============================================================
# 文本处理工具函数
# ============================================================
def _inject_pic_linebreaks(stem: str) -> str:
    """在图片占位符前后添加换行"""
    def repl(m):
        return f"<br>§Pic.{m.group(1)}§<br>"
    return _PIC_RE.sub(repl, stem)


def _normalize_linebreaks_to_br(s: str) -> str:
    """统一换行符为 <br>，保留空白段落"""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\n\n", "\n<PARA>\n")
    s = s.replace("\n", "<br>")
    return s.replace("<PARA>", "<br>")


def _sanitize_stem(stem: str) -> str:
    """清理题干中的垃圾行/伪选项/空行"""
    stem = _normalize_linebreaks_to_br(stem)
    parts = stem.split("<br>")
    result: list[str] = []
    blank_seen = False

    for raw in parts:
        line = _NOT_SELECTED.sub("", raw).strip()
        if not line:
            blank_seen = True
            continue
        if _GRADE_ARTIFACT.match(line):
            blank_seen = False
            continue
        if _NAKED_LETTER.match(line):
            blank_seen = False
            continue
        if _LOWER_OPT_LINE.match(line) and line[:1].islower():
            blank_seen = False
            continue

        text = raw.strip()
        if not text:
            blank_seen = False
            continue

        if result:
            result.append("<br><br>" if blank_seen else "<br>")
        elif blank_seen:
            result.append("<br><br>")

        result.append(text)
        blank_seen = False

    return "".join(result)


def _strip_option_prefix(text: str) -> str:
    """选项文本去头部前缀：A./(A)/•/く 等，保留纯句子"""
    t = text.strip()
    t = re.sub(r"^\s*[\(\[]?\s*[A-Za-z]\s*[\.\)]\s*", "", t)  # A. / (A) / A)
    t = re.sub(r"^[•\-\–\—\·\*]\s*", "", t)  # bullet
    t = re.sub(r"^[く]+\s*", "", t)  # 奇怪前缀
    t = _NOT_SELECTED.sub("", t).strip()
    return t


def _format_title_html(title_main: str, title_sub: str) -> str:
    """
    格式化标题为HTML

    规则：
    - title_main的每行单独加粗，用<br>连接
    - title_sub的每行不加粗，用<br>连接

    Example:
        >>> _format_title_html("Test Bank: Chapter 4", "The Chemistry of Behavior")
        '<b>Test Bank: Chapter 4</b><br>The Chemistry of Behavior'

        >>> _format_title_html("Line1\\nLine2", "Sub1\\nSub2")
        '<b>Line1</b><br><b>Line2</b><br>Sub1<br>Sub2'
    """
    parts = []

    # 处理主标题（每行加粗）
    if title_main:
        main_lines = [line.strip() for line in title_main.split("\n") if line.strip()]
        for line in main_lines:
            parts.append(f"<b>{line}</b>")

    # 处理副标题（不加粗）
    if title_sub:
        sub_lines = [line.strip() for line in title_sub.split("\n") if line.strip()]
        parts.extend(sub_lines)

    # 用<br>连接所有部分
    return "<br>".join(parts) if parts else ""


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


def _has_any_option_text(options: dict) -> bool:
    """检查是否有任何非空选项"""
    return any((options.get(k) or "").strip() for k in OPTION_LETTERS)


def _collapse_br(s: str) -> str:
    """折叠过多的 <br>，保留双换行"""
    while "<br><br><br>" in s:
        s = s.replace("<br><br><br>", "<br><br>")
    return s


def _normalize_translation_text(text: str) -> str:
    """Normalize translation text to use <br> markers consistently."""
    return _collapse_br(_normalize_linebreaks_to_br(text.strip())) if text else ""


def _combine_bilingual(text_en: str, text_cn: str) -> str:
    """Render English + Chinese translation as a single block, line by line."""
    text_en = text_en.strip()
    text_cn = text_cn.strip()
    if not text_en and not text_cn:
        return ""
    if not text_cn:
        return text_en
    return _interleave_translation(text_en, text_cn)


def _interleave_translation(text_en: str, text_cn: str) -> str:
    """Interleave translation lines against English lines robustly.

    Rules:
    - Only attach a CN line to a non-empty EN line.
    - Skip CN segments that are placeholders like '§Pic.N§' or empty.
    - Preserve EN-only blank lines to maintain paragraph spacing.
    - For EN placeholders '§Pic.N§', render EN only (no CN line).
    - Discard leftover CN segments to avoid drifting translations.
    """
    en_segments = text_en.split("<br>") if text_en else [""]
    cn_segments = text_cn.split("<br>") if text_cn else []

    def _is_pic(seg: str) -> bool:
        s = seg.strip()
        return bool(_PIC_RE.fullmatch(s))

    out_segments: list[str] = []
    j = 0  # pointer into cn_segments

    for en_part_raw in en_segments:
        en_part = en_part_raw.strip()

        # Preserve blank EN lines (paragraph spacing); don't consume CN
        if not en_part:
            out_segments.append("")
            continue

        # Image placeholder: render EN only (no CN pairing)
        if _is_pic(en_part):
            out_segments.append(en_part)
            continue

        # Find next usable CN segment (non-empty, non-placeholder)
        cn_part = ""
        while j < len(cn_segments):
            cand = cn_segments[j].strip()
            j += 1
            if not cand:
                # skip empty CN
                continue
            if _is_pic(cand):
                # skip CN placeholder echo
                continue
            cn_part = cand
            break

        if cn_part:
            out_segments.append(f"{en_part}<br>((::{cn_part}))")
        else:
            out_segments.append(en_part)

    return "<br>".join(out_segments)


def _format_analysis(item: QuizItem) -> str:
    analysis = item.analysis
    if analysis is None:
        return ""

    sections: list[str] = []
    if analysis.domain.strip():
        sections.append(f"<div>领域：{analysis.domain.strip()}</div>")

    answer_letter = (item.answer or "").strip().upper()
    options_map = item.options.model_dump()
    answer_text = (options_map.get(answer_letter) or "").strip()
    header = f"为什么选 {answer_letter.lower()}"
    if answer_text:
        header += f"（{answer_text}）"
    sections.append(f"<div>{header}</div>")

    if analysis.rationale.strip():
        sections.append(f"<div>{_normalize_linebreaks_to_br(analysis.rationale.strip())}</div>")

    key_points = [kp.strip() for kp in analysis.key_points if kp.strip()]
    if key_points:
        sections.append("<div><br></div>")
        sections.append("<div>相关知识：</div>")
        for kp in key_points:
            sections.append(f"<div>{_normalize_linebreaks_to_br(kp)}</div>")

    distractors_html: list[str] = []
    for dist in analysis.distractors:
        option_letter = (dist.option or "").strip().upper()
        if not option_letter:
            continue
        reason = _normalize_linebreaks_to_br(dist.reason.strip())
        distractors_html.append(f"<div>{option_letter}. {reason}</div>")

    if distractors_html:
        sections.append("<div><br></div>")
        sections.append(f"<div>其他选项为什么不如 {answer_letter.lower()}：</div>")
        sections.extend(distractors_html)

    if not sections:
        return ""

    analysis_body = _collapse_br("".join(sections))
    return f"<br><br>[[解析::<br>{analysis_body}]]<br>"


def _remove_option_texts_from_stem(stem: str, options: dict) -> str:
    """把题干中"恰好和某个选项文本相同"的行移除，避免重复"""
    option_texts = set(
        (options.get(k) or "").strip()
        for k in OPTION_LETTERS
        if (options.get(k) or "").strip()
    )
    if not option_texts:
        return stem
    parts = [p.strip() for p in stem.split("<br>")]
    kept = [p for p in parts if p not in option_texts]
    return "<br>".join(kept)


# ============================================================
# QuizFormatter 类
# ============================================================
class QuizFormatter:
    """
    Quiz 格式化器

    将 QuizItem 列表格式化为 ShouldBe.txt 格式

    Example:
        >>> formatter = QuizFormatter()
        >>> items = [...]  # QuizItem 列表
        >>> text = formatter.format(items, "Chapter 3 Quiz", "Mental Disorders")
        >>> print(text)
    """

    def format(
        self,
        items: list[QuizItem],
        title_main: str,
        title_sub: str = "",
        *,
        batch_code: str = "",
        question_start: int | None = None,
        question_prefix: str = "L",
    ) -> str:
        """
        格式化 Quiz 题目列表

        Args:
            items: QuizItem 列表
            title_main: 主标题（如 "Chapter 3 Quiz"）
            title_sub: 副标题（如 "Mental Disorders"）
            batch_code: 批次代码（输出文件名的前缀）
            question_start: 题号起始基准值（例如文件名中的数字部分）
            question_prefix: 题号前缀，默认 "L"

        Returns:
            格式化后的文本（ShouldBe.txt 格式）
        """
        blocks = []
        head = _format_title_html(title_main, title_sub)
        base_number = question_start or 0

        for idx, item in enumerate(items, start=1):
            qtype = item.qtype.upper()
            stem_en = item.stem.strip()
            stem_cn = _normalize_translation_text(item.stem_translation)
            opts = item.options.model_dump()  # 转为 dict
            opts_cn = {
                key: _normalize_translation_text(value)
                for key, value in item.options_translation.model_dump().items()
            }
            for letter in OPTION_LETTERS:
                opts.setdefault(letter, "")
                opts_cn.setdefault(letter, "")
            ans = item.answer.strip().upper()
            cloz = item.cloze_answers or []

            # 统一换行 & 图片占位
            stem_en = _inject_pic_linebreaks(_normalize_linebreaks_to_br(stem_en))
            # 清理题干垃圾
            stem_en = _sanitize_stem(stem_en)

            # 跳过"答案总结句"伪题（仅当非 CLOZE & 无选项文本）
            if qtype != "CLOZE" and not _has_any_option_text(opts) and _ANS_SUMMARY_RE.search(stem_en):
                continue

            # —— CLOZE 误判兜底：有选项却是 CLOZE → 当 MCQ，且还原 {{...}} 为 _______ ——
            if qtype == "CLOZE" and _has_any_option_text(opts):
                qtype = "MCQ"
                stem_en = _restore_underscores(stem_en)

            if qtype == "CLOZE":
                # 正常 CLOZE：按答案覆盖
                stem_render_en = _replace_cloze(stem_en, cloz)
                stem_render_en = _collapse_br(stem_render_en)
                body = _combine_bilingual(stem_render_en, stem_cn)
                analysis_html = _format_analysis(item)
                blocks.append(f"{head}<br><br>{body}{analysis_html}")
                continue

            # MCQ：图题若选项全空 → 回填字母本身
            if not _has_any_option_text(opts) and "§Pic." in stem_en:
                for letter in OPTION_LETTERS[:4]:
                    opts[letter] = letter
                    opts_cn.setdefault(letter, "")
                for letter in OPTION_LETTERS[4:]:
                    opts.setdefault(letter, "")
                    opts_cn.setdefault(letter, "")

            # 规范化选项文本（去内层前缀）
            for k in list(opts.keys()):
                if opts.get(k):
                    opts[k] = _strip_option_prefix(opts[k])

            # —— 去题干里的"重复选项句子" ——
            stem_en = _remove_option_texts_from_stem(stem_en, opts)
            stem_render = _combine_bilingual(stem_en, stem_cn)

            # MCQ 渲染
            lines = [f"[{stem_render}"]
            for letter in OPTION_LETTERS:
                text = (opts.get(letter) or "").strip()
                text_cn = (opts_cn.get(letter) or "").strip()
                if not (text or text_cn):
                    continue
                lines.append(f"{letter}. {_combine_bilingual(text, text_cn)}")
            lines.append(f"]::({ans})")
            body = _collapse_br("<br>".join(lines))
            analysis_html = _format_analysis(item)

            blocks.append(f"{head}<br><br>{body}{analysis_html}")

        if not blocks:
            return ""

        question_blocks: list[str] = []
        for offset, block in enumerate(blocks, start=1):
            code_number = base_number + offset
            question_code = f"{question_prefix}{code_number:06d}"
            meta_parts = []
            if batch_code:
                meta_parts.append(f"<div style=\"text-align: right;\">{batch_code}</div>")
            if question_code:
                meta_parts.append(f"<div style=\"text-align: right;\">{question_code}</div>")
            metadata_html = "".join(meta_parts)
            question_blocks.append(f"{block}{metadata_html}")

        # 每题之间物理换行
        return "\n".join(question_blocks)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    from ...domain.models import QuizItem, QuizOptions

    # 示例数据
    item1 = QuizItem(
        qtype="MCQ",
        stem="What is the capital of France?",
        options=QuizOptions(A="London", B="Paris", C="Berlin", D="Madrid"),
        answer="B"
    )

    item2 = QuizItem(
        qtype="CLOZE",
        stem="The capital of France is {{Paris}}.",
        cloze_answers=["Paris"]
    )

    formatter = QuizFormatter()
    text = formatter.format([item1, item2], "Sample Quiz", "Geography")
    print(text)
