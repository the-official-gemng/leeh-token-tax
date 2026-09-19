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

## 2026-09-16 -- harness/equalizer.py's BASE_MAX_TOKENS was drastically undersized for MAPS (fixed)

**What happened:** `BASE_MAX_TOKENS = 2048` (English's budget, before the
per-language multiplier) was an unvalidated guess made when building the
Equalizer, never checked against what these tasks actually need. Phase 1's
own C0 data (uncapped, no max_tokens set at all) shows MAPS completion_tokens
averaging 4702 with a max of **28778** -- even after the fertility
multiplier (up to ~1.87x), the resulting C2 budgets (2048-2735 tokens)
were a small fraction of that. First full C2 run: **41.7% of MAPS answers
truncated mid-generation** (vs. 0% in C0). This corrupted the first
H1/H2/H3 pass -- both the apparent accuracy collapse and the apparent
cost *increase* under C2 were substantially truncation artifacts, not a
real reflection of LEEH's design. MGSM was unaffected (truncation ~1%,
its answers are naturally short).

**Fix:** `harness/conditions.py`'s `run_c2`/`run_c3a`/`run_condition` now
accept an explicit `base_max_tokens` override, threaded through to
`execute_equalized()`. `scripts/run_phase3.py` sets it per dataset,
calibrated from C0's own observed distribution rather than guessed again:
`MAX_TOKENS_BY_DATASET = {"MGSM": 8192, "MAPS": 32768}` (both comfortably
above C0's respective observed max: 6879 and 28778).
`harness/equalizer.py`'s own default also moved from 2048 to 8192 (safe
for MGSM-scale callers that don't pass an override; MAPS-scale callers
must pass one explicitly -- 8192 alone is still not enough for MAPS).

**Also found:** `phase3_c1_raw.csv` and `phase3_c2_raw.csv` needed the
same MAPS/Math boxed-answer scoring fix already applied to
`phase1_raw.csv` (see the entry earlier in this file) -- they'd been
generated with the same broken always-0%-on-Math scoring and were never
patched. Caught before the first H1/H2/H3 report, since C0 (fixed) vs
C1/C2 (still broken) would have been an apples-to-oranges accuracy
comparison. Rescored in place, no API calls re-run (same approach as the
original fix -- extract `\boxed{}` from the reference solution, check it
against the already-saved model answer).

