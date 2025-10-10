"""
Memosyne API - 编程接口

提供简单的函数调用接口，用于在其他程序中使用 Reanimater 和 Lithoformer 功能

Example:
    >>> from memosyne.api import reanimate, lithoform
    >>>
    >>> # 处理术语 (Reanimater)
    >>> results = reanimate(
    ...     input_csv="data/input/reanimater/221.csv",
    ...     start_memo_index=221,
    ...     model="gpt-4o-mini"
    ... )
    >>>
    >>> # 解析 Quiz (Lithoformer)
    >>> output_path = lithoform(
    ...     input_md="data/input/lithoformer/quiz.md",
    ...     model="gpt-4o-mini"
    ... )
"""
from pathlib import Path
from typing import Literal

from .config import get_settings
from .providers import OpenAIProvider, AnthropicProvider
from .repositories import CSVTermRepository, TermListRepo
from .services import Reanimater, Lithoformer
from .utils import BatchIDGenerator, QuizFormatter, unique_path
from .models import TermOutput


def reanimate(
    input_csv: str | Path,
    start_memo_index: int,
    output_csv: str | Path | None = None,
    model: str = "gpt-4o-mini",
    provider: Literal["openai", "anthropic"] = "openai",
    batch_note: str = "",
    temperature: float | None = None,
    show_progress: bool = True,
) -> dict:
    """
    处理术语列表（Reanimater Pipeline - 术语处理）

    Args:
        input_csv: 输入 CSV 文件路径（包含 word, zh_def 列）
        start_memo_index: 起始 Memo 编号（如 221 表示从 M000222 开始）
        output_csv: 输出 CSV 文件路径（默认自动生成到 data/output/reanimater/）
        model: 模型 ID（默认 gpt-4o-mini）
        provider: LLM 提供商（openai 或 anthropic）
        batch_note: 批次备注
        temperature: 温度参数（None 使用模型默认值）
        show_progress: 是否显示进度条

    Returns:
        字典，包含：
        - success: bool - 是否成功
        - output_path: str - 输出文件路径
        - batch_id: str - 批次 ID
        - processed_count: int - 处理的术语数量
        - results: list[TermOutput] - 处理结果列表

    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 参数错误
        LLMError: LLM 调用失败

    Example:
        >>> results = reanimate(
        ...     input_csv="data/input/reanimater/221.csv",
        ...     start_memo_index=221,
        ...     model="gpt-4o-mini",
        ...     batch_note="测试批次"
        ... )
        >>> print(f"成功处理 {results['processed_count']} 个术语")
        >>> print(f"输出文件: {results['output_path']}")
    """
    settings = get_settings()
    settings.ensure_dirs()

    # 1. 解析输入路径
    input_path = Path(input_csv)
    if not input_path.is_absolute():
        input_path = settings.reanimater_input_dir / input_path
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 2. 读取输入术语
    term_inputs = CSVTermRepository.read_input(input_path)
    if not term_inputs:
        raise ValueError(f"输入文件为空或格式错误: {input_path}")

    # 3. 加载术语表
    term_list_repo = TermListRepo()
    term_list_repo.load(settings.term_list_path)

    # 4. 生成批次 ID
    batch_gen = BatchIDGenerator(
        output_dir=settings.reanimater_output_dir,
        timezone=settings.batch_timezone
    )
    batch_id = batch_gen.generate(term_count=len(term_inputs))

    # 5. 创建 LLM Provider
    if provider == "openai":
        llm = OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置")
        llm = AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")

    # 6. 创建处理器
    processor = Reanimater(
        llm_provider=llm,
        term_list_mapping=term_list_repo.mapping,
        start_memo_index=start_memo_index,
        batch_id=batch_id,
        batch_note=batch_note
    )

    # 7. 处理术语
    results = processor.process(term_inputs, show_progress=show_progress)

    # 8. 确定输出路径
    if output_csv is None:
        output_path = settings.reanimater_output_dir / f"{batch_id}.csv"
    else:
        output_path = Path(output_csv)
        if not output_path.is_absolute():
            output_path = settings.reanimater_output_dir / output_path

    # 9. 写出结果
    CSVTermRepository.write_output(output_path, results)

    return {
        "success": True,
        "output_path": str(output_path),
        "batch_id": batch_id,
        "processed_count": len(results),
        "results": results,
    }


