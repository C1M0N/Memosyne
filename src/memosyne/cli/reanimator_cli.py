#!/usr/bin/env python3
"""
Reanimate CLI - 术语重生工具

基于原 src/mms_pipeline/main.py
改进：依赖注入、模块化、使用新架构

运行方式：
    python -m memosyne.cli.reanimate
    或
    python src/memosyne/cli/reanimate.py
"""
import sys
from pathlib import Path

# 支持直接运行：将 src/ 加入 Python 路径
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from memosyne.config import get_settings
from memosyne.repositories import CSVTermRepository
from memosyne.services import Reanimator
from memosyne.utils import (
    BatchIDGenerator,
    resolve_input_path,
    unique_path,
    resolve_model_input,
    get_provider_from_model,
    generate_output_filename,
)
from memosyne.cli.prompts import ask


def resolve_model_choice(user_input: str, settings) -> tuple[str, str, str, str]:
    """
    解析模型选择（支持 4 位简写、快捷方式、完整模型名）

    Args:
        user_input: 用户输入（4/5/claude/4位简写/完整模型名）
        settings: Settings 对象（用于获取默认模型）

    Returns:
        (provider, model_id, model_code, model_display)
    """
    s = user_input.strip().lower()

    # 旧的快捷方式（兼容性）
    if s == "4":
        model = settings.default_openai_model
        from memosyne.utils import get_code_from_model
        code = get_code_from_model(model)
        return "openai", model, code, "4oMini"
    elif s == "5":
        model = "gpt-5-mini"
        code = "o50m"
        return "openai", model, code, "5Mini"
    elif s == "claude":
        model = settings.default_anthropic_model
        from memosyne.utils import get_code_from_model
        code = get_code_from_model(model)
        return "anthropic", model, code, "Claude"

    # 尝试统一解析（支持 4 位代码或完整模型名）
    try:
        model, code = resolve_model_input(s)
        provider = get_provider_from_model(model)
        display = code.upper()  # 使用大写代码作为显示名
        return provider, model, code, display
    except ValueError:
        # 解析失败，仍然尝试作为完整模型名（兼容性）
        if "claude" in s:
            from memosyne.utils import get_code_from_model
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"  # 未知模型
            return "anthropic", user_input, code, "Claude"
        else:
            from memosyne.utils import get_code_from_model
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"  # 未知模型
            return "openai", user_input, code, user_input.replace("-", " ").title()


def resolve_input_and_memo(
    user_path: str,
    default_dir: Path
) -> tuple[Path, int]:
    """
    解析输入路径和起始 Memo

    Args:
        user_path: 用户输入
        default_dir: 默认输入目录

    Returns:
        (input_path, start_memo_index)
    """
    s = user_path.strip()

    # 纯数字：data/input/{num}.csv，起始 Memo = num
    if s.isdigit():
        memo = int(s)
        path = default_dir / f"{s}.csv"
        return path, memo

    # 包含 .csv 或路径分隔符：询问起始 Memo
    if ".csv" in s or any(ch in s for ch in ("/", "\\")):
        path = resolve_input_path(s, default_dir)
        memo_str = ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）：")
        try:
            memo = int(memo_str)
        except ValueError:
            raise ValueError("起始Memo编号必须为整数")
        return path, memo

    # 留空：使用 short.csv 并询问起始 Memo
    path = default_dir / "short.csv"
    memo_str = ask("起始Memo编号（整数，例：2700 表示从 M002701 开始）：")
    try:
        memo = int(memo_str)
    except ValueError:
        raise ValueError("起始Memo编号必须为整数")
    return path, memo


def main():
    """Reanimator 主流程"""
    print("=== Reanimator | 术语处理工具（重构版 v2.0）===")

    # 1. 加载配置
    try:
        settings = get_settings()
        settings.ensure_dirs()  # 确保目录存在
    except Exception as e:
        print(f"配置加载失败：{e}")
        print("请检查 .env 文件是否存在且 API Key 已正确配置")
        return

    # 2. 交互输入
    model_input = ask("引擎（4位简写如 o4oo/cs45，或快捷键 4/5/claude，或完整模型名）：")
    path_input = ask(
        "输入CSV路径（纯数字=按 {num}.csv；含 .csv/路径=直接使用；留空=使用 short.csv）：",
        required=False
    )
    note_input = ask("批注（BatchNote，可空）：", required=False)

    # 3. 解析选择
    try:
        provider_type, model_id, model_code, model_display = resolve_model_choice(model_input, settings)
        input_path, start_memo = resolve_input_and_memo(path_input, settings.reanimator_input_dir)
    except Exception as e:
        print(f"解析失败：{e}")
        return

    print(f"[Provider] {provider_type}")
    print(f"[Model   ] {model_id} ({model_display})")
    print(f"[Code    ] {model_code}")
    print(f"[Input   ] {input_path}")
    print(f"[Start   ] Memo = {start_memo}")
    print(f"[TermList] {settings.term_list_path}")

    # 4. 读取输入
    try:
        csv_repo = CSVTermRepository()
        terms_input = csv_repo.read_input(input_path)
        print(f"读取到 {len(terms_input)} 个词条")
    except Exception as e:
        print(f"读取输入失败：{e}")
        return

    # 5. 生成 BatchID
    try:
        batch_gen = BatchIDGenerator(
            output_dir=settings.reanimator_output_dir,
            timezone=settings.batch_timezone
        )
        batch_id = batch_gen.generate(term_count=len(terms_input))
        print(f"[BatchID ] {batch_id}")
    except Exception as e:
        print(f"BatchID 生成失败：{e}")
        return

    # 6. 生成输出路径（使用智能命名：BatchID-FileName-ModelCode.csv）
    output_filename = generate_output_filename(
        batch_id=batch_id,
        model_code=model_code,
        input_filename=str(input_path),
        ext="csv"
    )
    output_path = unique_path(settings.reanimator_output_dir / output_filename)
    print(f"[Output  ] {output_path}")

    # 7. 创建 LLM Provider
    try:
        from memosyne.providers import OpenAIProvider, AnthropicProvider

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
        print(f"创建 LLM Provider 失败：{e}")
        return

    # 8. 使用工厂方法创建处理器
    try:
        processor = Reanimator.from_settings(
            settings=settings,
            llm_provider=llm_provider,
            start_memo_index=start_memo,
            batch_id=batch_id,
            batch_note=note_input,
        )
    except Exception as e:
        print(f"创建处理器失败：{e}")
        return

    # 9. 处理术语
    try:
        process_result = processor.process(terms_input, show_progress=True)
    except Exception as e:
        import traceback
        print(f"处理失败：{e}")
        traceback.print_exc()
        return

    # 10. 写出结果
    try:
        csv_repo.write_output(output_path, process_result.items)
        print(f"\n✅ 完成：{output_path}")
        print(f"   共处理 {process_result.success_count}/{process_result.total_count} 个词条")
        print(f"   Token 使用：{process_result.token_usage}")
    except Exception as e:
        print(f"写出失败：{e}")
        return


if __name__ == "__main__":
    main()
