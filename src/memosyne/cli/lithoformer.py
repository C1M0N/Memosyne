#!/usr/bin/env python3
"""
Lithoformer CLI - Quiz 解析工具（重构版 v2.0）

功能：将 Markdown 格式的 Quiz 解析并格式化为 ShouldBe.txt

使用：
    python src/memosyne/cli/lithoformer.py

重构改进：
- ✅ 使用统一的 Settings 和 Provider
- ✅ 依赖注入，无全局状态
- ✅ 类型安全，使用 Pydantic 模型
- ✅ 职责分离（Parser, Formatter, CLI）
"""
import sys
from pathlib import Path

# 支持直接执行（python src/memosyne/cli/exparser.py）
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from memosyne.config import get_settings
from memosyne.providers import OpenAIProvider, AnthropicProvider
from memosyne.services import Lithoformer
from memosyne.utils import QuizFormatter, unique_path
from memosyne.cli.prompts import ask


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


def _resolve_output_path(user_input: str, settings) -> Path:
    """
    解析输出路径

    - 留空：默认 ShouldBe.txt（自动防重名）
    - 目录：在目录下生成 ShouldBe.txt（防重名）
    - 文件：使用指定文件名（防重名）
    """
    s = (user_input or "").strip()
    default_dir = settings.lithoformer_output_dir
    default_name = "ShouldBe.txt"

    if not s:
        default_dir.mkdir(parents=True, exist_ok=True)
        return unique_path(default_dir / default_name)

    p = Path(s)
    if p.suffix.lower() != ".txt":
        # 当作目录处理
        p.mkdir(parents=True, exist_ok=True)
        return unique_path(p / default_name)

    # 当作文件处理
    p.parent.mkdir(parents=True, exist_ok=True)
    return unique_path(p)


def main():
    """CLI 主函数"""
    print("=== Lithoformer | Quiz 解析工具（重构版 v2.0）===")

    # 1. 加载配置
    settings = get_settings()
    settings.ensure_dirs()

    # 2. 用户输入
    model_input = ask("引擎（4 = gpt-4o-mini，5 = gpt-5-mini，claude = Claude，或输入完整模型ID）：")
    input_raw = ask("输入 Markdown 文件路径（默认 data/input/parser/...）：", required=False)
    output_raw = ask("输出 TXT 文件路径（默认 data/output/parser/ShouldBe.txt）：", required=False)

    # 3. 解析路径
    input_path = _resolve_input_md(input_raw, settings)
    output_path = _resolve_output_path(output_raw, settings)

    # 4. 推断标题
    title_main, title_sub = _infer_titles_from_filename(input_path)

    # 5. 展示配置
    print(f"[Input  ] {input_path}")
    print(f"[Output ] {output_path}")
    print(f"[Title  ] {title_main} | {title_sub}")

    # 6. 读取 Markdown
    try:
        md_text = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ 读取输入文件失败：{e}")
        return

    # 7. 创建 LLM Provider
    try:
        if model_input.lower() == "4":
            llm = OpenAIProvider(
                model="gpt-4o-mini",
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature
            )
            print("[Provider] openai")
            print("[Model   ] gpt-4o-mini")
        elif model_input.lower() == "5":
            llm = OpenAIProvider(
                model="gpt-5-mini",
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature
            )
            print("[Provider] openai")
            print("[Model   ] gpt-5-mini")
        elif model_input.lower() == "claude":
            if not settings.anthropic_api_key:
                print("❌ Anthropic API Key 未配置")
                return
            llm = AnthropicProvider(
                model=settings.default_anthropic_model,
                api_key=settings.anthropic_api_key,
                temperature=settings.default_temperature
            )
            print("[Provider] anthropic")
            print(f"[Model   ] {settings.default_anthropic_model}")
        else:
            # 完整模型ID（假设 OpenAI）
            llm = OpenAIProvider(
                model=model_input,
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature
            )
            print("[Provider] openai")
            print(f"[Model   ] {model_input}")
    except Exception as e:
        print(f"❌ 创建 LLM Provider 失败：{e}")
        return

    # 8. 解析 Markdown
    try:
        parser = Lithoformer(llm_provider=llm)
        items = parser.parse(md_text)
        print(f"✅ 解析成功：{len(items)} 道题")
    except Exception as e:
        print(f"❌ 解析失败：{e}")
        return

    # 9. 格式化输出
    try:
        formatter = QuizFormatter()
        out_text = formatter.format(items, title_main, title_sub)
    except Exception as e:
        print(f"❌ 格式化失败：{e}")
        return

    # 10. 写出文件
    try:
        output_path.write_text(out_text, encoding="utf-8")
        print(f"✅ 完成：{output_path}")
    except Exception as e:
        print(f"❌ 写出失败：{e}")
        return


if __name__ == "__main__":
    main()
