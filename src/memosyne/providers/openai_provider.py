"""OpenAI Provider - 重构版本.

This provider previously relied solely on ``chat.completions``. The OpenAI
Python SDK >=2.0, which ships with this project, promotes the ``responses`` API
as the canonical way to request structured JSON via ``response_format``.  macOS
users running the latest SDK reported ``OSError: [Errno 63] File name too
long`` when invoking the CLI pipelines.  The error originated from deep within
the SDK after it attempted to treat the raw Markdown prompt as a temporary file
while formatting the request.  Falling back to ``responses.parse`` avoids that
path and is the officially supported workflow going forward.  For
compatibility, we still retain the old ``chat.completions`` based code path as a
fallback should an older SDK be in use.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from openai import APIStatusError, BadRequestError, OpenAI

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

    def complete_prompt(self, word: str, zh_def: str) -> dict[str, Any]:
        """调用 OpenAI API 生成术语信息"""
        user_message = USER_TEMPLATE.format(word=word, zh_def=zh_def)

        return self._request_json_schema(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_message,
            schema_payload=TERM_RESULT_SCHEMA,
        )

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        schema_name: str = "Response"
    ) -> dict[str, Any]:
        """调用 OpenAI API 生成结构化 JSON 响应"""
        schema_payload = {
            "name": schema_name,
            "strict": True,
            "schema": schema,
        }

        return self._request_json_schema(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema_payload=schema_payload,
        )

    def _validate_config(self) -> None:
        """验证配置"""
        super()._validate_config()
        if not self.client.api_key:
            raise ValueError("OpenAI API Key 未设置")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request_json_schema(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Request structured JSON via Responses API with chat fallback."""

        last_error: Exception | None = None

        if hasattr(self.client, "responses") and hasattr(self.client.responses, "parse"):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "instructions": system_prompt,
                    "input": user_prompt,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": schema_payload,
                    },
                }
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature

                response = self.client.responses.parse(**kwargs)
                parsed = self._extract_responses_output(response)
                if parsed is not None:
                    return parsed
                raise LLMError("OpenAI 未返回结构化结果")
            except (APIStatusError, BadRequestError) as exc:
                raise LLMError(f"OpenAI API 错误：{exc}") from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        # Fallback to legacy chat completions for backward compatibility.
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": schema_payload,
            },
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        try:
            response = self.client.chat.completions.create(**kwargs)
            return self._extract_chat_output(response)
        except BadRequestError as exc:
            error_msg = str(exc).lower()
            if "temperature" in error_msg and "unsupported" in error_msg:
                kwargs.pop("temperature", None)
                response = self.client.chat.completions.create(**kwargs)
                return self._extract_chat_output(response)
            raise LLMError(f"OpenAI API 错误：{exc}") from exc
        except Exception as exc:  # noqa: BLE001
            if last_error is not None:
                raise LLMError(
                    "调用 OpenAI 时发生意外错误："
                    f"Responses.parse 失败（{last_error}）；"
                    f"ChatCompletion 失败（{exc}）"
                ) from exc
            raise LLMError(f"调用 OpenAI 时发生意外错误：{exc}") from exc

    @staticmethod
    def _extract_responses_output(response: Any) -> dict[str, Any] | None:
        """Safely extract parsed JSON from ``responses.parse`` output."""

        parsed = getattr(response, "output_parsed", None)
        if isinstance(parsed, dict):
            return parsed

        output_items: Iterable[Any] = getattr(response, "output", []) or []
        text_chunks: list[str] = []

        for item in output_items:
            content_list = getattr(item, "content", []) or []
            for content in content_list:
                parsed_content = getattr(content, "parsed", None)
                if isinstance(parsed_content, dict):
                    return parsed_content
                text = getattr(content, "text", None)
                if isinstance(text, str):
                    text_chunks.append(text)

        if text_chunks:
            joined = "".join(text_chunks).strip()
            if joined:
                try:
                    return json.loads(joined)
                except json.JSONDecodeError as exc:
                    raise LLMError(f"解析 LLM 响应失败：{exc}") from exc

        return None

    @staticmethod
    def _extract_chat_output(response: Any) -> dict[str, Any]:
        """Extract structured JSON from ``chat.completions`` output."""

        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError) as exc:  # noqa: BLE001
            raise LLMError(f"解析 LLM 响应失败：{exc}") from exc

        if isinstance(content, dict):
            parsed = content.get("parsed")
            if isinstance(parsed, dict):
                return parsed
            text_value = content.get("text")
            if isinstance(text_value, str):
                return OpenAIProvider._loads_json(text_value)

        if isinstance(content, list):
            text_segments: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    parsed = part.get("parsed")
                    if isinstance(parsed, dict):
                        return parsed
                    text_val = part.get("text") or part.get("value")
                else:
                    text_val = getattr(part, "text", None)
                    parsed = getattr(part, "parsed", None)
                    if isinstance(parsed, dict):
                        return parsed
                if isinstance(text_val, str):
                    text_segments.append(text_val)
            if text_segments:
                return OpenAIProvider._loads_json("".join(text_segments))

        if isinstance(content, str):
            return OpenAIProvider._loads_json(content)

        raise LLMError("OpenAI 响应格式未知，无法解析 JSON")

    @staticmethod
    def _loads_json(payload: str) -> dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LLMError(f"解析 LLM 响应失败：{exc}") from exc
