"""
Post-hoc harness-hardening track (docs/harness_hardening_log.md) -- NOT
part of the confirmatory C4 pilot (docs/methodology-notes.md). Reusable
across iterations: applies the same statistic and target used throughout
this project (bootstrap CI of the median per-task cost ratio, C4-lang vs
C0-English, via analyze_decision_rules.py's bootstrap_ci()) to whichever
results file and language(s) this iteration produced.

Usage: python scripts/analyze_c4_hardening.py <results_csv> <lang1[,lang2,...]>
Example: python scripts/analyze_c4_hardening.py phase3_c4_raw_v3_zh_finalanswer.csv zh
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_decision_rules import bootstrap_ci

ROOT = Path(__file__).resolve().parent.parent
MODEL = "deepseek-flash"
THRESHOLD = 1.2


def load(path):
    df = pd.read_csv(ROOT / "results" / path)
    df["task_id"] = df["task_id"].astype(str)
    return df


def analyze(results_filename: str, langs: list, label: str = ""):
    c0 = load("phase1_raw.csv")
    data = load(results_filename)

    en = c0[(c0.model == MODEL) & (c0.dataset == "MGSM") & (c0.language == "en") & c0.error.isna()]
    en_map = en.groupby("task_id")["cost_usd"].mean().to_dict()

    c0_lang_acc = {}
    for lang in langs:
        c0_lang_acc[lang] = c0[(c0.model == MODEL) & (c0.dataset == "MGSM") & (c0.language == lang)
                                & c0.error.isna()]["correct"].mean() * 100

    print("=" * 78)
    print(f"harness-hardening track{' -- ' + label if label else ''} -- {results_filename}")
    print("(post-hoc engineering, not part of the confirmatory study)")
    print("=" * 78)

    rows = []
    for lang in langs:
        lang_rows = data[(data.model == MODEL) & (data.language == lang) & data.error.isna()]
        lang_map = lang_rows.groupby("task_id")["cost_usd"].mean().to_dict()

        common = set(en_map) & set(lang_map)
        ratios = np.array([lang_map[k] / en_map[k] for k in common if en_map[k] > 0])
        median_ratio = float(np.median(ratios))
        ci_low, ci_high = bootstrap_ci(ratios, statistic=np.median)
        margin = THRESHOLD - ci_high

        acc = lang_rows["correct"].mean() * 100
        print(f"\n{MODEL}/{lang}: n={len(ratios)}  median={median_ratio:.3f}x  "
              f"95% CI=[{ci_low:.3f}, {ci_high:.3f}]  margin below 1.2={margin:+.3f}")
        print(f"  accuracy: {acc:.1f}%  (C0 baseline: {c0_lang_acc[lang]:.1f}%)")
        rows.append({"file": results_filename, "model": MODEL, "language": lang, "n": len(ratios),
                     "median_ratio": median_ratio, "ci_low": ci_low, "ci_high": ci_high,
                     "accuracy_pct": acc, "c0_accuracy_pct": c0_lang_acc[lang]})

    return pd.DataFrame(rows)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: analyze_c4_hardening.py <results_csv> <lang1[,lang2,...]> [label]")
    fname = sys.argv[1]
    langs = sys.argv[2].split(",")
    label = sys.argv[3] if len(sys.argv) > 3 else ""
    df = analyze(fname, langs, label)
    print(f"\n{'='*78}")
