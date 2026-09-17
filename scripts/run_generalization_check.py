"""
scripts/run_generalization_check.py -- exploratory spot-check, NOT part of
the frozen Phase 1 design (see docs/methodology-notes.md's "Generalization
spot-check" section for the full caveat).

Tests whether deepseek-flash's real baseline token tax and gpt-5.6-luna's
near-null tax (both already measured in Phase 1 -- results/phase1_raw.csv)
generalize across tokenizers, by running two more cheap-tier models
(Qwen3.5-Flash, gemini-2.5-flash-lite) through a small MGSM-only spot
check. Does NOT re-run gpt-5.6-luna/deepseek-flash -- their Phase 1 data
is the reference this compares against.

Does NOT modify run_phase1.py, harness/, run_phase3.py, or
results/phase1_raw.csv. Copies run_phase1.py's call_model() PATTERN (same
shape: client + chat.completions.create + usage extraction) rather than
importing it, since the two new providers need base_url/pricing config
run_phase1.py's get_client()/PRICES have no slots for, and extending
those is out of scope here (editing run_phase1.py is explicitly off the
table for this task).

N=30/language/model (not Phase 1's N=50 -- a spot-check, stated
explicitly wherever results are reported), MGSM only, en/es/zh (no
Arabic -- matches Phase 1's MGSM scope exactly, same reason logged in
pre_registration.md's Amendments Log: juletxara/mgsm has no 'ar' config).
Reuses the exact same MGSM data files, question/answer columns, and
is_correct() exact-match logic as Phase 1, unchanged.
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
RESULTS_PATH = ROOT / "results" / "generalization_check.csv"

SEED = 42            # own reproducibility, NOT paired against Phase 1's task_ids -- this is an independent sample
N_PER_LANG = 30
LANGS = ["en", "es", "zh"]
HARD_TIMEOUT_S = 120  # same value Phase 1 settled on (see methodology-notes.md) -- consistency, not that MGSM tends to need it

QUESTION_COL = "question"
ANSWER_COL = "answer_number"

# Pricing verified 2026-09-15 against each provider's own official pricing
# page (ai.google.dev/gemini-api/docs/pricing; alibabacloud.com/help/en/
# model-studio/model-pricing, Singapore/international tier) -- not
# third-party aggregators, same discipline as Phase 1's PRICES dict.
# base_url for qwen3.5-flash: DashScope's official docs describe a newer
# workspace-ID-scoped MaaS endpoint AND the long-standing simple
# dashscope[-intl].aliyuncs.com/compatible-mode/v1 form inconsistently
# across pages; used the latter (matches the long-standing DashScope
# convention and the form the task specified as "likely") and verified it
# with a live smoke-test call before running the real batch, rather than
# trusting any single doc source.
MODELS = [
    {
        "name": "qwen3.5-flash",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "QWEN_API_KEY",  # .env already has this name -- not DASHSCOPE_API_KEY as originally specified
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
    },
    {
        # gemini-2.5-flash-lite (as originally specified) is retired --
        # Google's API 404s and points to this model instead ("no longer
        # available to new users... use models/gemini-3.5-flash-lite").
        # Confirmed via smoke test; pricing re-verified for THIS model
        # specifically (standard tier) -- do not assume it matches
        # 2.5-flash-lite's rate, it doesn't ($0.30/$2.50 vs $0.10/$0.40).
        "name": "gemini-3.5-flash-lite",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "input_per_1m": 0.30,
        "output_per_1m": 2.50,
    },
]

_clients = {}


def get_client(model_cfg: dict) -> OpenAI:
    name = model_cfg["name"]
    if name not in _clients:
        key = os.getenv(model_cfg["api_key_env"])
        if not key:
            raise RuntimeError(f"{model_cfg['api_key_env']} not set (see .env)")
        _clients[name] = OpenAI(api_key=key, base_url=model_cfg["base_url"], timeout=60.0, max_retries=2)
    return _clients[name]


def cost_usd(model_cfg: dict, prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * model_cfg["input_per_1m"] / 1_000_000
            + completion_tokens * model_cfg["output_per_1m"] / 1_000_000)


def _call(model_cfg: dict, question: str) -> dict:
    client = get_client(model_cfg)
    start = time.monotonic()
    resp = client.chat.completions.create(
        model=model_cfg["name"],
        messages=[{"role": "user", "content": question}],
    )
    latency_s = time.monotonic() - start
    choice = resp.choices[0]
    usage = resp.usage
    return {
        "answer_text": choice.message.content,
        "finish_reason": choice.finish_reason,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "latency_s": latency_s,
    }


def call_model_with_hard_timeout(model_cfg: dict, question: str) -> dict:
    ex = ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_call, model_cfg, question)
    try:
        return future.result(timeout=HARD_TIMEOUT_S)
    finally:
        ex.shutdown(wait=False)


def is_correct(model_answer, expected) -> bool:
    if model_answer is None or expected is None:
        return False
    return str(expected).strip().lower() in model_answer.strip().lower()


FIELDNAMES = [
    "timestamp", "model", "provider", "dataset", "subset", "language",
    "task_id", "repeat_index", "question", "expected_answer", "model_answer",
    "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
    "latency_s", "correct", "truncated", "error",
]


def append_row(row: dict):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def load_completed_keys() -> set:
    if not RESULTS_PATH.exists():
        return set()
    df = pd.read_csv(RESULTS_PATH)
    ok = df[df["error"].isna()]
    return set(zip(ok["model"], ok["language"], ok["task_id"].astype(str)))


_completed = load_completed_keys()


def run_one(model_cfg: dict, language: str, task_id, question: str, expected_answer):
    key = (model_cfg["name"], language, str(task_id))
    if key in _completed:
        return

    row = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model_cfg["name"], "provider": "openai_compatible",
        "dataset": "MGSM", "subset": None, "language": language,
        "task_id": task_id, "repeat_index": 1,
        "question": question, "expected_answer": expected_answer, "model_answer": None,
        "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
        "cost_usd": None, "latency_s": None, "correct": None, "truncated": None, "error": None,
    }
    try:
        result = call_model_with_hard_timeout(model_cfg, question)
        row["model_answer"] = result["answer_text"]
        row["prompt_tokens"] = result["prompt_tokens"]
        row["completion_tokens"] = result["completion_tokens"]
        row["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
        row["latency_s"] = result["latency_s"]
        row["truncated"] = (result["finish_reason"] == "length")
        row["cost_usd"] = cost_usd(model_cfg, result["prompt_tokens"], result["completion_tokens"])
        row["correct"] = is_correct(result["answer_text"], expected_answer)
    except FutureTimeoutError:
        row["error"] = f"Hard timeout: no response within {HARD_TIMEOUT_S}s (thread abandoned)"
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"

    append_row(row)
    if row["error"] is None:
        _completed.add(key)


def run():
    for lang in LANGS:
        path = DATA_DIR / f"mgsm_{lang}.csv"
        if not path.exists():
            print(f"[mgsm/{lang}] SKIPPED -- {path} not found, run download_data.py first")
            continue
        df = pd.read_csv(path)
        sample = df.sample(n=min(N_PER_LANG, len(df)), random_state=SEED)

        for model_cfg in MODELS:
            for task_id, row in sample.iterrows():
                run_one(model_cfg, lang, task_id, row[QUESTION_COL], row[ANSWER_COL])
        print(f"[mgsm/{lang}] {len(sample)} tasks x {len(MODELS)} models logged")


if __name__ == "__main__":
    run()
    print(f"\nDone. Results -> {RESULTS_PATH}")
