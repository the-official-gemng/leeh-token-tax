"""
Phase 1 analysis -- implements pre_registration.md Section 3's statistical
plan against results/phase1_raw.csv, and checks the baseline numbers
against Section 4's decision rules to the extent Phase 1 (C0-only,
no-intervention baseline) data can speak to them.

IMPORTANT SCOPE NOTE: Section 4's decision rules (H1/H2/H3) are written as
Phase 3 pass/fail criteria comparing an intervention condition (C1/C2)
against baseline (C0). Phase 1 only collects C0 -- there is no C1/C2 data
yet, so none of H1/H2/H3 can be literally evaluated here. What this script
DOES do: measure the baseline "token tax" (cost ratio, fertility ratio)
Section 4 assumes LEEH will shrink, with the pre-registered paired
Wilcoxon + Holm-Bonferroni + bootstrap-BCa plan from Section 3, so a human
can judge whether closing that gap to H1's <=1.2x target is plausible
before any harness code gets written.

Design notes (documented here rather than pre_registration.md -- these are
analysis-implementation choices, not changes to frozen scope):

- Pairing is by task_id, within (model, dataset, subset), matching
  Section 3 ("English vs language X, per model, on matched task instances").
  For MAPS's N=2 repeats, a task_id's cost is averaged across its repeats
  first, so each task_id contributes exactly one paired observation.
- Per the Amendments Log, language coverage is asymmetric by dataset:
  MGSM has en/es/zh (no ar), MAPS has en/es/ar (no zh). 'es' therefore has
  paired observations from BOTH datasets; 'zh' only from MGSM; 'ar' only
  from MAPS. Pooling task-level paired differences for a given (model,
  language) across whichever dataset(s) contain it reduces cleanly to
  exactly 6 tests (2 models x {es, zh, ar}), matching Section 3's "2
  models x 3 non-English languages = 6 pairwise tests" despite the
  per-dataset asymmetry.
- Only successful (non-error) rows have a cost/token value; a task_id is
  included in a pair only if BOTH its English and target-language rows
  succeeded. This is a real limitation given uneven failure rates by
  language (deepseek-flash/GAIA especially -- see methodology-notes.md) --
  the per-cell N and success rate are reported alongside every result so
  a reader can judge how much survivorship bias might be at play.
"""

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, bootstrap
from statsmodels.stats.multitest import multipletests

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "results" / "phase1_raw.csv"

MODELS = ["gpt-5.6-luna", "deepseek-flash"]
NON_ENGLISH_LANGS = ["es", "zh", "ar"]
ALPHA = 0.05
N_RESAMPLES = 10_000


def load_paired(df: pd.DataFrame, model: str, lang: str, metric: str):
    """Return (english_values, lang_values, per-dataset N/success-rate info)
    for matched task_ids, pooling across every dataset/subset that has both
    an English and a `lang` row for this model."""
    sub = df[df["model"] == model]
    pairs_en, pairs_lang, coverage = [], [], []

    for (dataset, subset), g in sub.groupby(["dataset", "subset"], dropna=False):
        en_g = g[(g["language"] == "en") & (g["error"].isna())]
        lang_g = g[(g["language"] == lang) & (g["error"].isna())]
        if en_g.empty or lang_g.empty:
            continue

        en_by_task = en_g.groupby("task_id")[metric].mean()
        lang_by_task = lang_g.groupby("task_id")[metric].mean()
        common = en_by_task.index.intersection(lang_by_task.index)
        if len(common) == 0:
            continue

        pairs_en.extend(en_by_task.loc[common].tolist())
        pairs_lang.extend(lang_by_task.loc[common].tolist())

        total_lang_attempts = len(g[g["language"] == lang])
        total_lang_success = len(lang_g)
        coverage.append(
            f"{dataset}/{subset or '-'}: n_pairs={len(common)}, "
            f"{lang} success {total_lang_success}/{total_lang_attempts} "
            f"({100*total_lang_success/max(total_lang_attempts,1):.0f}%)"
        )

    return np.array(pairs_en), np.array(pairs_lang), coverage


