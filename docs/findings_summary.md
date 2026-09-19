# Phase 1 findings summary

Baseline (C0, no intervention) measurement results for `gpt-5.6-luna` and
`deepseek-flash` across English/Spanish/Chinese/Arabic on MGSM and MAPS
(GAIA+MATH subsets). See pre_registration.md for the frozen design and
docs/methodology-notes.md for the full implementation-level log this
summary draws from.

## Cost ratio (non-English / English), paired by task_id

| model | language | median ratio | 95% BCa CI | Holm-significant |
|---|---|---|---|---|
| deepseek-flash | es | 1.36x | [1.27, 1.45] | yes (p=2.5e-7) |
| deepseek-flash | zh | 1.30x | [1.21, 1.38] | yes (p=6.3e-5) |
| deepseek-flash | ar | 1.07x | [0.96, 1.39] | no |
| gpt-5.6-luna | zh | 1.08x | [1.03, 1.17] | yes (p=0.007) |
| gpt-5.6-luna | es | 1.06x | [1.01, 1.08] | no |
| gpt-5.6-luna | ar | 1.03x | [0.88, 1.14] | no |

`deepseek-flash` shows a real, significant baseline token tax on
Spanish/Chinese (1.3-1.36x); `gpt-5.6-luna` is already near parity on all
three. Full detail: results/phase1_cost_ratios.csv, results/phase1_fertility_ratios.csv.

## Accuracy

MGSM and MAPS/GAIA accuracy use clean short-answer ground truth
(`answer_number`, `Final answer`) and are reliable as measured. MAPS/Math
accuracy required a scoring fix (see Threats to Validity) -- corrected
numbers below.

| model | dataset | language | accuracy (successful attempts) |
|---|---|---|---|
| gpt-5.6-luna | MGSM | en/es/zh | 90-96% |
| deepseek-flash | MGSM | en/es/zh | 90-96% |
| gpt-5.6-luna | MAPS/GAIA | en/es/ar | 20-30% |
| deepseek-flash | MAPS/GAIA | en/es/ar | 32-35% |
| gpt-5.6-luna | MAPS/Math | en/es/ar | 50-70% (corrected) |
| deepseek-flash | MAPS/Math | en/es/ar | 70-80% (corrected) |

Paired English-vs-non-English Wilcoxon tests on accuracy (results/phase1_accuracy_diffs.csv)
did not reach significance for any language/model after Holm-Bonferroni
correction. This file reflects the corrected (post-Math-fix) accuracy
numbers -- see Threats to Validity for the fix itself.

## Threats to validity

- **MAPS/Math accuracy scoring bug (fixed 2026-09-15).** `expected_answer`
  for Math was the full worked `solution` text, and correctness was a
  verbatim substring match against that -- which essentially never matches
  even when the model's answer is correct, since models paraphrase their
  derivation differently from the reference. This produced a flat 0.0%
  accuracy for MAPS/Math across every model and language, which was a
  measurement artifact, not a real result. Fixed by extracting the final
  answer from the reference solution's `\boxed{...}` (Hendrycks MATH
  convention; balanced-brace parsing, not a naive regex, since answers can
  contain nested braces like `\boxed{\frac{121}{25}}`) and matching that
  short value against the already-saved model answer -- no API calls
  re-run. Corrected accuracy: 50-80% depending on model/language, a
  realistic range for competition math. **Merged into phase1_raw.csv's
  `correct` column and into phase1_accuracy_diffs.csv's Wilcoxon test**
  (the intermediate side file, `results/phase1_maps_math_rescored.csv`,
  no longer exists -- merged in and deleted). The cost ratio, accuracy,
  and Wilcoxon numbers in this document all reflect the corrected data;
  none of them need re-running.

- **deepseek-flash/MAPS/GAIA: survivorship bias across all three
  languages** (es, en, ar -- not just Arabic; see
  docs/methodology-notes.md's 2026-09-15 entry for the full breakdown and
  correction of an earlier Arabic-only framing). Completion rates of
  11-21% mean the ~19-20 surviving tasks per language may be a biased
  (easier/shorter) subset of the full attempted set, which could make
  `deepseek-flash`'s measured GAIA cost ratio, fertility ratio, and
  accuracy look better than its true performance on the full
  distribution. `gpt-5.6-luna`'s GAIA completion (65-74%) does not carry
  this caveat.

- **DeepSeek API outage + account-balance exhaustion** during data
  collection (2026-09-14/15) affected `deepseek-flash` specifically;
  `gpt-5.6-luna` was unaffected throughout. Full detail in
  methodology-notes.md.

- **`deepseek-flash`/MAPS/GAIA final N is 19-20/20**, not the full
  pre-registered 20/20, for one specific task
  (`72c06643-a2fa-4186-aa5c-9ec33ae9b445`, a Freon-12/Marianas-Trench
  physics problem) that reproducibly times out at 120s for this model.
  Treated as a genuine truncation-failure data point rather than a gap to
  paper over.
