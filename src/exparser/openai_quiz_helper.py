# src/quiz_agent/openai_quiz_helper.py
import os
import json
import openai  # 捕获 BadRequestError
from openai import OpenAI

SYSTEM_PROMPT = """You are an exam parser agent.

GOAL
- Parse a quiz in Markdown into a structured JSON list of questions.

OUTPUT CONTRACT
- Return ONLY one compact JSON object with key: "items".
- "items" is an array; each item is an object with:
  - "stem": string (one-line stem; inline images should be kept as a compact placeholder like "§Pic.1§" if the source implies an image or figure reference)
  - "options": object with keys "A","B","C","D","E","F" (strings).
    Always output all option keys A..F; missing ones must be empty strings "".
  - "answer": one uppercase letter among A..F if determinable; if unknown, use "".
- No markdown code fences, no commentary, no extra keys.

STYLE
- Stem should be self-contained text; remove leading numbers and trailing punctuation artifacts.
- Preserve essential inline hints but do NOT copy full markdown; convert line breaks inside stem to spaces.
- For image lines like ![caption](url) or explicit figure notes, transform to "§Pic.N§" and place it inline in stem where appropriate.
"""

# 使用 Structured Outputs: JSON Schema 严格模式
QUIZ_SCHEMA = {
  "name": "QuizItems",
  "strict": True,
  "schema": {
    "type": "object",
    "additionalProperties": False,
    "properties": {
      "items": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": False,
          "properties": {
            "stem": { "type": "string", "minLength": 1 },
            "options": {
              "type": "object",
              "additionalProperties": False,
              "properties": {
                "A": { "type": "string" },
                "B": { "type": "string" },
                "C": { "type": "string" },
                "D": { "type": "string" },
                "E": { "type": "string" },
                "F": { "type": "string" }
              },
              # Strict 模式要求：properties 中的键都必须出现在 required 里
              "required": ["A","B","C","D","E","F"]
            },
            "answer": { "type": "string", "pattern": "^[A-F]?$" }
          },
          "required": ["stem", "options", "answer"]
        }
      }
    },
    "required": ["items"]
  }
}

USER_TEMPLATE = """Source markdown quiz:

---
{md}
---

TASK
- Extract questions with choices and the correct answer letter if explicitly available in the markdown.
- If answer not explicit, leave "answer" as empty string "".
- Clean stems: remove numbering like "1.", "(1)", "Q1:", etc.
- Ensure options text are concise.
- Return JSON only, matching the schema strictly.
"""

class OpenAIQuizHelper:
  def __init__(self, model: str, api_key: str | None = None, temperature: float | None = None):
    self.model = model
    self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    if not self.client.api_key:
      raise RuntimeError("OPENAI_API_KEY 未设置。请配置环境变量。")
    # 某些模型不支持自定义温度；传 None 则不携带
    self.temperature = temperature

  def parse_md_to_items(self, md_text: str) -> list[dict]:
    msg_user = USER_TEMPLATE.format(md=md_text)

    kwargs = {
      "model": self.model,
      "messages": [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": msg_user},
      ],
      "response_format": {
        "type": "json_schema",
        "json_schema": QUIZ_SCHEMA
      },
    }
    if self.temperature is not None:
      kwargs["temperature"] = self.temperature

    try:
      resp = self.client.chat.completions.create(**kwargs)
    except openai.BadRequestError as e:
      em = str(e).lower()
      if "temperature" in em and "unsupported" in em:
        kwargs.pop("temperature", None)
        resp = self.client.chat.completions.create(**kwargs)
      else:
        raise

    data = json.loads(resp.choices[0].message.content)
    return data.get("items", [])