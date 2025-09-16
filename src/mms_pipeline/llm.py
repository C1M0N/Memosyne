import json
import time
from typing import Optional
from openai import OpenAI, APIError, RateLimitError

from .prompts import system_message, user_message

def call_openai_once(client: OpenAI, model: str, temperature: float,
    word: str, zhdef: str, cnTags: list[str], prettyGloss: str) -> dict:
  sys = system_message()
  usr = user_message(word, zhdef, cnTags, prettyGloss)
  resp = client.chat.completions.create(
    model=model,
    messages=[
      {"role": "system", "content": sys},
      {"role": "user", "content": usr},
    ],
    temperature=temperature,
    response_format={"type": "json_object"},
  )
  text = resp.choices[0].message.content.strip()
  return json.loads(text)

def call_openai_with_retry(client: OpenAI, model: str, temperature: float,
    word: str, zhdef: str, cnTags: list[str], prettyGloss: str,
    max_retries: int = 2) -> dict:
  last_err: Optional[Exception] = None
  for attempt in range(max_retries + 1):
    try:
      return call_openai_once(client, model, temperature, word, zhdef, cnTags, prettyGloss)
    except (APIError, RateLimitError) as e:
      last_err = e
      time.sleep(2 + attempt)
    except json.JSONDecodeError as e:
      last_err = e
      time.sleep(1)
  raise RuntimeError(f"OpenAI call failed after retries: {last_err}")