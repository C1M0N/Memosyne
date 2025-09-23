# openai_helper.py
import os
import json
import re
import openai
from typing import Dict, List, Optional
from openai import OpenAI

SKIP = "__SKIP__"  # 仅允许用于 IPA/EnDef/Example 三个可跳过字段

# —— System Prompt：语义规则（结构约束交给 json_schema）——
SYSTEM_PROMPT = """You are a terminologist and lexicographer.

OUTPUT RULES
- Return ONLY one JSON object that matches the provided JSON Schema strictly.
- No markdown, no extra text, no comments.

FIELD SEMANTICS (must be followed in addition to the schema)
• EnDef: exactly ONE sentence; must literally contain the headword (anywhere); learner-friendly dictionary tone; must match the given Chinese gloss (ZhDef).
• Example: exactly ONE natural usage sentence for the *same* sense; NOT a definition; no quotes.
• IPA:
  - For normal words and phrases: American IPA between slashes, e.g., "/ˈsʌmplɚ/".
  - For abbreviations (POS="abbr."): IPA MUST be "" (empty). Do NOT invent an expanded form.
• POS: exactly one of ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."].
  - "P." means multi-word phrase (Word contains a space) unless it is an abbreviation.
  - "abbr." for abbreviation/initialism/acronym (e.g., ATP, Na+/K+, S-P).
• Rarity: "" or "RARE"; use "RARE" ONLY if reliable dictionaries indicate THIS sense is uncommon/technical.
• Morphemes:
  - Only include widely recognized classical morphemes (Greek/Latin).
  - PPfix: space-separated lowercase tokens, no hyphens.
  - PPmeans: space-separated ASCII tokens, 1-to-1 with PPfix; use underscores inside a token for multi-word gloss (e.g., study_of).
• TagEN:
  - Choose ONE domain label strictly from the whitelist provided by the user message; if none apply, return "".
IMPORTANT
- The special token "__SKIP__" is allowed ONLY for fields explicitly marked to skip (IPA/EnDef/Example). NEVER use "__SKIP__" for POS, Rarity, TagEN, PPfix, or PPmeans.
"""

def _schema_main(allowed_en: List[str], skip_ipa: bool, skip_endef: bool, skip_example: bool) -> Dict:
  """严格 JSON Schema（Structured Outputs）。只允许 IPA/EnDef/Example 使用 __SKIP__。"""
  def _skip_prop() -> Dict:
    return {"type": "string", "enum": [SKIP]}

  def _nonempty_no_skip() -> Dict:
    return {"type": "string", "pattern": rf"^(?!{SKIP}$).+$", "minLength": 1}

  # 非 skip 时，IPA 必须是 /.../；abbr. 的 IPA=空串，会由业务层结合 POS 再行校验允许空
  ipa_prop = {"type": "string", "pattern": r"^(?!__SKIP__$)(\/[^\s\/].*\/)$"}

  return {
    "name": "TermRecord",
    "strict": True,
    "schema": {
      "type": "object",
      "additionalProperties": False,
      "properties": {
        "IPA": _skip_prop() if skip_ipa else ipa_prop,
        "POS": {"type": "string", "enum": ["n.","vt.","vi.","adj.","adv.","P.","O.","abbr."]},
        "Rarity": {"type": "string", "enum": ["", "RARE"]},
        "EnDef": _skip_prop() if skip_endef else _nonempty_no_skip(),
        "Example": _skip_prop() if skip_example else _nonempty_no_skip(),
        "PPfix": {"type": "string"},   # 可空；ASCII 由模型自守；业务层再清洗
        "PPmeans": {
          "type": "string",
          "pattern": r"^[\x20-\x7E]*$"   # ASCII; 下划线允许
        },
        "TagEN": {"type": "string", "enum": (sorted(set([s.lower() for s in allowed_en])) + [""])}
      },
      "required": ["IPA","POS","Rarity","EnDef","Example","PPfix","PPmeans","TagEN"]
    }
  }

