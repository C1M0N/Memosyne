#!/usr/bin/env python3
"""
Reanimator CLI - Term Processing Tool (Refactored)

A thin adapter that orchestrates dependency injection.

Usage:
    python -m memosyne.reanimator.cli.main
    or
    python src/memosyne/reanimator/cli/main.py

Architecture:
- CLI layer: User interaction and dependency injection
- Application layer: Business orchestration (ProcessTermsUseCase)
- Domain layer: Pure business logic
- Infrastructure layer: Technical implementations (adapters)
"""
import sys
from pathlib import Path

# Support direct execution
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[3]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from ...config import get_settings
from ...providers import OpenAIProvider, AnthropicProvider
from ...utils import (
    BatchIDGenerator,
    resolve_model_input,
    get_provider_from_model,
    generate_output_filename,
    unique_path,
)
from ...cli.prompts import ask

# Import from Reanimator subdomain
from ..application import ProcessTermsUseCase
from ..infrastructure import (
    ReanimatorLLMAdapter,
    CSVTermAdapter,
    TermListAdapter,
)


def resolve_model_choice(user_input: str, settings) -> tuple[str, str, str, str]:
    """
    Parse model selection (supports 4-digit codes, shortcuts, full model names)

    Args:
        user_input: User input (4/5/claude/4-digit code/full model name)
        settings: Settings object

    Returns:
        (provider, model_id, model_code, model_display)
    """
    from ...utils import get_code_from_model

    s = user_input.strip().lower()

    # Legacy shortcuts (compatibility)
    if s == "4":
        model = settings.default_openai_model
        code = get_code_from_model(model)
        return "openai", model, code, "4oMini"
    elif s == "5":
        model = "gpt-5-mini"
        code = "o50m"
        return "openai", model, code, "5Mini"
    elif s == "claude":
        model = settings.default_anthropic_model
        code = get_code_from_model(model)
        return "anthropic", model, code, "Claude"

    # Try unified parsing (supports 4-digit code or full model name)
    try:
        model, code = resolve_model_input(s)
        provider = get_provider_from_model(model)
        display = code.upper()
        return provider, model, code, display
    except ValueError:
        # Fallback: try as full model name
        if "claude" in s:
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"
            return "anthropic", user_input, code, "Claude"
        else:
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"
            return "openai", user_input, code, user_input.replace("-", " ").title()


def resolve_input_and_memo(
    user_path: str,
    default_dir: Path
) -> tuple[Path, int]:
    """
    Parse input path and starting Memo

    Args:
        user_path: User input
        default_dir: Default input directory

    Returns:
        (input_path, start_memo_index)
    """
    from ...utils import resolve_input_path

    s = user_path.strip()

    # Pure number: data/input/{num}.csv, start Memo = num
    if s.isdigit():
        memo = int(s)
        path = default_dir / f"{s}.csv"
        return path, memo

    # Contains .csv or path separator: ask for start Memo
    if ".csv" in s or any(ch in s for ch in ("/", "\\")):
        path = resolve_input_path(s, default_dir)
        memo_str = ask("Starting Memo number (integer, e.g., 2700 for M002701):")
        try:
            memo = int(memo_str)
        except ValueError:
            raise ValueError("Starting Memo number must be an integer")
        return path, memo

    # Empty: use short.csv and ask for start Memo
    path = default_dir / "short.csv"
    memo_str = ask("Starting Memo number (integer, e.g., 2700 for M002701):")
    try:
        memo = int(memo_str)
    except ValueError:
        raise ValueError("Starting Memo number must be an integer")
    return path, memo


def main():
    """CLI main function (thin orchestration layer)"""
    print("=== Reanimator | Term Processing Tool (Refactored v3.0) ===")

    # 1. Load configuration
    try:
        settings = get_settings()
        settings.ensure_dirs()
    except Exception as e:
        print(f"Configuration loading failed: {e}")
        print("Please check .env file and API keys")
        return

    # 2. User input
    model_input = ask("Engine (4-digit code like o4oo/cs45, or shortcut 4/5/claude, or full model name):")
    path_input = ask(
        "Input CSV path (number={num}.csv; .csv/path=direct; empty=short.csv):",
        required=False
    )
    note_input = ask("Batch note (optional):", required=False)

    # 3. Parse inputs
    try:
        provider_type, model_id, model_code, model_display = resolve_model_choice(model_input, settings)
        input_path, start_memo = resolve_input_and_memo(path_input, settings.reanimator_input_dir)
    except Exception as e:
        print(f"Parsing failed: {e}")
        return

    print(f"[Provider] {provider_type}")
    print(f"[Model   ] {model_id} ({model_display})")
    print(f"[Code    ] {model_code}")
    print(f"[Input   ] {input_path}")
    print(f"[Start   ] Memo = {start_memo}")
    print(f"[TermList] {settings.term_list_path}")

    # 4. Read input terms (using Infrastructure adapter)
    try:
        csv_adapter = CSVTermAdapter.create()
        terms_input = csv_adapter.read_input(input_path)
        print(f"Read {len(terms_input)} terms")
    except Exception as e:
        print(f"Failed to read input: {e}")
        return

    # 5. Generate BatchID
    try:
        batch_gen = BatchIDGenerator(
            output_dir=settings.reanimator_output_dir,
            timezone=settings.batch_timezone
        )
        batch_id = batch_gen.generate(term_count=len(terms_input))
        print(f"[BatchID ] {batch_id}")
    except Exception as e:
        print(f"BatchID generation failed: {e}")
        return

    # 6. Generate output path (smart naming: BatchID-FileName-ModelCode.csv)
    output_filename = generate_output_filename(
        batch_id=batch_id,
        model_code=model_code,
        input_filename=str(input_path),
        ext="csv"
    )
    output_path = unique_path(settings.reanimator_output_dir / output_filename)
    print(f"[Output  ] {output_path}")

    # 7. Create LLM Provider
    try:
        if provider_type == "anthropic":
            llm_provider = AnthropicProvider(
                model=model_id,
                api_key=settings.anthropic_api_key,
                temperature=settings.default_temperature,
            )
        else:
            llm_provider = OpenAIProvider(
                model=model_id,
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature,
            )
    except Exception as e:
        print(f"Failed to create LLM Provider: {e}")
        return

    # 8. Create Infrastructure adapters (Dependency Injection)
    try:
        llm_adapter = ReanimatorLLMAdapter.from_provider(llm_provider)
        term_list_adapter = TermListAdapter.from_settings(settings)
    except Exception as e:
        print(f"Failed to create adapters: {e}")
        return

    # 9. Create Use Case (Application layer)
    try:
        use_case = ProcessTermsUseCase(
            llm=llm_adapter,
            term_list=term_list_adapter,
            start_memo_index=start_memo,
            batch_id=batch_id,
            batch_note=note_input,
        )
    except Exception as e:
        print(f"Failed to create use case: {e}")
        return

    # 10. Execute Use Case
    try:
        process_result = use_case.execute(terms_input, show_progress=True)
    except Exception as e:
        import traceback
        print(f"Processing failed: {e}")
        traceback.print_exc()
        return

    # 11. Write output (using Infrastructure adapter)
    try:
        csv_adapter.write_output(output_path, process_result.items)
        print(f"\n✅ Complete: {output_path}")
        print(f"   Processed {process_result.success_count}/{process_result.total_count} terms")
        print(f"   Token usage: {process_result.token_usage}")
    except Exception as e:
        print(f"Failed to write output: {e}")
        return


if __name__ == "__main__":
    main()
