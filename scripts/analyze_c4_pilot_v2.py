"""
Same pre-committed pass criterion as analyze_c4_pilot.py, applied to the
pilot-continuation results (results/phase3_c4_raw_v2_fixed.csv -- the
per-language-fixed templates: es gets an added final-answer-only clause,
zh gets the trimmed 18-token overhead). See docs/methodology-notes.md's
C4 pilot continuation entry. Criterion, statistic, and denominator are
byte-for-byte the same as analyze_c4_pilot.py -- only the input file
differs, kept as a separate script (not a param) so the original v1
pilot analysis stays exactly reproducible on its own.
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
c4v2 = load("phase3_c4_raw_v2_fixed.csv")

en = c0[(c0.model == MODEL) & (c0.dataset == "MGSM") & (c0.language == "en") & c0.error.isna()]
en_map = en.groupby("task_id")["cost_usd"].mean().to_dict()

print("=" * 78)
print("C4 pilot v2 (per-language fixes) -- pre-committed pass criterion applied")
print("Criterion: median ratio <=1.2x AND 95% CI excludes 1.2 (== CI_high < 1.2), both cells")
print("=" * 78)

results = []
for lang in LANGS:
    lang_rows = c4v2[(c4v2.model == MODEL) & (c4v2.language == lang) & c4v2.error.isna()]
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

out_path = ROOT / "results" / "c4_pilot_v2_cost_ratio.csv"
df.to_csv(out_path, index=False)
print(f"\nSaved -> {out_path}")
