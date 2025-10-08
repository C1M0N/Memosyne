#!/usr/bin/env python3
"""
MMS CLI - 重构版本

这玩意以后会叫Reanimate！


基于原 src/mms_pipeline/main.py
改进：依赖注入、模块化、使用新架构

运行方式：
    python -m memosyne.cli.mms
    或
    python src/memosyne/cli/mms.py
"""
import sys
from pathlib import Path

# 支持直接运行：将 src/ 加入 Python 路径
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from memosyne.config import get_settings
from memosyne.providers import OpenAIProvider, AnthropicProvider
from memosyne.repositories import CSVTermRepository, TermListRepo
from memosyne.services import TermProcessor
from memosyne.utils import BatchIDGenerator, resolve_input_path, unique_path
from memosyne.cli.prompts import ask


def resolve_model_choice(user_input: str) -> tuple[str, str, str]:
    """
    解析模型选择

    Args:
        user_input: 用户输入（4/5/claude/完整模型名）

    Returns:
        (provider, model_id, model_display)
    """
    s = user_input.strip().lower()

    # 快捷方式
    shortcuts = {
        "4": ("openai", "gpt-4o-mini", "4oMini"),
        "5": ("openai", "gpt-5-mini", "5Mini"),
        "claude": ("anthropic", "claude-3-5-sonnet-20241022", "Claude"),
    }

    if s in shortcuts:
        return shortcuts[s]

    # Claude 模型
    if "claude" in s:
        return ("anthropic", user_input, "Claude")

    # OpenAI 模型
    return ("openai", user_input, user_input.replace("-", " ").title())


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
    """MMS 主流程"""
    print("=== MMS | 术语处理工具（重构版 v2.0）===")

    # 1. 加载配置
    try:
        settings = get_settings()
        settings.ensure_dirs()  # 确保目录存在
    except Exception as e:
        print(f"配置加载失败：{e}")
        print("请检查 .env 文件是否存在且 API Key 已正确配置")
        return

    # 2. 交互输入
    model_input = ask("引擎（4 = gpt-4o-mini，5 = gpt-5-mini，claude = Claude，或输入完整模型ID）：")
    path_input = ask(
        "输入CSV路径（纯数字=按 {num}.csv；含 .csv/路径=直接使用；留空=使用 short.csv）：",
        required=False
    )
    note_input = ask("批注（BatchNote，可空）：", required=False)

    # 3. 解析选择
    try:
        provider_type, model_id, model_display = resolve_model_choice(model_input)
        input_path, start_memo = resolve_input_and_memo(path_input, settings.mms_input_dir)
    except Exception as e:
        print(f"解析失败：{e}")
        return

    print(f"[Provider] {provider_type}")
    print(f"[Model   ] {model_id} ({model_display})")
    print(f"[Input   ] {input_path}")
    print(f"[Start   ] Memo = {start_memo}")
    print(f"[TermList] {settings.term_list_path}")

    # 4. 创建 LLM Provider
    try:
        if provider_type == "anthropic":
            if not settings.anthropic_api_key:
                print("错误：ANTHROPIC_API_KEY 未设置")
                return
            llm_provider = AnthropicProvider(
                model=model_id,
                api_key=settings.anthropic_api_key,
                temperature=settings.default_temperature
            )
        else:
            llm_provider = OpenAIProvider(
                model=model_id,
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature
            )
    except Exception as e:
        print(f"LLM Provider 初始化失败：{e}")
        return

    # 5. 读取输入
    try:
        csv_repo = CSVTermRepository()
        terms_input = csv_repo.read_input(input_path)
        print(f"读取到 {len(terms_input)} 个词条")
    except Exception as e:
        print(f"读取输入失败：{e}")
        return

    # 6. 加载术语表
    try:
        term_list_repo = TermListRepo()
        term_list_repo.load(settings.term_list_path)
        print(f"加载术语表：{len(term_list_repo)} 条")
    except Exception as e:
        print(f"读取术语表失败：{e}")
        return

    # 7. 生成 BatchID
    try:
        batch_gen = BatchIDGenerator(
            output_dir=settings.mms_output_dir,
            timezone=settings.batch_timezone
        )
        batch_id = batch_gen.generate(term_count=len(terms_input))
        print(f"[BatchID ] {batch_id}")
    except Exception as e:
        print(f"BatchID 生成失败：{e}")
        return

    # 8. 生成输出路径（防覆盖）
    output_filename = f"{batch_id}.csv"
    output_path = unique_path(settings.mms_output_dir / output_filename)
    print(f"[Output  ] {output_path}")

    # 9. 处理术语
    try:
        processor = TermProcessor(
            llm_provider=llm_provider,
            term_list_mapping=term_list_repo.mapping,
            start_memo_index=start_memo,
            batch_id=batch_id,
            batch_note=note_input,
        )

        results = processor.process(terms_input, show_progress=True)

    except Exception as e:
        print(f"处理失败：{e}")
        return

    # 10. 写出结果
    try:
        csv_repo.write_output(output_path, results)
        print(f"\n✅ 完成：{output_path}")
        print(f"   共处理 {len(results)} 个词条")
    except Exception as e:
        print(f"写出失败：{e}")
        return


if __name__ == "__main__":
    main()
