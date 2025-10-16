"""
Lithoformer Domain Services - Pure business logic

Dependency rules:
- Zero external dependencies
- Stateless functions (pure functions, testable)
- Encapsulate business rules

Business rules:
1. Quiz validation (check completeness)
2. Title inference from filename
3. Quiz type detection
"""
import re
from pathlib import Path

from .models import QuizItem


QUESTION_BLOCK_PATTERN = re.compile(
    r"```Question\s*\n(?P<question>.*?)```(?:\s*\n)*```Answer\s*\n(?P<answer>.*?)```",
    re.IGNORECASE | re.DOTALL
)
HEADING_PATTERN = re.compile(r"^\s*##\s+.*$", re.MULTILINE)
NUMBER_HEADING = re.compile(r"^\s*##\s+\d+.*$")
LEGACY_BLOCK_PATTERN = re.compile(
    r"```Gezhi\s*\n(?P<question>.*?)```(?:\s*\n)*```Gezhi\s*\n(?P<answer>.*?)```",
    re.IGNORECASE | re.DOTALL
)


def split_markdown_into_questions(markdown: str) -> list[dict[str, str]]:
    """
    将遵循 ```Question``` / ```Answer``` 格式的 Markdown 拆分为题目块，返回包含上下文信息的字典。

    Returns:
        每个元素包含 {"context": ..., "question": ..., "answer": ...}
    """
    blocks: list[dict[str, str]] = []
    last_end = 0

    for match in QUESTION_BLOCK_PATTERN.finditer(markdown):
        question = match.group("question").strip()
        answer = match.group("answer").strip()

        heading_segment = markdown[last_end:match.start()]
        headings = HEADING_PATTERN.findall(heading_segment)
        heading_prefix = headings[-1].strip() if headings else ""

        blocks.append({
            "context": heading_prefix,
            "question": question,
            "answer": answer,
        })
        last_end = match.end()

    if not blocks:
        for match in LEGACY_BLOCK_PATTERN.finditer(markdown):
            question = match.group("question").strip()
            answer = match.group("answer").strip()
            blocks.append({
                "context": "",
                "question": question,
                "answer": answer,
            })

    if not blocks and markdown.strip():
        blocks.append({
            "context": "",
            "question": markdown.strip(),
            "answer": "",
        })

    return blocks


def is_quiz_item_valid(item: QuizItem) -> bool:
    """
    Check if quiz item is valid (complete)

    Args:
        item: Quiz item to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> item = QuizItem(qtype="MCQ", stem="Question?", options=..., answer="A")
        >>> is_quiz_item_valid(item)
        True
    """
    return item.is_valid()


def filter_valid_items(items: list[QuizItem]) -> list[QuizItem]:
    """
    Filter out invalid quiz items

    Args:
        items: List of quiz items

    Returns:
        List of valid items only

    Example:
        >>> items = [valid_item, invalid_item, valid_item2]
        >>> filter_valid_items(items)
        [valid_item, valid_item2]
    """
    return [item for item in items if item.is_valid()]


def infer_titles_from_markdown(markdown: str) -> tuple[str, str]:
    """
    Infer titles from Markdown content

    Args:
        markdown: Markdown text

    Returns:
        (title_main, title_sub)

    Example:
        >>> md = "# Concept Clip:\\nAnxiety"
        >>> infer_titles_from_markdown(md)
        ('Concept Clip', 'Anxiety')
    """
    lines = [line.strip() for line in markdown.splitlines()]
    main = ""
    sub = ""

    for idx, line in enumerate(lines):
        if not line:
            continue
        if not line.startswith("#"):
            continue

        # Only handle level-1 headings (# ...)
        if not line.startswith("# "):
            continue

        content = line.lstrip("#").strip()
        if not content:
            continue

        # Normalise colon variants
        normalized = content.replace("：", ":")
        if ":" in normalized:
            left, right = normalized.split(":", 1)
            left = left.strip()
            right = right.strip()
            if left:
                main = left
            else:
                main = normalized.rstrip(":").strip()
            if right:
                sub = right
        else:
            main = normalized.rstrip(":").strip()

        if not sub:
            # Look ahead for the next non-empty line that isn't a heading
            for follow_line in lines[idx + 1:]:
                if not follow_line:
                    continue
                if follow_line.startswith("#"):
                    break
                sub = follow_line.strip()
                break

        if main:
            return main, sub

    # 尝试从题目前的自由文本中获取标题（兼容无 # 标题的旧数据）
    preface: list[str] = []
    saw_context = False
    for raw_line in markdown.splitlines():
        stripped_right = raw_line.rstrip()
        stripped = stripped_right.strip()
        upper = stripped.upper()
        if upper.startswith("```QUESTION") or upper.startswith("```ANSWER"):
            break
        if NUMBER_HEADING.match(stripped):
            break
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
            stripped_right = stripped
            if not stripped:
                continue
        saw_context = True
        preface.append(stripped_right if stripped_right else stripped)

    if saw_context and preface:
        cleaned = [line.strip() for line in preface if line.strip()]
        if cleaned:
            first = cleaned[0]
            rest = cleaned[1:]
            normalized = first.replace(":", "：")
            if "：" in normalized:
                left, right = normalized.split("：", 1)
                left = left.strip()
                right = right.strip()
                if left:
                    main = left
                if right:
                    sub = right
                elif rest:
                    sub = rest[0]
            else:
                main = first.strip()
                if rest:
                    sub = rest[0]
            if main:
                return main, sub

    return "", ""


