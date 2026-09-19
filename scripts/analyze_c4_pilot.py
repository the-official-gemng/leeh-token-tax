"""
Applies the C4 pilot's pre-committed pass criterion (see
docs/methodology-notes.md's 2026-09-17 "C4 pilot: design + pre-committed
pass criterion" entry, written before this script was run against real
results) to results/phase3_c4_raw.csv.

Criterion, verbatim from that entry: C4 counts as working if the median
per-task cost ratio (C4 / English) is <=1.2x AND the 95% bootstrap CI
excludes 1.2, on BOTH target cells (deepseek-flash/es, deepseek-flash/zh)
independently. This reduces to CI upper bound < 1.2 strictly.

Statistic: bootstrap_ci() imported directly from analyze_decision_rules.py
-- same BCa/percentile-fallback median-ratio CI as H1's own confirmatory
test, so this pilot cannot repeat the mean-ratio mistake documented in
the H1 recheck entry.

English denominator: C0's own phase1_raw.csv MGSM/en per-task cost (C4
was not run on English in this pilot -- see the pre-commitment entry for
why that's the correct denominator, not a shortcut).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_decision_rules import bootstrap_ci

ROOT = Path(__file__).resolve().parent.parent
MODEL = "deepseek-flash"
LANGS = ["es", "zh"]
THRESHOLD = 1.2


def load(path):
    df = pd.read_csv(ROOT / "results" / path)
    df["task_id"] = df["task_id"].astype(str)
    return df


c0 = load("phase1_raw.csv")
c4 = load("phase3_c4_raw.csv")

en = c0[(c0.model == MODEL) & (c0.dataset == "MGSM") & (c0.language == "en") & c0.error.isna()]
en_map = en.groupby("task_id")["cost_usd"].mean().to_dict()

print("=" * 78)
print("C4 pilot -- pre-committed pass criterion applied to actual results")
print("Criterion: median ratio <=1.2x AND 95% CI excludes 1.2 (== CI_high < 1.2), both cells")
print("=" * 78)

results = []
for lang in LANGS:
    lang_rows = c4[(c4.model == MODEL) & (c4.language == lang) & c4.error.isna()]
    lang_map = lang_rows.groupby("task_id")["cost_usd"].mean().to_dict()

    common = set(en_map) & set(lang_map)
    ratios = np.array([lang_map[k] / en_map[k] for k in common if en_map[k] > 0])
    median_ratio = float(np.median(ratios))
    ci_low, ci_high = bootstrap_ci(ratios, statistic=np.median)
    passes = median_ratio <= THRESHOLD and ci_high < THRESHOLD

    print(f"\n{MODEL}/{lang}: n={len(ratios)}  median={median_ratio:.3f}x  "
          f"95% CI=[{ci_low:.3f}, {ci_high:.3f}]")
    print(f"  median<=1.2: {median_ratio <= THRESHOLD}   CI_high<1.2 (strict): {ci_high < THRESHOLD}   "
          f"-> {'PASS' if passes else 'FAIL'}")
    results.append({"model": MODEL, "language": lang, "n": len(ratios),
                     "median_ratio": median_ratio, "ci_low": ci_low, "ci_high": ci_high,
                     "passes_pilot_criterion": passes})

df = pd.DataFrame(results)
n_pass = df["passes_pilot_criterion"].sum()
if n_pass == 2:
    verdict = "PASS -- both target cells clear the pre-committed criterion"
elif n_pass == 1:
    verdict = "PARTIAL -- only one of two target cells clears the criterion (not a pass)"
else:
    verdict = "FAIL -- neither target cell clears the criterion"
print(f"\n{'='*78}\nOVERALL: {verdict}\n{'='*78}")

out_path = ROOT / "results" / "c4_pilot_cost_ratio.csv"
df.to_csv(out_path, index=False)
print(f"\nSaved -> {out_path}")