def lithoform(
    input_md: str | Path,
    output_txt: str | Path | None = None,
    model: str = "gpt-4o-mini",
    provider: Literal["openai", "anthropic"] = "openai",
    title_main: str | None = None,
    title_sub: str | None = None,
    temperature: float | None = None,
) -> dict:
    """
    解析 Quiz Markdown 文档（Lithoformer - Quiz 解析）

    Args:
        input_md: 输入 Markdown 文件路径
        output_txt: 输出 TXT 文件路径（默认自动生成到 data/output/lithoformer/）
        model: 模型 ID（默认 gpt-4o-mini）
        provider: LLM 提供商（openai 或 anthropic）
        title_main: 主标题（None 则自动从文件名推断）
        title_sub: 副标题（None 则自动从文件名推断）
        temperature: 温度参数（None 使用模型默认值）

    Returns:
        字典，包含：
        - success: bool - 是否成功
        - output_path: str - 输出文件路径
        - item_count: int - 解析的题目数量
        - title_main: str - 主标题
        - title_sub: str - 副标题

    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 参数错误
        LLMError: LLM 调用失败

    Example:
        >>> result = lithoform(
        ...     input_md="data/input/lithoformer/chapter3.md",
        ...     model="gpt-4o-mini"
        ... )
        >>> print(f"成功解析 {result['item_count']} 道题")
        >>> print(f"输出文件: {result['output_path']}")
    """
    settings = get_settings()
    settings.ensure_dirs()

    # 1. 解析输入路径
    input_path = Path(input_md)
    if not input_path.is_absolute():
        input_path = settings.lithoformer_input_dir / input_path
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 2. 读取 Markdown
    md_text = input_path.read_text(encoding="utf-8")

    # 3. 推断标题（如果未提供）
    if title_main is None or title_sub is None:
        inferred_main, inferred_sub = _infer_titles_from_filename(input_path)
        title_main = title_main or inferred_main
        title_sub = title_sub or inferred_sub

    # 4. 创建 LLM Provider
    if provider == "openai":
        llm = OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置")
        llm = AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")

    # 5. 解析 Quiz
    parser = Lithoformer(llm_provider=llm)
    items = parser.parse(md_text)

    # 6. 格式化输出
    formatter = QuizFormatter()
    out_text = formatter.format(items, title_main, title_sub)

    # 7. 确定输出路径
    if output_txt is None:
        output_path = settings.lithoformer_output_dir / "ShouldBe.txt"
        output_path = unique_path(output_path)
    else:
        output_path = Path(output_txt)
        if not output_path.is_absolute():
            output_path = settings.lithoformer_output_dir / output_path

    # 8. 写出结果
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(out_text, encoding="utf-8")

    return {
        "success": True,
        "output_path": str(output_path),
        "item_count": len(items),
        "title_main": title_main,
        "title_sub": title_sub,
    }


def _infer_titles_from_filename(path: Path) -> tuple[str, str]:
    """
    从文件名推断标题

    Example:
        'Chapter 3 Quiz- Assessment and Classification.md'
        -> ('Chapter 3 Quiz', 'Assessment and Classification')
    """
    name = path.stem  # 不含扩展名

    # 常见模式："... Quiz- Subtitle"
    if "Quiz" in name:
        left, _, right = name.partition("Quiz")
        main = (left + "Quiz").strip()
        if "-" in right:
            _, _, sub = right.partition("-")
            sub = sub.strip()
        else:
            sub = right.strip().lstrip(":：-").strip()
        if main:
            return main, sub

    # 兜底
    return name.strip(), ""


# ============================================================
# 便捷别名（保留旧名兼容）
# ============================================================
process_terms = reanimate  # 旧名
parse_quiz = lithoform     # 旧名
mms = reanimate           # 旧别名
exparser = lithoform      # 旧别名

__all__ = [
    "reanimate",
    "lithoform",
    "process_terms",  # 保留旧名兼容
    "parse_quiz",     # 保留旧名兼容
    "mms",           # 保留旧别名
    "exparser",      # 保留旧别名
]
