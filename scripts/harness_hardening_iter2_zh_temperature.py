"""
Iteration 2 continued (docs/harness_hardening_log.md): temperature sweep
on deepseek-flash/zh's current best prompt (brevity-on-both-arms), same
setting applied to zh and en arms every time. Post-hoc engineering, NOT
part of the confirmatory study. Does not touch harness/conditions.py,
phase3_c1/c2/c4_raw.csv, or decision_rule_h*.csv. harness/executor.py's
new `temperature` passthrough param (added this entry, purely additive,
same pattern as max_tokens) is exercised here for the first time.
"""
import csv
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_phase1 import SEED, cost_usd
from harness.executor import execute

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PATH = ROOT / "results" / "harness_hardening_iter2_zh_temperature.csv"

N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
MODEL = "deepseek-flash"
PROVIDER = "deepseek"

SHIPPED_ZH_TEMPLATE = (
    "Reason in English only -- never '{lang}'. Then give only the final "
    "answer in '{lang}', no explanation. Keep numbers/formatting exact."
)

SETTINGS = {
    "default": None,
    "t0.3": 0.3,
    "t0.0": 0.0,
}
ARMS = ["zh", "en"]

FIELDNAMES = ["timestamp", "model", "setting", "temperature", "arm_language",
              "task_id", "question", "expected_answer", "model_answer",
              "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
              "latency_s", "correct", "truncated", "error"]


def is_correct(ans, expected):
    if ans is None or expected is None:
        return False
    return str(expected).strip().lower() in str(ans).strip().lower()


def append_row(row):
    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    for setting_name, temp in SETTINGS.items():
        for arm_lang in ARMS:
            df = pd.read_csv(DATA_DIR / f"mgsm_{arm_lang}.csv")
            sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
            system = SHIPPED_ZH_TEMPLATE.format(lang=arm_lang)
            print(f"=== {setting_name} (temp={temp}) / arm={arm_lang} ===\nsystem: {system}\n")
            for task_id, row in sample.iterrows():
                q, expected = row[QUESTION_COL], row[ANSWER_COL]
                messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
                out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                       "setting": setting_name, "temperature": temp, "arm_language": arm_lang,
                       "task_id": task_id, "question": q, "expected_answer": expected,
                       "model_answer": None, "prompt_tokens": None, "completion_tokens": None,
                       "total_tokens": None, "cost_usd": None, "latency_s": None,
                       "correct": None, "truncated": None, "error": None}
                exec_result = execute(MODEL, PROVIDER, messages, temperature=temp)
                if exec_result.error:
                    out["error"] = exec_result.error
                else:
                    out["model_answer"] = exec_result.answer_text
                    out["prompt_tokens"] = exec_result.prompt_tokens
                    out["completion_tokens"] = exec_result.completion_tokens
                    out["total_tokens"] = exec_result.total_tokens
                    out["cost_usd"] = cost_usd(MODEL, exec_result.prompt_tokens, exec_result.completion_tokens)
                    out["latency_s"] = exec_result.latency_s
                    out["truncated"] = exec_result.truncated
                    out["correct"] = is_correct(exec_result.answer_text, expected)
                append_row(out)
            print(f"[{setting_name}/{arm_lang}] {len(sample)} done")
    print(f"Done. Results -> {OUT_PATH}")