def bca_ci(ratios: np.ndarray):
    if len(ratios) < 2:
        return (float("nan"), float("nan"))
    res = bootstrap(
        (ratios,), np.median, confidence_level=1 - ALPHA,
        n_resamples=N_RESAMPLES, method="BCa", random_state=42,
    )
    return res.confidence_interval.low, res.confidence_interval.high


def analyze(metric: str, label: str):
    df = pd.read_csv(RESULTS_PATH)
    results = []

    for model in MODELS:
        for lang in NON_ENGLISH_LANGS:
            en_vals, lang_vals, coverage = load_paired(df, model, lang, metric)
            n = len(en_vals)
            if n < 5:
                results.append({
                    "model": model, "language": lang, "n_pairs": n,
                    "median_ratio": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"),
                    "wilcoxon_p": float("nan"), "coverage": coverage,
                })
                continue

            ratios = lang_vals / en_vals
            median_ratio = float(np.median(ratios))
            ci_low, ci_high = bca_ci(ratios)
            stat, p = wilcoxon(lang_vals, en_vals)

            results.append({
                "model": model, "language": lang, "n_pairs": n,
                "median_ratio": median_ratio, "ci_low": ci_low, "ci_high": ci_high,
                "wilcoxon_p": p, "coverage": coverage,
            })

    res_df = pd.DataFrame(results)
    valid = res_df["wilcoxon_p"].notna()
    if valid.sum():
        reject, p_corrected, _, _ = multipletests(res_df.loc[valid, "wilcoxon_p"], alpha=ALPHA, method="holm")
        res_df.loc[valid, "p_holm"] = p_corrected
        res_df.loc[valid, "significant_holm"] = reject

    print(f"\n{'='*70}\n{label} ratio (non-English / English), paired by task_id\n{'='*70}")
    for _, r in res_df.iterrows():
        print(f"\n{r['model']} / {r['language']}  (n_pairs={r['n_pairs']})")
        for c in r["coverage"]:
            print(f"    {c}")
        if pd.isna(r["median_ratio"]):
            print("    too few paired observations (n<5) -- skipped")
            continue
        sig = r.get("significant_holm", False)
        print(f"    median ratio = {r['median_ratio']:.3f}x   "
              f"95% BCa CI = [{r['ci_low']:.3f}, {r['ci_high']:.3f}]")
        print(f"    Wilcoxon p = {r['wilcoxon_p']:.4g}   "
              f"Holm-corrected p = {r.get('p_holm', float('nan')):.4g}   "
              f"significant @ alpha={ALPHA}: {sig}")

    return res_df


