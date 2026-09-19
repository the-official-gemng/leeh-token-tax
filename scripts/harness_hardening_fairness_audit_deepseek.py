"""
Fairness-audit correction pass (docs/harness_hardening_log.md) -- checks
whether deepseek-flash's shipped C4 fixes (es and zh) contain general
brevity instructions that would also reduce English's own cost, not just
language-specific ones. Both templates contain "no explanation" --
classified MIXED, not clean, per the audit's Step 1.

Applies the EXACT verbatim shipped templates (harness/conditions.py's
_C4_SYSTEM_TEMPLATES_BY_LANG), formatted with lang='en', to English MGSM
questions -- including any resulting self-referential oddity (e.g. the
zh template's "never 'en'" clause when lang=en) rather than editing the
template to remove it, since the point is testing the IDENTICAL
instruction, not a cleaned-up one.

Bypasses harness/conditions.py's run_c4() dispatch (which never routes
English through these templates in the real pipeline -- English always
skips to raw passthrough) and calls harness.executor.execute() directly
with a hand-built messages list, same pattern used throughout this
project's diagnostic work. Post-hoc engineering, NOT part of the
confirmatory study. Does not touch harness/, phase3_c1/c2/c4_raw.csv, or
decision_rule_h*.csv.
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
OUT_PATH = ROOT / "results" / "harness_hardening_fairness_deepseek_en.csv"

N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
MODEL = "deepseek-flash"
PROVIDER = "deepseek"

# Verbatim from harness/conditions.py, 2026-09-19 -- copied, not
# re-imported, so this script has no dependency on that module changing
# later; if the shipped template is ever edited, this audit's own record
# stays a faithful snapshot of what it tested.
TEMPLATES = {
    "es_template_on_en": (
        "The question below is in '{lang}'. Reason in English internally; give only "
        "the final answer in '{lang}', no explanation, no English in the output. Keep "
        "numbers/formatting exact."
    ),
    "zh_template_on_en": (
        "Reason in English only -- never '{lang}'. Then give only the final answer "
        "in '{lang}', no explanation. Keep numbers/formatting exact."
    ),
}

FIELDNAMES = ["timestamp", "model", "template", "task_id", "question", "expected_answer",
              "model_answer", "prompt_tokens", "completion_tokens", "total_tokens",
              "cost_usd", "latency_s", "correct", "truncated", "error"]


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
    df = pd.read_csv(DATA_DIR / "mgsm_en.csv")
    sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)

    for template_name, template in TEMPLATES.items():
        system = template.format(lang="en")
        print(f"=== {template_name} ===\nsystem: {system}\n")
        for task_id, row in sample.iterrows():
            q, expected = row[QUESTION_COL], row[ANSWER_COL]
            messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
            out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                   "template": template_name, "task_id": task_id, "question": q,
                   "expected_answer": expected, "model_answer": None, "prompt_tokens": None,
                   "completion_tokens": None, "total_tokens": None, "cost_usd": None,
                   "latency_s": None, "correct": None, "truncated": None, "error": None}
            exec_result = execute(MODEL, PROVIDER, messages)
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
        print(f"[{template_name}] {len(sample)} done")
    print(f"Done. Results -> {OUT_PATH}")