def infer_question_seed(value: str | Path) -> int:
    """
    根据文件名或路径推断题号种子（用于计算题代码 L000xxx）。

    规则：提取路径最后一段中的数字，返回其整数值；若包含多组数字，使用最后一组。
    """
    if isinstance(value, Path):
        stem = value.stem
    else:
        stem = Path(value).stem

    matches = re.findall(r"\d+", stem)
    if not matches:
        return 0
    try:
        return int(matches[-1])
    except ValueError:
        return 0


def infer_titles_from_filename(path: Path) -> tuple[str, str]:
    """
    Infer titles from filename

    Args:
        path: File path

    Returns:
        (title_main, title_sub)

    Example:
        >>> infer_titles_from_filename(Path("Chapter 3 Quiz- Mental Disorders.md"))
        ('Chapter 3 Quiz', 'Mental Disorders')
    """
    name = path.stem  # Without extension

    # Common pattern: "... Quiz- Subtitle"
    if "Quiz" in name:
        left, _, right = name.partition("Quiz")
        main = (left + "Quiz").strip()
        # Check for '-' leading subtitle
        if "-" in right:
            _, _, sub = right.partition("-")
            sub = sub.strip()
        else:
            sub = right.strip().lstrip(":：-").strip()
        if main:
            return main, sub

    # Fallback
    return name.strip(), ""


def detect_quiz_type(item: QuizItem) -> str:
    """
    Detect quiz type (for validation)

    Args:
        item: Quiz item

    Returns:
        Quiz type string

    Example:
        >>> detect_quiz_type(mcq_item)
        'MCQ'
    """
    return item.qtype


def count_questions_by_type(items: list[QuizItem]) -> dict[str, int]:
    """
    Count questions by type

    Args:
        items: List of quiz items

    Returns:
        Dictionary of type -> count

    Example:
        >>> count_questions_by_type(items)
        {'MCQ': 10, 'CLOZE': 3, 'ORDER': 2}
    """
    counts: dict[str, int] = {}
    for item in items:
        qtype = item.qtype
        counts[qtype] = counts.get(qtype, 0) + 1
    return counts


# ============================================================
# Usage examples
# ============================================================
if __name__ == "__main__":
    from .models import QuizItem, QuizOptions

    # 1. Validate quiz item
    valid_item = QuizItem(
        qtype="MCQ",
        stem="What is 2+2?",
        options=QuizOptions(A="3", B="4", C="5", D="6"),
        answer="B"
    )
    print(f"Valid: {is_quiz_item_valid(valid_item)}")

    invalid_item = QuizItem(
        qtype="MCQ",
        stem="Incomplete question",
        # Missing options and answer
    )
    print(f"Invalid: {is_quiz_item_valid(invalid_item)}")

    # 2. Filter valid items
    items = [valid_item, invalid_item]
    valid_only = filter_valid_items(items)
    print(f"\nFiltered: {len(valid_only)} valid items out of {len(items)}")

    # 3. Infer titles
    titles = infer_titles_from_filename(
        Path("Chapter 3 Quiz- Mental Disorders.md")
    )
    print(f"\nTitles: {titles}")

    # 4. Count by type
    counts = count_questions_by_type([valid_item, valid_item, invalid_item])
    print(f"\nCounts: {counts}")
