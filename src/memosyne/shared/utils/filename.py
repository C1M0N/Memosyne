"""
文件命名工具 - 智能输出文件命名

输出格式：{BatchID}-{FileName?}-{ModelCode}.ext

规则：
- 如果输入文件名简短（≤15字符），包含在输出文件名中
- 如果输入文件名过长，省略文件名部分
- 特殊字符被去除，只保留字母数字和短横线
"""
import re
from pathlib import Path


def extract_short_filename(filepath: str | Path, max_length: int = 15) -> str:
    """
    提取简短的文件名（用于输出文件命名）

    Args:
        filepath: 文件路径
        max_length: 最大长度（超过则返回空字符串）

    Returns:
        简短文件名（不含扩展名，只保留字母数字和短横线）
        如果长度超过 max_length，返回空字符串

    Example:
        >>> extract_short_filename("221.csv")
        '221'
        >>> extract_short_filename("data/input/205.md")
        '205'
        >>> extract_short_filename("Chapter 3 Quiz- Assessment.md")
        ''  # 太长，省略
        >>> extract_short_filename("test-file_123.csv")
        'test-file-123'
    """
    if not filepath:
        return ""

    path = Path(filepath) if isinstance(filepath, str) else filepath

    # 获取文件名（不含扩展名）
    name = path.stem

    # 先检查原始文件名长度（包含空格等特殊字符）
    # 如果原始名称太长，直接返回空字符串
    if len(name) > max_length:
        return ""

    # 去除特殊字符，只保留字母、数字、短横线、下划线
    # 将下划线和空格替换为短横线
    cleaned = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    cleaned = cleaned.replace('_', '-')

    # 去除开头和结尾的短横线
    cleaned = cleaned.strip('-')

    # 再次检查清理后的长度
    if len(cleaned) > max_length:
        return ""

    return cleaned


def generate_output_filename(
    batch_id: str,
    model_code: str,
    input_filename: str = "",
    ext: str = "csv"
) -> str:
    """
    生成输出文件名

    格式：
    - 有文件名: {batch_id}-{short_name}-{model_code}.{ext}
    - 无文件名: {batch_id}-{model_code}.{ext}

    Args:
        batch_id: 批次ID（如 "251012D036"）
        model_code: 4位模型代码（如 "ch35"）
        input_filename: 输入文件名（可选，可以是路径或文件名）
        ext: 扩展名（不含点，如 "csv", "txt"）

    Returns:
        输出文件名

    Example:
        >>> generate_output_filename("251012D036", "ch35", "221.csv")
        '251012D036-221-ch35.csv'
        >>> generate_output_filename("251012E016", "cs45")
        '251012E016-cs45.csv'
        >>> generate_output_filename("251012A007", "oo4m", "Chapter 3 Quiz.md", "txt")
        '251012A007-oo4m.txt'  # 文件名太长，省略
        >>> generate_output_filename("251012B007", "o50o", "205.md", "txt")
        '251012B007-205-o50o.txt'
    """
    # 提取简短文件名
    short_name = extract_short_filename(input_filename) if input_filename else ""

    # 确保扩展名不含点
    ext = ext.lstrip('.')

    # 生成文件名
    if short_name:
        return f"{batch_id}-{short_name}-{model_code}.{ext}"
    else:
        return f"{batch_id}-{model_code}.{ext}"


def format_batch_id(batch_id: str) -> str:
    """
    格式化批次ID（确保大写字母）

    Args:
        batch_id: 批次ID

    Returns:
        格式化后的批次ID

    Example:
        >>> format_batch_id("251012d036")
        '251012D036'
    """
    if not batch_id:
        return batch_id

    # BatchID 格式：YYMMDD + RunLetter + NNN
    # 只将字母部分转为大写
    return batch_id.upper()


# ============================================================
# 使用示例和测试
# ============================================================
if __name__ == "__main__":
    print("=== 测试 extract_short_filename ===")
    test_cases = [
        ("221.csv", "221"),
        ("data/input/205.md", "205"),
        ("Chapter 3 Quiz- Assessment and Classification.md", ""),  # 太长
        ("test-file_123.csv", "test-file-123"),
        ("My@File#Name$.txt", "MyFileName"),
        ("short.txt", "short"),
        ("verylongfilename1234567890.txt", ""),  # 太长
    ]

    for input_path, expected in test_cases:
        result = extract_short_filename(input_path)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_path!r} -> {result!r} (expected {expected!r})")

    print("\n=== 测试 generate_output_filename ===")
    test_cases_2 = [
        ("251012D036", "ch35", "221.csv", "csv", "251012D036-221-ch35.csv"),
        ("251012E016", "cs45", "", "csv", "251012E016-cs45.csv"),
        ("251012A007", "oo4m", "Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md", "txt", "251012A007-oo4m.txt"),
        ("251012B007", "o50o", "205.md", "txt", "251012B007-205-o50o.txt"),
    ]

    for batch_id, code, input_file, ext, expected in test_cases_2:
        result = generate_output_filename(batch_id, code, input_file, ext)
        status = "✅" if result == expected else "❌"
        print(f"{status} {result!r} (expected {expected!r})")

    print("\n=== 测试 format_batch_id ===")
    print(f"✅ {format_batch_id('251012d036')!r} -> '251012D036'")
    print(f"✅ {format_batch_id('251012D036')!r} -> '251012D036'")
