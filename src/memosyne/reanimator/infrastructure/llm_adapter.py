"""
Reanimator Infrastructure - LLM Adapter

LLM 适配器：实现 Application 层的 LLMPort 接口

职责：
- 封装 LLM Provider（OpenAI/Anthropic）
- 添加 Reanimator 特定的 Prompt
- 处理 LLM 调用和错误

依赖倒置：
- Infrastructure 层实现 Application 层定义的端口
- Infrastructure 依赖 Application（而非相反）
"""
from typing import Any

from ...core.interfaces import LLMProvider, LLMError


class ReanimatorLLMAdapter:
    """
    Reanimator LLM 适配器（实现 LLMPort）

    封装 LLM Provider，提供术语处理专用的接口。
    """

    def __init__(self, provider: LLMProvider):
        """
        Args:
            provider: LLM 提供商（OpenAI/Anthropic）
        """
        self.provider = provider

    def process_term(self, word: str, zh_def: str) -> tuple[dict[str, Any], dict[str, int]]:
        """
        处理单个术语（实现 LLMPort.process_term）

        Args:
            word: 英文词条
            zh_def: 中文释义

        Returns:
            (llm_response_dict, token_usage_dict)

        Raises:
            LLMError: LLM 调用失败
        """
        try:
            # 调用底层 LLM Provider
            llm_response, token_usage = self.provider.complete_prompt(
                word=word,
                zh_def=zh_def
            )

            # 转换 TokenUsage 对象为字典（适配端口接口）
            token_dict = {
                "prompt_tokens": token_usage.prompt_tokens,
                "completion_tokens": token_usage.completion_tokens,
                "total_tokens": token_usage.total_tokens,
            }

            return llm_response, token_dict

        except LLMError:
            # LLM 错误直接向上传播
            raise

        except Exception as e:
            # 其他错误包装为 LLMError
            raise LLMError(f"LLM 调用失败：{e}") from e

    @classmethod
    def from_provider(cls, provider: LLMProvider) -> "ReanimatorLLMAdapter":
        """
        工厂方法：从 LLM Provider 创建适配器

        Args:
            provider: LLM 提供商

        Returns:
            ReanimatorLLMAdapter 实例
        """
        return cls(provider=provider)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    print("""
    ReanimatorLLMAdapter 使用示例：

    # 1. 创建 LLM Provider
    from memosyne.providers import OpenAIProvider
    from memosyne.config import get_settings

    settings = get_settings()
    provider = OpenAIProvider(
        model=settings.default_openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.default_temperature
    )

    # 2. 创建适配器
    adapter = ReanimatorLLMAdapter.from_provider(provider)

    # 3. 处理术语
    result, tokens = adapter.process_term("neuron", "神经元")
    print(f"POS: {result['POS']}")
    print(f"Tokens: {tokens['total_tokens']}")

    # 4. 注入到用例
    from memosyne.reanimator.application import ProcessTermsUseCase

    use_case = ProcessTermsUseCase(
        llm=adapter,  # 实现了 LLMPort
        term_list=...,
        start_memo_index=2700,
        batch_id="251007A015"
    )
    """)