**Re-run:** removed just the truncated MAPS rows from
`phase3_c2_raw.csv` (truncated=True isn't an `error`, so resumability
wouldn't have retried them on its own) and reran C2 with the corrected
budgets. `gpt-5.6-luna` closed cleanly. `deepseek-flash` hit its now-familiar
balance depletion again partway through (same account, same recurring
pattern documented earlier in this file) -- refunded and completed after.
Final C2: 540/540 successes, 0.56% truncation (down from 19% -- MGSM's
own ~1% plus a handful of genuine long-tail MAPS answers, not budget-
constrained).

**Result, now trustworthy:** H1 is not supported for either model (C2's
cost ratios are *higher* than Phase 1's own baseline ratios in most
cells, not lower -- seemingly a real effect of the "reason in English,
then answer" structure adding overhead, not a truncation artifact this
time). See the chat report / results/decision_rule_h1.csv,
decision_rule_h2.csv, decision_rule_h3.csv for the full H1/H2/H3 numbers.

## 2026-09-16 -- Post-hoc exploratory follow-up: lean system prompt (v2), MGSM only

**Status:** this section documents a post-hoc exploratory refinement of the
harness, run *after* the confirmatory Phase 3 decision-rule check above.
It does **not** replace or overwrite that result. **H1/H2/H3 = "not
supported" (previous section) remains the pre-registered, citable
confirmatory finding.** This entry only investigates *why* and tests one
targeted fix, scoped to MGSM (en/es/zh), saved to a separate file
(`results/phase3_c2_raw_v2_leanprompt.csv`) that was never merged into
`phase3_c2_raw.csv`. No `pre_registration.md` changes.

**Diagnosis, quantified before changing anything:** compared mean prompt
tokens and dollar cost (input vs output) for C0 vs C2 (v1) on
gpt-5.6-luna/zh and deepseek-flash/zh. Both models show a **bimodal**
prompt-token delta, not a uniform one:
- ~65-70% of rows: delta is a *constant* +80 tokens (gpt-5.6-luna) / +78
  tokens (deepseek-flash) -- matches Packer's 76-token
  `_PROMPT_MODE_SYSTEM_TEMPLATE` almost exactly (+ ~4 tokens of chat-
  format overhead). This is the system-prompt-overhead effect the v1
  root-cause hypothesis pointed at, and it's confirmed, cleanly.
- ~30-36% of rows: delta is +205 to +398 tokens, far larger than the
  template could explain on its own, and correlated with a real jump in
  completion_tokens and latency too (not just prompt_tokens).

Weighting by row count, that second group turned out to dominate the
overall mean cost gap: it explains only ~5% of gpt-5.6-luna/zh's gap
(system prompt explains the other ~95%) but **~95%** of gpt-5.6-luna's
own MGSM/zh gap is from the anomalous group, and roughly **50%** of
deepseek-flash/zh's gap either way. In other words, the original "traces
almost entirely to the system prompt" framing was too strong for
gpt-5.6-luna specifically -- confirmed quantitatively before proceeding,
per the same "verify before trusting" standard applied throughout this
project.

**Investigated the anomalous group before writing it off as untouchable:**
reconstructed the exact `messages` list (via a live `pack()` call) for
two task_ids that had shown the anomaly in the original run, and fired 8
fresh repeat API calls each (32 total, both models). The anomaly **never
reproduced** -- every repeat landed at the expected low value, and
`tool_calls` was never non-null (ruling out a hidden second turn through
`executor.py`'s tool loop, the only code path that could legitimately
double-count prompt tokens). Original-run timestamps for the high- and
low-delta rows are interleaved within the same few minutes, ruling out
stale-code contamination from an earlier harness version too. Conclusion:
this is not reproducible on demand and not attributable to a bug in this
repo's code -- most likely transient provider-side variance in how this
particular model bills prompt tokens on some fraction of calls. Left
unresolved; flagging it here rather than continuing to chase it, since it
isn't fixable from the harness side with the visibility available.

**Fix applied:** `harness/packer.py`'s `_PROMPT_MODE_SYSTEM_TEMPLATE`
trimmed from 76 to 18 tokens (verified via tiktoken o200k_base), keeping
only the two obligations the pipeline actually depends on -- reason in
English, answer only in the target language, preserve numbers/formatting.
Manually spot-checked on 4 real MGSM questions (both models, es and zh)
before running the full set: correct language, correct answer, no
language mixing, formatting intact in all 4.

**Re-run:** `python scripts/run_phase3.py --condition c2 --datasets MGSM
--output-suffix _v2_leanprompt --retry-until-filled`. Added `--datasets`
and `--output-suffix` flags to `scripts/run_phase3.py` for this (generic,
reusable -- not a one-off hack). 300/300 rows, 0 errors, 0 truncation, one
round.

**Result -- cost ratio (C2/C0), v1 vs v2:**

| model | lang | v1 ratio | v2 ratio | cleared 1.2x? |
|---|---|---|---|---|
| gpt-5.6-luna | es | 1.140x | **0.975x** | yes (already close in v1, now clearly under) |
| gpt-5.6-luna | zh | 1.477x | **1.260x** | no -- improved but still above 1.2x |
| deepseek-flash | es | 0.999x | 1.071x | yes (was already under in v1) |
| deepseek-flash | zh | 1.230x | 1.350x | no -- moved further from 1.2x |

**Accuracy (C0 / C1 / v1 / v2), held steady, no quality regression:**
gpt-5.6-luna/es 96/90/94/94, gpt-5.6-luna/zh 92/84/92/90, deepseek-flash/es
90/92/90/92, deepseek-flash/zh 94/90/90/90 (all percentages, n=50 each).
No sign the leaner prompt is quietly trading accuracy for cost.

**Why deepseek-flash got *worse*, not better, in v2:** checked whether the
anomalous-token group's *occurrence rate* changed between v1 and v2 draws
(it should be independent of prompt length if the diagnosis above is
right). It didn't move meaningfully -- gpt-5.6-luna/zh 34%->36%,
deepseek-flash/zh 30%->32%, both /es groups near-identical rates too. The
*median* delta dropped exactly in proportion to the template shrink (80->22
gpt-5.6-luna, 78->18 deepseek-flash) confirming the fix itself worked
cleanly on the population it targets. deepseek-flash/es and /zh coming out
worse in v2 is best read as between-run sampling noise in the (still
unexplained) anomalous group's per-call severity, not a real effect of the
shorter prompt -- N=50 single-draw comparisons aren't enough to separate
those given the anomaly's apparent non-determinism. Flagging rather than
asserting either way.

**Bottom line:** the lean-prompt fix is real, verified, and worth keeping
-- it cleanly removes the template-overhead component of the cost gap
(confirmed via the median-delta match) and doesn't touch accuracy. But it
is not a complete fix for H1: gpt-5.6-luna/zh and deepseek-flash/zh still
sit above the 1.2x threshold, driven by a separate, non-reproducible,
unresolved cost anomaly that a prompt-length change can't address. This
is an exploratory, underpowered (N=50, single draw, no CI/Holm-Bonferroni
correction) follow-up -- not a re-run of the confirmatory test, and it
does not change the "H1 not supported" conclusion on file above.

**NOTE (see next entry below): the "Why deepseek-flash got worse" paragraph
above turned out to be wrong.** It claimed the anomalous group's per-call
severity was roughly equal between v1 and v2, making deepseek-flash's
regression pure sampling noise. Directly tested afterward and disproven --
see the 2026-09-16 "H1 recheck + retraction" entry below for the real
numbers. Left the paragraph above unedited (rather than silently rewritten)
so the record of what was claimed and when stays intact; treat it as
superseded, not current.

## 2026-09-16 -- H1 recheck under the real decision rule, a corrected statistic, and a retraction

This entry closes out the harness-debugging thread that produced the v2
lean-prompt entry above. It's a documentation/analysis pass only -- no new
experiment runs, no harness/ changes beyond what's already on file, no
further chasing of the unresolved cost anomaly.

**1. The v2 lean-prompt fix itself stands, verified correctness-neutral.**
The 76-to-18-token system prompt trim (previous entry) held accuracy
steady across all four checked cells (gpt-5.6-luna es 96/90/94/94,
gpt-5.6-luna zh 92/84/92/90, deepseek-flash es 90/92/90/92, deepseek-flash
zh 94/90/90/90 -- C0/C1/v1/v2, n=50 each) and did remove the
template-overhead cost component it specifically targeted: the *median*
prompt-token delta vs C0 dropped in exact proportion to the template
shrink (gpt-5.6-luna 80->22, deepseek-flash 78->18 tokens), confirmed
again in this round's anomalous-subset check below. Nothing here changes
that -- it's a real, narrow fix, worth keeping.

**2. Under the correct pre-registered statistic, H1 remains not
supported, even with the fix applied.** H1's actual decision rule
(`scripts/analyze_decision_rules.py`'s `h1_cost_ratio()`) is bootstrap CI
of the **median per-task cost ratio** (BCa->percentile fallback,
alpha=0.05, 10,000 resamples), CI upper bound <=1.2x, for >=2/3
non-English languages. Recomputed with that exact statistic: ar unchanged
from the original confirmatory run, es/zh recomputed from the v2
lean-prompt file --

| model | lang | source | n | median ratio | 95% CI | <=1.2x? |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | ar | original (unchanged) | 20 | 0.999x | [0.837, 1.204] | No |
| gpt-5.6-luna | es | v2 | 50 | 1.017x | [0.972, 1.111] | Yes |
| gpt-5.6-luna | zh | v2 | 50 | 1.209x | [1.078, 1.794] | No |
| deepseek-flash | ar | original (unchanged) | 20 | 1.054x | [0.864, 1.335] | No |
| deepseek-flash | es | v2 | 50 | 1.304x | [1.200, 1.419] | No |
| deepseek-flash | zh | v2 | 50 | 1.677x | [1.390, 2.257] | No |

gpt-5.6-luna: 1/3 (es only). deepseek-flash: 0/3. **H1 not supported for
either model**, v2 lean prompt included -- consistent with, not a reversal
of, the standing confirmatory result.

**3. Correction: an earlier report in this thread used the wrong
statistic.** The "v1 vs v2 cost ratio (C2/C0)" table given in chat used
**ratio of mean costs** (`b.cost_usd.mean() / a.cost_usd.mean()`), not
H1's actual statistic (median of per-task ratios + bootstrap CI). All four
cells in that table are affected, not just one:

| model | lang | reported (wrong: ratio-of-means) | correct (median-ratio + CI) |
|---|---|---|---|
| gpt-5.6-luna | es, v1 | 1.140x | 1.173x, CI [1.119, 1.223] -- fails |
| gpt-5.6-luna | es, v2 | 0.975x | 1.017x, CI [0.972, 1.111] -- **passes** |
| gpt-5.6-luna | zh, v1 | 1.477x | 1.472x, CI [1.312, 1.711] -- fails |
| gpt-5.6-luna | zh, v2 | 1.260x | 1.209x, CI [1.078, 1.794] -- fails |
| deepseek-flash | es, v1 | 0.999x ("already passing") | 1.530x, CI [1.289, 1.619] -- **fails clearly** |
| deepseek-flash | es, v2 | 1.071x | 1.304x, CI [1.200, 1.419] -- fails clearly |
| deepseek-flash | zh, v1 | 1.230x | 1.867x, CI [1.546, 2.087] -- fails clearly |
| deepseek-flash | zh, v2 | 1.350x | 1.677x, CI [1.390, 2.257] -- fails clearly |

The worst miss: deepseek-flash/es v1 was reported as "already under 1.2x"
(0.999x) and treated as a pass. Under the real statistic it's 1.530x with
a CI entirely above 1.2 -- a clear fail, in both v1 and v2. **Do not reuse
the "reported" column above for anything** -- point estimates and pass/fail
calls from that chat table are superseded by this entry's table and by
`results/decision_rule_h1.csv`/this entry's es/zh-from-v2 numbers.
Accuracy figures reported alongside that table were plain percentages, not
a ratio statistic, and are unaffected.

**4. v1-vs-v2 is not a clean before/after -- scope differs.** v1's es/zh
numbers (`results/decision_rule_h1.csv`, and the "reported" column above)
pool MGSM+MAPS. v2 is MGSM-only (that's all that was re-run). Same
statistical method applied to both, but not the same underlying task set
-- the table in point 3 compares them anyway because that's what was
asked, but treat any v1-vs-v2 delta as directional, not a controlled
before/after.

**5. Retraction: the "anomaly severity is roughly equal, deepseek's
regression is pure noise" explanation (previous entry) is false, tested
directly.** For the anomalous row subset only (delta > that run's own
median + 40), mean and median prompt-token delta vs C0, v1 vs v2:

| model | v1 mean / median (n) | v2 mean / median (n) |
|---|---|---|
| gpt-5.6-luna (es+zh pooled) | 256.2 / 248.5 (n=20) | 181.0 / 186.0 (n=25) |
| deepseek-flash (es+zh pooled) | 256.1 / 265.0 (n=17) | 212.7 / 195.0 (n=18) |

Severity went **down** from v1 to v2 for both models, not "roughly equal."
deepseek-flash's anomalous subset got cheaper per row (265.0 -> 195.0
median) while its overall es/zh cost ratio still got worse -- so the
anomalous subset is demonstrably **not** what's driving deepseek-flash's
v1->v2 regression. The real cause is unidentified. Pointed-to but
unexplored lead for future work, not investigated in this round per
explicit scope: whether the *non-anomalous majority* group's completion
tokens or cost shifted between the v1 and v2 draws for deepseek-flash.
Not chased further here -- the project moves to write-up after this entry.

**6. Fixed `scripts/analyze_decision_rules.py`'s `keyed()` helper.** Root
cause of why point 2's first attempt returned n=0 for v2's es/zh: two
separate `keyed()` calls could hand back non-identical NaN float objects
for MGSM's all-missing `subset` column, and since NaN != NaN unless it's
the literal same object, `(dataset, nan, task_id)` keys from two different
calls could fail tuple equality while printing as identical --
`set(en_map) & set(lang_map)` silently came back empty. The original v1/ar
confirmatory run wasn't affected (NaN object reuse happened to work out
that time), which is exactly why this went unnoticed until now. Fixed by
filling `subset` with a fixed string sentinel (`_NO_SUBSET`) before
grouping, so the key is always a real string, never a raw NaN. Added
`_selftest_keyed()`, which runs automatically on import and asserts a real
MGSM en-vs-other-language match returns at least one common task_id
against whatever results files are on disk (skips quietly if none exist
yet) -- so a future regression here fails loudly instead of silently
returning what looks like "not enough data."

**File state, confirmed:** `results/decision_rule_h1.csv`, `_h2.csv`,
`_h3.csv` are untouched -- still the original confirmatory numbers,
`keyed()`'s bug and fix included, since the fix doesn't change output for
data where it happened to work (v1/ar). The v2 lean-prompt data
(`results/phase3_c2_raw_v2_leanprompt.csv`) and every number in this
entry live separately and were never merged over `phase3_c2_raw.csv` or
the decision_rule_*.csv files.

## 2026-09-17 -- C4 pilot: design + pre-committed pass criterion (written BEFORE running anything)

**Status:** a time-boxed pilot, parallel to paper-writing, not a
replacement for anything already done. The confirmatory H1/H2/H3 result
(above) stays exactly as it is, untouched and separately citable.
`results/phase3_c0_raw.csv` doesn't exist as such -- C0 is
`phase1_raw.csv`, untouched here -- and `phase3_c1_raw.csv`/
`phase3_c2_raw.csv` are untouched by this pilot too.

**What C4 is:** a single-call redesign, implemented as a new condition in
`harness/conditions.py` (`run_c4()`) and `harness/router.py`
(`should_skip_intervention()`), both purely additive -- C0/C1/C2/C3a's
existing code paths are not modified. Detector runs first (language ID).
Router applies a first-pass "low-tax-skip" check: skip intervention
entirely if the input is English, or if the (model, language) pair's own
Phase 1 cost-ratio CI upper bound already clears 1.2x (`results/
phase1_cost_ratios.csv`) -- nothing to fix for that pair. Otherwise, one
system+user message pair goes straight to the Executor: no Packer call
(no separate translation call), no Equalizer (no cross-call token budget
to reconcile with a single call -- `max_tokens` is left uncapped, same as
C0's own MGSM calls), no Expander call (no post-hoc language check or
retranslation safety net -- the system prompt's own instruction is the
only thing keeping the answer in the target language on this path). The
system prompt (36 tokens, verified via tiktoken o200k_base) was manually
spot-checked on 2 real MGSM questions (deepseek-flash, es and zh) before
any batch run -- correct answer, correct language, no English leakage in
either, in both cases.

**Pass criterion, committed in writing before seeing a single C4 result:**

> C4 counts as working if the median per-task cost ratio (C4 / English)
> is <=1.2x **and** the 95% bootstrap CI excludes 1.2, on **both** target
> cells (`deepseek-flash`/es and `deepseek-flash`/zh independently -- not
> pooled, not "2 of 2 on average").

Statistic: bootstrap CI of the **median** per-task ratio (BCa with
percentile fallback, alpha=0.05, 10,000 resamples) -- the same statistic
`h1_cost_ratio()` in `scripts/analyze_decision_rules.py` uses, reused
directly by import rather than reimplemented, specifically so this
pilot cannot repeat the mean-ratio mistake documented in the H1 recheck
entry above. Precision note, spelled out now so it can't be fudged after
the fact: "median <=1.2x AND CI excludes 1.2" reduces exactly to **CI
upper bound < 1.2, strictly** -- not <=1.2 like H1's original rule. This
is deliberately a hair stricter than H1's own bar, so a boundary case
like H1's gpt-5.6-luna/ar near-miss (CI upper bound 1.204 against a <=1.2
target) can't get waved through as a pass here. If both cells clear
CI_high < 1.2: PASS. If one does: PARTIAL, not a pass. If neither does:
FAIL. No other outcome gets reported as "working."

