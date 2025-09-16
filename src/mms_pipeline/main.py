import argparse
import os
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

from .config import RunConfig, get_api_key
from .io_utils import read_input_csv, write_output_csv, ensure_dir
from .termlist import load_termlist
from .schema import build_schema, validate_payload
from .llm import call_openai_with_retry
from .postprocess import postprocess_record
from .ids import generate_memo_ids, build_batch_id, format_batch_note, build_wmpair

def parse_args():
  ap = argparse.ArgumentParser("MMS V3 local pipeline")
  ap.add_argument("--input", required=True, help="input CSV with Word,ZhDef")
  ap.add_argument("--termlist", required=True, help="term_list_v1.csv path")
  ap.add_argument("--output-dir", default="data/output", help="output directory")
  ap.add_argument("--start-memo", type=int, required=True, help="current total in deck (e.g., 2700)")
  ap.add_argument("--batch-run", type=int, required=True, help="batch index of the day (1..26)")
  ap.add_argument("--note", default="", help="batch note text")
  ap.add_argument("--model-name", default=os.getenv("MODEL_NAME", "o4mini"), help="model name for file naming")
  ap.add_argument("--model", default=os.getenv("MODEL_ID", "gpt-4o-mini"), help="OpenAI model id to call")
  ap.add_argument("--date", dest="batch_date_YYMMDD", default=None, help="override date YYMMDD")
  return ap.parse_args()

def main():
  load_dotenv()
  args = parse_args()
  cfg = RunConfig(
    input_csv=args.input,
    termlist_csv=args.termlist,
    output_dir=args.output_dir,
    start_memo=args.start_memo,
    batch_run=args.batch_run,
    note=args.note,
    model_name=args.model_name,
    batch_date_YYMMDD=args.batch_date_YYMMDD,
  )

  api_key = get_api_key()
  client = OpenAI(api_key=api_key)

  # 1) 读取输入与词表
  items = read_input_csv(cfg.input_csv)
  catalog = load_termlist(cfg.termlist_csv)
  cnTags = catalog["cnTags"]
  prettyGloss = catalog["prettyGloss"]

  # 2) JSON Schema（动态注入 Tag enum）
  schema = build_schema(cnTags)

  # 3) 调 LLM 并后处理
  processed = []
  for row in tqdm(items, desc="LLM"):
    word = row["Word"]
    zh = row["ZhDef"]
    raw = call_openai_with_retry(
      client, cfg.model, cfg.temperature, word, zh, cnTags, prettyGloss, cfg.max_retries
    )
    # 验证（先用 schema，Tag 枚举已注入）
    errs = validate_payload(raw, schema)
    # 若违反“IPA 必须有”的硬规则（除了 abbr.），schema 无法判断，只在 postprocess 校
    # 这里若 errs 非空，你也可选择重试，这里打印记录继续
    if errs:
      # 简单记录（你也可在这里再触发一次重试）
      print(f"[warn] schema errors for '{word}': {errs}")
    final = postprocess_record(raw, word, zh, catalog, enforce_phrase_pos=True)
    processed.append(final)

  # 4) 批次/ID/补列与导出
  count = len(processed)
  memo_ids = generate_memo_ids(cfg.start_memo, count)
  batch_id = build_batch_id(cfg.batch_date(), cfg.batch_run, count)
  batch_note = format_batch_note(cfg.note)

  out_rows = []
  for i, rec in enumerate(processed):
    out_rows.append({
      "WMpair":   build_wmpair(rec["Word"], rec["ZhDef"]),
      "MemoID":   memo_ids[i],
      "Word":     rec["Word"],
      "ZhDef":    rec["ZhDef"],
      "IPA":      rec["IPA"],
      "POS":      rec["POS"],
      "Tag":      rec["Tag"],
      "Rarity":   rec["Rarity"],
      "EnDef":    rec["EnDef"],
      "PPfix":    rec["PPfix"],
      "PPmeans":  rec["PPmeans"],
      "BatchID":  batch_id,
      "BatchNote":batch_note,
    })

  filename = f"{batch_id}_MMS_V3_{cfg.model_name}.csv"
  ensure_dir(cfg.output_dir)
  path = write_output_csv(out_rows, cfg.output_dir, filename)
  print(f"✅ Done. Wrote: {path}")

if __name__ == "__main__":
  main()