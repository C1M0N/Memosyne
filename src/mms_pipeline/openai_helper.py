# openai_helper.py
import os
import json
import openai  # 仅用于捕获 BadRequestError（温度不支持时重试）
from openai import OpenAI

SYSTEM_PROMPT = """You are a terminologist and lexicographer.

OUTPUT
- Return ONLY one compact JSON object with keys: IPA, POS, Rarity, EnDef, PPfix, PPmeans, TagEN.
- No markdown, no code fences, no commentary, no extra keys.

FIELD RULES
1) EnDef
   - Exactly ONE sentence and must literally contain the target word (anywhere).
   - Must fit the given Chinese gloss (ZhDef); learner can infer meaning from EnDef alone.

2) IPA
   - American IPA between slashes, e.g., "/ˈsʌmplɚ/".
   - If and only if POS="abbr.", set IPA to "" (empty). Otherwise IPA MUST be non-empty (phrases included).

3) POS (exactly one)
   - Choose from: ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."].
   - "P." = phrase (Word contains a space). "abbr." = abbreviation/initialism/acronym. "O." = other/unclear.

4) TagEN
   - Output ONE English domain label (e.g., psychology, psychiatry, medicine, biology, culture, linguistics...).
   - Do NOT output Chinese in TagEN. If uncertain, use "".

5) Rarity
   - Allowed: "" or "RARE". Use "RARE" only if reputable dictionaries mark THIS sense as uncommon/technical.

6) Morphemes
   - Fill ONLY for widely recognized Greek/Latin morphemes.
   - PPfix: space-separated lowercase tokens, no hyphens (e.g., "psycho dia gnosis").
   - PPmeans: space-separated ASCII tokens 1-to-1 with PPfix; if a single token is a multi-word gloss, use underscores (e.g., "study_of").
"""

USER_TEMPLATE = """Given:
Word: {word}
ZhDef: {zh}

Task:
Return the JSON with keys: IPA, POS, Rarity, EnDef, PPfix, PPmeans, TagEN."""

# Structured Outputs JSON Schema（严格模式）
TERM_RESULT_SCHEMA = {
  "name": "TermResult",
  "description": "Terminology fields for a single headword.",
  "strict": True,  # 严格遵循 Schema
  "schema": {
    "type": "object",
    "additionalProperties": False,
    "properties": {
      "IPA": {
        "type": "string",
        "description": "American IPA between slashes; empty only if POS is abbr.",
        "pattern": r"^(\/[^\\s\/].*\/|)$"
      },
      "POS": {
        "type": "string",
        "enum": ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."]
      },
      "Rarity": {
        "type": "string",
        "enum": ["", "RARE"]
      },
      "EnDef": {
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
    "required": ["IPA", "POS", "Rarity", "EnDef", "PPfix", "PPmeans", "TagEN"]
  }
}


class OpenAIHelper:
  def __init__(self, model: str, api_key: str | None = None, temperature: float | None = None):
    self.model = model
    self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    if not self.client.api_key:
      raise RuntimeError("OPENAI_API_KEY 未设置。请在环境变量或运行配置中提供。")
    # 可选温度：部分模型（如 gpt-5-mini）不支持自定义温度，只能用默认值
    self.temperature = temperature

  def fetch_term_info(self, word: str, zh_def: str) -> dict:
    msg_user = USER_TEMPLATE.format(word=word, zh=zh_def)

    kwargs = {
      "model": self.model,
      "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": msg_user},
      ],
      "response_format": {
        "type": "json_schema",
        "json_schema": TERM_RESULT_SCHEMA
      },
    }
    if self.temperature is not None:
      kwargs["temperature"] = self.temperature

    try:
      resp = self.client.chat.completions.create(**kwargs)
    except openai.BadRequestError as e:
      # 小兼容：若模型不支持自定义 temperature，则去掉后重试
      em = str(e).lower()
      if "temperature" in em and "unsupported" in em:
        kwargs.pop("temperature", None)
        resp = self.client.chat.completions.create(**kwargs)
      else:
        raise

    # strict=true 下返回就是合法 JSON 字符串
    return json.loads(resp.choices[0].message.content)