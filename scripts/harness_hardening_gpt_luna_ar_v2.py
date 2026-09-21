"""
Part 3 of the four-part follow-up (docs/harness_hardening_log.md): retest
gpt-5.6-luna/ar under C2 with the v2 lean-prompt Packer template (already
the LIVE default in harness/packer.py -- no code change needed here, this
is purely a new data-collection run). ar was never retested with v2
because v2's scope was explicitly MGSM-only and ar has no MGSM arm.

Reuses run_phase3.py's exact MAPS sampling logic (same SEED, same
MAPS_N_TASKS/MAPS_N_REPEATS, same task_id derivation) so task_ids align
with the EXISTING English MAPS C2 rows already in phase3_c2_raw.csv --
English is not re-run here (architecturally unaffected by the Packer
template version, since English skips Packer entirely under C2, verified
directly from harness/packer.py's own code this session).

Math scoring replicates the historical \\boxed{} extraction fix
(methodology-notes.md, "boxed-answer scoring fix") since run_phase3.py's
own is_correct() is the naive substring-match version that scores Math
as always-wrong -- that fix was applied as a one-time data patch to the
existing guardrail files, never merged into code, so it must be
reproduced here to score new Math rows correctly. Verified against 10
known-correct phase1_raw.csv Math rows before use (10/10 match).

Output: results/harness_hardening_gpt_luna_ar_v2.csv -- new, separate.
Does NOT touch phase3_c1_raw.csv, phase3_c2_raw.csv, or any guardrail
file. Post-hoc, not part of the confirmatory study.
"""
import csv
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_phase1 import SEED, DATA_DIR
from harness.conditions import run_condition

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "results" / "harness_hardening_gpt_luna_ar_v2.csv"

MODEL = "gpt-5.6-luna"
PROVIDER = "openai"
MAPS_N_TASKS = 10
MAPS_N_REPEATS = 2
MAX_TOKENS_MAPS = 32768
QUESTION_COL = {"Math": "problem", "GAIA": "Question"}
ANSWER_COL = {"Math": "solution", "GAIA": "Final answer"}

_BOXED_RE = re.compile(r'\\boxed\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}')


def is_correct(subset, model_answer, expected_answer):
    if model_answer is None or expected_answer is None:
        return False
    if subset == "Math":
        m = _BOXED_RE.findall(str(expected_answer))
        if not m:
            return str(expected_answer).strip().lower() in model_answer.strip().lower()
        return m[-1].strip() in model_answer
    return str(expected_answer).strip().lower() in model_answer.strip().lower()


FIELDNAMES = ["timestamp", "condition", "model", "provider", "dataset", "subset", "language",
              "task_id", "repeat_index", "question", "expected_answer", "model_answer",
              "detected_language", "task_type", "route_through_english",
              "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
              "latency_s", "correct", "truncated", "error", "reasoning_content", "reasoning_tokens"]


def append_row(row):
    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    for subset in ["Math", "GAIA"]:
        path = DATA_DIR / f"maps_{subset}_Arabic.csv"
        df = pd.read_csv(path)
        if "file_name" in df.columns:
            df = df[df["file_name"].isna() | (df["file_name"] == "")]
        n = min(MAPS_N_TASKS, len(df))
        sample = df.sample(n=n, random_state=SEED)
        print(f"=== MAPS/{subset}/Arabic: {n} tasks x {MAPS_N_REPEATS} repeats ===")
        for repeat in range(1, MAPS_N_REPEATS + 1):
            for _, row in sample.iterrows():
                task_id = row["task_id"] if "task_id" in df.columns else row.name
                question = row[QUESTION_COL[subset]]
                expected = row[ANSWER_COL[subset]]
                out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "condition": "c2",
                       "model": MODEL, "provider": PROVIDER, "dataset": "MAPS", "subset": subset,
                       "language": "ar", "task_id": task_id, "repeat_index": repeat,
                       "question": question, "expected_answer": expected, "model_answer": None,
                       "detected_language": None, "task_type": None, "route_through_english": None,
                       "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                       "cost_usd": None, "latency_s": None, "correct": None, "truncated": None,
                       "error": None, "reasoning_content": None, "reasoning_tokens": None}
                try:
                    result = run_condition("c2", MODEL, PROVIDER, question,
                                            task_type_hint="agentic", base_max_tokens=MAX_TOKENS_MAPS)
                    out["model_answer"] = result.final_answer
                    out["detected_language"] = result.detected_language
                    out["task_type"] = result.task_type
                    out["route_through_english"] = result.route_through_english
                    out["prompt_tokens"] = result.prompt_tokens
                    out["completion_tokens"] = result.completion_tokens
                    out["total_tokens"] = result.total_tokens
                    out["cost_usd"] = result.cost_usd
                    out["latency_s"] = result.latency_s
                    out["truncated"] = result.truncated
                    out["correct"] = is_correct(subset, result.final_answer, expected)
                    out["error"] = result.error
                    out["reasoning_content"] = result.reasoning_content
                    out["reasoning_tokens"] = result.reasoning_tokens
                except Exception as e:
                    out["error"] = f"{type(e).__name__}: {e}"
                append_row(out)
        print(f"[{subset}] done")
    print(f"Done. Results -> {OUT_PATH}")
