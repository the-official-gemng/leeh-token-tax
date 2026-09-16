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

## 2026-09-14 -- deepseek-flash/MAPS/GAIA: final N short of target (account balance)

**What happened:** after the outage (above) and the timeout-ceiling fix,
closing the remaining `deepseek-flash`/GAIA gap needed several resume
passes -- GAIA's per-attempt success rate for this model stayed low
(roughly 35-40%) even outside the outage window, for reasons not fully
diagnosed (plausibly this model needing more attempts to produce a
well-formed long-form GAIA answer within the timeout, independent of the
earlier outage). An automated retry loop (`--retry-until-filled` in
run_phase1.py) was added to close this without manual re-launching. Partway
through, the DeepSeek account ran out of balance (`APIStatusError: Error
code: 402 - Insufficient Balance`, first occurrence 2026-09-14T20:01:48).
Every attempt after that point failed instantly and unrecoverably --
distinguishable in the data from the earlier outage/timeout failures by
being a fast, explicit billing rejection rather than a slow timeout.

**Impact:** `deepseek-flash`/MAPS/GAIA finished this data-collection phase
below the pre-registered 10 tasks x 2 repeats = 20 target for all three
languages: ar 18/20, en 17/20, es 15/20 (vs. 20/20 for every other
model x dataset x language x subset cell, including gpt-5.6-luna/GAIA and
deepseek-flash/Math). This is a real reduction in statistical power
specifically for `deepseek-flash` GAIA comparisons -- smaller matched-pair
sample for the Wilcoxon signed-rank test on that cell -- not a sampling or
pairing issue (task_id alignment with the successfully-collected instances
is unaffected; see the entry above). Resolvable by adding funds and running
`python scripts/run_phase1.py --models deepseek-flash --retry-until-filled`
again, which will pick up exactly these remaining task instances.

**Update 2026-09-15 -- funds added, closed to 19/20 (not 20/20), and why:**
After funding, three more retry passes closed ar to 20/20 and brought en/es
to 19/20 each. The single remaining gap in both is the *same* GAIA task
(`task_id=72c06643-a2fa-4186-aa5c-9ec33ae9b445`, en repeat 2 / es repeat 1)
-- a physics problem asking for the volume of Freon-12 refrigerant at the
bottom of the Marianas Trench. It was attempted 50 times per language slot;
excluding stale pre-funding 402s, every single post-funding attempt (~18-21
per language) timed out at the full 120s ceiling. This reads as a genuine,
reproducible property of this task for `deepseek-flash` -- not transient
flakiness -- so further retries were stopped rather than continuing to burn
calls on a call that won't complete.

This is arguably a legitimate data point in its own right: pre_registration.md
Section 1 lists "truncation-failure rate" as a tracked metric, and a task
`deepseek-flash` cannot complete within a generous 120s budget is exactly
that. Final N for `deepseek-flash`/MAPS/GAIA: ar 20/20, en 19/20, es 19/20
(vs. 20/20 everywhere else in the dataset). The paired analysis in
analyze_phase1.py handles this without special-casing: a task_id is only
included in a pair when both its English and target-language sides have at
least one successful repeat, so this one task is naturally underweighted
(fewer averaged repeats) rather than dropped or corrupting other pairs.

## 2026-09-15 -- deepseek-flash/MAPS/GAIA: survivorship-bias risk applies to all three languages, not just Arabic

**Correction:** an earlier informal summary of this data described the
survivorship-bias concern below as an Arabic-specific issue. It isn't --
it applies to `deepseek-flash`'s GAIA results in **all three** languages
(es, en, ar). Recording it properly here instead of leaving it only in
conversation.

**What the concern is:** the final successful-attempt ratios for
`deepseek-flash`/MAPS/GAIA are low enough that the 19-20 tasks that
*did* survive into the paired sample per language may not be
representative of the full attempted set -- if failure (timeout at the
120s ceiling) correlates with task difficulty/length, the surviving
sample is biased toward easier/shorter tasks, which would make
`deepseek-flash`'s measured GAIA cost ratio, fertility ratio, and
accuracy all look *better* than its true performance on the full task
distribution.

**Evidence (successes / total attempts, i.e. including all retry rounds
across the outage and balance-shortfall episodes above):**

| language | successes | attempts | completion rate |
|---|---|---|---|
| es | 19 | 170 | ~11% |
| en | 19 | 124 | ~15% |
| ar | 20 | 94 | ~21% |

All three are low enough to carry this caveat -- es and en are actually
*worse* than ar's completion rate, not better, so singling out Arabic was
specifically wrong, not just incomplete.

**Contrast:** `gpt-5.6-luna`'s GAIA completion is 65-74% across all three
languages (ar 20/27, en 20/31, es 20/27) -- healthy enough that this
caveat does not apply to it. This is model-specific, not a property of
GAIA or of any particular language.

**Status:** not fixed -- flagging as a known limitation on the
`deepseek-flash`/GAIA cell of every Phase 1 metric, rather than a bug
with a code fix. Closing it for real would mean either a much higher
timeout ceiling specifically to give `deepseek-flash` a fairer shot at
GAIA's long-form answers, or accepting the smaller/biased sample as a
limitation in the eventual write-up.

## 2026-09-15 -- harness/packer.py and harness/expander.py had no hard-timeout protection (Phase 3 bug, now fixed)

