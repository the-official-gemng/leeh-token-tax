"""
Harness-hardening track (docs/harness_hardening_log.md) -- Step 1's
deferred question: re-measure qwen3.5-flash/zh and gemini-3.5-flash-lite/zh
baseline at higher N to resolve the N=30 spot-check's inconclusive CIs
(qwen/zh: [0.967, 2.393]; gemini/zh: [0.902, 1.272]) before deciding
whether either needs a fix. Post-hoc engineering, NOT part of the
confirmatory study. Does not touch harness/, deepseek-flash/gpt-5.6-luna
data, or the original N=30 generalization_check.csv.

Fresh N=50 (Phase 1's own MGSM seed/sampling) for zh on both models, plus
qwen's en baseline (gemini's en baseline is already on file from the es
harness-hardening run, same seed/N, reused as-is -- no need to redraw).
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
OUT_PATH = ROOT / "results" / "harness_hardening_zh_baseline.csv"

SEED = 42
N_PROBLEMS = 50
QUESTION_COL = "question"
ANSWER_COL = "answer_number"
HARD_TIMEOUT_S = 60

MODELS = [
    {"name": "qwen3.5-flash", "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
     "api_key_env": "QWEN_API_KEY", "input_per_1m": 0.10, "output_per_1m": 0.40,
     "languages": ["en", "zh"]},
    {"name": "gemini-3.5-flash-lite", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
     "api_key_env": "GEMINI_API_KEY", "input_per_1m": 0.30, "output_per_1m": 2.50,
     "languages": ["zh"]},  # en already on file from harness_hardening_gemini_es_v1.csv
]

FIELDNAMES = ["timestamp", "model", "language", "task_id", "question", "expected_answer",
              "model_answer", "prompt_tokens", "completion_tokens", "total_tokens",
              "cost_usd", "latency_s", "correct", "truncated", "error"]

_clients = {}


def get_client(cfg):
    if cfg["name"] not in _clients:
        key = os.getenv(cfg["api_key_env"])
        if not key:
            raise RuntimeError(f"{cfg['api_key_env']} not set")
        _clients[cfg["name"]] = OpenAI(api_key=key, base_url=cfg["base_url"], timeout=60.0, max_retries=2)
    return _clients[cfg["name"]]


def cost_usd(cfg, p, c):
    return p * cfg["input_per_1m"] / 1e6 + c * cfg["output_per_1m"] / 1e6


def _call(cfg, messages):
    client = get_client(cfg)
    resp = client.chat.completions.create(model=cfg["name"], messages=messages)
    choice = resp.choices[0]
    return {"answer_text": choice.message.content, "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens, "finish_reason": choice.finish_reason}


def call_with_timeout(cfg, messages):
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(_call, cfg, messages)
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


def append_row(row):
    is_new = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if is_new:
            w.writeheader()
        w.writerow(row)


if __name__ == "__main__":
    for cfg in MODELS:
        for lang in cfg["languages"]:
            df = pd.read_csv(DATA_DIR / f"mgsm_{lang}.csv")
            sample = df.sample(n=min(N_PROBLEMS, len(df)), random_state=SEED)
            for task_id, row in sample.iterrows():
                q, expected = row[QUESTION_COL], row[ANSWER_COL]
                out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": cfg["name"],
                       "language": lang, "task_id": task_id, "question": q, "expected_answer": expected,
                       "model_answer": None, "prompt_tokens": None, "completion_tokens": None,
                       "total_tokens": None, "cost_usd": None, "latency_s": None, "correct": None,
                       "truncated": None, "error": None}
                start = time.monotonic()
                result = call_with_timeout(cfg, [{"role": "user", "content": q}])
                out["latency_s"] = time.monotonic() - start
                if "error" in result:
                    out["error"] = result["error"]
                else:
                    out["model_answer"] = result["answer_text"]
                    out["prompt_tokens"] = result["prompt_tokens"]
                    out["completion_tokens"] = result["completion_tokens"]
                    out["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
                    out["cost_usd"] = cost_usd(cfg, result["prompt_tokens"], result["completion_tokens"])
                    out["truncated"] = (result["finish_reason"] == "length")
                    out["correct"] = is_correct(result["answer_text"], expected)
                append_row(out)
            print(f"[{cfg['name']}/{lang}] {len(sample)} done")
    print(f"Done. Results -> {OUT_PATH}")
