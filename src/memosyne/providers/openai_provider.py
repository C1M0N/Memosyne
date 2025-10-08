"""
OpenAI Provider - 重构版本

基于原 src/mms_pipeline/openai_helper.py
改进：继承抽象基类、结构化日志、可注入配置
"""
import json
from openai import OpenAI, BadRequestError

from ..core.interfaces import BaseLLMProvider, LLMError


# ============================================================
# Prompt 和 Schema 定义
# ============================================================
SYSTEM_PROMPT = """You are a terminologist and lexicographer.

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

TERM_RESULT_SCHEMA = {
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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider"""

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float | None = None,
        max_retries: int = 2
    ):
        self.client = OpenAI(api_key=api_key, max_retries=max_retries)
        super().__init__(model=model, temperature=temperature)

    @classmethod
    def from_settings(cls, settings) -> "OpenAIProvider":
        """从配置创建实例"""
        return cls(
            model=settings.default_openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.default_temperature,
        )

    def complete_prompt(self, word: str, zh_def: str) -> dict:
        """调用 OpenAI API 生成术语信息"""
        user_message = USER_TEMPLATE.format(word=word, zh_def=zh_def)

        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": TERM_RESULT_SCHEMA
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            response = self.client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            error_msg = str(e).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise LLMError(f"OpenAI API 错误：{e}") from e
        except Exception as e:
            raise LLMError(f"调用 OpenAI 时发生意外错误：{e}") from e

        try:
            content = response.choices[0].message.content
            return json.loads(content)
        except (json.JSONDecodeError, IndexError, AttributeError) as e:
            raise LLMError(f"解析 LLM 响应失败：{e}") from e

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("OpenAI API Key 未设置")
