#!/usr/bin/env python3
"""
Lithoform CLI - Quiz 重塑工具

功能：将 Markdown 格式的 Quiz 解析并格式化为 ShouldBe.txt

运行方式：
    python -m memosyne.cli.lithoform
    或
    python src/memosyne/cli/lithoform.py

重构改进：
- ✅ 使用统一的 Settings 和 Provider
- ✅ 依赖注入，无全局状态
- ✅ 类型安全，使用 Pydantic 模型
- ✅ 职责分离（Lithoformer, Formatter, CLI）
"""
import sys
from pathlib import Path

# 支持直接执行（python src/memosyne/cli/lithoform.py）
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from memosyne.config import get_settings
from memosyne.services import Lithoformer
from memosyne.utils import (
    QuizFormatter,
    unique_path,
    resolve_model_input,
    get_provider_from_model,
    get_code_from_model,
    BatchIDGenerator,
    generate_output_filename,
)
from memosyne.cli.prompts import ask


def _resolve_model_choice(user_input: str, settings) -> tuple[str, str, str]:
    """
    解析模型选择（支持 4 位简写、快捷方式、完整模型名）

    Args:
        user_input: 用户输入（4/5/claude/4位简写/完整模型名）
        settings: Settings 对象（用于获取默认模型）

    Returns:
        (provider_type, model_id, model_code)
    """
    s = user_input.strip().lower()

    # 旧的快捷方式（兼容性）
    if s == "4":
        model = settings.default_openai_model
        code = get_code_from_model(model)
        return "openai", model, code
    elif s == "5":
        model = "gpt-5-mini"
        code = "o50m"
        return "openai", model, code
    elif s == "claude":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API Key 未配置")
        model = settings.default_anthropic_model
        code = get_code_from_model(model)
        return "anthropic", model, code

    # 尝试统一解析（支持 4 位代码或完整模型名）
    try:
        model, code = resolve_model_input(s)
        provider = get_provider_from_model(model)
        return provider, model, code
    except ValueError:
        # 解析失败，仍然尝试作为完整模型名（兼容性）
        if "claude" in s:
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"  # 未知模型
            return "anthropic", user_input, code
        else:
            try:
                code = get_code_from_model(s)
            except ValueError:
                code = "????"  # 未知模型
            return "openai", user_input, code


def _infer_titles_from_filename(path: Path) -> tuple[str, str]:
    """
    从文件名推断标题

    Example:
        'Chapter 3 Quiz-Assessment and Classification.md'
        -> ('Chapter 3 Quiz', 'Assessment and Classification')
    """
    name = path.stem  # 不含扩展名

    # 常见模式："... Quiz- Subtitle"
    if "Quiz" in name:
        # 先按 'Quiz' 切
        left, _, right = name.partition("Quiz")
        main = (left + "Quiz").strip()
        # 再看是否有 '-' 引导的副标题
        if "-" in right:
            _, _, sub = right.partition("-")
            sub = sub.strip()
        else:
            sub = right.strip().lstrip(":：-").strip()
        if main:
            return main, sub

    # 兜底
    return name.strip(), ""


def _resolve_input_md(user_input: str, settings) -> Path:
    """
    解析输入 Markdown 路径

    - 留空：使用默认文件
    - 只给文件名：从 lithoformer_input_dir 查找
    - 完整路径：直接使用
    """
    s = (user_input or "").strip()
    default_file = "Chapter 3 Quiz- Assessment and Classification of Mental Disorders.md"

    if not s:
        return settings.lithoformer_input_dir / default_file

    p = Path(s)
    if p.is_absolute() or any(ch in s for ch in ("/", "\\")):
        return p

    return settings.lithoformer_input_dir / s


def main():
    """CLI 主函数"""
    print("=== Lithoformer | Quiz 解析工具（重构版 v2.0）===")

    # 1. 加载配置
    settings = get_settings()
    settings.ensure_dirs()

    # 2. 用户输入
    model_input = ask("引擎（4位简写如 o4oo/cs45，或快捷键 4/5/claude，或完整模型名）：")
    input_raw = ask("输入 Markdown 文件路径（默认 data/input/lithoformer/...）：", required=False)

    # 3. 解析输入路径
    input_path = _resolve_input_md(input_raw, settings)

    # 4. 推断标题
    title_main, title_sub = _infer_titles_from_filename(input_path)

    # 5. 读取 Markdown
    try:
        md_text = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ 读取输入文件失败：{e}")
        return

    # 6. 确定 Provider 和 Model（集中配置）
    try:
        provider_type, model_id, model_code = _resolve_model_choice(model_input, settings)
        print(f"[Provider] {provider_type}")
        print(f"[Model   ] {model_id}")
        print(f"[Code    ] {model_code}")
    except Exception as e:
        print(f"❌ 解析模型配置失败：{e}")
        return

    print(f"[Input   ] {input_path}")
    print(f"[Title   ] {title_main} | {title_sub}")

    # 7. 使用工厂方法创建解析器
    try:
        parser = Lithoformer.from_settings(
            settings=settings,
            provider_type=provider_type,
            model=model_id,
        )
    except Exception as e:
        print(f"❌ 创建解析器失败：{e}")
        return

    # 8. 解析 Markdown
    try:
        process_result = parser.process(md_text, show_progress=True)
        print(f"✅ 解析成功：{process_result.success_count} 道题")
        print(f"   Token 使用：{process_result.token_usage}")
    except Exception as e:
        import traceback
        print(f"❌ 解析失败：{e}")
        traceback.print_exc()
        return

    # 9. 生成 BatchID（基于题目数量）
    try:
        batch_gen = BatchIDGenerator(
            output_dir=settings.lithoformer_output_dir,
            timezone=settings.batch_timezone
        )
        batch_id = batch_gen.generate(term_count=process_result.success_count)
        print(f"[BatchID ] {batch_id}")
    except Exception as e:
        print(f"❌ BatchID 生成失败：{e}")
        return

    # 10. 生成输出路径（使用智能命名：BatchID-FileName-ModelCode.txt）
    output_filename = generate_output_filename(
        batch_id=batch_id,
        model_code=model_code,
        input_filename=str(input_path),
        ext="txt"
    )
    output_path = unique_path(settings.lithoformer_output_dir / output_filename)
    print(f"[Output  ] {output_path}")

    # 11. 格式化输出
    try:
        formatter = QuizFormatter()
        out_text = formatter.format(process_result.items, title_main, title_sub)
    except Exception as e:
        print(f"❌ 格式化失败：{e}")
        return

    # 12. 写出文件
    try:
        output_path.write_text(out_text, encoding="utf-8")
        print(f"✅ 完成：{output_path}")
    except Exception as e:
        print(f"❌ 写出失败：{e}")
        return


if __name__ == "__main__":
    main()
