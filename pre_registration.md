---
project: LEEH — Language Efficiency Equalizer Harness
document: Phase 1 Pre-Registration
status: FROZEN
version: 1
team: Lucas + teammate (___)
---

# Pre-Registration — Phase 1 (Measurement Study)

Written and frozen **before** any Phase 1 data is collected or looked at.
Do not edit the Hypotheses, Metrics, or Decision Rules sections after freezing —
log any change in the Amendments Log at the bottom instead, with a date and reason.

## 1. Frozen configuration

**Models** (exact API identifiers — fill in the snapshot/version date the day you start running):

| Slot | Model | Notes |
|---|---|---|
| Western, cheap tier | `gpt-5.6-luna` | Confirmed real, cheapest tier of the GPT-5.6 family (Sol > Terra > Luna). Token counting: tiktoken. |
| Chinese-origin, cheap tier | `deepseek-flash` | Direct match for the "cheap tier" slot, pairs symmetrically with Luna. Token counting: `deepseek-ai/DeepSeek-V4-Flash` tokenizer on Hugging Face. |
| Snapshot date | _fill in on Day 1_ | Record the exact date you pin these; if either provider updates the model under the same name mid-study, re-baseline C0 before comparing (Threats to Validity). |

**Languages:** English (reference), Chinese, Arabic, Spanish.

**Datasets:**
- Single-turn: MGSM, ~50 problems/language, N=1 repeat.
- Agentic: MAPS (GAIA + MATH subsets only), ~8–10 tasks/language/subset (~16–20/language total), N=2 repeats.
- Trusted cross-check: GAIA-v2-LILT, Arabic slice.

**Metrics:** total tokens, fertility ratio (tokens[lang] ÷ tokens[English]), dollar cost (price pulled the day of the run — record the pull date here: __________), wall-clock latency, exact-match accuracy, tool-call count, truncation-failure rate.

## 2. Hypotheses (Phase 1 is measurement-only; these are tested in Phase 3, but the measurement design must support them)

- **H1 (primary):** LEEH (C2, Phase 3) reduces the median cost ratio vs. English from the Phase-1-measured baseline down to ≈1.05–1.2×.
- **H2 (non-inferiority):** LEEH's task accuracy is not meaningfully worse than the no-intervention baseline (C0). Non-inferiority margin: **≤2 accuracy points.**
- **H3:** LEEH (C2) beats naive translate-to-English (C1) on accuracy.
- **H4 (stretch, only if the C3a ablation is run):** removing the token-budget equalizer measurably increases the truncation-failure rate for high-fertility languages.

## 3. Statistical plan (decided now, not after seeing results)

- Primary test: paired Wilcoxon signed-rank, English vs. language X, per model, on matched task instances.
- Multiple-comparison correction: Holm–Bonferroni across the 2 models × 3 non-English languages = 6 pairwise tests.
- Effect sizes: bootstrap 95% CI (BCa, ≥10,000 resamples) reported alongside every ratio.
- Significance level: α = 0.05 (corrected).
- Mixed-effects model: optional/stretch, not required for the core claims.

## 4. Decision rules (what counts as a pass, decided in advance)

- H1 supported if the measured cost ratio's 95% CI upper bound is ≤1.2× for at least 2 of the 3 non-English languages.
- H2 supported if the accuracy CI does not exclude a difference smaller than the 2-point margin.
- H3 supported if C2's accuracy exceeds C1's with the corrected test significant at α=0.05.
- If a language or dataset turns out infeasible (e.g., API errors, missing translations), document it in the Amendments Log below — do not quietly drop it and stay silent.

## 5. Amendments Log

_(Leave empty until frozen. Any change after freezing goes here — logged as a PR, not a silent edit.)_

| Date | Change | Reason | PR link | Approved by (both) |
|---|---|---|---|---|
| | | | | |
