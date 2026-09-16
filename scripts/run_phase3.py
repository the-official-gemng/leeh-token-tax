"""
Phase 3 harness run -- same task set as Phase 1 (same seed, same sampling
logic, same task_id space -- verified deterministic/reproducible, see
docs/methodology-notes.md), run through one of the four conditions instead
of Phase 1's raw call_model().

Usage:
    python scripts/run_phase3.py --condition c2
    python scripts/run_phase3.py --condition c1 --models gpt-5.6-luna
    python scripts/run_phase3.py --condition c2 --retry-until-filled

Each condition writes its own results/phase3_<condition>_raw.csv (kept
separate from Phase 1's results/phase1_raw.csv and from each other, so a
partial/interrupted run of one condition can't corrupt another's resume
state).

Reuses run_phase1.py's constants (SEED, language lists, task counts,
question/answer columns) rather than duplicating them as separate magic
numbers, so task_id sets are guaranteed identical to Phase 1's -- required
for the paired comparison in Section 3 of pre_registration.md. Does NOT
reuse run_phase1.py's sampling CODE directly (it's inlined in
run_mgsm_block/run_maps_block there, not factored into a standalone
function, and this script shouldn't risk touching Phase 1's
already-validated script to extract it) -- duplicates the ~3-line
df.sample(...) call using the SAME imported SEED/constants instead, which
is sufficient for identical task_id alignment (already verified
empirically for Phase 1 itself, across languages and datasets).
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run_phase1 import (
    SEED, MODELS, DATA_DIR,
    MGSM_LANGS, MGSM_N_PROBLEMS, MGSM_QUESTION_COL, MGSM_ANSWER_COL,
    MAPS_LANGS, MAPS_LANG_CODE, MAPS_SUBSETS, MAPS_N_TASKS, MAPS_N_REPEATS,
    MAPS_QUESTION_COL, MAPS_ANSWER_COL,
)
from harness.conditions import run_condition

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

FIELDNAMES = [
    "timestamp", "condition", "model", "provider", "dataset", "subset", "language",
    "task_id", "repeat_index", "question", "expected_answer", "model_answer",
    "detected_language", "task_type", "route_through_english",
    "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd",
    "latency_s", "correct", "truncated", "error",
]


def results_path(condition: str) -> Path:
    return RESULTS_DIR / f"phase3_{condition}_raw.csv"


def load_completed_keys(condition: str) -> set:
    path = results_path(condition)
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    done = df[df["error"].isna()]
    keys = set()
    for _, r in done.iterrows():
        subset = None if pd.isna(r["subset"]) else r["subset"]
        keys.add((r["model"], r["dataset"], subset, r["language"], str(r["task_id"]), r["repeat_index"]))
    return keys


def is_correct(model_answer, expected) -> bool:
    if model_answer is None or expected is None:
        return False
    return str(expected).strip().lower() in model_answer.strip().lower()


def append_row(condition: str, row: dict):
    path = results_path(condition)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def run_one(condition: str, model: dict, dataset: str, subset, language: str,
            task_id, repeat_index: int, question: str, expected_answer,
            completed_keys: set, task_type_hint=None):
    key = (model["name"], dataset, subset, language, str(task_id), repeat_index)
    if key in completed_keys:
        return

    row = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "condition": condition, "model": model["name"], "provider": model["provider"],
        "dataset": dataset, "subset": subset, "language": language,
        "task_id": task_id, "repeat_index": repeat_index,
        "question": question, "expected_answer": expected_answer, "model_answer": None,
        "detected_language": None, "task_type": None, "route_through_english": None,
        "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
        "cost_usd": None, "latency_s": None, "correct": None, "truncated": None, "error": None,
    }
    try:
        kwargs = {"language": language} if condition == "c1" else {"task_type_hint": task_type_hint}
        result = run_condition(condition, model["name"], model["provider"], question, **kwargs)
        row["model_answer"] = result.final_answer
        row["detected_language"] = result.detected_language
        row["task_type"] = result.task_type
        row["route_through_english"] = result.route_through_english
        row["prompt_tokens"] = result.prompt_tokens
        row["completion_tokens"] = result.completion_tokens
        row["total_tokens"] = result.total_tokens
        row["cost_usd"] = result.cost_usd
        row["latency_s"] = result.latency_s
        row["truncated"] = result.truncated
        row["correct"] = is_correct(result.final_answer, expected_answer)
        row["error"] = result.error
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"

    append_row(condition, row)
    if row["error"] is None:
        completed_keys.add(key)


def run_mgsm_block(condition: str, completed_keys: set):
    print("\n=== MGSM run block ===")
    for lang in MGSM_LANGS:
        path = DATA_DIR / f"mgsm_{lang}.csv"
        if not path.exists():
            print(f"[mgsm/{lang}] SKIPPED -- {path} not found, run download_data.py first")
            continue
        df = pd.read_csv(path)
        sample = df.sample(n=min(MGSM_N_PROBLEMS, len(df)), random_state=SEED)

        for model in MODELS:
            for task_id, row in sample.iterrows():
                run_one(condition, model, "MGSM", None, lang, task_id, 1,
                        row[MGSM_QUESTION_COL], row[MGSM_ANSWER_COL], completed_keys,
                        task_type_hint="single_turn")
        print(f"[mgsm/{lang}] {len(sample)} tasks x {len(MODELS)} models logged")


def run_maps_block(condition: str, completed_keys: set):
    print("\n=== MAPS run block (GAIA+MATH subsets) ===")
    for subset in MAPS_SUBSETS:
        for lang in MAPS_LANGS:
            path = DATA_DIR / f"maps_{subset}_{lang}.csv"
            if not path.exists():
                print(f"[maps/{subset}/{lang}] SKIPPED -- {path} not found, run download_data.py first")
                continue
            df = pd.read_csv(path)
            if "file_name" in df.columns:
                df = df[df["file_name"].isna() | (df["file_name"] == "")]
            n = min(MAPS_N_TASKS, len(df))
            sample = df.sample(n=n, random_state=SEED)
            lang_code = MAPS_LANG_CODE[lang]

            for model in MODELS:
                for repeat in range(1, MAPS_N_REPEATS + 1):
                    for _, row in sample.iterrows():
                        task_id = row["task_id"] if "task_id" in df.columns else row.name
                        run_one(condition, model, "MAPS", subset, lang_code, task_id, repeat,
                                row[MAPS_QUESTION_COL[subset]], row[MAPS_ANSWER_COL[subset]], completed_keys,
                                task_type_hint="agentic")
            print(f"[maps/{subset}/{lang}] {n} tasks x {len(MODELS)} models x {MAPS_N_REPEATS} repeats logged")


def remaining_deficit(condition: str, completed_keys: set) -> int:
    deficit = 0
    for m in MODELS:
        for lang in MGSM_LANGS:
            n = sum(1 for k in completed_keys if k[0] == m["name"] and k[1] == "MGSM" and k[3] == lang)
            deficit += max(0, MGSM_N_PROBLEMS - n)
        for subset in MAPS_SUBSETS:
            for lang in MAPS_LANGS:
                lang_code = MAPS_LANG_CODE[lang]
                n = sum(1 for k in completed_keys if k[0] == m["name"] and k[1] == "MAPS"
                        and k[2] == subset and k[3] == lang_code)
                deficit += max(0, MAPS_N_TASKS * MAPS_N_REPEATS - n)
    return deficit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True, choices=["c0", "c1", "c2", "c3a"])
    parser.add_argument("--models", type=str, default=None,
                         help="Comma-separated model names to run (default: all).")
    parser.add_argument("--retry-until-filled", action="store_true",
                         help="Same mechanism as run_phase1.py's flag of the same name -- "
                              "keep re-looping (only re-attempting not-yet-successful keys) "
                              "until every cell hits target or a cap below is hit.")
    parser.add_argument("--max-rounds", type=int, default=15)
    parser.add_argument("--max-minutes", type=float, default=180.0)
    args = parser.parse_args()

    if args.models:
        wanted = {m.strip() for m in args.models.split(",")}
        unknown = wanted - {m["name"] for m in MODELS}
        if unknown:
            raise SystemExit(f"--models: unknown model(s) {unknown}, expected subset of {[m['name'] for m in MODELS]}")
        MODELS[:] = [m for m in MODELS if m["name"] in wanted]
        print(f"Running with models restricted to: {[m['name'] for m in MODELS]}")

    completed_keys = load_completed_keys(args.condition)

    if not args.retry_until_filled:
        run_mgsm_block(args.condition, completed_keys)
        run_maps_block(args.condition, completed_keys)
    else:
        start = time.monotonic()
        round_num = 0
        while True:
            round_num += 1
            print(f"\n########## Round {round_num} (elapsed {(time.monotonic()-start)/60:.1f} min) ##########")
            run_mgsm_block(args.condition, completed_keys)
            run_maps_block(args.condition, completed_keys)

            deficit = remaining_deficit(args.condition, completed_keys)
            print(f"\n[round {round_num}] remaining deficit across all cells: {deficit}")
            if deficit == 0:
                print("All cells at target. Done.")
                break
            if round_num >= args.max_rounds:
                print(f"Hit --max-rounds ({args.max_rounds}) with deficit={deficit} still remaining. Stopping.", file=sys.stderr)
                break
            if (time.monotonic() - start) / 60 >= args.max_minutes:
                print(f"Hit --max-minutes ({args.max_minutes}) with deficit={deficit} still remaining. Stopping.", file=sys.stderr)
                break

    print(f"\nDone. Results -> {results_path(args.condition)}")
