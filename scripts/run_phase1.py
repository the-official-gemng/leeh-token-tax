"""
Phase 1 baseline run — no harness, straight model calls.

Logs every field pre_registration.md requires: tokens, cost, latency,
correctness, truncation. See pre_registration.md Section 1 (currently on
branch add-prereg-content / PR #1, pending review) for the frozen config
this implements, and its Amendments Log for two dataset-availability gaps
found while building scripts/download_data.py:

  - MGSM has no 'ar' config on Hugging Face -> MGSM here runs en/es/zh only.
  - MAPS (Fujitsu-FRE/MAPS) has no Chinese split in any config -> MAPS here
    runs en/es/ar only, across the 'Math' and 'GAIA' configs (GAIA+MATH
    subsets, per Section 1; GAIA-v2-LILT is the separate trusted cross-check
    and is not part of this run block).

Run scripts/download_data.py first so data/*.csv exist.
"""

import csv
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
RESULTS_PATH = RESULTS_DIR / "phase1_raw.csv"

SEED = 42  # fixed so repeated runs sample the same tasks

# Hard wall-clock ceiling per call. The openai SDK's own `timeout=` only
# bounds a single HTTP attempt -- it does NOT bound time spent sleeping
# between retries (e.g. honoring a server-sent Retry-After on a 429), which
# is what actually caused this run to hang for 40+ minutes on a single
# deepseek-flash/zh call. Running each call in its own thread and giving up
# on the future after this many seconds bounds it regardless of what the
# SDK is doing internally. The underlying thread is abandoned, not killed
# (Python has no clean way to kill a thread) -- acceptable here since we
# only care about forward progress and an accurate error row, not reclaiming
# that thread.
#
# 120s, uniform across every dataset (not just GAIA). An earlier 30s value
# was cutting off genuine GAIA responses mid-flight (successful GAIA calls
# measured mean=18.2s/median=17.4s/max=29.5s -- right against that wall).
# One generous ceiling for everything, rather than tuning per-dataset,
# avoids re-doing this exercise for any slow outlier in MAPS/Math or MGSM
# and avoids treating datasets differently for a parameter that isn't part
# of the frozen design. See docs/methodology-notes.md.
HARD_TIMEOUT_S = 120


def call_model_with_hard_timeout(model_name: str, provider: str, question: str) -> dict:
    # A fresh single-use executor per call, not a shared persistent one --
    # a shared max_workers=1 pool would permanently wedge on the first hang
    # (its one worker never frees up), silently blocking every call after
    # it forever. shutdown(wait=False) lets a hung thread be abandoned
    # instead of blocking us on cleanup too.
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(call_model, model_name, provider, question)
    try:
        return future.result(timeout=HARD_TIMEOUT_S)
    finally:
        executor.shutdown(wait=False)

# --- Frozen config (pre_registration.md Section 1) ---------------------

MODELS = [
    {"name": "gpt-5.6-luna", "provider": "openai"},
    {"name": "deepseek-flash", "provider": "deepseek"},
]

# Pulled 2026-09-14. $ per 1M tokens.
# gpt-5.6-luna:   https://developers.openai.com/api/docs/models/gpt-5.6-luna
#                 (cached input is $0.02/1M -- not modeled here, Phase 1 calls
#                 aren't expected to hit cache in a controlled way)
# deepseek-flash: https://deepseek.ai/pricing (DeepSeek-V4-Flash). Cache-miss
#                 input rate used as the baseline ($0.0028/1M cache-hit rate
#                 not modeled, same reasoning as above). Site explicitly notes
#                 the announced peak-hour surcharge is NOT currently active --
#                 several aggregator sites (pricepertoken.com, benchlm.ai,
#                 layer3labs.io) disagree and list an active 2x peak surcharge;
#                 went with the official page over those.
PRICES = {
    "gpt-5.6-luna": {"input_per_1m": 0.20, "output_per_1m": 1.20},
    "deepseek-flash": {"input_per_1m": 0.14, "output_per_1m": 0.28},
}

