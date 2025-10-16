"""
Memosyne API - 编程接口

提供简单的函数调用接口，用于在其他程序中使用 Reanimator 和 Lithoformer 功能

Example:
    >>> from memosyne.api import reanimate, lithoform
    >>>
    >>> # 处理术语 (Reanimator)
    >>> results = reanimate(
    ...     input_csv="data/input/reanimator/221.csv",
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

# Shared 层导入（DDD: Shared Kernel / Infrastructure）
from .shared.config import get_settings
from .shared.infrastructure.llm import OpenAIProvider, AnthropicProvider
from .shared.utils import (
    BatchIDGenerator,
    unique_path,
    get_code_from_model,
    generate_output_filename,
)

# 子域导入（DDD: Bounded Contexts）
from .reanimator.application import ProcessTermsUseCase
from .reanimator.infrastructure import (
    ReanimatorLLMAdapter,
    CSVTermAdapter,
    TermListAdapter,
)
from .lithoformer.application import ParseQuizUseCase
from .lithoformer.infrastructure import (
    LithoformerLLMAdapter,
    FileAdapter,
    FormatterAdapter,
)
from .lithoformer.domain.services import (
    infer_titles_from_markdown,
    infer_titles_from_filename,
    infer_question_seed,
)


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
    处理术语列表（Reanimator Pipeline - 术语处理）

    Args:
        input_csv: 输入 CSV 文件路径（包含 word, zh_def 列）
        start_memo_index: 起始 Memo 编号（如 221 表示从 M000222 开始）
        output_csv: 输出 CSV 文件路径（默认自动生成到 data/output/reanimator/）
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
        >>> result = reanimate(
        ...     input_csv="data/input/reanimator/221.csv",
        ...     start_memo_index=221,
        ...     model="gpt-4o-mini",
        ...     batch_note="测试批次"
        ... )
        >>> print(f"成功处理 {result['processed_count']} 个术语")
        >>> print(f"输出文件: {result['output_path']}")
    """
    settings = get_settings()
    settings.ensure_dirs()

    # 1. 解析输入路径
    input_path = Path(input_csv)
    if not input_path.is_absolute():
        input_path = settings.reanimator_input_dir / input_path
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 2. 读取输入术语（使用新的 Infrastructure Adapter）
    csv_adapter = CSVTermAdapter.create()
    term_inputs = csv_adapter.read_input(input_path)
    if not term_inputs:
        raise ValueError(f"输入文件为空或格式错误: {input_path}")

    # 3. 生成批次 ID
    batch_gen = BatchIDGenerator(
        output_dir=settings.reanimator_output_dir,
        timezone=settings.batch_timezone
    )
    batch_id = batch_gen.generate(term_count=len(term_inputs))

    # 4. 创建 LLM Provider
    if provider == "openai":
        llm_provider = OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置")
        llm_provider = AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")

    # 5. 创建 Infrastructure Adapters（依赖注入）
    llm_adapter = ReanimatorLLMAdapter.from_provider(llm_provider)
    term_list_adapter = TermListAdapter.from_settings(settings)

    # 6. 创建 Use Case（Application 层）
    use_case = ProcessTermsUseCase(
        llm=llm_adapter,
        term_list=term_list_adapter,
        start_memo_index=start_memo_index,
        batch_id=batch_id,
        batch_note=batch_note,
    )

    # 7. 执行 Use Case
    process_result = use_case.execute(term_inputs, show_progress=show_progress)

    # 8. 确定输出路径（使用智能命名）
    if output_csv is None:
        # 获取模型代码
        try:
            model_code = get_code_from_model(model)
        except ValueError:
            model_code = "????"  # 未知模型

        # 生成输出文件名：{BatchID}-{FileName}-{ModelCode}.csv
        output_filename = generate_output_filename(
            batch_id=batch_id,
            model_code=model_code,
            input_filename=str(input_path),
            ext="csv"
        )
        output_path = unique_path(settings.reanimator_output_dir / output_filename)
    else:
        output_path = Path(output_csv)
        if not output_path.is_absolute():
            output_path = settings.reanimator_output_dir / output_path

    # 9. 写出结果（使用 Infrastructure Adapter）
    csv_adapter.write_output(output_path, process_result.items)

    return {
        "success": True,
        "output_path": str(output_path),
        "batch_id": batch_id,
        "processed_count": process_result.success_count,
        "total_count": process_result.total_count,
        "results": process_result.items,
        "token_usage": {
            "prompt_tokens": process_result.token_usage.prompt_tokens,
            "completion_tokens": process_result.token_usage.completion_tokens,
            "total_tokens": process_result.token_usage.total_tokens,
        },
    }


