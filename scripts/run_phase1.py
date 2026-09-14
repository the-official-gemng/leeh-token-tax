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

# --- Frozen config (pre_registration.md Section 1) ---------------------

MODELS = [
    {"name": "gpt-5.6-luna", "provider": "openai"},
    {"name": "deepseek-flash", "provider": "deepseek"},
]

# TODO (Step 3): fill in with today's per-token pricing, $ per 1M tokens.
# Do not run Step 4 until both are filled in -- see the assertion below.
PRICES = {
    "gpt-5.6-luna": {"input_per_1m": None, "output_per_1m": None},
    "deepseek-flash": {"input_per_1m": None, "output_per_1m": None},
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
            _clients[provider] = OpenAI(api_key=key)
        elif provider == "deepseek":
            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise RuntimeError("DEEPSEEK_API_KEY not set (see .env)")
            _clients[provider] = OpenAI(api_key=key, base_url="https://api.deepseek.com")
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


def run_one(model: dict, dataset: str, subset: str, language: str,
            task_id, repeat_index: int, question: str, expected_answer: str):
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
        result = call_model(model["name"], model["provider"], question)
        row["model_answer"] = result["answer_text"]
        row["prompt_tokens"] = result["prompt_tokens"]
        row["completion_tokens"] = result["completion_tokens"]
        row["total_tokens"] = result["total_tokens"]
        row["latency_s"] = result["latency_s"]
        row["truncated"] = result["finish_reason"] == "length"
        row["cost_usd"] = cost_usd(model["name"], result["prompt_tokens"], result["completion_tokens"])
        row["correct"] = is_correct(result["answer_text"], expected_answer)
    except Exception as e:
        row["error"] = str(e)

    append_row(row)


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


if __name__ == "__main__":
    run_mgsm_block()
    run_maps_block()
    print(f"\nDone. Results -> {RESULTS_PATH}")