MGSM_LANGS = ["en", "es", "zh"]  # 'ar' dropped -- see Amendments Log
MGSM_N_PROBLEMS = 50
MGSM_N_REPEATS = 1
MGSM_QUESTION_COL = "question"
MGSM_ANSWER_COL = "answer_number"  # numeric ground truth; 'answer' is full CoT text

MAPS_LANGS = ["English", "Spanish", "Arabic"]  # 'zh' dropped -- see Amendments Log
MAPS_LANG_CODE = {"English": "en", "Spanish": "es", "Arabic": "ar"}
MAPS_SUBSETS = ["Math", "GAIA"]
MAPS_N_TASKS = 10  # 8-10 tasks/language/subset per pre_registration.md Section 1
MAPS_N_REPEATS = 2
MAPS_QUESTION_COL = {"Math": "problem", "GAIA": "Question"}
MAPS_ANSWER_COL = {"Math": "solution", "GAIA": "Final answer"}

# --- Clients -------------------------------------------------------------

_clients = {}


def get_client(provider: str) -> OpenAI:
    if provider not in _clients:
        if provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise RuntimeError("OPENAI_API_KEY not set (see .env)")
            _clients[provider] = OpenAI(api_key=key, timeout=60.0, max_retries=2)
        elif provider == "deepseek":
            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise RuntimeError("DEEPSEEK_API_KEY not set (see .env)")
            _clients[provider] = OpenAI(
                api_key=key, base_url="https://api.deepseek.com", timeout=60.0, max_retries=2
            )
        else:
            raise ValueError(f"unknown provider: {provider}")
    return _clients[provider]


def call_model(model_name: str, provider: str, question: str) -> dict:
    client = get_client(provider)
    start = time.monotonic()
    resp = client.chat.completions.create(
        model=model_name,
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
        "total_tokens": usage.total_tokens,
        "latency_s": latency_s,
    }


def cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICES[model_name]
    assert prices["input_per_1m"] is not None and prices["output_per_1m"] is not None, (
        f"PRICES['{model_name}'] not filled in yet -- do Step 3 before running Step 4"
    )
    return (
        prompt_tokens * prices["input_per_1m"] / 1_000_000
        + completion_tokens * prices["output_per_1m"] / 1_000_000
    )


def is_correct(model_answer: str, expected: str) -> bool:
    if model_answer is None or expected is None:
        return False
    return str(expected).strip().lower() in model_answer.strip().lower()


# --- CSV logging -----------------------------------------------------------

FIELDNAMES = [
    "timestamp", "model", "provider", "dataset", "subset", "language",
    "task_id", "repeat_index", "question", "expected_answer", "model_answer",
    "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
    "latency_s", "correct", "truncated", "error",
]


def append_row(row: dict):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    is_new = not RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _row_key(model_name, dataset, subset, language, task_id, repeat_index):
    return (model_name, dataset, subset, language, str(task_id), repeat_index)


def load_completed_keys() -> set:
    """Rows already logged with no error, so a re-run after an interrupted
    batch doesn't repeat (and re-bill) successful calls."""
    if not RESULTS_PATH.exists():
        return set()
    df = pd.read_csv(RESULTS_PATH)
    done = df[df["error"].isna()]
    keys = set()
    for _, r in done.iterrows():
        subset = None if pd.isna(r["subset"]) else r["subset"]
        keys.add(_row_key(r["model"], r["dataset"], subset, r["language"], r["task_id"], r["repeat_index"]))
    return keys


_completed = load_completed_keys()


