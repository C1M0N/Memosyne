#!/usr/bin/env python3
"""
Lithoformer CLI - Quiz Parsing Tool (Refactored)

Usage:
    python -m memosyne.lithoformer.cli.main

    Or use the convenience script:
    ./scripts/LfC.sh
"""
from pathlib import Path

from ...shared.config import get_settings
from ...shared.infrastructure.llm import OpenAIProvider, AnthropicProvider
from ...shared.utils import (
    BatchIDGenerator,
    resolve_model_input,
    get_provider_from_model,
    get_code_from_model,
    generate_output_filename,
    unique_path,
)
from ...shared.cli.prompts import ask
from ..application import ParseQuizUseCase
from ..infrastructure import LithoformerLLMAdapter, FileAdapter, FormatterAdapter
from ..domain.services import (
    infer_titles_from_filename,
    infer_titles_from_markdown,
    infer_question_seed,
)


def main():
    """CLI main function"""
    print("=== Lithoformer | Quiz Parsing Tool (Refactored v3.0) ===")

    settings = get_settings()
    settings.ensure_dirs()

    model_input = ask("Engine (4-digit code like o4oo/cs45):")
    input_raw = ask("Input Markdown file (default misc/input/lithoformer/...):", required=False)

    # Parse inputs
    try:
        s = model_input.strip().lower()
        if s == "4":
            model_id = settings.default_openai_model
            model_code = get_code_from_model(model_id)
            provider_type = "openai"
        elif s == "claude":
            model_id = settings.default_anthropic_model
            model_code = get_code_from_model(model_id)
            provider_type = "anthropic"
        else:
            model_id, model_code = resolve_model_input(s)
            provider_type = get_provider_from_model(model_id)
    except Exception as e:
        print(f"Model parsing failed: {e}")
        return

    # Resolve input path
    default_input = settings.lithoformer_input_dir / "Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md"
    input_value = input_raw.strip()
    if input_value:
        potential = Path(input_value)
        if not potential.is_absolute():
            potential = Path.cwd() / potential
        input_path = potential
    else:
        input_path = default_input

    if not input_path.exists():
        print("⚠️  未找到默认示例题库。请提供要解析的 Markdown 文件路径。")
        user_path = ask("Input Markdown file (absolute or relative path):", required=True)
        input_path = Path(user_path).expanduser()
        if not input_path.is_absolute():
            input_path = Path.cwd() / input_path

    if settings.is_sample_path(input_path):
        print("ℹ️  当前使用的是 misc 中的示例文件（只读）。如需解析自己的测验，请在 config/paths.json 中修改默认路径或在此输入自定义路径。")

    print(f"[Provider] {provider_type}")
    print(f"[Model   ] {model_id}")
    print(f"[Input   ] {input_path}")

    # Read input
    file_adapter = FileAdapter.create()
    try:
        markdown = file_adapter.read_markdown(input_path)
    except Exception as e:
        print(f"Failed to read input: {e}")
        return

    # Infer titles from markdown content first, fall back to filename
    title_main, title_sub = infer_titles_from_markdown(markdown)
    if not title_main:
        title_main, title_sub = infer_titles_from_filename(input_path)
    elif not title_sub:
        _, fallback_sub = infer_titles_from_filename(input_path)
        title_sub = fallback_sub
    print(f"[Title   ] {title_main} | {title_sub}")

    # Create LLM Provider
    if provider_type == "anthropic":
        if not settings.anthropic_api_key:
            print("Anthropic provider selected，但未配置 ANTHROPIC_API_KEY。请在 .env 中填写后重试。")
            return
        llm_provider = AnthropicProvider(model=model_id, api_key=settings.anthropic_api_key, temperature=settings.default_temperature)
    else:
        llm_provider = OpenAIProvider(model=model_id, api_key=settings.openai_api_key, temperature=settings.default_temperature)

    # Create adapters
    llm_adapter = LithoformerLLMAdapter.from_provider(llm_provider)

    # Create use case
    use_case = ParseQuizUseCase(llm=llm_adapter)

    # Execute
    try:
        result = use_case.execute(markdown, show_progress=True)
        print(f"✅ Parsed {result.success_count} questions")
        print(f"   Token usage: {result.token_usage}")
    except Exception as e:
        import traceback
        print(f"Parsing failed: {e}")
        traceback.print_exc()
        return

    # Resolve output directory (avoid read-only samples)
    output_dir = settings.lithoformer_output_dir
    if settings.is_sample_path(output_dir):
        print("⚠️  默认输出目录位于 misc 示例资源中（只读）。请指定实际的输出目录。")
        custom_dir = ask("Output directory (absolute or relative path):", required=True)
        output_dir = Path(custom_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_gen = BatchIDGenerator(output_dir=output_dir, timezone=settings.batch_timezone)
    batch_id = batch_gen.generate(term_count=result.success_count)

    # Generate output filename
    output_filename = generate_output_filename(batch_id=batch_id, model_code=model_code, input_filename=str(input_path), ext="txt")
    output_path = unique_path((output_dir / output_filename).resolve())

    # Format output
    formatter_adapter = FormatterAdapter.create()
    output_text = formatter_adapter.format(
        result.items,
        title_main,
        title_sub,
        batch_code=batch_id,
        question_start=infer_question_seed(input_path),
    )

    # Write output
    try:
        file_adapter.write_text(output_path, output_text)
        print(f"✅ Complete: {output_path}")
    except Exception as e:
        print(f"Failed to write output: {e}")


if __name__ == "__main__":
    main()