def lithoform(
    input_md: str | Path,
    output_txt: str | Path | None = None,
    model: str = "gpt-4o-mini",
    provider: Literal["openai", "anthropic"] = "openai",
    title_main: str | None = None,
    title_sub: str | None = None,
    temperature: float | None = None,
    show_progress: bool = True,
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
        show_progress: 是否显示进度条

    Returns:
        字典，包含：
        - success: bool - 是否成功
        - output_path: str - 输出文件路径
        - item_count: int - 解析的题目数量
        - title_main: str - 主标题
        - title_sub: str - 副标题
        - token_usage: dict - Token 使用统计

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

    # 2. 读取 Markdown（使用新的 Infrastructure Adapter）
    file_adapter = FileAdapter.create()
    md_text = file_adapter.read_markdown(input_path)

    # 3. 推断标题（如果未提供）
    if title_main is None or title_sub is None:
        md_main, md_sub = infer_titles_from_markdown(md_text)
        if md_main and title_main is None:
            title_main = md_main
        if md_sub and title_sub is None:
            title_sub = md_sub

        if title_main is None or title_sub is None:
            inferred_main, inferred_sub = infer_titles_from_filename(input_path)
            title_main = title_main or inferred_main
            title_sub = title_sub or inferred_sub

    # 4. 创建 LLM Provider
    if provider == "openai":
        llm_provider = OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置")
        llm_provider = AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature if temperature is not None else settings.default_temperature
        )
    else:
        raise ValueError(f"不支持的 provider: {provider}")

    # 5. 创建 Infrastructure Adapters（依赖注入）
    llm_adapter = LithoformerLLMAdapter.from_provider(llm_provider)

    # 6. 创建 Use Case（Application 层）
    use_case = ParseQuizUseCase(llm=llm_adapter)

    # 7. 执行 Use Case
    process_result = use_case.execute(md_text, show_progress=show_progress)

    # 8. 生成 BatchID（基于题目数量）
    batch_gen = BatchIDGenerator(
        output_dir=settings.lithoformer_output_dir,
        timezone=settings.batch_timezone
    )
    batch_id = batch_gen.generate(term_count=process_result.success_count)

    # 9. 格式化输出（使用 Infrastructure Adapter）
    formatter_adapter = FormatterAdapter.create()
    out_text = formatter_adapter.format(
        process_result.items,
        title_main,
        title_sub,
        batch_code=batch_id,
        question_start=infer_question_seed(input_path),
    )

    # 10. 确定输出路径（使用智能命名）
    if output_txt is None:
        # 获取模型代码
        try:
            model_code = get_code_from_model(model)
        except ValueError:
            model_code = "????"  # 未知模型

        # 生成输出文件名：{BatchID}-{FileName}-{ModelCode}.txt
        output_filename = generate_output_filename(
            batch_id=batch_id,
            model_code=model_code,
            input_filename=str(input_path),
            ext="txt"
        )
        output_path = unique_path(settings.lithoformer_output_dir / output_filename)
    else:
        output_path = Path(output_txt)
        if not output_path.is_absolute():
            output_path = settings.lithoformer_output_dir / output_path

    # 11. 写出结果（使用 Infrastructure Adapter）
    file_adapter.write_text(output_path, out_text)

    return {
        "success": True,
        "output_path": str(output_path),
        "batch_id": batch_id,
        "item_count": process_result.success_count,
        "total_count": process_result.total_count,
        "title_main": title_main,
        "title_sub": title_sub,
        "token_usage": {
            "prompt_tokens": process_result.token_usage.prompt_tokens,
            "completion_tokens": process_result.token_usage.completion_tokens,
            "total_tokens": process_result.token_usage.total_tokens,
        },
    }



__all__ = [
    "reanimate",
    "lithoform",
]