def run_one(model: dict, dataset: str, subset: str, language: str,
            task_id, repeat_index: int, question: str, expected_answer: str):
    key = _row_key(model["name"], dataset, subset, language, task_id, repeat_index)
    if key in _completed:
        return

    row = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model["name"],
        "provider": model["provider"],
        "dataset": dataset,
        "subset": subset,
        "language": language,
        "task_id": task_id,
        "repeat_index": repeat_index,
        "question": question,
        "expected_answer": expected_answer,
        "model_answer": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "latency_s": None,
        "correct": None,
        "truncated": None,
        "error": None,
    }
    try:
        result = call_model_with_hard_timeout(model["name"], model["provider"], question)
        row["model_answer"] = result["answer_text"]
        row["prompt_tokens"] = result["prompt_tokens"]
        row["completion_tokens"] = result["completion_tokens"]
        row["total_tokens"] = result["total_tokens"]
        row["latency_s"] = result["latency_s"]
        row["truncated"] = result["finish_reason"] == "length"
        row["cost_usd"] = cost_usd(model["name"], result["prompt_tokens"], result["completion_tokens"])
        row["correct"] = is_correct(result["answer_text"], expected_answer)
    except FutureTimeoutError:
        row["latency_s"] = HARD_TIMEOUT_S
        row["error"] = f"Hard timeout: no response within {HARD_TIMEOUT_S}s (thread abandoned)"
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"

    append_row(row)
    if row["error"] is None:
        _completed.add(key)


# --- MGSM run block ----------------------------------------------------

def run_mgsm_block():
    print("\n=== MGSM run block ===")
    for lang in MGSM_LANGS:
        path = DATA_DIR / f"mgsm_{lang}.csv"
        if not path.exists():
            print(f"[mgsm/{lang}] SKIPPED -- {path} not found, run download_data.py first")
            continue
        df = pd.read_csv(path)
        sample = df.sample(n=min(MGSM_N_PROBLEMS, len(df)), random_state=SEED)

        for model in MODELS:
            for repeat in range(1, MGSM_N_REPEATS + 1):
                for task_id, row in sample.iterrows():
                    run_one(
                        model=model, dataset="MGSM", subset=None, language=lang,
                        task_id=task_id, repeat_index=repeat,
                        question=row[MGSM_QUESTION_COL],
                        expected_answer=row[MGSM_ANSWER_COL],
                    )
        print(f"[mgsm/{lang}] {len(sample)} tasks x {len(MODELS)} models x {MGSM_N_REPEATS} repeat(s) logged")


# --- MAPS run block (GAIA+MATH subsets) ---------------------------------

def run_maps_block():
    print("\n=== MAPS run block (GAIA+MATH subsets) ===")
    for subset in MAPS_SUBSETS:
        for lang in MAPS_LANGS:
            path = DATA_DIR / f"maps_{subset}_{lang}.csv"
            if not path.exists():
                print(f"[maps/{subset}/{lang}] SKIPPED -- {path} not found, run download_data.py first")
                continue
            df = pd.read_csv(path)

            # GAIA tasks that reference an attached file can't be answered
            # in this no-tool-use Phase 1 baseline (harness/ isn't built yet
            # -- see CLAUDE.md). Filter those out of the sample.
            if "file_name" in df.columns:
                df = df[df["file_name"].isna() | (df["file_name"] == "")]

            n = min(MAPS_N_TASKS, len(df))
            sample = df.sample(n=n, random_state=SEED)
            lang_code = MAPS_LANG_CODE[lang]

            for model in MODELS:
                for repeat in range(1, MAPS_N_REPEATS + 1):
                    for _, row in sample.iterrows():
                        task_id = row["task_id"] if "task_id" in df.columns else row.name
                        run_one(
                            model=model, dataset="MAPS", subset=subset, language=lang_code,
                            task_id=task_id, repeat_index=repeat,
                            question=row[MAPS_QUESTION_COL[subset]],
                            expected_answer=row[MAPS_ANSWER_COL[subset]],
                        )
            print(f"[maps/{subset}/{lang}] {n} tasks x {len(MODELS)} models x {MAPS_N_REPEATS} repeats logged")


