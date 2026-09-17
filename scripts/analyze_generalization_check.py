"""
Analysis for the exploratory generalization spot-check (see
docs/methodology-notes.md). Same bootstrap-BCa method as
scripts/analyze_phase1.py's cost-ratio analysis, applied to
results/generalization_check.csv instead of results/phase1_raw.csv.

Not paired against Phase 1's task_id sample (this is an independent,
smaller N=30 sample) -- ratios here are median(non-English cost) /
median(English cost) across each language's own sample, not a per-task
paired ratio the way Phase 1's is. Reported alongside accuracy per
model/language. Small-N, exploratory -- not expected to reach
significance; no significance testing is applied here (see
methodology-notes.md for why).
"""

import numpy as np
import pandas as pd
from scipy.stats import bootstrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "results" / "generalization_check.csv"

ALPHA = 0.05
N_RESAMPLES = 10_000


def bca_ci(values: np.ndarray):
    if len(values) < 2:
        return (float("nan"), float("nan"))
    res = bootstrap((values,), np.median, confidence_level=1 - ALPHA,
                     n_resamples=N_RESAMPLES, method="BCa", random_state=42)
    return res.confidence_interval.low, res.confidence_interval.high


def main():
    df = pd.read_csv(RESULTS_PATH)
    df["ok"] = df["error"].isna()
    rows = []

    for model in df["model"].unique():
        m = df[df["model"] == model]
        en_ok = m[(m["language"] == "en") & m["ok"]]
        en_median_cost = en_ok["cost_usd"].median()

        for lang in ["en", "es", "zh"]:
            sub = m[m["language"] == lang]
            ok = sub[sub["ok"]]
            n_ok, n_total = len(ok), len(sub)
            accuracy = 100 * ok["correct"].mean() if n_ok else float("nan")

            if lang == "en":
                ratio_ci = (1.0, 1.0, 1.0)  # by definition
            elif n_ok >= 5 and pd.notna(en_median_cost) and en_median_cost > 0:
                ratios = ok["cost_usd"].values / en_median_cost
                median_ratio = float(np.median(ratios))
                ci_low, ci_high = bca_ci(ratios)
                ratio_ci = (median_ratio, ci_low, ci_high)
            else:
                ratio_ci = (float("nan"), float("nan"), float("nan"))

            rows.append({
                "model": model, "language": lang, "N": n_ok, "attempts": n_total,
                "accuracy_pct": accuracy,
                "median_cost_ratio": ratio_ci[0], "ci_low": ratio_ci[1], "ci_high": ratio_ci[2],
            })

    out = pd.DataFrame(rows)
    print(f"\n{'='*76}\nGeneralization spot-check (N={30} target/language/model -- exploratory, "
          f"not powered for significance)\n{'='*76}")
    for _, r in out.iterrows():
        ratio_str = f"{r['median_cost_ratio']:.2f}x [{r['ci_low']:.2f}, {r['ci_high']:.2f}]" if pd.notna(r["median_cost_ratio"]) else "n/a"
        print(f"{r['model']:22s} {r['language']}: N={r['N']}/{r['attempts']:<3d} "
              f"accuracy={r['accuracy_pct']:.1f}%  cost ratio vs en = {ratio_str}")

    out.to_csv(ROOT / "results" / "generalization_check_summary.csv", index=False)
    print(f"\nSaved -> results/generalization_check_summary.csv")


if __name__ == "__main__":
    main()
