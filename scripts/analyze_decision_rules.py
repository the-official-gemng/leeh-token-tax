"""
Evaluates pre_registration.md Section 4's decision rules against real
Phase 3 data:
  - H1: cost ratio (non-English/English) on C2, CI upper bound <=1.2x
        for >=2 of 3 non-English languages.
  - H2: accuracy non-inferiority, C2 vs C0 (paired by task), CI lower
        bound > -2.0 points (i.e. can't rule out C2 being >=2 points
        worse than C0 is the failure condition; CI_low > -2 supports
        non-inferiority).
  - H3: C2's accuracy exceeds C1's, paired Wilcoxon significant at
        alpha=0.05 (Holm-corrected across all cells tested).

Uses the corrected results/phase1_raw.csv as C0 (see
docs/methodology-notes.md's MAPS/Math scoring-bug entry -- must run
AFTER that merge, not before, or H2/H3 inherit the broken always-0%
Math accuracy).

Pairing key across C0/C1/C2: (model, dataset, subset, language, task_id,
repeat_index) -- all three share the same seeded sampling from the same
source data files (see run_phase1.py's SEED and run_phase3.py's docstring
on reusing it), so this key aligns the same task instance across all
three conditions.
"""

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, bootstrap
from statsmodels.stats.multitest import multipletests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ["gpt-5.6-luna", "deepseek-flash"]
NON_ENGLISH_LANGS = ["es", "zh", "ar"]
ALPHA = 0.05
N_RESAMPLES = 10_000


def load(path):
    df = pd.read_csv(ROOT / "results" / path)
    df["task_id"] = df["task_id"].astype(str)
    return df


def keyed(df, model, lang, metric):
    """Per-task_id value (averaged over repeats), successful rows only,
    for one model+language, pooled across every dataset/subset present."""
    sub = df[(df["model"] == model) & (df["language"] == lang) & df["error"].isna()]
    out = {}
    for (dataset, subset, task_id), g in sub.groupby(["dataset", "subset", "task_id"], dropna=False):
        out[(dataset, subset, task_id)] = g[metric].mean()
    return out


def bootstrap_ci(values, statistic=np.mean):
    if len(values) < 2:
        return (float("nan"), float("nan"))
    res = bootstrap((np.asarray(values),), statistic, confidence_level=1 - ALPHA,
                     n_resamples=N_RESAMPLES, method="BCa", random_state=42)
    low, high = res.confidence_interval.low, res.confidence_interval.high
    if np.isnan(low) or np.isnan(high):
        res = bootstrap((np.asarray(values),), statistic, confidence_level=1 - ALPHA,
                         n_resamples=N_RESAMPLES, method="percentile", random_state=42)
        low, high = res.confidence_interval.low, res.confidence_interval.high
    return low, high


def h1_cost_ratio(c2):
    print(f"\n{'='*76}\nH1: cost ratio (non-English/English) on C2 -- target <=1.2x CI upper "
          f"bound for >=2/3 non-English languages, per model\n{'='*76}")
    results = []
    for model in MODELS:
        en_map = keyed(c2, model, "en", "cost_usd")
        passes = 0
        for lang in NON_ENGLISH_LANGS:
            lang_map = keyed(c2, model, lang, "cost_usd")
            common = set(en_map) & set(lang_map)
            if len(common) < 5:
                print(f"{model:16s} {lang}: n={len(common)} -- too few paired tasks, skipped")
                continue
            ratios = np.array([lang_map[k] / en_map[k] for k in common if en_map[k] > 0])
            median_ratio = float(np.median(ratios))
            ci_low, ci_high = bootstrap_ci(ratios, statistic=np.median)
            meets = ci_high <= 1.2
            passes += meets
            print(f"{model:16s} {lang}: n={len(ratios)}  median={median_ratio:.3f}x  "
                  f"CI=[{ci_low:.3f}, {ci_high:.3f}]  CI_upper<=1.2x: {meets}")
            results.append({"model": model, "language": lang, "n": len(ratios),
                             "median_ratio": median_ratio, "ci_low": ci_low, "ci_high": ci_high,
                             "meets_h1_target": meets})
        print(f"  -> {model}: {passes}/3 non-English languages meet the <=1.2x target "
              f"({'H1 SUPPORTED' if passes >= 2 else 'H1 NOT supported'} for this model)")
    return pd.DataFrame(results)