def remaining_deficit() -> int:
    """Total (successes-short-of-target) across every cell for the
    currently active MODELS. Used to decide whether another round is
    needed -- reads the CSV fresh each call rather than trusting the
    in-memory _completed set alone, so it reflects what's actually on
    disk."""
    if not RESULTS_PATH.exists():
        return sum(len(MGSM_LANGS) * MGSM_N_PROBLEMS + len(MAPS_SUBSETS) * len(MAPS_LANGS) * MAPS_N_TASKS * MAPS_N_REPEATS for _ in MODELS)

    df = pd.read_csv(RESULTS_PATH)
    df = df[df["model"].isin({m["name"] for m in MODELS})]
    ok = df[df["error"].isna()]

    deficit = 0
    for m in MODELS:
        for lang in MGSM_LANGS:
            n = len(ok[(ok["model"] == m["name"]) & (ok["dataset"] == "MGSM") & (ok["language"] == lang)])
            deficit += max(0, MGSM_N_PROBLEMS - n)
        for subset in MAPS_SUBSETS:
            for lang in MAPS_LANGS:
                lang_code = MAPS_LANG_CODE[lang]
                n = len(ok[(ok["model"] == m["name"]) & (ok["dataset"] == "MAPS")
                           & (ok["subset"] == subset) & (ok["language"] == lang_code)])
                deficit += max(0, MAPS_N_TASKS * MAPS_N_REPEATS - n)
    return deficit


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models", type=str, default=None,
        help="Comma-separated model names to run (default: all). "
             "E.g. --models gpt-5.6-luna to skip a model that's temporarily "
             "unavailable -- the resumable design means the rest can be "
             "filled in later without redoing this pass.",
    )
    parser.add_argument(
        "--retry-until-filled", action="store_true",
        help="After the normal pass, keep re-looping over MGSM+MAPS -- which "
             "only ever re-attempt not-yet-successful (model,dataset,subset,"
             "language,task_id,repeat_index) keys, never fresh samples -- "
             "until every cell hits its target count, or a cap below is hit. "
             "For a model with a low per-attempt success rate (e.g. "
             "deepseek-flash on MAPS/GAIA during a degraded period), one pass "
             "leaves most missing cells partially filled since each pass "
             "gives every outstanding key exactly one more attempt; this "
             "keeps going so a single invocation can close the gap instead "
             "of it being re-launched manually round after round.",
    )
    parser.add_argument("--max-rounds", type=int, default=15, help="Cap on retry rounds with --retry-until-filled.")
    parser.add_argument("--max-minutes", type=float, default=180.0, help="Wall-clock cap with --retry-until-filled.")
    args = parser.parse_args()
    if args.models:
        wanted = {m.strip() for m in args.models.split(",")}
        unknown = wanted - {m["name"] for m in MODELS}
        if unknown:
            raise SystemExit(f"--models: unknown model(s) {unknown}, expected subset of {[m['name'] for m in MODELS]}")
        MODELS[:] = [m for m in MODELS if m["name"] in wanted]
        print(f"Running with models restricted to: {[m['name'] for m in MODELS]}")

    if not args.retry_until_filled:
        run_mgsm_block()
        run_maps_block()
        print(f"\nDone. Results -> {RESULTS_PATH}")
    else:
        start = time.monotonic()
        round_num = 0
        while True:
            round_num += 1
            elapsed_min = (time.monotonic() - start) / 60
            print(f"\n########## Round {round_num} (elapsed {elapsed_min:.1f} min) ##########")
            run_mgsm_block()
            run_maps_block()

            deficit = remaining_deficit()
            print(f"\n[round {round_num}] remaining deficit across all cells: {deficit}")
            if deficit == 0:
                print("All cells at target. Done.")
                break
            if round_num >= args.max_rounds:
                print(f"Hit --max-rounds ({args.max_rounds}) with deficit={deficit} still remaining. Stopping.", file=sys.stderr)
                break
            if elapsed_min >= args.max_minutes:
                print(f"Hit --max-minutes ({args.max_minutes}) with deficit={deficit} still remaining. Stopping.", file=sys.stderr)
                break
        print(f"\nDone ({round_num} round(s)). Results -> {RESULTS_PATH}")
