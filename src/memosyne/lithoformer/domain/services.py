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
from pathlib import Path
from .models import QuizItem


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

    return "", ""


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
