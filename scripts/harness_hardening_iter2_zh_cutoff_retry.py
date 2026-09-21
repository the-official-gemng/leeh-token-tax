"""
Iteration 2 continued (docs/harness_hardening_log.md): bounded, early-
cutoff streaming retry for deepseek-flash/zh, via
harness.executor.execute_with_cutoff_retry(). Same shipped zh template
(brevity-on-both-arms) as every recent entry, cutoff_tokens=1000
(calibrated from the pooled completion-length distribution -- see the
log entry), applied identically to zh and en arms. Post-hoc engineering,
NOT part of the confirmatory study. Does not touch harness/conditions.py,
phase3_c1/c2/c4_raw.csv, or decision_rule_h*.csv.

Usage: python scripts/harness_hardening_iter2_zh_cutoff_retry.py [draw_suffix]
  draw_suffix (optional): appended to the output filename, e.g. "draw2"
  for the reproducibility re-run. Same SEED, same 50 questions each time
  (this project's standing convention -- "independent draw" means fresh
  API calls on the same fixed sample, not a new sample).
"""
import csv
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_phase1 import SEED, cost_usd
from harness.executor import execute_with_cutoff_retry

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
MODEL = "deepseek-flash"
PROVIDER = "deepseek"
CUTOFF_TOKENS = 1000

SHIPPED_ZH_TEMPLATE = (
    "Reason in English only -- never '{lang}'. Then give only the final "
    "answer in '{lang}', no explanation. Keep numbers/formatting exact."
)
ARMS = ["zh", "en"]

FIELDNAMES = ["timestamp", "model", "cutoff_tokens", "arm_language", "task_id",
              "question", "expected_answer", "model_answer", "prompt_tokens",
              "completion_tokens", "total_tokens", "cost_usd", "latency_s",
              "correct", "truncated", "error", "retry_fired", "cutoff_hit_first",
              "cutoff_hit_second", "est_completion_tokens_first", "wasted_cost_usd"]


def is_correct(ans, expected):
    if ans is None or expected is None:
        return False
    return str(expected).strip().lower() in str(ans).strip().lower()


def append_row(out_path, row):
    is_new = not out_path.exists()
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    suffix = f"_{sys.argv[1]}" if len(sys.argv) > 1 else ""
    out_path = ROOT / "results" / f"harness_hardening_iter2_zh_cutoff_retry{suffix}.csv"
    for arm_lang in ARMS:
        df = pd.read_csv(DATA_DIR / f"mgsm_{arm_lang}.csv")
        sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
        system = SHIPPED_ZH_TEMPLATE.format(lang=arm_lang)
        print(f"=== arm={arm_lang} cutoff={CUTOFF_TOKENS} ===\nsystem: {system}\n")
        for task_id, row in sample.iterrows():
            q, expected = row[QUESTION_COL], row[ANSWER_COL]
            messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
            out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                   "cutoff_tokens": CUTOFF_TOKENS, "arm_language": arm_lang, "task_id": task_id,
                   "question": q, "expected_answer": expected, "model_answer": None,
                   "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                   "cost_usd": None, "latency_s": None, "correct": None, "truncated": None,
                   "error": None, "retry_fired": None, "cutoff_hit_first": None,
                   "cutoff_hit_second": None, "est_completion_tokens_first": None,
                   "wasted_cost_usd": None}
            r = execute_with_cutoff_retry(MODEL, PROVIDER, messages, cutoff_tokens=CUTOFF_TOKENS)
            if r.error:
                out["error"] = r.error
                out["retry_fired"] = r.retry_fired
                out["cutoff_hit_first"] = r.cutoff_hit_first
            else:
                out["model_answer"] = r.answer_text
                out["prompt_tokens"] = r.prompt_tokens
                out["completion_tokens"] = r.completion_tokens
                out["total_tokens"] = r.total_tokens
                out["cost_usd"] = r.cost_usd
                out["latency_s"] = r.latency_s
                out["truncated"] = r.truncated
                out["correct"] = is_correct(r.answer_text, expected)
                out["retry_fired"] = r.retry_fired
                out["cutoff_hit_first"] = r.cutoff_hit_first
                out["cutoff_hit_second"] = r.cutoff_hit_second
                out["est_completion_tokens_first"] = r.est_completion_tokens_first
                out["wasted_cost_usd"] = r.wasted_cost_usd
            append_row(out_path, out)
        print(f"[{arm_lang}] {len(sample)} done")
    print(f"Done. Results -> {out_path}")
