"""
Harness-hardening track extension to qwen3.5-flash/zh
(docs/harness_hardening_log.md) -- post-hoc engineering, NOT part of the
confirmatory study, NOT part of the frozen Phase 1/3 design.

Does not touch harness/, run_phase1.py, run_phase3.py, or any
deepseek-flash/gpt-5.6-luna/gemini-3.5-flash-lite results file.

Diagnosis: qwen3.5-flash exposes a `reasoning_content` field (like
deepseek-flash) that is ALREADY in English by default (100% compliance,
N=8 checked) -- the inflation is not a language-compliance problem but
an excessive REASONING LENGTH problem (reasoning_tokens averaging
~85-95% of completion_tokens, frequently 1000-6000+ tokens of repetitive
back-and-forth on a single MGSM problem). Fix targets conciseness
directly, not language.

EN baseline reused from results/harness_hardening_zh_baseline.csv
(already collected, same seed/N=50) -- only the zh-fix draw is new here.
"""
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_PATH = ROOT / "results" / "harness_hardening_qwen_zh_fix.csv"

SEED = 42
N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
HARD_TIMEOUT_S = 120  # raised from 60 -- qwen's own reasoning can run long even on the fix

MODEL_NAME = "qwen3.5-flash"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
API_KEY_ENV = "QWEN_API_KEY"
INPUT_PER_1M = 0.10
OUTPUT_PER_1M = 0.40

FIX_TEMPLATE = ("Reason briefly and directly -- do not second-guess yourself or explore "
                 "alternative interpretations. Reach a conclusion in a few steps. Give the "
                 "final answer in '{lang}'.")

FIELDNAMES = ["timestamp", "model", "language", "task_id", "question", "expected_answer",
              "model_answer", "prompt_tokens", "completion_tokens", "reasoning_tokens",
              "total_tokens", "cost_usd", "latency_s", "correct", "truncated", "error"]

_client = None


def get_client():
    global _client
    if _client is None:
        key = os.getenv(API_KEY_ENV)
        if not key:
            raise RuntimeError(f"{API_KEY_ENV} not set")
        _client = OpenAI(api_key=key, base_url=BASE_URL, timeout=120.0, max_retries=2)
    return _client


def cost_usd(p, c):
    return p * INPUT_PER_1M / 1e6 + c * OUTPUT_PER_1M / 1e6


def _call(messages):
    client = get_client()
    resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
    choice = resp.choices[0]
    details = resp.usage.completion_tokens_details
    rt = details.reasoning_tokens if details else None
    return {"answer_text": choice.message.content, "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens, "reasoning_tokens": rt,
            "finish_reason": choice.finish_reason}


def call_with_timeout(messages):
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_call, messages)
    try:
        return fut.result(timeout=HARD_TIMEOUT_S)
    except FutureTimeoutError:
        return {"error": f"Hard timeout: no response within {HARD_TIMEOUT_S}s"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        ex.shutdown(wait=False)


def is_correct(ans, expected):
    if ans is None or expected is None:
        return False
    return str(expected).strip().lower() in str(ans).strip().lower()


def load_completed():
    if not OUT_PATH.exists():
        return set()
    df = pd.read_csv(OUT_PATH)
    done = df[df.error.isna()]
    return {str(r.task_id) for _, r in done.iterrows()}


def append_row(row):
    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    completed = load_completed()
    df = pd.read_csv(DATA_DIR / "mgsm_zh.csv")
    sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)

    for round_num in range(1, 4):
        print(f"--- round {round_num} ---")
        for task_id, row in sample.iterrows():
            if str(task_id) in completed:
                continue
            q, expected = row[QUESTION_COL], row[ANSWER_COL]
            system = FIX_TEMPLATE.format(lang="zh")
            out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL_NAME,
                   "language": "zh", "task_id": task_id, "question": q, "expected_answer": expected,
                   "model_answer": None, "prompt_tokens": None, "completion_tokens": None,
                   "reasoning_tokens": None, "total_tokens": None, "cost_usd": None,
                   "latency_s": None, "correct": None, "truncated": None, "error": None}
            start = time.monotonic()
            result = call_with_timeout([{"role": "system", "content": system}, {"role": "user", "content": q}])
            out["latency_s"] = time.monotonic() - start
            if "error" in result:
                out["error"] = result["error"]
            else:
                out["model_answer"] = result["answer_text"]
                out["prompt_tokens"] = result["prompt_tokens"]
                out["completion_tokens"] = result["completion_tokens"]
                out["reasoning_tokens"] = result["reasoning_tokens"]
                out["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
                out["cost_usd"] = cost_usd(result["prompt_tokens"], result["completion_tokens"])
                out["truncated"] = (result["finish_reason"] == "length")
                out["correct"] = is_correct(result["answer_text"], expected)
                completed.add(str(task_id))
            append_row(out)
        deficit = N_PROBLEMS - len(completed)
        print(f"deficit: {deficit}")
        if deficit == 0:
            break
    print(f"Done. Results -> {OUT_PATH}")
