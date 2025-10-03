# src/mms_pipeline/anthropic_helper.py
import os
import json
from anthropic import Anthropic, APIError
from openai_helper import SYSTEM_PROMPT, USER_TEMPLATE, TERM_RESULT_SCHEMA  # 复用同一套提示与 Schema

class AnthropicHelper:
  """
  Claude 消息接口封装，输出与 OpenAIHelper 一致：
  complete_prompt(word, zh_def) -> dict（严格匹配 TERM_RESULT_SCHEMA）
  """

  def __init__(self, model: str, api_key: str | None = None,
      temperature: float | None = None,
      max_tokens: int = 1024):
    self.model = model
    self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
    if not self.client.api_key:
      raise RuntimeError("ANTHROPIC_API_KEY 未设置。请在 .env 或环境变量中配置。")
    self.temperature = temperature
    self.max_tokens = max_tokens

  def complete_prompt(self, word: str, zh_def: str) -> dict:
    """
    使用 tools + tool_choice 强制返回结构化 JSON：
    - tools[0].input_schema 为我们要求的 JSON Schema（TERM_RESULT_SCHEMA['schema']）
    - tool_choice 指定必须调用该“工具”，Claude 会把结构化数据放到 tool_use.input 里
    """
    msg_user = USER_TEMPLATE.format(word=word, zh=zh_def)

    tool = {
      "name": "TermResult",
      "description": "Return the required structured fields for the term as the tool input; do not chat.",
      "input_schema": TERM_RESULT_SCHEMA["schema"],  # 必须是纯 schema 对象
    }

    kwargs = {
      "model": self.model,
      "system": SYSTEM_PROMPT,
      "messages": [{"role": "user", "content": msg_user}],
      "max_tokens": self.max_tokens,   # Anthropic 必填
      "tools": [tool],
      # 强制调用该工具，确保输出严格是 schema 结构（JSON 模式）
      "tool_choice": {"type": "tool", "name": "TermResult"},
    }
    if self.temperature is not None:
      kwargs["temperature"] = self.temperature

    try:
      resp = self.client.messages.create(**kwargs)
    except APIError as e:
      # 极端情况下某些老环境不接受 tool_choice；降级取消强制，但仍保留 tools
      if "tool_choice" in str(e):
        kwargs.pop("tool_choice", None)
        resp = self.client.messages.create(**kwargs)
      else:
        raise

    # 解析 tool_use 区块：Claude 会把结构化字段放在 block.input 中
    for block in (resp.content or []):
      # SDK 的 block 可能是对象也可能是 dict，做两种方式兼容
      btype = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")
      bname = getattr(block, "name", None) if hasattr(block, "name") else block.get("name")
      if btype == "tool_use" and bname == "TermResult":
        binput = getattr(block, "input", None) if hasattr(block, "input") else block.get("input")
        if isinstance(binput, dict):
          return binput

    # 容错：若未见 tool_use，则尝试从纯文本里切 JSON（理论上不应触发）
    text_parts = []
    for block in (resp.content or []):
      if hasattr(block, "type") and block.type == "text" and hasattr(block, "text"):
        text_parts.append(block.text or "")
      elif isinstance(block, dict) and block.get("type") == "text":
        text_parts.append(block.get("text") or "")
    text = "".join(text_parts).strip()

    try:
      return json.loads(text)
    except json.JSONDecodeError:
      s, e = text.find("{"), text.rfind("}")
      if s != -1 and e != -1 and e > s:
        return json.loads(text[s:e+1])
      raise RuntimeError("Claude 未返回可解析的结构化结果。")