def h2_non_inferiority(c0, c2):
    print(f"\n{'='*76}\nH2: accuracy non-inferiority, C2 vs C0 -- non-inferiority margin "
          f"<=2.0 points (supported if CI lower bound > -2.0)\n{'='*76}")
    results = []
    for model in MODELS:
        for lang in ["en"] + NON_ENGLISH_LANGS:
            c0_map = keyed(c0, model, lang, "correct")
            c2_map = keyed(c2, model, lang, "correct")
            common = set(c0_map) & set(c2_map)
            if len(common) < 5:
                print(f"{model:16s} {lang}: n={len(common)} -- too few paired tasks, skipped")
                continue
            diffs = np.array([(c2_map[k] - c0_map[k]) * 100 for k in common])
            mean_diff = float(np.mean(diffs))
            ci_low, ci_high = bootstrap_ci(diffs, statistic=np.mean)
            supported = ci_low > -2.0
            print(f"{model:16s} {lang}: n={len(diffs)}  mean diff (C2-C0)={mean_diff:+.1f}pts  "
                  f"CI=[{ci_low:+.1f}, {ci_high:+.1f}]  non-inferior (CI_low>-2): {supported}")
            results.append({"model": model, "language": lang, "n": len(diffs),
                             "mean_diff": mean_diff, "ci_low": ci_low, "ci_high": ci_high,
                             "h2_supported": supported})
    return pd.DataFrame(results)


def h3_c2_beats_c1(c1, c2):
    print(f"\n{'='*76}\nH3: C2 accuracy > C1 accuracy -- paired Wilcoxon, Holm-corrected "
          f"across all cells tested\n{'='*76}")
    results = []
    for model in MODELS:
        for lang in ["en"] + NON_ENGLISH_LANGS:
            c1_map = keyed(c1, model, lang, "correct")
            c2_map = keyed(c2, model, lang, "correct")
            common = set(c1_map) & set(c2_map)
            if len(common) < 5:
                print(f"{model:16s} {lang}: n={len(common)} -- too few paired tasks, skipped")
                continue
            c1_vals = np.array([c1_map[k] for k in common])
            c2_vals = np.array([c2_map[k] for k in common])
            c1_acc, c2_acc = float(np.mean(c1_vals)) * 100, float(np.mean(c2_vals)) * 100
            try:
                _stat, p = wilcoxon(c2_vals, c1_vals)
            except ValueError:
                p = float("nan")
            print(f"{model:16s} {lang}: n={len(common)}  C1={c1_acc:.1f}%  C2={c2_acc:.1f}%  "
                  f"C2>C1: {c2_acc > c1_acc}  Wilcoxon p={p:.4g}" if pd.notna(p) else
                  f"{model:16s} {lang}: n={len(common)}  C1={c1_acc:.1f}%  C2={c2_acc:.1f}%  "
                  f"C2>C1: {c2_acc > c1_acc}  Wilcoxon: not computable (zero variance)")
            results.append({"model": model, "language": lang, "n": len(common),
                             "c1_accuracy": c1_acc, "c2_accuracy": c2_acc,
                             "c2_beats_c1": c2_acc > c1_acc, "wilcoxon_p": p})

    df = pd.DataFrame(results)
    valid = df["wilcoxon_p"].notna()
    if valid.sum():
        reject, p_corrected, _, _ = multipletests(df.loc[valid, "wilcoxon_p"], alpha=ALPHA, method="holm")
        df.loc[valid, "p_holm"] = p_corrected
        df.loc[valid, "significant_holm"] = reject
        print("\nHolm-corrected significance:")
        for _, r in df[valid].iterrows():
            print(f"  {r['model']:16s} {r['language']}: p_holm={r['p_holm']:.4g}  "
                  f"H3 supported (C2>C1 AND significant): {r['c2_beats_c1'] and r['significant_holm']}")
    return df


if __name__ == "__main__":
    c0 = load("phase1_raw.csv")
    c1 = load("phase3_c1_raw.csv")
    c2 = load("phase3_c2_raw.csv")

    h1 = h1_cost_ratio(c2)
    h2 = h2_non_inferiority(c0, c2)
    h3 = h3_c2_beats_c1(c1, c2)

    h1.to_csv(ROOT / "results" / "decision_rule_h1.csv", index=False)
    h2.to_csv(ROOT / "results" / "decision_rule_h2.csv", index=False)
    h3.to_csv(ROOT / "results" / "decision_rule_h3.csv", index=False)
    print(f"\nSaved -> results/decision_rule_h1.csv, decision_rule_h2.csv, decision_rule_h3.csv")
