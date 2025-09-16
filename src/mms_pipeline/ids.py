from typing import List

def run_to_letter(n: int) -> str:
  x = max(1, min(int(n or 1), 26))
  return chr(64 + x)  # 1->A

def generate_memo_ids(start_memo: int, count: int) -> List[str]:
  base = int(start_memo)
  return [f"M{(base+i+1):06d}" for i in range(count)]

def build_batch_id(yymmdd: str, batch_run: int, count: int) -> str:
  letter = run_to_letter(batch_run)
  return f"{yymmdd}{letter}{count:03d}"

def format_batch_note(note: str) -> str:
  note = (note or "").strip()
  return f"「{note}」" if note else ""

def build_wmpair(word: str, zh: str) -> str:
  return f"{(word or '').strip()} - {(zh or '').strip()}"