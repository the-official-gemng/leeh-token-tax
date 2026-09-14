# Methodology notes / threats to validity

Implementation-level notes for the eventual write-up. This file tracks
things that affected data collection but are **not** pre-registration
amendments -- nothing here changes the frozen scope (languages, datasets,
task counts, decision rules) in pre_registration.md. Parameters like a
client-side timeout live in scripts/run_phase1.py, not in the frozen
design, so bugs in them get fixed and documented here instead.

## 2026-09-14 -- HARD_TIMEOUT_S too tight for GAIA, undercounted successes

**What happened:** scripts/run_phase1.py wraps each model call in a hard
wall-clock ceiling (a thread-based timeout independent of the API client's
own retry/backoff behavior -- see the comment above `HARD_TIMEOUT_S` in the
script for why that's necessary at all). While tuning this value down to
push through an unrelated DeepSeek API outage, it was set to 30s. That
value was fine for MGSM and MAPS/Math but too tight for MAPS/GAIA, which
produced long-form answers even from a `gpt-5.6-luna` baseline unaffected
by the outage.

**Diagnostic evidence:** at the 30s ceiling, GAIA success rate was 41.7%
(n=120) vs. 82.4% (n=499) for everything else (MGSM + MAPS/Math combined).
Critically, this gap showed up on `gpt-5.6-luna` too, which had zero
DeepSeek-outage-related failures anywhere else -- ruling out "bad luck with
the outage" as the explanation. Looking at latency on the calls that *did*
succeed under the 30s ceiling: GAIA answers averaged 18.2s (median 17.4s,
max 29.5s) -- right up against the wall, and not explained by longer
prompts (GAIA questions average 218 chars, actually shorter than MAPS/Math's
268). GAIA simply requires longer generations to answer even without any
tool use, so a large share of the "failures" were genuine in-progress
responses getting cut off, not the model or the API being unavailable.

**Fix:** raised `HARD_TIMEOUT_S` to 120s, uniformly across all datasets
(not a GAIA-specific value) -- see the comment in run_phase1.py. A single
generous ceiling avoids repeating this exercise if MAPS/Math or MGSM ever
produces its own slow outlier, and avoids the appearance of tuning
per-dataset.

**Impact on results:** any `phase1_raw.csv` rows logged before this fix
with `error = "Hard timeout: no response within 30s (thread abandoned)"`
on a GAIA row are very likely undercounting genuine successful completions,
not measuring true model unavailability. The resumable run design (skip
already-successful `(model, dataset, subset, language, task_id,
repeat_index)` keys) means the post-fix run re-attempts exactly those
same task instances rather than drawing new samples, so pairing for the
Wilcoxon signed-rank analysis (Section 3 of pre_registration.md) is
preserved -- confirmed by checking that sampled task_id sets are identical
across languages for MGSM, MAPS/Math, and MAPS/GAIA before re-running.

## 2026-09-14 -- DeepSeek API outage during MAPS collection

**What happened:** `deepseek-flash` calls started failing/hanging around
11:31am PDT and continued intermittently for several hours (23:34 UTC per
third-party outage trackers, though DeepSeek's own status page reported
"all systems operating normally" throughout -- status pages can lag actual
degradation). Confirmed via direct empirical testing (repeated smoke-test
calls) rather than relying on either source alone. This affected MGSM/zh
and MAPS/Math (en/es/ar) collection for `deepseek-flash` specifically --
`gpt-5.6-luna` was unaffected throughout.

**Impact:** some `deepseek-flash` rows in `phase1_raw.csv` carry
`error = "Request timed out."` or `"Hard timeout: ..."` / `APIConnectionError`
from this window. The resumable run design re-attempts these same task
instances once the outage cleared; the CSV retains the failed attempt rows
too (not deleted), so the full retry history is auditable.