**What happened:** both modules call the model directly to do their own
translation (packer.py's MT-based mode translates the input; expander.py
translates the output back) via `run_phase1.call_model` -- the *raw*,
unprotected function. Only `harness/executor.py` used
`call_model_with_hard_timeout`. Condition C1 makes 3 calls per task
(translate-in, execute, translate-out), so 2 of its 3 calls had zero
protection against the exact class of SDK-level hang that
`call_model_with_hard_timeout` exists to prevent (see the comment above
that function in run_phase1.py). Surfaced as a ~35-minute stall during a
Phase 3 C1 `--retry-until-filled` run -- diagnosed by confirming a fresh
process and raw network reachability both worked fine immediately
(ruling out an actual outage), which pointed at something specific to
the long-running process's own call path instead.

**Fix:** both modules now import `call_model_with_hard_timeout` (aliased
to the name `call_model` so the rest of each module's code didn't need
to change) instead of the raw function. Verified with a direct smoke
test post-fix.

**Note:** `harness/conditions.py`'s C2 path already usually avoided this
exposure in practice -- prompt-based mode means expander.py's translation
call only fires when the model didn't already answer in the target
language, which is the common case, not the rare one. C2's actual Phase 3
run finished 540/540 with zero errors *before* this bug was found, so it
wasn't re-run -- the exposure existed in the code but didn't happen to
manifest there.

## 2026-09-15 -- Phase 3 C1: same Freon-12 GAIA task blocks deepseek-flash again, plus balance ran out again

**What happened:** after the hard-timeout fix above, C1's
`deepseek-flash`/MAPS block converged to 116/120 and then stopped
improving. The 4 remaining gaps (en repeat 1, es repeat 1, ar repeat 1,
ar repeat 2) are all the *same task* identified in Phase 1's entry above
(`task_id=72c06643-a2fa-4186-aa5c-9ec33ae9b445`, the Freon-12/Marianas
Trench volume problem) -- mostly genuine 120s timeouts (10-12 per slot),
consistent with Phase 1's finding that this specific task is a
reproducible truncation-failure for this model, not something more
retries fix. The DeepSeek account also ran out of balance again partway
through (a handful of 402s mixed into the same slots). Checked directly
afterward: balance is currently depleted (`call_model` to `deepseek-flash`
returns `402 Insufficient Balance` right now).

**Status:** stopped rather than continuing to retry against an empty
balance and an already-documented task-level limitation. Final C1 state:
536/540 (99.3%) -- `deepseek-flash`/MAPS at 116/120, everything else
(gpt-5.6-luna both datasets, deepseek-flash/MGSM) at full target. Mirrors
Phase 1's own resolution of the identical task (accepted 19/20 rather
than exhausting funds indefinitely).

## Generalization spot-check (exploratory, post-Phase-3)

**This sits outside the frozen pre-registered design.** pre_registration.md
Section 1 fixes the two models under test (`gpt-5.6-luna`,
`deepseek-flash`) and the full task set; nothing about that is changing
here, so there is no pre_registration.md Amendments Log entry for this --
scope isn't changing, an exploratory side-check is being added alongside
it.

**What this is:** Phase 1 found a real, statistically significant
baseline token tax for `deepseek-flash` on Spanish/Chinese (median cost
ratio 1.30-1.36x) and a near-null tax for `gpt-5.6-luna` (1.03-1.08x,
mostly not significant) -- see docs/findings_summary.md. An open question
this raises: is that split a property of the *tokenizer* each model uses
(which would suggest it generalizes to other models sharing similar
tokenizer characteristics), or something idiosyncratic to these two
specific models? scripts/run_generalization_check.py adds two more
cheap-tier models (`qwen3.5-flash`, `gemini-3.5-flash-lite` -- see below
for why not gemini-2.5-flash-lite as originally named) and re-runs a
small MGSM-only (en/es/zh) check to see which pattern, if either, each
new model's tax tracks.

**By design, this is underpowered and not meant to hit significance.**
N=30/language/model, one dataset (MGSM), no repeats, vs. Phase 1's
N=50/language on MGSM alone plus the full MAPS battery. It exists to show
*directional* consistency (does the new model's ratio land near
`deepseek-flash`'s territory or `gpt-5.6-luna`'s?), not to produce a
publishable effect size or a corrected-for-multiple-comparisons
significance test. Results should be read qualitatively.

**Model substitution:** `gemini-2.5-flash-lite` (as originally specified)
returned `404 Not Found` -- "no longer available to new users... use
models/gemini-3.5-flash-lite instead." Substituted per direction, with
pricing re-verified for the substitute specifically against Google's
official pricing page rather than assumed to match the retired model's
rate (they don't: $0.30/$2.50 per 1M in/out for 3.5-flash-lite vs. the
originally-assumed $0.10/$0.40 for 2.5-flash-lite).

**Other implementation notes:**
- `qwen3.5-flash`'s DashScope base_url wasn't unambiguous across official
  documentation pages (one showed a newer workspace-ID-scoped endpoint,
  another the long-standing simple form) -- resolved with a live
  smoke-test call rather than trusting either doc page blindly; the
  simple `dashscope-intl.aliyuncs.com/compatible-mode/v1` form works.
- `.env` already had the Qwen key under `QWEN_API_KEY`, not
  `DASHSCOPE_API_KEY` as originally specified -- used the name actually
  present rather than requesting a rename.
- `qwen3.5-flash` used surprisingly many completion tokens even on a
  trivial "Say OK." prompt (137 tokens) and real MGSM questions (800-1100
  tokens) -- consistent with an internal reasoning/thinking mode running
  before the visible answer. This inflates its absolute cost regardless
  of language, but doesn't by itself bias the *ratio* (non-English /
  English) this check cares about, since the same reasoning behavior
  applies to English too.
- Total batch cost: ~$0.08 for all 180 calls, confirmed via real-MGSM-
  question smoke tests before running (not the misleadingly cheap
  trivial-prompt smoke test, given qwen3.5-flash's reasoning-token
  behavior above).
