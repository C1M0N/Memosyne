from dataclasses import dataclass
from zoneinfo import ZoneInfo
from datetime import datetime
import os

NY_TZ = ZoneInfo("America/New_York")

@dataclass
class RunConfig:
  input_csv: str
  termlist_csv: str
  output_dir: str
  start_memo: int
  batch_run: int  # 1..26 -> A..Z
  note: str
  model_name: str | None = None
  batch_date_YYMMDD: str | None = None
  enforce_phrase_pos: bool = True          # Word 含空格 → P.
  max_retries: int = 2                     # LLM 失败/JSON失败的重试
  temperature: float = 0.0

  def batch_date(self) -> str:
    if self.batch_date_YYMMDD:
      return self.batch_date_YYMMDD
    now = datetime.now(NY_TZ)
    return now.strftime("%y%m%d")

def get_api_key() -> str:
  key = os.getenv("OPENAI_API_KEY")
  if not key:
    raise RuntimeError("OPENAI_API_KEY not set (use .env or environment).")
  return key