def _schema_single(key: str) -> Dict:
  """兜底单字段：IPA/EnDef/Example；此处不允许 __SKIP__。"""
  if key == "IPA":
    prop = {"type": "string", "pattern": r"^\/[^\s\/].*\/$"}  # 必须 /.../
  else:
    prop = {"type": "string", "minLength": 1}
  return {
    "name": f"{key}Only",
    "strict": True,
    "schema": {
      "type": "object",
      "additionalProperties": False,
      "properties": {key: prop},
      "required": [key]
    }
  }

USER_TEMPLATE = """Given:
Word: {word}
ZhDef: {zh}

Allowed domains (choose ONE from the whitelist below, or "" if none applies):
{whitelist}

Skip plan for generation:
- IPA: {skip_ipa}
- EnDef: {skip_endef}
- Example: {skip_example}
"""

_fence = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)

def _extract_json(text: str) -> Dict:
  text = (text or "").strip()
  try:
    return json.loads(text)
  except Exception:
    pass
  cleaned = _fence.sub("", text).strip()
  return json.loads(cleaned)  # 若失败，让上层抛出真实错误以便排查

class OpenAIHelper:
  def __init__(self, model: str, api_key: Optional[str] = None, temperature: Optional[float] = None):
    self.model = model
    self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    if not self.client.api_key:
      raise RuntimeError("OPENAI_API_KEY 未设置。")
    self.temperature = temperature
    self._usage = {"prompt": 0, "completion": 0, "total": 0}

  def _record_usage(self, resp) -> None:
    u = getattr(resp, "usage", None)
    if not u:
      return
    pt = getattr(u, "prompt_tokens", 0) or 0
    ct = getattr(u, "completion_tokens", 0) or 0
    self._usage["prompt"] += pt
    self._usage["completion"] += ct
    self._usage["total"] += (pt + ct)

  def usage_summary(self) -> Dict[str, int]:
    return dict(self._usage)

  def _call(self, messages: List[Dict], response_format: Dict) -> Dict:
    kwargs = {"model": self.model, "messages": messages, "response_format": response_format}
    if self.temperature is not None:
      kwargs["temperature"] = self.temperature
    try:
      resp = self.client.chat.completions.create(**kwargs)
    except openai.BadRequestError as e:
      em = str(e).lower()
      # 某些模型不接受自定义温度
      if "temperature" in em and "unsupported" in em:
        kwargs.pop("temperature", None)
        resp = self.client.chat.completions.create(**kwargs)
      else:
        raise
    self._record_usage(resp)
    text = resp.choices[0].message.content or ""
    return _extract_json(text)

  def fetch_main(self, word: str, zh: str, allowed_tag_en: List[str],
      skip_ipa: bool, skip_endef: bool, skip_example: bool) -> Dict:
    schema = _schema_main(allowed_tag_en, skip_ipa, skip_endef, skip_example)
    wl = "\n".join(f"- {s}" for s in sorted(set([s.lower() for s in allowed_tag_en]))[:120]) or "(no domain)"
    msg_user = USER_TEMPLATE.format(
      word=word, zh=zh, whitelist=wl,
      skip_ipa=str(skip_ipa).lower(),
      skip_endef=str(skip_endef).lower(),
      skip_example=str(skip_example).lower(),
    )
    messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": msg_user},
    ]
    return self._call(messages, {"type": "json_schema", "json_schema": schema})

  def fetch_single(self, key: str, word: str, zh: str) -> str:
    assert key in ("IPA","EnDef","Example")
    schema = _schema_single(key)
    if key == "IPA":
      instr = "Return only IPA strictly in American slashes '/.../' for the headword."
    elif key == "EnDef":
      instr = "Return only EnDef: exactly ONE sentence; must contain the headword; must match the Chinese gloss."
    else:
      instr = "Return only Example: exactly ONE natural usage sentence for the same sense; not a definition."
    messages = [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": f"Word: {word}\nZhDef: {zh}\n{instr}"}
    ]
    data = self._call(messages, {"type": "json_schema", "json_schema": schema})
    return data[key]