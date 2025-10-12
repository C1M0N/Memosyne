"""
Quiz 解析服务（Lithoformer） - 重构版本

负责使用 LLM 将 Markdown 格式的 Quiz 解析成结构化数据

重构改进：
- ✅ Logger 支持：统一日志记录
- ✅ 工厂方法：提供 from_settings() 便捷创建
- ✅ 进度条支持：显示token使用量
- ✅ 文件路径支持：可接受文件路径或字符串
- ✅ 统一返回：ProcessResult[QuizItem]
- ✅ 方法名统一：process()（parse() 作为别名）
"""
import logging
from pathlib import Path
from typing import Union
from tqdm import tqdm

from ..core.interfaces import LLMProvider, LLMError
from ..models.quiz import QuizItem, QuizResponse
from ..models.result import ProcessResult, TokenUsage
from ..prompts import LITHOFORMER_SYSTEM_PROMPT, LITHOFORMER_USER_TEMPLATE
from ..schemas import QUIZ_SCHEMA
from ..utils.logger import get_logger


class Lithoformer:
    """
    Lithoformer - Quiz 解析器（重塑器）

    使用 LLM 将 Markdown 格式的 Quiz 解析成结构化的 QuizItem 列表

    Example:
        >>> from memosyne.config import get_settings
        >>>
        >>> settings = get_settings()
        >>> parser = Lithoformer.from_settings(settings)
        >>>
        >>> md_text = "1. What is...\\nA. Option A\\nB. Option B"
        >>> result = parser.process(md_text, show_progress=True)
        >>> print(result.token_usage)
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        logger: logging.Logger | None = None
    ):
        """
        Args:
            llm_provider: LLM Provider（OpenAI 或 Anthropic）
            logger: 日志记录器（None 则使用默认）
        """
        self.llm = llm_provider
        self.logger = logger or get_logger("memosyne.lithoformer")

    @classmethod
    def from_settings(
        cls,
        settings,
        provider_type: str = "openai",
        model: str | None = None,
        logger: logging.Logger | None = None,
    ) -> "Lithoformer":
        """
        从 Settings 创建 Lithoformer 实例（工厂方法）

        Args:
            settings: Settings 对象
            provider_type: Provider 类型（"openai" 或 "anthropic"）
            model: 模型名称（None 则使用 settings 默认值）
            logger: 日志记录器

        Returns:
            Lithoformer 实例
        """
        from ..providers import OpenAIProvider, AnthropicProvider

        # 创建 LLM Provider
        if provider_type == "anthropic":
            llm = AnthropicProvider(
                model=model or settings.default_anthropic_model,
                api_key=settings.anthropic_api_key,
                temperature=settings.default_temperature,
            )
        else:
            llm = OpenAIProvider(
                model=model or settings.default_openai_model,
                api_key=settings.openai_api_key,
                temperature=settings.default_temperature,
            )

        return cls(llm_provider=llm, logger=logger)

    def process(
        self,
        markdown_source: Union[str, Path],
        show_progress: bool = True,
    ) -> ProcessResult[QuizItem]:
        """
        解析 Markdown 格式的 Quiz

        Args:
            markdown_source: Markdown 文本或文件路径
            show_progress: 是否显示进度条

        Returns:
            ProcessResult[QuizItem] - 包含结果列表和 token 统计

        Raises:
            LLMError: LLM 调用失败
            FileNotFoundError: 文件路径不存在
        """
        self.logger.info("开始解析 Quiz...")

        # 1. 读取 Markdown 内容
        if isinstance(markdown_source, Path):
            # 是 Path 对象，直接读取
            self.logger.info(f"从文件读取: {markdown_source}")
            markdown_text = markdown_source.read_text(encoding="utf-8")
        elif isinstance(markdown_source, str):
            # 是字符串，先判断是否为文件路径
            try:
                path_obj = Path(markdown_source)
                if path_obj.exists() and path_obj.is_file():
                    # 存在的文件路径
                    self.logger.info(f"从文件读取: {markdown_source}")
                    markdown_text = path_obj.read_text(encoding="utf-8")
                else:
                    # 不是文件路径，当作内容处理
                    markdown_text = markdown_source
                    self.logger.info(f"使用提供的文本，长度: {len(markdown_text)} 字符")
            except (OSError, ValueError):
                # Path() 构造失败（文件名太长等），当作内容处理
                markdown_text = markdown_source
                self.logger.info(f"使用提供的文本，长度: {len(markdown_text)} 字符")
        else:
            markdown_text = str(markdown_source)
            self.logger.info(f"使用提供的文本，长度: {len(markdown_text)} 字符")

        # 2. 准备 LLM 请求
        user_message = LITHOFORMER_USER_TEMPLATE.format(md=markdown_text)

        # 3. 显示进度条（虽然只有一次调用，但保持一致性）
        if show_progress:
            pbar = tqdm(
                total=1,
                desc="Parsing Quiz [Tokens: 0]",
                ncols=100,
                ascii=True,
            )

        try:
            self.logger.info("调用 LLM 解析...")

            # 使用统一的 Provider 接口
            data, tokens = self.llm.complete_structured(
                system_prompt=LITHOFORMER_SYSTEM_PROMPT,
                user_prompt=user_message,
                schema=QUIZ_SCHEMA["schema"],
                schema_name="QuizItems"
            )

            if show_progress:
                pbar.set_description(f"Parsing Quiz [Tokens: {tokens.total_tokens:,}]")
                pbar.update(1)
                pbar.close()

            self.logger.info(f"LLM 调用成功，Token 使用: {tokens}")

            response = QuizResponse(**data)

            # 校验：确保至少有一个题目
            if not response.items:
                raise LLMError(
                    "LLM 返回空题目列表。可能的原因：\n"
                    "1. 输入的 Markdown 格式不规范\n"
                    "2. 输入中没有可识别的题目\n"
                    "3. LLM 解析失败\n"
                    "请检查输入文件格式。"
                )

            self.logger.info(f"解析成功：{len(response.items)} 道题")

            return ProcessResult(
                items=response.items,
                success_count=len(response.items),
                total_count=len(response.items),
                token_usage=tokens,
            )

        except LLMError:
            if show_progress:
                pbar.close()
            raise
        except Exception as e:
            if show_progress:
                pbar.close()
            self.logger.error(f"解析 Quiz 失败：{e}", exc_info=True)
            raise LLMError(f"解析 Quiz 失败：{e}") from e


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    from ..config import get_settings

    # 1. 准备依赖
    settings = get_settings()

    # 2. 使用工厂方法创建解析器
    parser = Lithoformer.from_settings(
        settings=settings,
        provider_type="openai",
    )

    # 3. 示例 Markdown
    sample_md = """
1. What is the capital of France?
   A. London
   B. Paris
   C. Berlin
   D. Madrid

Correct answer: B
"""

    # 4. 解析（新接口）
    result = parser.process(sample_md, show_progress=True)

    # 5. 输出
    print(f"\n处理结果：{result}")
    print(f"Token 使用：{result.token_usage}")
    for item in result.items:
        print(f"Type: {item.qtype}")
        print(f"Stem: {item.stem}")
        print(f"Answer: {item.answer}")
        print()
