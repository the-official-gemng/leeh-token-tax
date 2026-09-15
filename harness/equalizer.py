"""
harness/equalizer.py -- Token-Budget Equalizer (cross-cutting)

Dynamically raises max_tokens for high-fertility languages so they get an
equivalent SEMANTIC budget to English, not just an equal token count --
if language X needs on average 1.3x as many tokens as English to express
the same content (its measured "fertility ratio"), it should get 1.3x
English's token budget, not the same budget English gets.

Fertility-ratio multipliers are loaded from
results/phase1_fertility_ratios.csv -- the actual numbers
scripts/analyze_phase1.py measured in Phase 1 (median total-token ratio
per model x language, paired by task_id) -- rather than hardcoded, so this
stays grounded in real data and won't silently drift out of sync if Phase
1 is ever re-run. English is always multiplier 1.0 by definition (it's
the ratio denominator, not a measured row in that CSV).

Wraps harness.executor.execute() (cross-cutting: every call in C2/C3a
passes through here per conditions.py's pipeline). Has a disable switch
for the C3a ablation run (H4: does removing the equalizer measurably
increase the truncation-failure rate for high-fertility languages?).
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.executor import execute, ExecutionResult

ROOT = Path(__file__).resolve().parent.parent
FERTILITY_CSV = ROOT / "results" / "phase1_fertility_ratios.csv"

BASE_MAX_TOKENS = 2048  # English's budget; non-English scales up from here
MIN_MULTIPLIER = 1.0    # never shrink a language's budget below English's


def _load_multipliers() -> dict:
    """Returns {(model, language): multiplier}. Falls back to an empty
    dict (multiplier 1.0 for everyone, i.e. equalizer becomes a no-op)
    if Phase 1 hasn't been analyzed yet, rather than crashing -- this
    shouldn't be able to block Phase 3 from running at all."""
    if not FERTILITY_CSV.exists():
        return {}
    df = pd.read_csv(FERTILITY_CSV)
    mult = {}
    for _, row in df.iterrows():
        if pd.isna(row.get("median_ratio")):
            continue
        mult[(row["model"], row["language"])] = max(MIN_MULTIPLIER, float(row["median_ratio"]))
    return mult


_MULTIPLIERS = _load_multipliers()


def get_multiplier(model_name: str, language: str) -> float:
    if language == "en":
        return 1.0
    return _MULTIPLIERS.get((model_name, language), 1.0)  # unmeasured (model, language) -> no adjustment, not a guess


def equalized_max_tokens(model_name: str, language: str, base_max_tokens: int = BASE_MAX_TOKENS) -> int:
    return round(base_max_tokens * get_multiplier(model_name, language))


def execute_equalized(model_name: str, provider: str, messages: list, language: str,
                       base_max_tokens: int = BASE_MAX_TOKENS,
                       tools: Optional[list] = None, tool_executor: Optional[dict] = None,
                       disable_equalizer: bool = False, **kwargs) -> ExecutionResult:
    """Cross-cutting wrapper around executor.execute(). Pass
    disable_equalizer=True for the C3a ablation run (H4) -- every language
    then gets English's raw base_max_tokens with no multiplier applied,
    everything else about the call identical."""
    max_tokens = base_max_tokens if disable_equalizer else equalized_max_tokens(model_name, language, base_max_tokens)
    return execute(model_name, provider, messages, tools=tools, tool_executor=tool_executor,
                    max_tokens=max_tokens, **kwargs)
