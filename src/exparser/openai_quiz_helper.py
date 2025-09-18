# src/quiz_agent/openai_quiz_helper.py
import os
import json
import openai  # 捕获 BadRequestError
from openai import OpenAI

# openai_quiz_helper.py（只贴需要替换/更新的两段）

SYSTEM_PROMPT = """You are an exam parser agent.

VERBATIM MANDATE (CRITICAL)
- DO NOT paraphrase or shorten any wording.
- COPY stems, step lines (A./B./C./D.) and option texts VERBATIM.
- Preserve punctuation, parentheses, acronyms, numbers (e.g., 'DSM-5-TR', '(positively charged ion)').
- Allowed edits ONLY:
  (a) remove leading numbering tokens at the very start of the stem (e.g., '1.', '(1)', 'Q1:');
  (b) insert '<br>' for line breaks;
  (c) replace figures/images with placeholders '§Pic.N§' in order of appearance.

STRICT SEPARATION
- NEVER put any answer choices (like 'a. ...', 'A. ...') inside the stem. All choices must go into 'options'.
- Remove UI/grade artifacts from the source such as: 'Correct answer:', 'Incorrect answer:', ', Not Selected', 'Not Selected'.
- Remove naked markers 'A.'/'B.'/'C.'/'D.' that appear WITHOUT text.

TYPE DECISION RULES
- If lettered choices (A./B./C./D.) exist in the source, the item is MCQ, even if the stem has blanks/underscores.
- Use CLOZE ONLY when there are underscores '____' in the stem AND there are NO lettered choices.
- Use ORDER when the prompt asks to place/order AND there are labeled step lines A./B./C./D., plus separate sequence choices (e.g., 'B,A,C,D').
- For figure-only MCQ (labels A/B/C/D without descriptions), set options A='A', B='B', C='C', D='D' (others empty).

OUTPUT CONTRACT
- Return ONLY one compact JSON object with key: "items".
- "items" is an array; each item is an object with:
  - "qtype": "MCQ" or "CLOZE" or "ORDER".
  - "stem": string (VERBATIM; may include '<br>' and '§Pic.N§').
  - "steps": array of strings. For ORDER, put the labeled step lines VERBATIM (e.g., 'A. ...', 'B. ...'); else [].
  - "options": object with keys "A","B","C","D","E","F" (strings). ALWAYS output all keys; if a key doesn't exist, set "".
    *For ORDER, options are the SEQUENCE choices (e.g., 'B,A,C,D'), NOT the step lines.*
  - "answer": one uppercase letter among A..F for MCQ/ORDER; "" for CLOZE.
  - "cloze_answers": array of strings. For CLOZE, provide exact fills in order; for MCQ/ORDER, [].
- No markdown code fences, no commentary, no extra keys.
- Do NOT create items that are merely answer summaries (e.g., '... in the proper sequence: D, C, A, B.').

STYLE
- Stems: only remove leading numbering tokens; otherwise copy verbatim.
- Keep parentheses and qualifiers.
- For blanks '____', list fills in cloze_answers (renderer will place '{{...}}' or keep underscores as needed)."""

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
            "qtype":  { "type": "string", "enum": ["MCQ","CLOZE","ORDER"] },
            "stem":   { "type": "string", "minLength": 1 },
            "steps":  {
              "type": "array",
              "items": { "type": "string" }
            },
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
              "required": ["A","B","C","D","E","F"]
            },
            "answer": { "type": "string", "pattern": "^[A-F]?$" },
            "cloze_answers": {
              "type": "array",
              "items": { "type": "string" }
            }
          },
          "required": ["qtype","stem","steps","options","answer","cloze_answers"]
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