**English denominator, decided now, not after seeing costs:** C4 is not
run on English in this pilot (see scope below) -- its English behavior is
architecturally a raw passthrough, identical in shape to C0's own call
(same `if language == "en": messages = [{"role": "user", ...}]` shape as
C2's English branch, which has already been shown to track C0 closely).
Rather than spend pilot budget re-confirming that, **the ratio's
denominator is C0's own `phase1_raw.csv` MGSM/en per-task cost** -- the
same denominator every other cost ratio in this project uses (Phase 1's
`phase1_cost_ratios.csv`, Phase 3's `decision_rule_h1.csv`). Paired by
`task_id`, same seed as everywhere else in this project, so the task_id
sets already align without re-sampling.

**Scope, exact:** MGSM only. N=50 (`MGSM_N_PROBLEMS`, unchanged --
within the requested 30-50 range and reuses the exact existing seeded
sample, so task_ids align with C0/C2 without any new sampling logic).
`deepseek-flash` only -- not `gpt-5.6-luna`. `es` and `zh` only -- not
`ar` (MGSM has no `ar` arm at all, per the Amendments Log, so this is
automatic, not a separate exclusion to enforce). No MAPS/GAIA.

**Three checks, in this order, before the pass/fail question -- written
down now so the order is pre-committed too, not chosen after looking at
results:**
1. Completion token length vs. C0, same tasks -- flag if C4 generates
   longer completions than needed.
2. Whether the unexplained high-variance anomaly (2-4x cost spikes, 30-36%
   of C2's zh rows) reappears under C4 -- report rate and severity as
   measured, don't assume a different architecture removes a provider-side
   effect just because the code changed.
3. Accuracy vs. C0 and C1, same tasks.

**Output file:** `results/phase3_c4_raw.csv` -- new, separate, never
merged into or overwriting `phase3_c1_raw.csv` or `phase3_c2_raw.csv`.

**Not in scope for this pilot (per explicit instruction):** no
`gpt-5.6-luna`, no MAPS/GAIA, no `ar`, no scaling past N=50, no
`harness/` changes beyond what C4 needs, no `paper_draft.md` edits. This
entry is being committed before the pilot is run -- the result (pass,
partial, or fail) is a separate entry appended after, not edited into
this one.

## 2026-09-17 -- C4 pilot: result -- FAIL against the pre-committed criterion

Applies the criterion committed in the entry above, unchanged, to the
actual pilot data. 100/100 rows collected, 0 errors, 0 truncation
(`results/phase3_c4_raw.csv`).

**Check 1 -- completion length vs. C0:** no inflation. C4 completions are
*shorter* than C0's on both mean and median (es: 371.6/190.5 vs C0's
496.3/232.0; zh: 447.8/169.5 vs C0's 519.0/205.0). Prompt-token delta vs.
C0 is exactly +36 tokens on every one of the 100 rows -- matches the
system prompt's measured size precisely.

**Check 2 -- anomaly reappearance:** **0% (0/50 on both es and zh)**,
sharp contrast to C2's 30-36% on zh. Prompt-token delta vs. C0 has
*zero* variance across all 100 rows (min=p25=p50=p75=max=36) -- no
bimodal split, no 2-4x spikes. Completion-token length does show real
variance (coefficient of variation 1.27 es / 2.37 zh), but that's normal
difficulty-driven variance already present in C0's own baseline (C0's own
zh max completion_tokens was 6879; C4's is 7209, same order of
magnitude) -- not the input-side anomaly being tested for, which was
specifically about unexplained *prompt*-token inflation uncorrelated
with input length. Reported as observed at N=50, not as proof the
anomaly can't occur under C4 -- one clean batch isn't the same claim as
"architecturally impossible."

**Check 3 -- accuracy vs. C0 and C1:** held steady, no collapse. es: C0
90.0%, C1 92.0%, C4 92.0%. zh: C0 94.0%, C1 90.0%, C4 92.0%.

**Data-quality footnote, not a C4-specific defect:** 4/50 zh rows were
misdetected by the Detector as `ko` (Korean) instead of `zh` --
pre-existing `langdetect` limitation, already visible in C2's data, not
introduced by C4. Checked directly: the model complied with the
(wrong) instruction and answered in Korean for all 4. This does **not**
give C4 a disadvantage C2 doesn't share -- C2's Expander checks against
the same Router-derived target-language label, so it would make the
identical mistake on these exact task_ids (Expander sees the output
already "matches" the mis-detected target and does nothing). Accuracy
scoring is unaffected either way, since `is_correct()` substring-matches
the numeric answer, which appears identically in Korean and Chinese
text.

**Pass criterion applied (`scripts/analyze_c4_pilot.py`, reusing
`analyze_decision_rules.py`'s `bootstrap_ci()` directly):**

| model | language | n | median ratio | 95% CI | median<=1.2 | CI_high<1.2 | verdict |
|---|---|---|---|---|---|---|---|
| deepseek-flash | es | 50 | 1.301x | [1.144, 1.436] | No | No | **FAIL** |
| deepseek-flash | zh | 50 | 1.209x | [1.034, 1.344] | No | No | **FAIL** |

**OVERALL: FAIL.** Neither target cell clears the pre-committed
criterion. Stated plainly, not rationalized: es fails clearly (median
itself, 1.301x, is already above 1.2 before the CI is even considered).
zh's median (1.209x) sits just above the 1.2 point-estimate threshold,
but its CI ([1.034, 1.344]) is wide and does not come close to excluding
1.2 -- this is not the kind of tight, ambiguous near-miss H1's own
gpt-5.6-luna/ar cell was (CI upper bound 1.204 against <=1.2); zh's CI
upper bound here is 1.344, meaningfully above the bar.

**Context, not part of the verdict:** C4 is a substantial improvement
over C2's confirmatory numbers for the same two cells -- es: 1.530x
(C2 v1) -> 1.301x (C4); zh: 1.867x (C2 v1) -> 1.209x (C4), or against
C2's v2 lean-prompt numbers, es: 1.304x -> 1.301x (essentially flat), zh:
1.677x -> 1.209x (a large drop, consistent with Check 2's finding that
the anomaly didn't reappear). Real, measured progress -- just not enough
to clear the strict pre-committed bar on this pilot's N=50 draw.

**File state:** `results/phase3_c4_raw.csv` (new) and
`results/c4_pilot_cost_ratio.csv` (new, the table above) are the only
new results files. `phase1_raw.csv`, `phase3_c1_raw.csv`,
`phase3_c2_raw.csv`, and all three `decision_rule_h*.csv` files are
untouched. Per the pilot's scope: stopping here -- not scaling to
`gpt-5.6-luna`, MAPS/GAIA, or a larger N without a decision to proceed.

## 2026-09-18 -- C4 pilot continuation: two targeted fixes, final iteration, PARTIAL result

Continues the C4 pilot above with two independent, per-cell fixes, per
explicit instruction. Same pre-committed criterion, same N=50, same
cells, no new API calls for the diagnosis step. **This is the final
iteration** -- no further rounds, no N scaling, regardless of outcome.

**Step 1 -- diagnosis (existing data only, `results/phase3_c4_raw.csv`
vs. `phase1_raw.csv`).** First pass used the wrong denominator (C4-lang
vs. C0's *own* same-language cost) and had to be redone against the
denominator that actually feeds the pilot's ratio (C4-lang vs. C0's
*English* cost) -- corrected before reporting. The fixed +36-token
overhead is confirmed exactly constant (zero variance across all 100
v1 rows, as already established). Decomposing the dollar cost delta
(C4 vs. C0/en) into its prompt-token and completion-token components:

| lang | prompt ratio | completion ratio | % of $ delta: prompt-side | % of $ delta: completion-side |
|---|---|---|---|---|
| es | 1.611x | 1.199x | 25.9% | **74.1%** |
| zh | 1.436x | 1.166x | 10.2% | **89.8%** |

Both cells are predominantly completion-side, not prompt-side. es routes
to the completion-verbosity fix per the pre-specified branch. zh gets
the overhead-trim fix per explicit instruction regardless of its own
diagnosis also showing completion-side dominance -- noted here plainly
rather than silently substituting a different fix zh's own numbers might
have suggested.

**Step 2 -- es fix.** Added one clause to the existing 36-token template
("give **only** the final answer... **no explanation**") targeting the
diagnosed completion-side driver directly -- 38 tokens total (measured
via tiktoken). Spot-checked on the same 2 real MGSM questions (es and
zh) used for the original C4 prompt before batch-running: correct
answer, correct language, no leakage, both cases -- the zh-question
check came back a one-line "140 美元" with no explanation, a good sign
the instruction is doing its job even off-target.

**Step 3 -- zh fix.** Reused `harness/packer.py`'s already-validated
18-token C2 lean-prompt template verbatim ("Think in English internally.
Answer only in '{lang}'. Keep numbers/formatting exact.") rather than
writing a new one -- the strongest low-risk choice available, since it's
proven at N=50x2-models scale, not just a 2-question spot-check. Still
spot-checked again standalone (no Expander backstop in C4, unlike its
original C2 use) on the same 2 questions before batch-running: correct
answer, correct language, no leakage, both cases.

**Implementation:** `harness/conditions.py`'s `run_c4()` now selects a
per-language template from `_C4_SYSTEM_TEMPLATES_BY_LANG` (es, zh tuned;
falls back to the original shared 36-token template for any other
language). This changes C4's own default behavior going forward -- there
is no prior "confirmatory" C4 result to preserve (unlike C2's v1/v2
split), so refining C4's own template in place is the appropriate
iterative process here, not a violation of anything citable. The
original pilot run (`results/phase3_c4_raw.csv`, produced by the shared
36-token template) remains on file, unedited, and is no longer
reproducible from current code -- exactly the same situation as C2's v1
result after the lean-prompt template was edited in place, same
precedent.

**Re-run:** `python scripts/run_phase3.py --condition c4 --datasets MGSM
--models deepseek-flash --languages es,zh --output-suffix _v2_fixed
--retry-until-filled`. Both cells' fixes apply automatically via the
per-language dispatch, so a single combined run covers both. 100/100
rows, 0 errors, 0 truncation. Output:
`results/phase3_c4_raw_v2_fixed.csv` -- new, separate from the v1 pilot
file.

**Step 4 -- pass criterion applied, plainly (`scripts/analyze_c4_pilot_v2.py`,
same `bootstrap_ci()` import, same criterion, unchanged):**

| language | median ratio | 95% CI | median<=1.2 | CI_high<1.2 | verdict |
|---|---|---|---|---|---|
| es | 1.008x | [0.951, 1.089] | Yes | Yes | **PASS** |
| zh | 1.312x | [1.136, 1.405] | No | No | **FAIL** |

**es: PASS.** Comfortably clears the bar -- median at parity with
English, CI entirely below 1.2 with real margin. The completion-side fix
worked as diagnosed.

**zh: FAIL -- and notably, numerically worse than the v1 pilot's zh
result (1.209x -> 1.312x), not just "still failing."** Checked directly,
using only already-collected data (no new calls, consistent with this
being the final iteration): C4's own *absolute* mean cost for zh
actually went *down* slightly (v1 \$0.000142 -> v2 \$0.000133), prompt
tokens dropped by ~17 (close to the ~18-token trim, matching
expectations), and accuracy held exactly steady (92.0% both). The
*ratio* getting worse despite lower absolute cost is not a contradiction
-- the reported statistic is the **median of per-task ratios**, which is
sensitive to the shape of a right-skewed, high-variance distribution
(zh's completion-token coefficient of variation was already measured at
2.37 in the original pilot) in a way a mean-of-costs comparison isn't;
a small trim to a completion-side-dominated problem, combined with
`deepseek-flash`'s inherent generation stochasticity across an
independent batch draw, is a plausible explanation for the shift, but
not confirmed -- flagging as the most likely explanation, not asserting
it as proven, since chasing it further (a third batch, a variance
decomposition) is out of scope for this iteration.

**OVERALL: PARTIAL.** es passes the pre-committed criterion cleanly. zh
does not, and the specific fix applied (mechanically justified -- shrink
a confirmed-constant overhead -- but applied to a cell whose own
diagnosis showed that overhead was a 10.2% minority driver, not the
89.8% majority one) did not close the gap, and the ratio metric moved in
the wrong direction on this draw. Per the pre-committed stop condition:
**this is the final iteration.** No further rounds, no N scaling, no new
models/datasets/conditions on C4.

**File state:** `results/phase3_c4_raw_v2_fixed.csv` and
`results/c4_pilot_v2_cost_ratio.csv` are new. `results/phase3_c4_raw.csv`
and `results/c4_pilot_cost_ratio.csv` (the original pilot's files) are
untouched, still on file and citable as the v1 pilot result.
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, all three `decision_rule_h*.csv`
files, and `docs/paper_draft.md` are untouched by this entire
continuation.

## 2026-09-19 -- Audit: no "C2 makes 4 API calls" claim found; C2's real call count clarified; Expander-firing rate confirmed unrecoverable from stored data

Two checks, requested before scoping any new data collection around a
per-pipeline-step cost breakdown for C2 (see the "per-step cost
breakdown" question raised and left open above -- this entry answers a
narrower documentation-accuracy question first).

**1. Searched for an explicit "C2 makes 4 separate API calls" (or
similar) claim across every doc that describes the harness --
`methodology-notes.md` (this file), `paper_draft.md` (including
Discussion and Conclusion), `phase4_writing_reference.md`,
`harness_hardening_log.md`, `findings_summary.md`, `harness/README.md`.
**No such claim exists, literally, anywhere in these files.** Reporting
that plainly rather than inventing a correction for a claim that isn't
there. The closest related passage is the "Detector → Router → Packer →
Executor → Equalizer → Expander" six-module pipeline description
(`paper_draft.md`'s Methods, `harness/README.md`) -- accurate as
written (both already noted Packer's prompt-mode "no extra model call"
and Expander "usually a no-op"), but a six-stage diagram invites
misreading as six calls, or C2's five-arrow description as four or five.
Tightened both to state the real call count explicitly: **C2 makes at
most two model calls per task** -- one mandatory (Executor+Equalizer,
translate-in instruction embedded in its own prompt, not a separate
call) and one conditional (Expander, only when the model's answer isn't
already in the target language). Detector, Router, and Packer's
prompt-based mode are pure local logic, zero model calls, by
construction.

**2. Whether Expander's firing rate is recoverable from
`phase3_c2_raw.csv` without new API calls: no.** Checked the actual
code, not assumed: `harness/expander.py`'s `expand()` returns a
`was_translated: bool` on its `ExpandedResult` -- this IS computed at
runtime, every call -- but `harness/conditions.py`'s `_run_c2_family()`
only ever reads `expanded.prompt_tokens`, `.completion_tokens`,
`.latency_s`, `.cost_usd`, and `.final_text` from that result (confirmed
via `grep -n "was_translated" harness/*.py` -- the name appears only
inside `expander.py` itself, never in `conditions.py`). The flag is
computed and then discarded; `ConditionResult` has no field for it, and
`phase3_c2_raw.csv`'s header has no corresponding column. `route_through_
english` narrows nothing further here either -- checked directly, all
100 `deepseek-flash` es/zh rows have `route_through_english=True` (both
are non-English languages), so every row was *eligible* for Expander to
fire, with no signal distinguishing which ones actually did.

No indirect proxy was substituted for the missing flag. `expand()`'s own
translate-back prompt embeds the *executor's own output* as `{text}`
(see `_EXPAND_PROMPT_TEMPLATE`), so unlike the Packer system-prompt
overhead (a small, genuinely fixed addition that produced a clean,
detectable constant jump earlier in this project), Expander's call size
scales with each task's own answer length -- there is no clean constant
signature to look for in the aggregated `prompt_tokens`/`cost_usd`
totals, and attempting to infer per-row firing from that would be
presenting a guess as a measurement. **This is confirmed as a new
instrumentation + re-run question** (capture `was_translated` the same
way `reasoning_content`/`reasoning_tokens` were added to `execute()` for
the C4 track), separate from this documentation fix, and not undertaken
here pending a decision on whether it's worth the additional C2 run.

**File state:** `docs/paper_draft.md`'s Methods section and
`harness/README.md`'s condition table were edited (the call-count
clarification above) -- both explicitly authorized for this pass.
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, all three `decision_rule_h*.csv`
files, and every prior dated entry in this file (including the C4 pilot
section) are untouched.
