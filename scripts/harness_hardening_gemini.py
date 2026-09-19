"""
Harness-hardening track extension to gemini-3.5-flash-lite/es
(docs/harness_hardening_log.md) -- post-hoc engineering, NOT part of the
confirmatory study, NOT part of the frozen Phase 1/3 design.

Does not touch harness/, run_phase1.py, run_phase3.py, or any
deepseek-flash/gpt-5.6-luna results file. Standalone, matching
run_generalization_check.py's precedent for this model (separate
provider/pricing config, since run_phase1.py has no slot for it).

Draws a FRESH N=50 sample using Phase 1's own MGSM seed/sampling
(SEED=42, MGSM_N_PROBLEMS=50, same data/mgsm_<lang>.csv files) rather
than reusing the original N=30 generalization spot-check's independent
sample, so the EN baseline and the ES fix test are paired on identical
task_ids -- required for a real per-task cost ratio, and consistent with
every other cost-ratio computation in this project.

Diagnosis (see docs/harness_hardening_log.md): gemini-3.5-flash-lite
exposes no reasoning_content/completion_tokens_details field at all --
its cost inflation is visible-verbosity (step-by-step markdown answers
in BOTH languages), not hidden reasoning. Fix targets that directly, no
"reason in English internally" clause (not diagnosed as relevant for
this model).
"""

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

SEED = 42
N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
HARD_TIMEOUT_S = 60

MODEL_NAME = "gemini-3.5-flash-lite"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
API_KEY_ENV = "GEMINI_API_KEY"
INPUT_PER_1M = 0.30
OUTPUT_PER_1M = 2.50

# v1 (below, now superseded in this script -- kept in the results file's
# "fix" rows from the v1 run, distinguishable by output filename) caused
# a severe accuracy collapse (es 90.0%->74.0%, en 92.0%->66.0%) by
# suppressing this model's visible reasoning entirely -- unlike
# deepseek-flash, this model has no separate hidden reasoning channel,
# so "no explanation" removes its actual working, not just its
# presentation. v2 permits brief reasoning, targeting only the verbose
# markdown formatting (headers/bullets/bold) diagnosed as part of the
# inflation, not the reasoning process itself.
FIX_TEMPLATE_V1 = ("Give only the final answer to the question below, in '{lang}'. No "
                    "step-by-step explanation, no headers, no bullet points. Keep "
                    "numbers/formatting exact.")
FIX_TEMPLATE = ("Answer the question below in '{lang}'. You may reason briefly, but "
                 "keep it to 1-2 short sentences -- no headers, no bullet points, no "
                 "bold formatting. State the final answer clearly.")

FIELDNAMES = ["timestamp", "model", "language", "mode", "task_id", "question",
              "expected_answer", "model_answer", "prompt_tokens", "completion_tokens",
              "total_tokens", "cost_usd", "latency_s", "correct", "truncated", "error"]

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        import os
        key = os.getenv(API_KEY_ENV)
        if not key:
            raise RuntimeError(f"{API_KEY_ENV} not set (see .env)")
        _client = OpenAI(api_key=key, base_url=BASE_URL, timeout=60.0, max_retries=2)
    return _client


def cost_usd(prompt_tokens, completion_tokens):
    return prompt_tokens * INPUT_PER_1M / 1e6 + completion_tokens * OUTPUT_PER_1M / 1e6


def _call(messages):
    client = get_client()
    resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
    choice = resp.choices[0]
    return {
        "answer_text": choice.message.content,
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "finish_reason": choice.finish_reason,
    }


def call_with_hard_timeout(messages):
    ex = ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_call, messages)
    try:
        return future.result(timeout=HARD_TIMEOUT_S)
    except FutureTimeoutError:
        return {"error": f"Hard timeout: no response within {HARD_TIMEOUT_S}s"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        ex.shutdown(wait=False)


def is_correct(model_answer, expected):
    if model_answer is None or expected is None:
        return False
    return str(expected).strip().lower() in str(model_answer).strip().lower()


def load_completed(path):
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    done = df[df.error.isna()]
    return {(str(r.language), str(r.mode), str(r.task_id)) for _, r in done.iterrows()}


def append_row(path, row):
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


def run_mode(path, language, mode, sample, completed):
    for task_id, row in sample.iterrows():
        key = (language, mode, str(task_id))
        if key in completed:
            continue
        question = row[QUESTION_COL]
        expected = row[ANSWER_COL]
        if mode == "baseline":
            messages = [{"role": "user", "content": question}]
        else:  # "fix"
            system = FIX_TEMPLATE.format(lang=language)
            messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]

        out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL_NAME,
               "language": language, "mode": mode, "task_id": task_id, "question": question,
               "expected_answer": expected, "model_answer": None, "prompt_tokens": None,
               "completion_tokens": None, "total_tokens": None, "cost_usd": None,
               "latency_s": None, "correct": None, "truncated": None, "error": None}
        start = time.monotonic()
        result = call_with_hard_timeout(messages)
        out["latency_s"] = time.monotonic() - start
        if "error" in result:
            out["error"] = result["error"]
        else:
            out["model_answer"] = result["answer_text"]
            out["prompt_tokens"] = result["prompt_tokens"]
            out["completion_tokens"] = result["completion_tokens"]
            out["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
            out["cost_usd"] = cost_usd(result["prompt_tokens"], result["completion_tokens"])
            out["truncated"] = (result["finish_reason"] == "length")
            out["correct"] = is_correct(result["answer_text"], expected)
        append_row(path, out)
        if out["error"] is None:
            completed.add(key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", type=str, default="baseline,fix",
                         help="Comma-separated: baseline (raw, no system prompt) and/or fix (verbosity-suppression prompt).")
    parser.add_argument("--languages", type=str, default="en,es")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--retry-until-filled", action="store_true")
    parser.add_argument("--max-rounds", type=int, default=8)
    args = parser.parse_args()

    out_path = RESULTS_DIR / args.output
    modes = args.modes.split(",")
    langs = args.languages.split(",")
    completed = load_completed(out_path)

    round_num = 0
    while True:
        round_num += 1
        print(f"--- round {round_num} ---")
        for lang in langs:
            df = pd.read_csv(DATA_DIR / f"mgsm_{lang}.csv")
            sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
            for mode in modes:
                run_mode(out_path, lang, mode, sample, completed)
                print(f"[{lang}/{mode}] done this round")
        deficit = 0
        for lang in langs:
            for mode in modes:
                n = sum(1 for k in completed if k[0] == lang and k[1] == mode)
                deficit += max(0, N_PROBLEMS - n)
        print(f"deficit: {deficit}")
        if deficit == 0 or not args.retry_until_filled or round_num >= args.max_rounds:
            break

    print(f"Done. Results -> {out_path}")