def analyze_accuracy():
    """Exact-match accuracy, English vs. each non-English language, paired
    by task_id -- same pairing machinery as analyze() (load_paired), but
    reported as a DIFFERENCE in accuracy points rather than a ratio. A
    ratio of two 0/1 correctness values doesn't mean the same thing a cost
    ratio does (and is degenerate whenever English accuracy is 0 on a
    matched subset); pre_registration.md's own H2 is framed as a
    difference too ("non-inferiority margin: <=2 accuracy points"), so
    this matches the pre-registered framing rather than forcing the
    cost-analysis's ratio framing onto a metric it doesn't fit."""
    df = pd.read_csv(RESULTS_PATH)
    results = []

    for model in MODELS:
        for lang in NON_ENGLISH_LANGS:
            en_vals, lang_vals, coverage = load_paired(df, model, lang, "correct")
            n = len(en_vals)
            if n < 5:
                results.append({
                    "model": model, "language": lang, "n_pairs": n,
                    "en_accuracy": float("nan"), "lang_accuracy": float("nan"),
                    "diff_points": float("nan"), "ci_low": float("nan"), "ci_high": float("nan"),
                    "wilcoxon_p": float("nan"), "coverage": coverage,
                })
                continue

            en_acc = float(np.mean(en_vals)) * 100
            lang_acc = float(np.mean(lang_vals)) * 100
            diffs = (lang_vals.astype(float) - en_vals.astype(float)) * 100
            diff_points = float(np.median(diffs))
            ci_low, ci_high = bca_ci(diffs)
            try:
                _stat, p = wilcoxon(lang_vals, en_vals)
            except ValueError:
                # raised when every paired difference is exactly zero
                # (e.g. both languages 100% correct on every matched task)
                p = float("nan")

            results.append({
                "model": model, "language": lang, "n_pairs": n,
                "en_accuracy": en_acc, "lang_accuracy": lang_acc,
                "diff_points": diff_points, "ci_low": ci_low, "ci_high": ci_high,
                "wilcoxon_p": p, "coverage": coverage,
            })

    res_df = pd.DataFrame(results)
    valid = res_df["wilcoxon_p"].notna()
    if valid.sum():
        reject, p_corrected, _, _ = multipletests(res_df.loc[valid, "wilcoxon_p"], alpha=ALPHA, method="holm")
        res_df.loc[valid, "p_holm"] = p_corrected
        res_df.loc[valid, "significant_holm"] = reject

    print(f"\n{'='*70}\nExact-match accuracy: English vs. non-English, paired by task_id\n{'='*70}")
    for _, r in res_df.iterrows():
        print(f"\n{r['model']} / {r['language']}  (n_pairs={r['n_pairs']})")
        for c in r["coverage"]:
            print(f"    {c}")
        if pd.isna(r["diff_points"]):
            print("    too few paired observations (n<5) -- skipped")
            continue
        sig = r.get("significant_holm", False)
        print(f"    English accuracy = {r['en_accuracy']:.1f}%   {r['language']} accuracy = {r['lang_accuracy']:.1f}%")
        print(f"    median paired difference ({r['language']} - en) = {r['diff_points']:+.1f} points   "
              f"95% BCa CI = [{r['ci_low']:+.1f}, {r['ci_high']:+.1f}]")
        if pd.isna(r["wilcoxon_p"]):
            print("    Wilcoxon: not computable (zero variance in paired differences)")
        else:
            print(f"    Wilcoxon p = {r['wilcoxon_p']:.4g}   "
                  f"Holm-corrected p = {r.get('p_holm', float('nan')):.4g}   "
                  f"significant @ alpha={ALPHA}: {sig}")

    return res_df


if __name__ == "__main__":
    print(f"Loading {RESULTS_PATH}")
    cost_results = analyze("cost_usd", "Dollar cost")
    token_results = analyze("total_tokens", "Fertility (total tokens)")

    print(f"\n{'='*70}\nH1 baseline-feasibility check (Section 4: target <=1.2x for >=2/3 "
          f"non-English languages -- this is a Phase 3 C0-vs-C2 criterion; "
          f"below is what Phase 1's C0-only baseline actually measures)\n{'='*70}")
    for _, r in cost_results.iterrows():
        if pd.isna(r["median_ratio"]):
            continue
        note = "ALREADY <=1.2x at baseline (little room for LEEH to show effect)" if r["ci_high"] <= 1.2 else \
               ("plausible target for LEEH to reach" if r["median_ratio"] <= 3.0 else
                "large gap -- ambitious target for LEEH")
        print(f"{r['model']:16s} {r['language']}: baseline median cost ratio "
              f"{r['median_ratio']:.2f}x [{r['ci_low']:.2f}, {r['ci_high']:.2f}]  -- {note}")

    accuracy_results = analyze_accuracy()

    cost_results.to_csv(ROOT / "results" / "phase1_cost_ratios.csv", index=False)
    token_results.to_csv(ROOT / "results" / "phase1_fertility_ratios.csv", index=False)
    accuracy_results.to_csv(ROOT / "results" / "phase1_accuracy_diffs.csv", index=False)
    print(f"\nSaved -> results/phase1_cost_ratios.csv, results/phase1_fertility_ratios.csv, "
          f"results/phase1_accuracy_diffs.csv")
