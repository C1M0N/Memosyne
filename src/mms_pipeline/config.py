from dataclasses import dataclass
from zoneinfo import ZoneInfo
from datetime import datetime
import os

NY_TZ = ZoneInfo("America/New_York")

def _env(key: str, default: str | None = None) -> str | None:
  return os.getenv(key, default)

@dataclass
class RunConfig:
  # 必填路径
  input_csv: str
  termlist_csv: str

  # 可选
  output_dir: str = "data/output"

  # 批次元信息
  start_memo: int = 1
  batch_run: int = 1
  note: str = ""

  # 文件名里展示的“模型别名”，以及**真正调用 API 的模型 ID**
  model_name: str = _env("MODEL_NAME", "o4mini") or "o4mini"
  model: str = _env("MODEL_ID", "gpt-4o-mini") or "gpt-4o-mini"   # ← 新增这个字段

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