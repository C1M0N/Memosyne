# openai_helper.py
import os
import json
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

class OpenAIHelper:
  def __init__(self, model: str, api_key: str | None = None, temperature: float = 0.0):
    self.model = model
    self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    if not self.client.api_key:
      raise RuntimeError("OPENAI_API_KEY 未设置。请在环境变量中配置。")
    self.temperature = temperature

  def fetch_term_info(self, word: str, zh_def: str) -> dict:
    msg_user = USER_TEMPLATE.format(word=word, zh=zh_def)
    resp = self.client.chat.completions.create(
      model=self.model,
      temperature=self.temperature,
      response_format={"type": "json_object"},
      messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": msg_user}
      ],
    )
    text = resp.choices[0].message.content.strip()
    try:
      return json.loads(text)
    except json.JSONDecodeError:
      # 偶发防御：截取最外层 JSON
      s, e = text.find("{"), text.rfind("}")
      if s != -1 and e != -1 and e > s:
        return json.loads(text[s:e+1])
      raise