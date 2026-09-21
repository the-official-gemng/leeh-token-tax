"""
Iteration 2 continued (docs/harness_hardening_log.md): one more targeted
attempt at deepseek-flash/zh. Three template x cap combinations, zh arm
and English arm, same round, fresh N=50 each:
  - brevity_both: shipped zh template (incl. "no explanation"), uncapped
    -- a fresh independent draw of the CORRECTION PASS's 1.149x comparison.
  - capped_lang_only: iteration 2's lang-only template (brevity removed),
    max_tokens=8192.
  - brevity_both_capped: shipped zh template, max_tokens=8192.
Cap applied symmetrically to both arms wherever used. Post-hoc engineering,
NOT part of the confirmatory study. Does not touch harness/,
phase3_c1/c2/c4_raw.csv, or decision_rule_h*.csv.
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
OUT_PATH = ROOT / "results" / "harness_hardening_iter2_zh_capfix.csv"

N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
MODEL = "deepseek-flash"
PROVIDER = "deepseek"

SHIPPED_ZH_TEMPLATE = (
    "Reason in English only -- never '{lang}'. Then give only the final "
    "answer in '{lang}', no explanation. Keep numbers/formatting exact."
)
LANG_ONLY_ZH_TEMPLATE = (
    "Reason in English only -- never '{lang}'. Then give the final answer "
    "in '{lang}'. Keep numbers/formatting exact."
)

CAP = 8192  # comfortably above C0 zh's completed-call max (6879) and
            # iteration 2's zh_lang_only fresh-draw max (5634); matches
            # this project's own established MGSM-wide precedent
            # (methodology-notes.md, 2026-09-16 entry: MAX_TOKENS_BY_DATASET).

VERSIONS = {
    "brevity_both": {"text": SHIPPED_ZH_TEMPLATE, "max_tokens": None},
    "capped_lang_only": {"text": LANG_ONLY_ZH_TEMPLATE, "max_tokens": CAP},
    "brevity_both_capped": {"text": SHIPPED_ZH_TEMPLATE, "max_tokens": CAP},
}
ARMS = ["zh", "en"]

FIELDNAMES = ["timestamp", "model", "version", "arm_language", "max_tokens_cap",
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
    for version_name, cfg in VERSIONS.items():
        for arm_lang in ARMS:
            df = pd.read_csv(DATA_DIR / f"mgsm_{arm_lang}.csv")
            sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
            system = cfg["text"].format(lang=arm_lang)
            print(f"=== {version_name} / arm={arm_lang} / cap={cfg['max_tokens']} ===\nsystem: {system}\n")
            for task_id, row in sample.iterrows():
                q, expected = row[QUESTION_COL], row[ANSWER_COL]
                messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
                out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                       "version": version_name, "arm_language": arm_lang,
                       "max_tokens_cap": cfg["max_tokens"], "task_id": task_id,
                       "question": q, "expected_answer": expected, "model_answer": None,
                       "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                       "cost_usd": None, "latency_s": None, "correct": None, "truncated": None,
                       "error": None}
                exec_result = execute(MODEL, PROVIDER, messages, max_tokens=cfg["max_tokens"])
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
            print(f"[{version_name}/{arm_lang}] {len(sample)} done")
    print(f"Done. Results -> {OUT_PATH}")
