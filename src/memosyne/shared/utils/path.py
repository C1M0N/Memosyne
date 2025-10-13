"""
路径工具模块 - 消除重复代码

重构收益：
- ✅ 单一实现：两个管道共享同一套工具
- ✅ 可测试性：可注入自定义根路径
- ✅ 类型安全：完整的类型提示
"""
from pathlib import Path
from typing import Callable


def find_project_root(
    marker: str = "data",
    start_path: Path | None = None,
    max_depth: int = 5
) -> Path:
    """
    向上查找项目根目录（通过标志目录识别）

    Args:
        marker: 标志目录名（如 "data", ".git"）
        start_path: 起始路径（默认为当前文件所在目录）
        max_depth: 最大向上查找层数

    Returns:
        项目根目录路径

    Raises:
        FileNotFoundError: 未找到标志目录

    Example:
        >>> root = find_project_root("data")
        >>> assert (root / "data").exists()
    """
    if start_path is None:
        # 调用者的文件路径（使用 __file__ 需要传入）
        start_path = Path.cwd()

    current = Path(start_path).resolve()

    for _ in range(max_depth):
        if (current / marker).is_dir():
            return current
        if current.parent == current:  # 已到根目录
            break
        current = current.parent

    raise FileNotFoundError(
        f"未找到包含 '{marker}' 目录的项目根（从 {start_path} 向上查找 {max_depth} 层）"
    )


def unique_path(path: Path, suffix_format: str = "_{n}") -> Path:
    """
    生成唯一文件路径（防覆盖）

    如果文件已存在，自动添加后缀 _2, _3, ...

    Args:
        path: 原始路径
        suffix_format: 后缀格式（{n} 会被替换为数字）

    Returns:
        唯一路径

    Example:
        >>> p = Path("/tmp/test.txt")
        >>> p.touch()  # 创建文件
        >>> unique = unique_path(p)
        >>> assert unique == Path("/tmp/test_2.txt")
    """
    if not path.exists():
        return path

    stem = path.stem
    ext = path.suffix
    parent = path.parent
    counter = 2

    while True:
        suffix = suffix_format.format(n=counter)
        candidate = parent / f"{stem}{suffix}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_dir(path: Path, parents: bool = True) -> Path:
    """
    确保目录存在（不存在则创建）

    Args:
        path: 目录路径
        parents: 是否创建父目录

    Returns:
        目录路径（便于链式调用）

    Example:
        >>> data_dir = ensure_dir(Path("data/output/memo"))
        >>> assert data_dir.exists()
    """
    path.mkdir(parents=parents, exist_ok=True)
    return path


def resolve_input_path(
    user_input: str,
    default_dir: Path,
    default_filename: str | None = None,
    validator: Callable[[Path], bool] | None = None
) -> Path:
    """
    智能解析输入路径（支持多种格式）

    Args:
        user_input: 用户输入（可为空、相对路径、绝对路径）
        default_dir: 默认目录
        default_filename: 默认文件名（user_input 为空时使用）
        validator: 路径验证函数（返回 False 时抛出异常）

    Returns:
        解析后的绝对路径

    Raises:
        ValueError: 路径验证失败

    Example:
        >>> # 用户输入空 -> 使用默认
        >>> p = resolve_input_path("", Path("data/input"), "default.csv")
        >>> assert p == Path("data/input/default.csv")
        >>>
        >>> # 用户输入文件名 -> 拼接到默认目录
        >>> p = resolve_input_path("my.csv", Path("data/input"))
        >>> assert p == Path("data/input/my.csv")
        >>>
        >>> # 用户输入绝对路径 -> 直接使用
        >>> p = resolve_input_path("/tmp/test.csv", Path("data/input"))
        >>> assert p == Path("/tmp/test.csv")
    """
    s = user_input.strip()

    # 1. 空输入 -> 使用默认
    if not s:
        if default_filename is None:
            raise ValueError("未提供输入路径且没有默认文件名")
        path = default_dir / default_filename
    else:
        path = Path(s).expanduser()

        if not path.is_absolute():
            # 推断项目根目录（寻找包含 data/ 或 src/ 的祖先）
            project_root = default_dir
            for candidate in [default_dir] + list(default_dir.parents):
                if (candidate / "data").is_dir() or (candidate / "src").is_dir():
                    project_root = candidate
                    break

            parts = path.parts

            if len(parts) == 1:
                path = default_dir / path
            elif parts and parts[0] in (".", ""):
                path = default_dir / Path(*parts[1:])
            elif parts and parts[0] == "..":
                path = (default_dir / path).resolve()
            else:
                path = project_root / path

    # 3. 验证（如需要）
    if validator and not validator(path):
        raise ValueError(f"路径验证失败：{path}")

    return path.resolve()


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 1. 查找项目根
    try:
        root = find_project_root("data")
        print(f"项目根目录：{root}")
    except FileNotFoundError as e:
        print(e)

    # 2. 生成唯一路径
    test_path = Path("/tmp/test.txt")
    test_path.touch()
    unique = unique_path(test_path)
    print(f"唯一路径：{unique}")

    # 3. 确保目录存在
    data_dir = ensure_dir(Path("data/test"))
    print(f"目录已创建：{data_dir}")

    # 4. 解析输入路径
    p1 = resolve_input_path("", Path("data/input"), "default.csv")
    print(f"解析路径1：{p1}")

    p2 = resolve_input_path("my.csv", Path("data/input"))
    print(f"解析路径2：{p2}")
