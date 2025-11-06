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


def is_quiz_item_valid(item: QuizItem, feature_config: "FeatureConfig | None" = None) -> bool:
    """
    Check if quiz item is valid (complete)

    Args:
        item: Quiz item to validate
        feature_config: 功能配置，用于决定是否验证translation/analysis字段

    Returns:
        True if valid, False otherwise

    Example:
        >>> item = QuizItem(qtype="MCQ", stem="Question?", options=..., answer="A")
        >>> is_quiz_item_valid(item)
        True
    """
    return item.is_valid(feature_config)


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
    从Markdown内容中提取标题

    提取规则：
    - 标题 = 从文件开头到第一个题目（## 数字）之前的所有内容
    - title_main: 所有以"# "开头的行（去掉"# "），用换行符连接
    - title_sub: 所有不以"# "开头的非空行，用换行符连接

    Args:
        markdown: Markdown文本

    Returns:
        (title_main, title_sub)

    Example:
        >>> md = "# Test Bank: Chapter 4\\nThe Chemistry of Behavior\\n\\n## 21\\n..."
        >>> infer_titles_from_markdown(md)
        ('Test Bank: Chapter 4', 'The Chemistry of Behavior')
    """
    lines = markdown.splitlines()
    title_main_lines: list[str] = []
    title_sub_lines: list[str] = []

    # 提取从开头到第一个题目（## 数字）之前的所有内容
    for line in lines:
        stripped = line.strip()

        # 遇到题目标记，停止
        if NUMBER_HEADING.match(stripped):
            break
        if stripped.upper().startswith("```QUESTION") or stripped.upper().startswith("```ANSWER"):
            break

        # 空行跳过
        if not stripped:
            continue

        # 以 "# " 开头的行 → 加入 title_main
        if stripped.startswith("# "):
            # 去掉 "# " 前缀
            content = stripped[2:].strip()
            if content:
                title_main_lines.append(content)
        else:
            # 非 "# " 开头的行 → 加入 title_sub
            title_sub_lines.append(stripped)

    # 用换行符连接
    title_main = "\n".join(title_main_lines)
    title_sub = "\n".join(title_sub_lines)

    return title_main, title_sub


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
        {'MCQ': 10, 'CLOZE': 3}
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
