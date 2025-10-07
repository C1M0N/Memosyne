"""
OpenAI Provider 重构版本

重构改进：
- ✅ 继承 BaseLLMProvider 抽象基类
- ✅ 使用 Pydantic 模型替代 dict
- ✅ 集中管理 Prompt 和 Schema
- ✅ 更好的错误处理和日志
- ✅ 可注入 API Key（便于测试）
"""
import json
import structlog
from openai import OpenAI, BadRequestError

from ..core.interfaces import BaseLLMProvider, LLMError
from ..models.term import LLMResponse


logger = structlog.get_logger()


# ============================================================
# Prompt 和 Schema 定义（集中管理）
# ============================================================
class PromptTemplates:
    """提示词模板（便于 A/B 测试和版本管理）"""

    SYSTEM_V1 = """You are a terminologist and lexicographer.

OUTPUT
- Return ONLY one compact JSON object with keys: IPA, POS, Rarity, EnDef, PPfix, PPmeans, TagEN.
- No markdown, no code fences, no commentary, no extra keys.

FIELD RULES
1) EnDef
   - Exactly ONE sentence and must literally contain the target word (anywhere).
   - Must fit the given Chinese gloss (ZhDef); learner can infer meaning from EnDef alone.

2) Example
   - Exactly ONE sentence and must literally contain the target word (anywhere).
   - Must fit the given Chinese gloss (ZhDef) AND real application scenarios; do NOT write random or generic sentences.
   - MUST NOT be identical to EnDef.

3) IPA
   - American IPA between slashes, e.g., "/ˈsʌmplɚ/".
   - If and only if POS="abbr.", set IPA to "" (empty). Otherwise IPA MUST be non-empty (phrases included).

4) POS (exactly one)
   - Choose from: ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."].
   - "P." = phrase (Word contains a space). "abbr." = abbreviation/initialism/acronym. "O." = other/unclear.

5) TagEN
   - Output ONE English domain label (e.g., psychology, psychiatry, medicine, biology, culture, linguistics...).
   - Do NOT output Chinese in TagEN. If uncertain, use "".

6) Rarity
   - Allowed: "" or "RARE". Use "RARE" only if reputable dictionaries mark THIS sense as uncommon/technical.

7) Morphemes
   - Fill ONLY for widely recognized Greek/Latin morphemes.
   - PPfix: space-separated lowercase tokens, no hyphens (e.g., "psycho dia gnosis").
   - PPmeans: space-separated ASCII tokens 1-to-1 with PPfix; if a single token is a multi-word gloss, use underscores (e.g., "study_of").
"""

    USER_TEMPLATE = """Given:
Word: {word}
ZhDef: {zh_def}

Task:
Return the JSON with keys: IPA, POS, Rarity, EnDef, Example, PPfix, PPmeans, TagEN."""


class SchemaDefinitions:
    """JSON Schema 定义"""

    TERM_RESULT_V1 = {
        "name": "TermResult",
        "description": "Terminology fields for a single headword.",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "IPA": {
                    "type": "string",
                    "description": "American IPA between slashes; empty only if POS is abbr.",
                    "pattern": r"^(\/[^\s\/].*\/|)$"
                },
                "POS": {
                    "type": "string",
                    "enum": ["n.", "vt.", "vi.", "adj.", "adv.", "P.", "O.", "abbr."]
                },
                "Rarity": {
                    "type": "string",
                    "enum": ["", "RARE"]
                },
                "EnDef": {
                    "type": "string",
                    "minLength": 1
                },
                "Example": {
                    "type": "string",
                    "minLength": 1
                },
                "PPfix": {
                    "type": "string"
                },
                "PPmeans": {
                    "type": "string",
                    "description": "ASCII only; use underscores inside a token for multi-word gloss.",
                    "pattern": r"^[\x20-\x7E]*$"
                },
                "TagEN": {
                    "type": "string"
                }
            },
            "required": ["IPA", "POS", "Rarity", "EnDef", "Example", "PPfix", "PPmeans", "TagEN"]
        }
    }


# ============================================================
# OpenAI Provider 实现
# ============================================================
class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM 提供商

    Example:
        >>> from config.settings import get_settings
        >>> settings = get_settings()
        >>> provider = OpenAIProvider.from_settings(settings)
        >>> result = provider.complete_prompt("neuron", "神经元")
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float | None = None,
        max_retries: int = 2
    ):
        """
        Args:
            model: 模型名称，如 "gpt-4o-mini"
            api_key: OpenAI API Key
            temperature: 温度参数（None 表示使用默认）
            max_retries: 最大重试次数
        """
        super().__init__(model=model, temperature=temperature)
        self.client = OpenAI(api_key=api_key, max_retries=max_retries)
        self._prompt_version = "V1"
        self._schema_version = "V1"

    @classmethod
    def from_settings(cls, settings) -> "OpenAIProvider":
        """从配置对象创建实例"""
        return cls(
            model=settings.default_openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.default_temperature,
        )

    def complete_prompt(self, word: str, zh_def: str) -> dict:
        """
        调用 OpenAI API 生成术语信息

        Args:
            word: 英文词条
            zh_def: 中文释义

        Returns:
            LLM 响应字典（可用于构造 LLMResponse）

        Raises:
            LLMError: API 调用失败
        """
        # 1. 构造消息
        user_message = PromptTemplates.USER_TEMPLATE.format(
            word=word,
            zh_def=zh_def
        )

        # 2. 准备参数
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": PromptTemplates.SYSTEM_V1},
                {"role": "user", "content": user_message},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": SchemaDefinitions.TERM_RESULT_V1
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        # 3. 调用 API（处理兼容性问题）
        try:
            response = self.client.chat.completions.create(**kwargs)

        except BadRequestError as e:
            # 处理某些模型不支持 temperature 的情况
            error_msg = str(e).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                logger.warning(
                    "model_temperature_unsupported",
                    model=self.model,
                    fallback="removing_temperature"
                )
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
            else:
                logger.error("openai_api_error", error=str(e), word=word)
                raise LLMError(f"OpenAI API 错误：{e}") from e

        except Exception as e:
            logger.error("openai_unexpected_error", error=str(e), word=word)
            raise LLMError(f"调用 OpenAI 时发生意外错误：{e}") from e

        # 4. 解析响应
        try:
            content = response.choices[0].message.content
            result = json.loads(content)
            logger.debug("llm_response_received", word=word, model=self.model)
            return result

        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            logger.error("response_parse_error", error=str(e), content=content)
            raise LLMError(f"解析 LLM 响应失败：{e}") from e

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("OpenAI API Key 未设置")


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # 1. 创建 Provider
    provider = OpenAIProvider(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.7
    )

    # 2. 调用
    result = provider.complete_prompt("neuron", "神经元")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 3. 转换为 Pydantic 模型（带验证）
    llm_response = LLMResponse(**result)
    print(llm_response.model_dump())
