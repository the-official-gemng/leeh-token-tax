"""
Part 4 of the four-part follow-up (docs/harness_hardening_log.md): does
gemini-3.5-flash-lite/es's verified fix hold on a multi-step task?

No multi-step/multi-call task has ever been tested anywhere in this
project -- confirmed directly from harness/executor.py's own docstring
and code: the tool-call loop is real and functional, but no caller
(run_phase1.py, run_phase3.py, any harness-hardening script) has ever
passed a real `tools`/`tool_executor`, including MAPS/GAIA despite its
"agentic" task_type_hint -- every call in this project has been single-
turn to date.

This pilot forces genuine multi-step execution on the SAME MGSM
es/en problem set already used throughout this project (same difficulty,
same matched translation, same fair-comparison precedent) by requiring
the model to use a calculator tool for every arithmetic operation
instead of computing mentally -- most MGSM problems need 2+ sequential
operations by construction, so this reliably produces multiple tool-call
round-trips per question. Uses the already-verified gemini-3.5-flash-lite
es v2 fix template unchanged, applied identically to both arms.

Required an infra fix first: harness/executor.py unconditionally set
reasoning_effort="none" whenever tools were passed (a gpt-5.6-luna-only
quirk), which gemini's endpoint rejects outright (400 INVALID_ARGUMENT).
Scoped to provider=="openai" this entry -- purely additive, confirmed
via a direct 2-turn tool-call smoke test before this pilot's real batch.
Also added "gemini" as a provider to run_phase1.py's get_client()/PRICES
(previously only usable via harness_hardening_gemini.py's own standalone
client) -- both purely additive, existing openai/deepseek callers
unaffected.

Post-hoc, not part of the confirmatory study. Does not touch
phase3_c1/c2/c4_raw.csv, decision_rule_h*.csv, or paper_draft.md.
"""
import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_phase1 import SEED
from harness.executor import execute

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PATH = ROOT / "results" / "harness_hardening_multistep_pilot.csv"

N_PROBLEMS = 30
MODEL = "gemini-3.5-flash-lite"
PROVIDER = "gemini"

# Same verified template as scripts/harness_hardening_gemini.py's FIX_TEMPLATE
# (v2, currently the shipped/passing fix), plus one added clause mandating
# tool use for every arithmetic step -- the only change from the already-
# verified MGSM fix.
FIX_TEMPLATE = (
    "Answer the question below in '{lang}'. You may reason briefly, but "
    "keep it to 1-2 short sentences -- no headers, no bullet points, no "
    "bold formatting. State the final answer clearly. You must use the "
    "calculator tool for every arithmetic operation in your solution -- "
    "do not compute any operation mentally, even simple ones."
)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluates a basic arithmetic expression and returns the numeric result.",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '12 * 4' or '100 - 37'"}},
            "required": ["expression"],
        },
    },
}]


def calculator(args_json):
    args = json.loads(args_json)
    expr = args["expression"]
    allowed = set("0123456789+-*/(). ")
    if not set(expr) <= allowed:
        return "error: invalid characters in expression"
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"error: {e}"


TOOL_EXECUTOR = {"calculator": calculator}

FIELDNAMES = ["timestamp", "model", "arm_language", "task_id", "question",
              "expected_answer", "model_answer", "prompt_tokens", "completion_tokens",
              "total_tokens", "cost_usd", "latency_s", "correct", "truncated",
              "tool_calls_made", "error"]


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
    for arm_lang in ["es", "en"]:
        df = pd.read_csv(DATA_DIR / f"mgsm_{arm_lang}.csv")
        sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
        system = FIX_TEMPLATE.format(lang=arm_lang)
        print(f"=== arm={arm_lang} ===\nsystem: {system}\n")
        for task_id, row in sample.iterrows():
            q, expected = row["question"], row["answer_number"]
            messages = [{"role": "system", "content": system}, {"role": "user", "content": q}]
            out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                   "arm_language": arm_lang, "task_id": task_id, "question": q,
                   "expected_answer": expected, "model_answer": None, "prompt_tokens": None,
                   "completion_tokens": None, "total_tokens": None, "cost_usd": None,
                   "latency_s": None, "correct": None, "truncated": None,
                   "tool_calls_made": None, "error": None}
            r = execute(MODEL, PROVIDER, messages, tools=TOOLS, tool_executor=TOOL_EXECUTOR)
            if r.error:
                out["error"] = r.error
                out["tool_calls_made"] = r.tool_calls_made
            else:
                out["model_answer"] = r.answer_text
                out["prompt_tokens"] = r.prompt_tokens
                out["completion_tokens"] = r.completion_tokens
                out["total_tokens"] = r.total_tokens
                out["cost_usd"] = r.cost_usd
                out["latency_s"] = r.latency_s
                out["truncated"] = r.truncated
                out["tool_calls_made"] = r.tool_calls_made
                out["correct"] = is_correct(r.answer_text, expected)
            append_row(out)
        print(f"[{arm_lang}] {len(sample)} done")
    print(f"Done. Results -> {OUT_PATH}")
