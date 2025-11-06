#!/usr/bin/env python3
"""
Lithoformer CLI - Quiz Parsing Tool (Refactored)

Usage:
    python -m memosyne.lithoformer.cli.main

    Or use the convenience script:
    ./scripts/LfC.sh
"""
from pathlib import Path
import argparse

from ...shared.config import get_settings
from ...shared.infrastructure.app_config import SQLiteAppConfigService
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
from ..application.factory import UseCaseFactory
from ..application.use_cases import ConcurrentParseQuizUseCase
from ..infrastructure import LithoformerLLMAdapter, FileAdapter, FormatterAdapter
from ..domain.services import (
    infer_titles_from_filename,
    infer_titles_from_markdown,
    infer_question_seed,
)


def main():
    """CLI main function"""
    print("=== Lithoformer | Quiz Parsing Tool (Refactored v3.1) ===")

    parser = argparse.ArgumentParser(description="Lithoformer CLI")
    parser.add_argument("-m", "--model", dest="model", help="Model id or 4-char code; '4' for default OpenAI; 'claude' for default Anthropic")
    parser.add_argument("-i", "--input", dest="input", help="Input Markdown file path")
    parser.add_argument("-o", "--output", dest="output", help="Output directory path")
    parser.add_argument("--concurrent", dest="concurrent", action="store_true", help="Enable concurrent mode")
    parser.add_argument("--no-concurrent", dest="concurrent", action="store_false", help="Disable concurrent mode")
    parser.set_defaults(concurrent=None)
    parser.add_argument("--max-concurrent", dest="max_concurrent", type=int, help="Max concurrency (1-100)")
    parser.add_argument("--max-retries", dest="max_retries", type=int, help="Max retries (0-10)")
    parser.add_argument("--save-default-dirs", dest="save_defaults", action="store_true", help="Save provided input/output dirs into config.db")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_dirs()
    appcfg = SQLiteAppConfigService(settings.db_dir / "config.db")

    # Resolve model input
    if args.model:
        model_input = args.model
    else:
        model_input = ask("Engine (4-digit code like o4oo/cs45):")

    # Resolve input path string
    input_raw = args.input if args.input else ask("Input Markdown file (default misc/input/lithoformer/...):", required=False)

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
    # Default input: prefer AppConfigService path; fallback to sample
    paths = appcfg.get_paths()
    default_input_root = paths.input_dir if paths and paths.input_dir else settings.lithoformer_input_dir
    default_input = default_input_root / "Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md"
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
        print("ℹ️  当前使用的是 misc 中的示例文件（只读）。如需解析自己的测验，请在 TUI 的配置选项卡中修改默认路径或在此输入自定义路径。")

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

    # Build FeatureConfig from AppConfigService, apply CLI overrides
    flags = appcfg.get_feature_flags()
    tuning = appcfg.get_runtime_tuning()
    from ..domain.models import FeatureConfig
    feature_config = FeatureConfig(
        enable_translation=flags.enable_translation,
        enable_parsing=flags.enable_parsing,
        enable_concurrent=flags.enable_concurrent,
        max_concurrent=tuning.max_concurrent,
        max_retries=tuning.max_retries,
    )

    # CLI overrides
    if args.concurrent is not None:
        feature_config.enable_concurrent = bool(args.concurrent)
    if args.max_concurrent is not None:
        feature_config.max_concurrent = max(1, min(100, int(args.max_concurrent)))
    if args.max_retries is not None:
        feature_config.max_retries = max(0, min(10, int(args.max_retries)))

    # Create stats repository
    from ...shared.infrastructure.config_db import get_stats_repository
    stats_repo = get_stats_repository(settings.db_dir / "stat.db")

    # Use factory to assemble
    factory = UseCaseFactory(settings)
    use_case, model_identifier = factory.build_use_case(
        provider=provider_type,
        model_id=model_id,
        feature_config=feature_config,
        stats_repo=stats_repo,
        output_filename="",
    )

    # Execute
    try:
        if feature_config.enable_concurrent:
            # Concurrent: stream events
            print(f"并发解析中（{feature_config.max_concurrent} 线程，重试 {feature_config.max_retries}）...")
            running_total = 0
            items = []
            async def _run_async():
                nonlocal running_total, items
                uc = ConcurrentParseQuizUseCase(
                    llm=use_case.llm,
                    feature_config=feature_config,
                    stats_repo=stats_repo,
                    model_identifier=model_identifier,
                    output_filename="",
                )
                async for event in uc.stream_async(markdown):
                    if event.status == "success" and event.item:
                        items.append(event.item)
                    running_total += event.tokens.total_tokens
                    print(f"完成 {event.index}/{event.total} - tokens累计 {running_total}")
                return items, running_total

            import asyncio
            items, total_tokens = asyncio.run(_run_async())
            from ...core.models import TokenUsage
            result_items = items
            token_usage = TokenUsage(total_tokens=total_tokens)
        else:
            result = use_case.execute(markdown, show_progress=True)
            result_items = result.items
            token_usage = result.token_usage
            print(f"✅ Parsed {result.success_count} questions")
            print(f"   Token usage: {result.token_usage}")
    except Exception as e:
        import traceback
        print(f"Parsing failed: {e}")
        traceback.print_exc()
        return

    # Resolve output directory (avoid read-only samples)
    op_paths = appcfg.get_paths()
    if args.output:
        output_dir = Path(args.output).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir
    else:
        output_dir = op_paths.output_dir if op_paths and op_paths.output_dir else settings.lithoformer_output_dir
    if settings.is_sample_path(output_dir):
        print("⚠️  默认输出目录位于 misc 示例资源中（只读）。请指定实际的输出目录。")
        custom_dir = ask("Output directory (absolute or relative path):", required=True)
        output_dir = Path(custom_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    # Optionally persist defaults
    if args.save_defaults:
        try:
            appcfg.update_paths(input_dir=str(default_input_root), output_dir=str(output_dir))
            print("[Config] 默认路径已保存到 config.db")
        except Exception as e:
            print(f"[Config] 保存默认路径失败: {e}")
    batch_gen = BatchIDGenerator(output_dir=output_dir, timezone=settings.batch_timezone)
    batch_id = batch_gen.generate(term_count=result.success_count)

    # Generate output filename
    output_filename = generate_output_filename(batch_id=batch_id, model_code=model_code, input_filename=str(input_path), ext="txt")
    output_path = unique_path((output_dir / output_filename).resolve())

    # Format output
    formatter_adapter = FormatterAdapter.create()
    output_text = formatter_adapter.format(
        result_items,
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
