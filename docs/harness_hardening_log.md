# Post-hoc engineering — product track, not part of the confirmatory study

Everything in this file is post-hoc harness iteration on `deepseek-flash`/zh (MGSM), pursued after the C4 pilot (`docs/methodology-notes.md`) closed with a PARTIAL result. **This is a separate, unbounded engineering track — not a re-run, extension, or reopening of the confirmatory H1/H2/H3 result or the completed C4 pilot.** Every number below carries this same label; if any result from this file is ever cited elsewhere, that caveat travels with it.

Guardrails observed throughout: `methodology-notes.md`'s existing C4 pilot section, `results/decision_rule_h{1,2,3}.csv`, `results/phase3_c1_raw.csv`, `results/phase3_c2_raw.csv`, `results/phase3_c4_raw.csv`, and `docs/paper_draft.md` are not edited by this track.

Target: `deepseek-flash`/zh, MGSM only. Goal: cost ratio (median per-task, C4/C0-English) comfortably under 1.2x, not a bare pass. No fixed N ceiling, no fixed stop condition — iterate until it works or a wall is hit and reported.

## 2026-09-18 -- Result: comfortable pass reached (iteration 3), with a real, documented mechanism gap along the way

**Bottom line up front:** `deepseek-flash`/zh reaches a comfortable pass --
median ratio **0.937x**, 95% CI **[0.872, 0.980]**, margin of 0.220 below
the 1.2x bar -- using a lean, hard-constraint prompt (iteration 3 below).
Accuracy matches C0's own baseline exactly (94.0%, comma-formatting-
corrected) and beats C1 (90.0%). *(Post-hoc engineering, product track,
not part of the confirmatory study.)*

### Step 1 -- try the es fix on zh directly

zh's original C4 diagnosis (methodology-notes.md's C4 pilot continuation
entry) showed 89.8% of its cost inflation was completion-side, the same
profile as es (74.1%). zh had never actually received es's fix -- it got
the separate C2-lean-prompt reuse instead. Applied es's exact template
(38 tokens: "...give only the final answer... no explanation...") to zh.
Spot-checked clean on the standard 2-question check first.

**Result (`results/phase3_c4_raw_v3_zh_finalanswer.csv`, N=50):** median
**0.944x**, CI **[0.875, 1.024]**, margin +0.176 below 1.2x. A strong
cost result on its face.

**Accuracy check caught a real scoring artifact before this got reported
as a clean win.** Raw (as-scored) accuracy was 88.0% vs. C0's 94.0% -- a
6-point drop that looked concerning. Inspected the 6 "wrong" rows
directly: 2 of 6 (task_ids 197, 201) were **false negatives** --
`is_correct()` does a literal substring match, and the model's
comma-formatted answers ("6,277") don't substring-match the
comma-free expected value ("6277"). Comma-tolerant rescoring (this
iteration's own results file only -- no shared scoring code touched, no
other results file touched) gives **92.0%**, in line with baseline. The
same class of bug as the original MAPS/Math scoring issue earlier in
this project, recurring here on a different dataset for a different
reason -- flagged, quantified, not silently absorbed into a "6-point
drop" that wasn't real.

### Step 2 -- verify English-internal-reasoning compliance before concluding anything (required check, not optional)

`deepseek-flash` exposes a `reasoning_content` field on the response
message, separate from the visible `content` -- and
`usage.completion_tokens_details.reasoning_tokens` bills it as real
completion tokens even though the harness's `execute()` never captures
or logs it (only `content` is stored). This explains why visible answers
are often a handful of characters while `completion_tokens` reads in the
hundreds: the bulk is this hidden reasoning trace, not the answer.

**First read (N=5, manual inspection): 3/5 English, looked fine.**
**Re-checked with a larger, automated sample (N=20, `langdetect` on
`reasoning_content`) to get a reliable number instead of trusting N=5:
only 5/20 (25%) reasoned in English.** Even more telling: re-calling the
*exact same 5 task_ids* from the first check independently flipped
almost entirely to Chinese the second time (all 5 came back `zh-cn`) --
reasoning-language compliance under this template is **stochastic
per-call**, not a fixed property of the task. This is the real bug the
instructions anticipated: the "reason in English" clause was being
followed roughly a quarter of the time, not reliably. Iteration 1's
0.944x cost win was real, but not evidently coming from the intended
"English reasoning is cheaper" mechanism for most of its rows -- worth
being honest that the mechanism and the outcome were not well aligned in
that iteration, even though the outcome itself would have cleared the
bar.

### Step 2 continued -- strengthen enforcement, re-test (per instruction)

**Iteration 2 (strengthened, verbose):** "You MUST think and reason in
English only, step by step -- never in '{lang}' or any other language...."
(55 tokens). Pre-checked on N=15: compliance jumped to 13/15 (86.7%) --
enforcement worked. But reasoning_tokens were visibly higher across the
sample than the unstrengthened version (several rows 150-220+ tokens vs.
mostly sub-100 before), consistent with a real trade-off: stronger,
more directive phrasing seems to make the model reason more
deliberately/at greater length, even while reasoning in the right
language.

**Full N=50 result (`results/phase3_c4_raw_v4_zh_strengthened.csv`):**
median **1.120x**, CI **[0.997, 1.179]**, margin only **+0.021**. This
technically clears the pre-committed-style criterion (median<=1.2 and
CI_high<1.2) but is a **bare pass, explicitly not what "comfortably
under, not a bare pass" means** -- not accepted as the stopping point.
Accuracy 92.0% (raw), reasonable, but the cost side regressed hard
enough from iteration 1 that better compliance came at close to the
entire cost-margin the earlier fix had bought.

**Iteration 3 (lean, still hard-constraint):** kept the explicit "never
'{lang}'" rule (the part that seems to drive compliance) but dropped
"step by step" and the heavier scaffolding language, on the hypothesis
that phrasing length/emphasis -- not the constraint itself -- was
inflating reasoning length. "Reason in English only -- never '{lang}'.
Then give only the final answer in '{lang}', no explanation. Keep
numbers/formatting exact." (29 tokens.) Pre-checked on the same N=15:
compliance **14/15 (93.3%)**, better than iteration 2. Two specific
tasks (task_ids 184, 236) showed extreme reasoning-length outliers
(2600+ tokens) under this prompt -- and had already shown similarly
extreme outliers under the *other* prompt variants too (task 184: 3894
reasoning_tokens under iteration 2; task 236: 1638 under the original
unstrengthened check) -- read as intrinsically hard/confusing problems
for this model, not something tied to a specific prompt wording, and not
chased further.

**Full N=50 result (`results/phase3_c4_raw_v5_zh_lean_strong.csv`):**
median **0.937x**, CI **[0.872, 0.980]**, margin **+0.220**. Comma-
tolerant accuracy **94.0%** (raw 88.0% -- same scoring artifact as
iteration 1, same fix applied to this iteration's own file only),
exactly matching C0's baseline and ahead of C1's 90.0%. The 3 genuinely
wrong answers (task_ids 177, 185, 146) are the *same three* task_ids
that were genuinely wrong in iteration 1 too -- reproducible,
model-level errors on specific problems, not prompt-tied noise.

**Caveat on the compliance number for this final iteration:** 93.3%
compliance is from the N=15 pre-check that validated this exact prompt
text before the batch run -- the harness itself doesn't currently
capture `reasoning_content` or `reasoning_tokens` into the results CSV
(only `content` is stored), so the full N=50 batch's compliance rate
isn't independently verified row-by-row. The pre-check used the same
template against the same task pool: a reasonable basis for the
93.3% estimate, but not identical to auditing the actual batch.
Extending `harness/executor.py` to capture these fields would close this
gap for any future iteration -- not done here since it wasn't necessary
to reach the target on this track, but flagged for whoever picks this
back up.

### Result table, all iterations, for the record

| iteration | template | tokens | compliance (pre-check) | median ratio | 95% CI | margin | accuracy (comma-corrected) |
|---|---|---|---|---|---|---|---|
| 1: es fix as-is | final-answer-only | 38 | 25% (N=20) | 0.944x | [0.875, 1.024] | +0.176 | 92.0% |
| 2: strengthened | verbose hard constraint | 55 | 86.7% (N=15) | 1.120x | [0.997, 1.179] | +0.021 (bare pass) | 92.0% |
| 3: lean + strong | lean hard constraint | 29 | 93.3% (N=15) | **0.937x** | **[0.872, 0.980]** | **+0.220** | **94.0%** |

**Stopping here** -- iteration 3 meets the explicit bar (comfortably
under 1.2x with real margin, not a bare pass), with accuracy at or above
both C0 and C1 baselines. `harness/conditions.py`'s zh template is left
set to iteration 3's text. es's template is untouched from the C4 pilot
(`the question below is in... give only the final answer... no
explanation...`, 38 tokens) -- this track never touched it.

### File state

New this track: `docs/harness_hardening_log.md` (this file),
`results/phase3_c4_raw_v3_zh_finalanswer.csv`,
`results/phase3_c4_raw_v4_zh_strengthened.csv`,
`results/phase3_c4_raw_v5_zh_lean_strong.csv`,
`scripts/analyze_c4_hardening.py`. `harness/conditions.py`'s zh entry in
`_C4_SYSTEM_TEMPLATES_BY_LANG` was edited three times in place (one per
iteration) -- each iteration's results file preserves what that specific
prompt version actually produced, so nothing is lost even though the
code now only reflects the final (iteration 3) version.

**Untouched, as required:** `methodology-notes.md`'s existing C4 pilot
section, `results/decision_rule_h{1,2,3}.csv`, `results/phase3_c1_raw.csv`,
`results/phase3_c2_raw.csv`, `results/phase3_c4_raw.csv` (the original
pilot file) and `results/phase3_c4_raw_v2_fixed.csv` (the pilot
continuation's file, es-pass/zh-fail), and `docs/paper_draft.md`.

## 2026-09-19 -- Verification: the 0.937x result was not a dropped-reasoning-tokens artifact. Confirmed, not assumed. Track closed.

Checked, before accepting iteration 3's result as final, whether
`harness/executor.py`'s `execute()` was silently dropping
`reasoning_content` tokens from the cost calculation -- i.e. whether
`cost_usd` was being computed on an incomplete token count for either
side of the C4-vs-C0 comparison. *(Post-hoc engineering, product track,
not part of the confirmatory study.)*

**Step 1 -- does C0 also produce `reasoning_content`, and was it ever
captured?** Neither `phase1_raw.csv` nor any other results file in this
project has ever stored raw API response objects -- only the aggregated
fields (`prompt_tokens`, `completion_tokens`, `cost_usd`, etc.), for
every condition including C0. So the *original* C0 calls' raw responses
can't be retroactively inspected. What can be checked, and was: a fresh
call reproducing C0's exact shape (raw, no system prompt, real MGSM zh
question) confirms `deepseek-flash` **does** expose `reasoning_content`
on C0-shaped calls too, not just C4's -- same model, same underlying
behavior, expected and confirmed rather than assumed.

**The premise motivating this check turned out to be incorrect --
checked directly, not taken on faith.** `usage.completion_tokens_details.
reasoning_tokens` is a **subset** of `usage.completion_tokens`, not an
addition to it -- confirmed both by inspection of a live response
(`completion_tokens=140`, `reasoning_tokens=79`, i.e. `79 <= 140`) and,
after instrumentation (below), across the full N=50 verification batch
(`reasoning_tokens <= completion_tokens` held for all 50 rows, no
exceptions). `execute()` has always billed `cost_usd` off the *full*
`usage.completion_tokens` figure returned by the API, which already
includes any reasoning tokens -- for every condition, not just C4. **No
dollars or tokens were ever dropped from any cost figure in this project
because of this.** What `execute()` did not capture, before this fix,
was the reasoning *text* (`reasoning_content`) -- useful for auditing
*language* compliance, never relevant to the dollar cost. Stating this
plainly since it corrects the premise of the request rather than
confirming it: the 0.937x figure was not an artifact of dropped cost.

**Step 2 -- instrumented `execute()` anyway**, since capturing
`reasoning_content`/`reasoning_tokens` is independently useful (exactly
what made Step 2 of the original pilot-continuation diagnosis possible
in the first place, via manual out-of-band calls -- now it's just part
of the normal pipeline). Purely additive: two new `Optional` fields on
`ExecutionResult` and `ConditionResult`, two new trailing columns in
`run_phase3.py`'s `FIELDNAMES`, populated only by `run_c4()` -- every
other condition's existing fields, values, and files are untouched by
this change. Smoke-tested end-to-end before batch use.

**Step 3 -- re-measured on a genuinely fresh N=50 batch** (the original
iteration-3 run's raw responses weren't preserved -- stated plainly,
per instruction, rather than assuming the old number still holds: this
is a new, independent draw, not a re-read of old data).
`results/phase3_c4_raw_v5_zh_instrumented.csv`, same iteration-3 zh
template, same denominator (C0's English cost, unchanged and untouched):

| | median ratio | 95% CI | margin | accuracy (comma-corrected) |
|---|---|---|---|---|
| iteration 3 (original draw) | 0.937x | [0.872, 0.980] | +0.220 | 94.0% |
| verification (fresh draw, instrumented) | **0.981x** | **[0.941, 1.085]** | **+0.115** | 92.0% |

Smaller margin on this draw (consistent with `deepseek-flash`'s
run-to-run stochasticity, observed repeatedly throughout this whole
project) but **still comfortably under 1.2x, not a bare pass** -- CI
upper bound 1.085 leaves real room below the 1.2 line. The 4 genuinely
wrong answers on this draw (task_ids 184, 177, 185, 146) are the same
recurring set seen across every prior iteration -- reproducible
model-level errors, not new ones introduced by this change.

**Step 4 -- real compliance rate on the actual batch, not a pre-check
sample:** `reasoning_content` was captured for all 50/50 rows;
`langdetect` classification gives **50/50 (100%) English reasoning** --
higher than the N=15 pre-check's 93.3% estimate, and a real audit of the
exact batch that produced the cost number above, not an extrapolation.

**Step 5 -- plain report and conclusion: the ratio holds. Track closed.**
Two independent draws of the same template (0.937x and 0.981x), both
with comfortable margin below 1.2x, one with a directly audited 100%
English-reasoning-compliance rate on the exact batch measured. Accuracy
both times at or near C0's own baseline once the comma-formatting
scoring artifact (documented in the prior entry) is corrected for.
**No further iteration needed on this track** -- the original concern
motivating this check (dropped reasoning tokens) is resolved as not
having been a real issue, and the underlying result is now more solidly
verified than it was before the check, not less.

### Final state of this track

`harness/conditions.py`'s zh template remains iteration 3's text
("Reason in English only -- never '{lang}'. Then give only the final
answer in '{lang}', no explanation. Keep numbers/formatting exact.", 29
tokens). `harness/executor.py` and `harness/conditions.py` now capture
`reasoning_content`/`reasoning_tokens` for any future C4 call, additive
and harmless to every other condition. New this entry:
`results/phase3_c4_raw_v5_zh_instrumented.csv`. Still untouched, as
required throughout this entire track: `methodology-notes.md`'s C4 pilot
section, all three `decision_rule_h*.csv`, `phase3_c1_raw.csv`,
`phase3_c2_raw.csv`, `phase3_c4_raw.csv`, and `docs/paper_draft.md`.

## 2026-09-19 -- Third independent draw: pattern holds

Requested re-check after the verification draw above showed a smaller
margin (0.115) than the original iteration-3 run (0.220) -- reasonable
to want a third data point before treating two draws as settled,
especially given `deepseek-flash`'s documented run-to-run variance
throughout this project. Same template, same instrumented pipeline, same
method, fresh N=50 batch: `results/phase3_c4_raw_v5_zh_draw3.csv`.
*(Post-hoc engineering, product track, not part of the confirmatory
study.)*

| draw | median ratio | 95% CI | margin | compliance (audited) | accuracy (comma-corrected) |
|---|---|---|---|---|---|
| 1 (iteration 3, original) | 0.937x | [0.872, 0.980] | +0.220 | 93.3% (N=15 pre-check only) | 94.0% |
| 2 (instrumented verification) | 0.981x | [0.941, 1.085] | +0.115 | 100% (N=50, audited) | 92.0% |
| 3 (this check) | 0.960x | [0.891, 1.012] | +0.188 | 92.0% (N=50, audited) | 92.0% |

**Pattern holds across all three independent draws.** Every CI upper
bound sits comfortably below 1.2 (0.980 / 1.085 / 1.012), average margin
~0.17. Compliance stays consistently high (92-100%) on the two draws
where it was actually audited against the real batch rather than
estimated from a pre-check. Accuracy sits at or within 2 points of C0's
94.0% baseline on every draw, once the comma-formatting scoring artifact
is corrected for. **The same 4 task_ids (184, 177, 185, 146) are wrong
on every single draw, now confirmed across three independent batches**
-- this is reproducible, model-level difficulty on specific problems,
not noise tied to any particular run or prompt wording.

**Conclusion, restated with three data points instead of one:** the
result is not a lucky pair. `deepseek-flash`/zh under the current C4
template reliably lands in the 0.93x-0.98x range, comfortably under the
1.2x bar, with reasoning-language compliance and accuracy both holding
up under direct audit. Track remains closed; no further re-verification
runs planned unless something changes (e.g. the template is edited
again, or this gets picked up for scaling beyond this pilot's scope).

---

# Extension: qwen3.5-flash and gemini-3.5-flash-lite

New, separately-labeled section. Same standing caveat as the header above
applies to everything below: **post-hoc engineering, product track, not
part of the confirmatory study.** Does not touch `deepseek-flash`
results, `phase3_c1_raw.csv`, `phase3_c2_raw.csv`, `phase3_c4_raw.csv`,
any `decision_rule_h*.csv`, or `docs/paper_draft.md`. New scripts:
`scripts/harness_hardening_gemini.py`,
`scripts/harness_hardening_zh_baseline.py`.

## 2026-09-19 -- Triage, gemini-3.5-flash-lite/es fix (found, verified), zh baseline resolved for both models

### Step 1 -- triage against `results/generalization_check_summary.csv` (N=30 spot-check, unchanged)

| model/lang | median ratio | 95% CI | status |
|---|---|---|---|
| gemini-3.5-flash-lite/es | 1.249x | [1.026, 1.450] | confirmed tax -- CI entirely above 1.0 |
| qwen3.5-flash/es | 0.823x | [0.654, 1.048] | skip -- already at/below parity |
| qwen3.5-flash/zh | 1.382x | [0.967, 2.393] | inconclusive -- CI spans both sides of 1.0 |
| gemini-3.5-flash-lite/zh | 1.134x | [0.902, 1.272] | inconclusive -- CI includes 1.0 |

Decided to re-measure the two inconclusive zh cells at higher N (cheap,
and N=30 genuinely couldn't distinguish real-tax from no-tax), sequenced
after the confirmed target (gemini/es) rather than before. Resolved
below, same entry -- time allowed for both this round.

### Step 2 -- gemini-3.5-flash-lite/es diagnosis

Cost decomposition (same dollar-weighted method as the deepseek track,
`results/generalization_check.csv`'s existing per-task data, no new
calls needed for this part): **98.9% of the inflation is completion-
side, 1.1% prompt-side** -- even more skewed than deepseek's case.

**Mechanism checked directly, not assumed to match deepseek's.**
Inspected a raw response: no `reasoning_content` field exists on this
model at all, and `usage.completion_tokens_details` is `None` --
Gemini's API (via this OpenAI-compatible endpoint) exposes no reasoning-
token breakdown. There's an opaque `extra_content.google.thought_
signature` blob, but it's encoded, not inspectable text. Checked
whether the verbosity is hidden or visible by reading sample answers
directly: it's **visible** -- both the English and Spanish baseline
answers are already full step-by-step markdown explanations (headers,
bold, multiple paragraphs) in the *baseline* (no-harness) condition, and
completion_tokens tracks closely with what's actually shown, no evidence
of a hidden multiplier. Also noted one task where the ES and EN baseline
answers reached different (and the ES one wrong) interpretations of "4
times as many" -- a real per-language comprehension difference to watch
when testing any verbosity fix, not just a formatting issue.

**Conclusion: this is not deepseek's mechanism.** No separate hidden
reasoning channel to redirect into English -- the deepseek fix doesn't
map onto this model. What should map: suppressing the step-by-step
*visible* explanation directly.

### Step 3 -- fix attempts, single-call redesign, standalone (not wired into `harness/`, matching how this model was already isolated from the main harness/scripts infrastructure)

**v1 (34 tokens): "Give only the final answer... No step-by-step
explanation, no headers, no bullet points."** Spot-checked clean on 2
real questions (terse, correct, in-language) before batch-running.
Fresh N=50 batch (`results/harness_hardening_gemini_es_v1.csv`, EN
baseline + ES fix, Phase 1's own MGSM seed/sampling so both are paired
on identical task_ids -- not reusing the original N=30 spot-check's
independent sample):

| | median ratio | 95% CI | accuracy |
|---|---|---|---|
| ES-v1-fix / EN-baseline | **0.071x** | [0.062, 0.083] | **es: 74.0%** (from 90.0% baseline, -16pts); **en: 66.0%** (from 92.0%, -26pts) |

Dramatic cost win, dramatic accuracy collapse -- completion_tokens
dropped to a mean of 3.0 (from 255.5). **Root cause: unlike
deepseek-flash, this model's visible output *is* its reasoning process --
there's no separable hidden layer to preserve while suppressing
presentation.** "No explanation" removed the model's actual working, not
just its formatting, and hurt English as badly as Spanish, confirming
it's a general capability loss, not a translation-specific one. This is
exactly the "different root cause the C4 approach doesn't address"
case -- v1 discarded, not shipped, per instruction not to force it.

**v2 (41 tokens): "You may reason briefly... 1-2 short sentences -- no
headers, no bullet points, no bold formatting."** One more iteration
before concluding this was a wall, targeting the diagnosed verbose
*formatting* specifically while explicitly preserving some reasoning
capacity. Spot-checked clean on 2 real questions. Fresh N=50
(`results/harness_hardening_gemini_es_v2.csv`, ES only, reusing v1's
EN baseline as denominator -- same seed/task_ids):

| | median ratio | 95% CI | margin | accuracy |
|---|---|---|---|---|
| ES-v2-fix / EN-baseline | **0.308x** | **[0.274, 0.336]** | **+0.864** | **92.0%** (vs. 90.0% baseline -- no loss, slight improvement) |

**PASS, comfortably, per the pre-committed bar.** Mean completion_tokens
dropped from 255.5 to 51.7 -- a real, substantial, non-extreme
reduction. `harness_hardening_gemini.py` keeps both templates (`FIX_
TEMPLATE_V1`, now unused, and `FIX_TEMPLATE`, the v2 text actually
run) so the discarded attempt stays on record, not silently deleted.

### Step 4 -- zh baseline re-measurement (Step 1's deferred question, resolved)

Fresh N=50 (`results/harness_hardening_zh_baseline.csv`, Phase 1's own
seed/sampling; qwen3.5-flash/zh landed at N=48/50 -- 2 rows hit the 60s
hard timeout even after one retry each, consistent with this model's
previously-noted heavy-completion behavior; accepted rather than chased
further, same precedent as elsewhere in this project):

| model/lang | N | median ratio | 95% CI | accuracy | resolution |
|---|---|---|---|---|---|
| qwen3.5-flash/zh | 48 | **1.395x** | **[1.181, 1.527]** | 91.7% | **confirmed real** -- CI entirely above 1.0, similar magnitude to deepseek-flash's own zh tax |
| gemini-3.5-flash-lite/zh | 50 | 1.069x | [0.991, 1.202] | 88.0% | **still borderline** -- CI narrowed a lot (was [0.902,1.272]) but still just barely includes 1.0; small in magnitude either way |

**qwen3.5-flash/zh is now a confirmed target, not attempted this round.**
The fix work this round was scoped to gemini/es specifically (per the
task that opened this section); qwen/zh's confirmation is new
information surfacing at the end of this round, not something to fold
into a fix attempt without a separate decision to do so.
gemini-3.5-flash-lite/zh stays out of scope -- still not confidently
distinguishable from no-tax, and small either way.

### Summary, per model/cell

| model/cell | confirmed broken? | diagnosis | fix attempted | verified result |
|---|---|---|---|---|
| gemini-3.5-flash-lite/es | yes | visible-verbosity (no hidden reasoning channel) | v1 discarded (accuracy collapse); v2 shipped | **0.308x, CI [0.274,0.336], accuracy 92.0% -- PASS** |
| qwen3.5-flash/es | no | -- (already <=1x) | none needed | n/a |
| qwen3.5-flash/zh | **yes, newly confirmed this round** | not diagnosed yet | none | 1.395x, CI [1.181,1.527] -- real tax, unaddressed |
| gemini-3.5-flash-lite/zh | still inconclusive (narrower now) | n/a | none | 1.069x, CI [0.991,1.202] -- likely small/negligible |

### File state

New this section: `docs/harness_hardening_log.md` (this section),
`scripts/harness_hardening_gemini.py`,
`scripts/harness_hardening_zh_baseline.py`,
`results/harness_hardening_gemini_es_v1.csv`,
`results/harness_hardening_gemini_es_v2.csv`,
`results/harness_hardening_zh_baseline.csv`. Untouched: everything
`deepseek-flash`-related, `phase3_c1_raw.csv`, `phase3_c2_raw.csv`,
`phase3_c4_raw.csv` (and its `_v2`/`_v3`/`_v4`/`_v5*` variants), all
three `decision_rule_h*.csv`, and `docs/paper_draft.md`.

## 2026-09-19 -- qwen3.5-flash/zh fixed (1.395x -> 0.748x), same single-call architecture, third distinct mechanism found

Continuation of the Extension section above. Same standing caveat:
**post-hoc engineering, product track, not part of the confirmatory
study.** Same architecture as both prior fixes -- one call, no
restructuring, no added calls. `gemini-3.5-flash-lite/zh` untouched, per
instruction: not confirmed broken (still [0.991, 1.202]), no fix
attempted, no prompt changes. New script:
`scripts/harness_hardening_qwen.py`.

### Step 1 -- diagnosis, checked directly, neither prior mechanism assumed to transfer

Cost decomposition (`results/harness_hardening_zh_baseline.csv`'s
already-collected qwen en/zh data, no new calls needed for this part):
**100.1% of the inflation is completion-side** (prompt-side is actually
slightly *negative*, -0.1% -- zh prompts were marginally shorter in
tokens than en here) -- the most completion-dominated of all three
models checked so far.

**Inspected the raw response directly, N=1 then N=8 to confirm the
pattern:** qwen3.5-flash *does* expose a `reasoning_content` field
(deepseek's mechanism, not gemini's -- `completion_tokens_details.
reasoning_tokens` present and populated). But unlike deepseek's zh
problem, **the reasoning is already in English by default, unprompted,
8/8 (100%) of a fresh sample** -- there is no language-compliance gap to
fix here at all. What's different: the reasoning trace itself is
*enormous and repetitive* -- reasoning_tokens ranged 895-5954 across the
8-sample check (mean ~2858), 85-95% of total completion_tokens, and
reading the raw text shows the model looping on the same ambiguity
(e.g. "should 'a week' mean 5 or 7 days?") ten or more times before
settling on an answer it had already reached early on.

**Conclusion: a third, distinct mechanism from both prior models.**
Not deepseek's language-compliance problem (already solved by default
here). Not gemini's visible-verbosity-is-the-reasoning problem (there's
a real separable hidden channel, same as deepseek's architecture). This
is excessive reasoning *length* specifically -- the model has a real
hidden reasoning channel, already correctly in English, that simply
runs far longer than the problem needs. Fix should target conciseness
directly, not language and not visible formatting.

### Step 2 -- fix

**"Reason briefly and directly -- do not second-guess yourself or
explore alternative interpretations. Reach a conclusion in a few steps.
Give the final answer in '{lang}'."** (32 tokens.) Spot-checked on the
same 2 real questions before batch-running: both correct, both
in-language, reasoning visibly shorter and more linear (still shows some
residual second-guessing on one sample -- "Wait, is there any
ambiguity..." -- but far less looping than baseline).

### Step 3 -- accuracy tracked at every step (this fix worked on the first full attempt, no discarded iteration this time, unlike gemini's v1)

Fresh N=50 (`results/harness_hardening_qwen_zh_fix.csv`, zh only,
reusing qwen's existing en baseline from `harness_hardening_zh_
baseline.csv` as denominator -- same seed/task_ids). 50/50, 0 errors,
0 truncated. Mean `reasoning_tokens` dropped from baseline's 2720.5
(mean completion_tokens, zh) to a fix mean of 1185.5 (median 861.0) --
roughly halved.

### Step 4 -- verified on the fresh N=50 draw

| | median ratio | 95% CI | margin | accuracy |
|---|---|---|---|---|
| zh-fix / en-baseline | **0.748x** | **[0.639, 0.878]** | **+0.322** | **92.0%** |

Accuracy: en-baseline 92.0%, zh-baseline (pre-fix) 91.7%, zh-fix 92.0%
-- held exactly, no loss, on either side of the comparison. **PASS,
comfortably, on the first full-batch attempt** -- no discarded iteration
needed this time, unlike gemini's v1.

### Step 5 -- gemini-3.5-flash-lite/zh confirmed untouched

No calls made, no prompt changes, no new data for this cell this round.
Its status stands exactly as the prior entry left it: [0.991, 1.202],
still inconclusive, out of scope.

### Summary, updated

| model/cell | confirmed broken? | mechanism | fix | verified result |
|---|---|---|---|---|
| gemini-3.5-flash-lite/es | yes | visible-verbosity, no hidden reasoning channel | v1 discarded (accuracy collapse); v2 shipped | 0.308x, CI [0.274,0.336], accuracy 92.0% -- PASS |
| qwen3.5-flash/es | no | -- | none needed | n/a |
| **qwen3.5-flash/zh** | **yes** | **hidden reasoning channel, already English, excessively long** | **shipped on first attempt** | **0.748x, CI [0.639,0.878], accuracy 92.0% -- PASS** |
| gemini-3.5-flash-lite/zh | still inconclusive | n/a | none, untouched per instruction | 1.069x, CI [0.991,1.202] |

Three models fixed (deepseek-flash/zh, gemini-3.5-flash-lite/es,
qwen3.5-flash/zh) via the same single-call architecture, three genuinely
different root causes each time: deepseek needed language enforcement,
gemini needed visible-verbosity suppression without cutting reasoning,
qwen needed reasoning-length discipline with no language change at all.
None of the three fixes transfer to each other's model without
re-diagnosing first -- confirmed empirically each time, never assumed.

### File state

New this entry: this section of `docs/harness_hardening_log.md`,
`scripts/harness_hardening_qwen.py`,
`results/harness_hardening_qwen_zh_fix.csv`. Untouched: everything
`deepseek-flash`-related, `phase3_c1_raw.csv`, `phase3_c2_raw.csv`,
`phase3_c4_raw.csv` (and variants), all three `decision_rule_h*.csv`,
`docs/paper_draft.md`, and `gemini-3.5-flash-lite`'s existing results
(`harness_hardening_gemini_es_v1.csv`, `_v2.csv`).

## 2026-09-19 -- CORRECTION PASS: fair-comparison audit of all four shipped fixes -- 3 of 4 claimed wins do not survive

**This is a labeled correction, not a silent edit.** Every ratio reported
in the four track entries above used the *original, unfixed* English
baseline as the denominator. That's the right comparison for a fix that
is purely language-specific (e.g. "reason in English, not the target
language" -- meaningless to apply to English at all). It is the **wrong**
comparison for a fix that also contains a general brevity/behavior
instruction, since English never got the same treatment and its baseline
cost is inflated by the same kind of verbosity the fix targets in the
other language. Same standing caveat as always: **post-hoc engineering,
product track, not part of the confirmatory study.**

### Step 1 -- classification, exact template text from `harness/conditions.py` and the standalone scripts

| fix | exact shipped template | classification |
|---|---|---|
| deepseek-flash/es | "...Reason in English internally; give only the final answer in '{lang}', **no explanation**, no English in the output. Keep numbers/formatting exact." | **MIXED** |
| deepseek-flash/zh | "Reason in English only -- never '{lang}'. Then give only the final answer in '{lang}', **no explanation**. Keep numbers/formatting exact." | **MIXED -- not clean.** Contradicts the "low risk" framing this cell was given when the fix shipped; it contains the same "no explanation" clause as every other fix. |
| gemini-3.5-flash-lite/es (v2) | "...You may **reason briefly, 1-2 short sentences -- no headers, no bullet points, no bold formatting**. State the final answer clearly." | **GENERAL** |
| qwen3.5-flash/zh | "**Reason briefly and directly -- do not second-guess yourself or explore alternative interpretations. Reach a conclusion in a few steps.** Give the final answer in '{lang}'." | **GENERAL** |

All four contain a general component. All four re-tested (Steps 2-4),
not just the three anticipated.

### Steps 2-4 -- fixed-English runs, fresh N=50 each, exact verbatim shipped templates applied to English MGSM questions

- `deepseek-flash`: both templates applied literally, including the
  resulting self-referential oddity when `{lang}` is substituted with
  `'en'` (e.g. the zh template becomes "Reason in English only -- never
  'en'... give only the final answer in 'en'" -- logically odd, tested
  as-is rather than cleaned up, since the point is the identical
  instruction, not an improved one). `harness/executor.execute()` called
  directly with a hand-built messages list (`scripts/harness_hardening_
  fairness_audit_deepseek.py`) -- `run_c4()`'s real dispatch never
  routes English through these templates at all (English always skips
  to raw passthrough), so this is a deliberately hypothetical
  construction to isolate the instruction's effect. 100/100, 0 errors.
- `gemini-3.5-flash-lite`: shipped v2 template, unmodified, run via the
  existing `harness_hardening_gemini.py --modes fix --languages en`.
  50/50, 0 errors.
- `qwen3.5-flash`: shipped template, unmodified, run via a small script
  reusing `harness_hardening_qwen.py`'s call machinery. 50/50, 0 errors.

**Accuracy on the fixed-English runs, all within normal range, no
collapse:**

| model | en-baseline (unfixed) | en, fixed |
|---|---|---|
| deepseek-flash (es template) | 96.0% | 94.0% |
| deepseek-flash (zh template) | 96.0% | 92.0% |
| gemini-3.5-flash-lite | 92.0% | 94.0% |
| qwen3.5-flash | 92.0% | 94.0% |

**Corrected ratios -- old (vs. unfixed English) side by side with new
(vs. fixed English), same bootstrap-median-CI statistic throughout:**

| cell | OLD ratio | OLD CI | NEW ratio | NEW CI | delta | survives? |
|---|---|---|---|---|---|---|
| deepseek-flash/es | 1.008x | [0.951, 1.089] | **1.303x** | **[1.132, 1.527]** | +0.295x | **NO -- was a pass, now fails clearly** |
| deepseek-flash/zh | 0.937x | [0.872, 0.980] | **1.149x** | **[1.098, 1.258]** | +0.212x | **NO -- CI upper bound now exceeds 1.2** |
| gemini-3.5-flash-lite/es | 0.308x | [0.274, 0.336] | 0.981x | [0.920, 1.028] | +0.673x | **YES -- still passes, much smaller margin** |
| qwen3.5-flash/zh | 0.748x | [0.639, 0.878] | **1.116x** | **[0.946, 1.390]** | +0.368x | **NO -- CI now spans both sides of 1.2, inconclusive at best** |

### Step 5 -- deepseek-flash/zh sanity check, result

Not clean. Contains "no explanation," the same general clause every
other fix has. Given the explicit instruction to treat this like the
others if it wasn't clean, it got the full re-test above rather than a
skip -- and the correction was the largest relative swing of the four
(0.937x comfortable pass -> 1.149x with a CI that no longer excludes
1.2).

### Step 6 -- plain verdict

**Only gemini-3.5-flash-lite/es survives a fair comparison.** All three
others (deepseek/es, deepseek/zh, qwen/zh) were passing the *wrong*
test -- crediting a general brevity effect that also applies to English,
against an English baseline that never received it. Once English gets
the identical instruction, deepseek/es fails clearly, deepseek/zh's CI
no longer excludes 1.2, and qwen/zh's CI widens to span both sides of
1.2 entirely. None of the underlying single-call architecture work was
wasted -- the per-model mechanism diagnoses (deepseek: language
compliance; gemini: visible-verbosity; qwen: reasoning length) still
stand on their own, checked directly each time and not contradicted by
this pass. What doesn't stand is the **specific claim that these fixes
close the gap relative to English** -- for three of the four cells, they
mostly just made both languages cheaper together, not the target
language cheaper *relative to* English, which is what the 1.2x bar
actually measures.

### File state

New this entry: this section,
`scripts/harness_hardening_fairness_audit_deepseek.py`,
`results/harness_hardening_fairness_deepseek_en.csv`,
`results/harness_hardening_fairness_gemini_en.csv`,
`results/harness_hardening_fairness_qwen_en.csv`. No existing results
file was overwritten -- every "OLD" number above is still on file,
unedited, in its original results CSV; this entry adds the "NEW" numbers
alongside rather than replacing anything. Untouched, as always:
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every
variant), all three `decision_rule_h*.csv`, and `docs/paper_draft.md`.

---

# Iteration 2, fair-comparison-by-design

Second refinement pass on the three cells that failed the correction
pass above (`deepseek-flash/es`, `deepseek-flash/zh`, `qwen3.5-flash/zh`).
**Hard rule for this entire pass, pre-committed before any new data:**
every candidate is tested on the target language and on English
simultaneously, same round, identical wording. The reported ratio is
always (fixed target-language cost) / (fixed English cost) -- never
against the original unfixed baseline. Same standing caveat: **post-hoc
engineering, product track, not part of the confirmatory study.**
`gemini-3.5-flash-lite/es` (already verified fair) is untouched by this
pass.

### Step 1 -- qwen: is the looping translation-specific? (existing data, no new calls)

Checked the *raw, unfixed* baseline (no instruction at all) for both
languages: mean completion_tokens en=1923.3 (median 1178.0), zh=2720.5
(median 1638.0) -- **ratio 1.41x**. English is already producing
1900+ reasoning-heavy tokens on a simple MGSM problem with zero
instruction. The looping is a generic model behavior, not a
translation-specific one -- Chinese amplifies it by ~41%, it doesn't
create it. This matches exactly what the correction pass already found
empirically (the same anti-looping instruction applied to both arms
brought the ratio from a misleading 0.748x down to 1.116x, CI
[0.946, 1.390] -- spanning both sides of 1.0 *and* 1.2). Per Step 2's
rule (generic fixes get applied to both arms from the start, and
whatever's left over is the thing needing a translation-specific
explanation): **the already-collected matched-arm data (`harness_
hardening_qwen_zh_fix.csv` + `harness_hardening_fairness_qwen_en.csv`,
same template, same N=50, same round) already satisfies this pass's hard
rule.** Not redrawing identical data a third time -- reused as this
iteration's qwen result, stated explicitly rather than silently
re-presented as new.

### Step 1 (continued) -- deepseek: decomposing the fair 1.303x / 1.149x gap

Both shipped templates contain one generic clause ("no explanation")
bundled with genuinely language-mechanical clauses ("reason in English
internally", "give the final answer in '{lang}'", "no English in the
output"). Per Step 2, stripped the generic clause, keeping only the
language-mechanical core, to isolate what's actually left:

| | shipped (mixed) | lang-only (this iteration) | tokens |
|---|---|---|---|
| es | "...give **only** the final answer in '{lang}', **no explanation**, no English in the output..." | "...give the final answer in '{lang}', no English in the output..." | 34 (was 38) |
| zh | "...give **only** the final answer in '{lang}', **no explanation**..." | "...give the final answer in '{lang}'..." | 25 (was 29) |

Both spot-checked on the standard 2 real questions before any batch run
-- correct, in-language, no leakage, both cases.

### Pre-committed design, before running the full batches

- Fresh N=50 per arm per cell (target-language arm and English arm,
  same round, identical lang-only template -- for the English arm, the
  template is applied exactly as written with `{lang}`='en', including
  the resulting self-referential oddity ("never 'en'... give the final
  answer in 'en'"), same precedent as the correction pass, not smoothed
  over.
- Statistic: bootstrap CI of the median per-task ratio (fixed-target /
  fixed-English), same `bootstrap_ci()` import as every other cell in
  this project.
- Pass = median <=1.2x **and** CI excludes 1.2 (CI_high < 1.2,
  comfortably, matching the original C4 pilot's stricter-than-H1
  criterion).
- Accuracy tracked on **both** arms, every iteration -- a fix that only
  gets checked on the target language could be silently breaking
  English, exactly the failure mode this whole pass exists to catch.
- After measuring, decompose any remaining gap into prompt-side vs.
  completion-side (same dollar-weighted method used throughout this
  project). If it's completion-side and traces to the target language's
  own answer-token cost with no further instruction lever available,
  document it as a structural tokenizer-fertility limit and stop --
  not a target to keep chasing.

## 2026-09-19 -- Iteration 2 results: es marginal pass, zh still fails and doesn't cleanly explain, qwen resolved as generic

Fresh N=50 per arm, both arms same round, identical lang-only templates
(`results/harness_hardening_iter2_deepseek.csv`, 200/200, 0 errors, 0
truncated). Statistic and criterion exactly as pre-committed above.

### deepseek-flash/es -- lang-only template

| | median ratio | 95% CI | margin | accuracy (target / en) |
|---|---|---|---|---|
| es_lang_only vs en_lang_only | **1.006x** | **[0.853, 1.181]** | **+0.019** | 92.0% / 96.0% |

**Technically clears the pre-committed criterion, but this is a bare
pass, not a comfortable one** -- CI upper bound sits 0.019 below 1.2,
not the kind of margin this project has otherwise required before
calling something resolved. Accuracy gap (92.0% vs 96.0%, -4pts) noted,
not dramatic but not zero either.

**Decomposition (median-based, more robust than the dollar-sum here --
see zh below for why the two can diverge):** median prompt_ratio=1.119x,
median completion_ratio=0.976x. **The median-level driver is prompt-
side**, not completion-side -- consistent with Spanish text itself
needing more input tokens than English for equivalent content, which is
this entire project's own core, already-established measurement (the
baseline token tax). This is expected, structural input-side tokenizer
fertility, not a translation-mechanics bug -- no further prompt lever
addresses it. **Reasonable to treat as adequately resolved given the
pass and the understood driver, without overselling the thin margin.**

### deepseek-flash/zh -- lang-only template

| | median ratio | 95% CI | margin | accuracy (target / en) |
|---|---|---|---|---|
| zh_lang_only vs en_lang_only | **1.330x** | **[1.183, 1.439]** | **-0.239** | 90.0% / 96.0% |

**Fails clearly -- and got worse than the mixed-template fair result
(1.149x -> 1.330x), not better, once the brevity clause was removed
from both arms.** That direction is itself informative: the brevity
clause was doing more real work for zh specifically than for its matched
English arm, not just adding symmetric noise.

**Decomposition: completion-side-dominated even at the median**
(median completion_ratio=1.520x, prompt_ratio=0.975x -- prompt is
*not* the driver here, unlike es). This does **not** cleanly fit Step
4's "stop, it's tokenizer fertility" bucket -- that bucket is for
prompt/input-side fertility on the question text, and here the gap is
squarely completion-side, on the model's own generated output. **Read
plainly, not forced into a resolved bucket: this most likely connects to
the same completion-token cost anomaly documented earlier in this
project's C2/C4 zh work** (`docs/methodology-notes.md`'s "unresolved,
non-reproducible... most likely transient provider-side variance"
finding, and the C4 pilot's own 30-36%-of-rows anomalous-cost group) --
never fully explained there either, and not something a prompt-wording
change is likely to reach given it already resisted direct
reproduction attempts. **Status: open, not stopped, not solved.**
Honestly unresolved rather than declared either a structural limit or a
fixable bug.

### qwen3.5-flash/zh -- resolved as generic, not translation-specific

Using the already-collected matched-arm data (Step 1 above): fair
ratio 1.116x, CI [0.946, 1.390] -- spans both sides of 1.0 *and* 1.2.
Combined with the raw-baseline finding that English already shows
1900+-token looping with zero instruction (1.41x zh/en ratio on raw
completion length, not a language-specific multiplier), **the honest
read is that there is no statistically confident residual zh-specific
tax here** -- the original 1.395x finding is adequately explained by a
generic verbosity/looping tendency this model has in both languages,
amplified somewhat (not dramatically, and not reliably at this N) in
Chinese. Not chased further with a new targeted fix, since there's no
diagnosed language-specific mechanism left to target -- the generic fix
already applied to both arms is the correct terminus here, not an
under-powered result to iterate past.

### Step 6 -- summary, per cell

| cell | what was tried | gap closed? | verdict |
|---|---|---|---|
| deepseek-flash/es | lang-only template (brevity clause removed), both arms | Yes, barely (median 1.006x, margin +0.019) | **Resolved, thin margin** -- driver is expected input-side tokenizer fertility |
| deepseek-flash/zh | lang-only template (brevity clause removed), both arms | No -- got worse (1.330x) | **Open, not structural, not solved** -- completion-side, likely the same unresolved anomaly documented earlier in this project |
| qwen3.5-flash/zh | generic anti-looping fix, already fairly applied to both arms | Effectively yes -- no confident residual | **Resolved as generic model behavior**, not a translation-specific tax |

### File state

New this entry: this section, `scripts/harness_hardening_iter2_deepseek.py`,
`results/harness_hardening_iter2_deepseek.csv`. No existing results file
edited or overwritten. Untouched, as always: `phase3_c1_raw.csv`,
`phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every variant), all three
`decision_rule_h*.csv`, `docs/paper_draft.md`, and
`gemini-3.5-flash-lite`'s already-verified es result.

---

## 2026-09-19 -- Iteration 2 continued: one more targeted attempt at deepseek-flash/zh

Only cell still open after the above: deepseek-flash/zh (1.330x, CI
[1.183, 1.439], completion-side-dominated, not explained by tokenizer
fertility). Two tracks, pre-committed before running anything. Same
standing caveat: **post-hoc engineering, product track, not part of the
confirmatory study.**

### Note on Step 1 -- this exact comparison already has one data point

"Brevity clause applied to both arms simultaneously" is not entirely
untested: the CORRECTION PASS's 1.149x figure (`phase3_c4_raw_v5_zh_lean_
strong.csv` zh arm vs. `harness_hardening_fairness_deepseek_en.csv`'s
`zh_template_on_en` rows) **is** exactly that comparison -- shipped
template (incl. "no explanation") on both zh and en, same wording. It
already has a CI ([1.098, 1.258]) that fails the strict bar (upper bound
exceeds 1.2 by 0.058). Flagging this rather than re-presenting it as
brand new. Running a **fresh, independent draw** of it anyway, both
because this iteration's hard rule asks for fresh N=50 and because this
project's own precedent (the 0.937x -> 0.981x -> ... zh reproducibility
checks earlier in this log) treats a single draw as insufficient to
trust on its own, especially given the completion-side variance already
on record for this exact cell.

### Note on Step 2 -- cap calibration, with a censoring caveat

C0's own deepseek-flash/zh MGSM distribution (`phase1_raw.csv`): of 72
attempts, **22 (30.6%) never returned a completion at all** -- hard
timeouts (10 at a 90s wall, 10 at a 30s wall from an earlier version of
the harness, 2 raw SDK "Request timed out"). Of the 50 that did complete:
median 205, p95 1029.7, p99 5912.2, **max 6879**, 0% truncated. This
means the observed distribution is **right-censored**: it's a lower
bound on the true tail, since the slowest ~30% of generations never ran
long enough to be measured at all. This is very plausibly the same
mechanism as the previously-documented, never-reproduced-on-demand
completion-cost anomaly (`methodology-notes.md`, "transient provider-side
variance"; the C4 pilot's 30-36%-of-rows anomalous group) -- a small
fraction of zh calls occasionally run away, and depending on how far
they get before hitting the wall, they show up either as an extreme
completion-token outlier or as an outright timeout/error.

**Cap: `max_tokens=8192`.** Calibrated the same way as the original
Equalizer fix (methodology-notes.md, 2026-09-16 entry) -- comfortably
above the observed completed-call max, not guessed -- and specifically
matches this project's own already-established MGSM-wide precedent
(`MAX_TOKENS_BY_DATASET = {"MGSM": 8192, ...}`), rather than inventing a
new number. Explicitly **not** claimed to be provably sufficient given
the censoring above -- a genuinely runaway generation could in principle
still exceed it, which is exactly what this step's truncation check is
for. Spot-checked on 2 real zh MGSM questions before the batch run:
correct answers, correct language, 103 and 92 completion tokens, 0%
truncated, cap doesn't interfere with normal-length generations.

### Pre-committed design (written before running the batch)

Three template x cap combinations (`scripts/harness_hardening_iter2_zh_
capfix.py`), zh arm and English arm, same round, fresh N=50 each (300
calls total):

| version | template | max_tokens |
|---|---|---|
| `brevity_both` | shipped zh template, incl. "no explanation" (fresh draw of the 1.149x comparison) | uncapped |
| `capped_lang_only` | iteration 2's lang-only template (brevity removed) | 8192 |
| `brevity_both_capped` | shipped zh template, incl. "no explanation" | 8192 |

- Cap applied symmetrically to both arms wherever a version uses one --
  it's generic infrastructure, not a language-specific lever, same
  principle applied to every other generic clause in this pass.
- Statistic: `bootstrap_ci()` import, median per-task ratio (fixed-zh /
  fixed-en), same as every other cell in this project.
- Pass = median <=1.2x **and** CI_high < 1.2, comfortably -- same bar as
  always.
- **Truncation must be 0% on every capped arm before trusting any cost
  number from it** -- a cap that clips real answers is a new bug, not a
  fix.
- Accuracy tracked on all six version/arm cells -- a version that drops
  cost by silently truncating or degrading answers gets discarded and
  reported, not shipped.
- All three versions run in the same batch regardless of `brevity_both`'s
  own result, but `brevity_both_capped` (Step 3) is only reported as the
  shipped candidate if `brevity_both` alone doesn't clear the bar --
  consistent with pre-registering the full design rather than branching
  after seeing partial results.
- If nothing here clears the bar comfortably, that gets reported exactly
  as plainly as every other honest non-result in this project -- not
  forced.

### Results

`results/harness_hardening_iter2_zh_capfix.csv`, 300/300, **0 errors, 0
truncated across all three versions** -- the cap never clipped a real
answer in any capped arm, so every cost number below is trustworthy by
this iteration's own pre-committed check.

| version | median cost ratio | 95% CI | margin (1.2 - hi) | accuracy zh/en | median prompt/completion ratio |
|---|---|---|---|---|---|
| `brevity_both` | **1.190x** | **[1.100, 1.312]** | **-0.112** | 90.0% / 94.0% | 0.976x / 1.371x |
| `capped_lang_only` | **1.312x** | **[1.230, 1.548]** | **-0.348** | 92.0% / 94.0% | 0.975x / 1.467x |
| `brevity_both_capped` | **1.222x** | **[1.117, 1.316]** | **-0.116** | 86.0% / 94.0% | 0.976x / 1.409x |

**All three fail the pre-committed bar.** None gets a CI upper bound
under 1.2.

**Step 1 result:** `brevity_both` is a fresh, independent draw of the
CORRECTION PASS's 1.149x comparison. Second draw: 1.190x, CI
[1.100, 1.312]. Same qualitative shape as the first draw (1.149x, CI
[1.098, 1.258]) -- median close to but under 1.2, CI upper bound
reliably above it. **Two independent draws now agree: this is a
reproducible failure to comfortably clear the bar, not a one-off.**
Brevity-on-both-arms does not resolve deepseek-flash/zh.

**Step 2 result: the cap never engaged, in any version.** Observed zh
completion-token max this round: 4172 (`brevity_both`), **7118**
(`capped_lang_only`), 5456 (`brevity_both_capped`) -- all below the 8192
ceiling, so truncated=0% everywhere and the cap changed nothing. This is
not a coincidence to be redone with a lower number: the completion-token
distribution's actual shape (all three versions) is a **moderate,
persistent tail, not a single catastrophic spike** -- median 120-215
tokens, but 8-16% of zh calls land above 1000 tokens, climbing smoothly
through the 90th/95th/99th percentiles rather than jumping. A cap tight
enough to bind on this tail without waiting for a rare true runaway would
have to sit somewhere under ~1000-2000 tokens -- which would truncate a
meaningful fraction of ordinary, correct, non-anomalous long answers
(8-16% of all zh rows), exactly the "new bug, not a fix" outcome this
step's own truncation check exists to prevent. **A truncation-safe cap
cannot structurally address this tail. Not a calibration miss -- a
mismatch between the tool (a hard ceiling) and the problem (a
consistently heavy-but-not-catastrophic distribution).**

**Step 3 result:** `brevity_both_capped` (1.222x, CI [1.117, 1.316]) is
statistically indistinguishable from `brevity_both` alone (1.190x, CI
[1.100, 1.312]) once accounting for draw-to-draw noise -- consistent with
the cap being inert, as Step 2 predicts. **Accuracy note:** zh accuracy
on this version (86.0%) is the lowest of the three, an 4-6pt gap versus
the other two zh cells (90.0%, 92.0%) run in the same batch. The cap
cannot be the mechanical cause (0% truncated, so no answer was cut off);
most likely N=50 sampling noise, but flagged per this iteration's Step 4
rule rather than silently absorbed -- **not treating this version as a
safe combination to ship** on the strength of a slightly-better cost
margin alone.

### Step 5/6 -- plain verdict

**deepseek-flash/zh remains open. No version tested this pass, or in
Iteration 2 before it, comfortably clears the bar.** What this pass adds
that wasn't known before:

- The 1.1-1.2x-median / CI-fails-to-exclude-1.2 pattern is now
  **reproduced on an independent draw** -- confidently a real, stable
  property of this cell, not sampling noise from a single unlucky batch.
- The completion-side inflation is now characterized precisely enough to
  rule out the obvious structural fix: it is **not** a rare catastrophic
  runaway (which a cap could safely clip) -- it is a **consistently
  heavy tail present in roughly 1 in 8-10 zh calls**, at magnitudes that
  overlap with genuine, correct, non-truncated long answers. No
  max_tokens value threads that needle: too high to bind (this pass's
  8192), too low and it starts truncating real answers instead of
  anomalous ones.
- No further prompt-side or cap-side lever is identified. Per this
  iteration's own instruction not to force a number: **stopping here,
  reported as genuinely unresolved** within the single-call architecture
  as currently scoped -- not relabeled as "structural tokenizer
  fertility" (Step 4's bucket is for prompt/input-side effects, and the
  driver here is squarely completion-side), and not shipped as a pass.
  A fix, if one exists, most likely requires a mechanism this
  architecture doesn't have (e.g. a bounded retry/fallback path on
  detecting the tail), which is out of scope for a single-call prompt
  hardening pass.

### File state

New this entry: this section, `scripts/harness_hardening_iter2_zh_capfix.py`,
`results/harness_hardening_iter2_zh_capfix.csv`. No existing results file
edited or overwritten. Untouched, as always: `phase3_c1_raw.csv`,
`phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every variant), all three
`decision_rule_h*.csv`, `docs/paper_draft.md`, and every other model's
already-verified results (`gemini-3.5-flash-lite`/es, `qwen3.5-flash`/zh).

---

## 2026-09-19 -- Iteration 2 continued: temperature sweep on deepseek-flash/zh

The remaining lever short of an architecture change: does lower
temperature shrink the completion-length tail identified above? Same
fair-comparison discipline as every round -- matched setting on zh and
en arms, always. Same standing caveat: **post-hoc engineering, product
track, not part of the confirmatory study.**

### Infra change: `harness/executor.py` gets a `temperature` passthrough

`_run_loop()` and `execute()` both gain an optional `temperature: Optional[float]
= None` parameter, threaded into `kwargs["temperature"]` only when not
`None` -- identical pattern to the existing `max_tokens` passthrough
added earlier in this track. Purely additive: every existing caller that
doesn't pass it gets the provider default, unchanged. Confirmed accepted
by deepseek's API with a trivial 2+2 smoke test at temp=0.3 and temp=0.0
(no errors, sane answers) before touching the real prompt. Spot-checked
on 2 real zh MGSM questions at all three planned settings (default,
0.3, 0.0) using the brevity-on-both-arms template -- correct answers,
correct language, no leakage, all three settings.

### Note on Step 3's "combine" instruction

Step 1 as literally specified already runs temperature x brevity-on-
both-arms together (the "current best zh prompt" *is* brevity-on-both-
arms, at each temperature setting) -- so Step 1's own design already is
the combination Step 3 asks for. No separate Step 3 run is needed unless
Step 1's results suggest a different combination is worth isolating;
noted explicitly rather than silently skipped.

### Tail threshold, carried over from the prior entry

The previous entry characterized the anomaly as "8-16% of zh calls land
above 1000 tokens" -- reusing that exact threshold (`completion_tokens
> 1000`) as this entry's tail-occurrence-rate definition, tracked on
both arms, not just zh.

### Pre-committed design (written before running the batch)

`scripts/harness_hardening_iter2_zh_temperature.py`. Three settings
(`default` = provider default / no override, `t0.3`, `t0.0`), zh and en
arms, same brevity-on-both-arms template, fresh N=50 each (300 calls
total).

- Statistic: `bootstrap_ci()` import, median per-task ratio (fixed-zh /
  fixed-en, `statistic=np.median`), same as every other cell.
- Pass = median <=1.2x **and** CI_high < 1.2, comfortably -- same bar as
  always.
- Tail-occurrence rate (`completion_tokens > 1000`) and accuracy tracked
  on **both** arms, every setting.
- **Step 2 (reproducibility gate):** if any setting passes comfortably
  without hurting accuracy on either arm, it gets one independent fresh
  N=50 re-draw at that exact setting before being called real -- same
  bar already applied to the brevity result (which needed two draws to
  trust).
- **Step 4 (stop condition):** if nothing here clears the bar, stop --
  no further prompt or sampling-parameter variations get tried. Report
  plainly and name the one remaining lever: a bounded retry (detect an
  anomalously long completion, re-issue the call once) would very likely
  work, but it reintroduces a conditional second call, breaking this
  track's single-call framing. That is an architecture decision, not a
  prompt tweak -- flagged for a decision, not implemented.

### Results

`results/harness_hardening_iter2_zh_temperature.csv`, 300/300, 0 errors,
0 truncated.

| setting | median cost ratio | 95% CI | margin (1.2-hi) | tail rate zh/en (>1000 tok) | accuracy zh/en | median completion_ratio |
|---|---|---|---|---|---|---|
| `default` | **1.146x** | **[1.054, 1.230]** | **-0.030** | 8.0% / 4.0% | 88.0% / 94.0% | 1.216x |
| `t0.3` | **1.282x** | **[1.101, 1.429]** | **-0.229** | 6.0% / 4.0% | 84.0% / 94.0% | 1.504x |
| `t0.0` | **1.261x** | **[1.163, 1.430]** | **-0.230** | 8.0% / 6.0% | 88.0% / 94.0% | 1.484x |

**All three fail. Lower temperature does not help -- it makes the ratio
worse, not better.** `default` (provider default, no override) is the
closest miss of any deepseek-flash/zh comparison run in this entire
track (margin -0.030, CI upper bound 1.230), and it is now the **third**
independent draw of essentially this same comparison:

| draw | median | CI | margin |
|---|---|---|---|
| correction pass | 1.149x | [1.098, 1.258] | -0.058 |
| iter2 cap-fix `brevity_both` | 1.190x | [1.100, 1.312] | -0.112 |
| this entry `default` | 1.146x | [1.054, 1.230] | -0.030 |

Three draws, same qualitative result every time: median clustered
1.15-1.19x, CI upper bound clustered 1.23-1.31x, **never** excluding
1.2. Consistent, reproducible, and a genuine near-miss -- but a miss.

**Why lower temperature makes it worse, not better:** both `t0.3` and
`t0.0` *do* shrink the single largest outlier relative to `default` (zh
max completion_tokens: 10762 at default -> 1955 at t0.3 -> 3002 at
t0.0), which looked promising going in. But the **median-level**
completion ratio gets worse at both lower settings (1.216x at default ->
1.504x at t0.3 -> 1.484x at t0.0) -- lower temperature doesn't shrink
the *typical* zh/en gap, it just clips the rare extreme case while (if
anything) making the model's ordinary-case verbosity asymmetry between
languages slightly more consistent. Tail-occurrence rate (>1000 tokens)
barely moves and isn't the thing driving the ratio either way. **Net
effect: temperature is not a lever on this problem at all** -- it
doesn't touch the mechanism, it only reshapes where the variance sits.

**Accuracy note:** `t0.3` shows the largest accuracy asymmetry of
anything measured in this whole track (84.0% zh vs. 94.0% en, a 10-point
gap) -- an additional, independent reason not to pursue lower
temperature even setting the cost ratio aside.

**Step 2 (reproducibility gate) does not trigger** -- no setting passed
comfortably, so no re-draw was needed or run. **Step 3 does not apply**
-- there is no "best temperature" to combine with brevity; every
temperature setting tested was worse than the no-override default, and
default alone (already brevity-on-both-arms, per the note above) still
misses.

### Step 4 -- plain verdict, per the pre-committed stop condition

**deepseek-flash/zh does not clear the bar under any prompt, cap, or
temperature variation tried across this iteration.** Three independent
draws of the best available prompt (brevity-on-both-arms, provider-
default sampling) land in a tight, reproducible band just above the
line (median 1.15-1.19x, CI upper bound 1.23-1.31x). Temperature
reduction, tested properly (matched on both arms, two settings, with a
tail-occurrence-rate and accuracy check), makes it worse, not better.
The completion-side cap tested in the prior entry is structurally unable
to bind without truncating real answers.

**No further prompt, cap, or sampling-parameter variation is planned.**
Per this pass's own stop condition: **the one remaining lever is a
bounded retry** -- detect an anomalously long completion (e.g.
completion_tokens crossing a threshold, or a wall-clock heuristic) and
re-issue the call once. This would very likely work, since the anomaly
is a minority-of-calls tail, not a universal property of every zh call.
But it requires a **conditional second call**, which breaks the
single-call framing this entire C4 track has held to from its original
design (`docs/methodology-notes.md`'s C4 pilot section: "no Packer call
... no Equalizer ... no Expander call"). That is an **architecture
decision**, not a prompt-hardening fix, and is explicitly **not
implemented here** -- flagged for a decision rather than built.

### File state

New this entry: this section, `harness/executor.py` (additive
`temperature` passthrough, mirrors the existing `max_tokens` pattern,
`None` default preserves every existing caller's behavior unchanged),
`scripts/harness_hardening_iter2_zh_temperature.py`,
`results/harness_hardening_iter2_zh_temperature.csv`. No existing
results file edited or overwritten. Untouched, as always:
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every
variant), all three `decision_rule_h*.csv`, `docs/paper_draft.md`, and
every other model's already-verified results (`gemini-3.5-flash-lite`/es,
`qwen3.5-flash`/zh).

---

## 2026-09-19 -- Bounded early-cutoff streaming retry for deepseek-flash/zh

The lever named and deliberately not built at the end of the previous
entry, now implemented on explicit instruction. Same standing caveat:
**post-hoc engineering, product track, not part of the confirmatory
study.**

### Step 1 -- threshold calibration (not a guess)

Pooled the three most recent independent draws of the current best zh
prompt (shipped template, brevity-on-both-arms, uncapped, default
temperature) that this track has already collected: `phase3_c4_raw_v5_
zh_lean_strong.csv` (correction pass), `harness_hardening_iter2_zh_
capfix.csv`'s `brevity_both` version, `harness_hardening_iter2_zh_
temperature.csv`'s `default` setting -- 150 zh + 100 en completion-
length observations, same template throughout.

| percentile | zh completion_tokens | en completion_tokens |
|---|---|---|
| 50 | 120 | 87 |
| 75 | 188 | 157 |
| 80 | 227 | 188 |
| 85 | 306 | 281 |
| 90 | 653 | 328 |
| 95 | 2101 | 533 |
| 99 | 4827 | 1263 |
| max | 10762 | 4669 |

Clear inflection between p85 (306) and p90 (653), accelerating sharply
by p95 (2101) -- consistent with "the tail" as previously characterized.
**Threshold: 1000 tokens.** At this value, 8.7% of zh calls land above
it vs. 4.0% of en calls -- matches the previously-reported "8-16%"
characterization almost exactly, and gives clean separation from English
(so the mechanism should rarely fire there, as Step 3 expects) without
being so low it would catch ordinary mid-length answers (which extend
smoothly out to ~650 tokens at p90 with no sign of anomaly yet).

### Step 2 -- implementation

`harness/executor.py` gains `execute_with_cutoff_retry()`, a new,
narrow, purely-additive function -- does not touch `_run_loop()` or
`execute()`, so every existing caller/condition (C0-C3a, every prior C4
run) is completely unaffected. Mechanism:

1. Stream the completion (`stream=True, stream_options={"include_usage":
   True}`), accumulating `content` and `reasoning_content` deltas
   together (both count toward billed `completion_tokens`, confirmed in
   an earlier entry -- reasoning_tokens is a subset, not additive).
2. After every chunk, re-estimate the running total via `tiktoken`
   (`o200k_base`) -- the same approximate-token-counting convention this
   project already uses elsewhere (`harness/conditions.py`,
   `harness/packer.py`) to sanity-check prompt lengths, now applied
   live. Not deepseek's real tokenizer, so this is an estimate, not an
   exact count -- used **only** for the aborted call's completion-token
   accounting, since a cancelled stream never receives a real `usage`
   object (that only arrives on the final chunk of a normally-finishing
   stream).
3. If the estimate reaches 1000 before the model finishes: close the
   stream immediately (`Stream.close()`) and re-issue the identical call
   once. The retry is allowed to run to completion regardless of what it
   does -- if it *also* crosses 1000, it is accepted as-is (bounded = one
   retry maximum, no loop, per instruction).
4. Cost accounting for a retried row = tiktoken-estimated cost of the
   aborted first attempt (its real prompt-token count, reused from the
   retry's own usage since both calls send identical messages, plus the
   tiktoken-estimated completion count at the moment of cancellation) +
   the retry's real, API-reported cost. Never the full first-attempt
   generation length -- that's the entire point.

**Billing-semantics caveat, stated plainly:** closing the stream is the
standard client-side signal to stop generation, and empirically an
aborted call returns in a fraction of the time a full one takes (a
forced 15-token-cutoff test completed in 0.84s vs. 12.66s for an uncut
~1700-token response on the same client) -- consistent with the
provider halting generation on disconnect, not proof of it. This project
has no visibility into DeepSeek's actual billing meter. If DeepSeek in
fact bills the originally-intended full generation regardless of
disconnect, true savings would be smaller than reported below (worst
case zero) -- flagged rather than assumed.

**Verification before any batch run:**
- Trivial 2+2 smoke test with streaming: works, sane usage.
- Forced artificial cutoff (`cutoff_tokens=20`) on 2 real zh MGSM
  questions to deterministically exercise the retry path: both fired
  (`retry_fired=True`), both also crossed on the retry given how low the
  forced threshold was (`cutoff_hit_second=True`, correctly accepted
  as-is), `est_completion_tokens_first=20` exactly in both cases
  (confirms the estimator stops right at threshold), final accounting
  (`wasted_cost_usd` + real retry cost) internally consistent, no
  double- or under-charging, correct answers, correct language in both.
- Real threshold (`cutoff_tokens=1000`) spot-checked on 2 real questions
  per arm (zh, en): none fired (expected -- typical-length answers stay
  well under 1000), normal path confirmed intact, correct answers,
  correct language, both arms.

### Pre-committed design (written before running the real batch)

`scripts/harness_hardening_iter2_zh_cutoff_retry.py`. zh and en arms,
same shipped template, `cutoff_tokens=1000` on both (Step 3 -- identical
mechanism, identical threshold, not language-specific), fresh N=50 each.

- Statistic: `bootstrap_ci()` import, median per-task ratio (fixed-zh /
  fixed-en), same as every other cell.
- Pass = median <=1.2x **and** CI_high < 1.2, comfortably -- same bar as
  always.
- Report per arm: retry-fire rate, fair cost ratio, accuracy.
- **Step 2's reproducibility gate:** if it passes comfortably without
  hurting accuracy on either arm, one independent second draw (same 50
  questions, this project's standing definition of "independent draw"
  -- fresh API calls, fresh model stochasticity, not a new sample) before
  calling it real.
- **Step 5:** spot-check a handful of retried rows' full token
  accounting by hand to confirm no double-charging, and report plainly
  whether the fair ratio actually clears 1.2x with the CI excluding it
  -- not forced either way.

### Results (draw 1)

`results/harness_hardening_iter2_zh_cutoff_retry_draw1.csv`, 100/100, 0
errors.

| | median cost ratio | 95% CI | margin (1.2-hi) |
|---|---|---|---|
| cutoff-retry (fixed-zh/fixed-en) | **1.232x** | **[1.117, 1.341]** | **-0.141** |

**Fails -- and comes in worse than every recent no-retry draw of the same
template** (1.146x, 1.149x, 1.190x). Per arm:

| arm | retry-fire rate | of those, also crossed on retry | accuracy | mean cost_usd |
|---|---|---|---|---|
| zh | 10.0% (5/50) | **100% (5/5)** | 88.0% | $0.0001952 |
| en | 2.0% (1/50) | 0% (0/1) | 94.0% | $0.0000612 |

Fire rate on en (2%) is well below zh (10%), as Step 3 expected -- the
mechanism is not language-biased by construction, it just rarely
triggers on English's naturally shorter completions.

### Step 5 -- why it fails: the tail is question-specific, not per-call noise

**Every single zh row that fired the retry also crossed the threshold
again on the retry (5/5, 100%)** -- not the "rare coincidence" the
bounded design was implicitly betting against. Checked whether these 5
exact questions (`task_id` 184, 236, 177, 159, 146) were already in the
tail in prior, independent draws of this same template:

| task_id | correction pass | capfix `brevity_both` | temperature `default` |
|---|---|---|---|
| 184 | 2164 | 1113 | 2025 |
| 236 | 4640 | 4172 | 966 |
| 177 | 1577 | 1259 | 5006 |
| 159 | 4347 | 2288 | 10762 |
| 146 | 2487 | 701 | 1031 |

**All five are already, consistently, in or near the tail across every
prior draw** (17 of 20 comparison cells above sit above 1000; the
lowest, 701, is still comfortably above the ordinary p75 of ~188). This
is not five unlucky rolls -- **the tail is substantially a property of
specific MGSM zh questions, not independent per-call stochastic noise.**
That directly explains the 100% cutoff-hit-second rate: retrying the
identical prompt on a question that reliably provokes long reasoning
mostly reproduces the same long reasoning, not a lucky short one.

**Consequence: for exactly the rows the mechanism exists to help, it
adds a wasted ~1000-token first attempt on top of a second attempt that
is usually just as expensive as the first would have been anyway.**
Sanity-checked by comparing this draw's actual cutoff-retry cost per
retried row against the same 5 questions' cost in the independent
`temperature`/`default` no-retry draw (different draw, so not a true
paired counterfactual, but the best available comparison):

| task_id | cutoff-retry cost (this draw) | single-call cost (other draw, same Q) |
|---|---|---|
| 184 | $0.001519 | $0.000580 |
| 236 | $0.001567 | $0.000286 |
| 177 | $0.000734 | $0.001422 |
| 159 | $0.002021 | $0.003030 |
| 146 | $0.001446 | $0.000307 |
| **sum** | **$0.007287** | **$0.005625** |

Cutoff-retry costs ~30% *more* in total across these 5 rows than the
comparison single-call realization -- directionally consistent with the
mechanism backfiring on exactly its target cases, though this is a
cross-draw comparison (real per-call stochastic variance exists even on
these "hard" questions -- 2 of 5 individual rows happened to come in
cheaper this way, 3 of 5 more expensive), not a controlled counterfactual
of the identical un-cut attempt.

**Excluding these 5 persistently-hard questions entirely, the remaining
45-pair median ratio is 1.222x, CI [1.104, 1.294]** -- barely different
from the full-sample 1.232x. The median statistic was never being pulled
around by just these five rows (consistent with every earlier
decomposition in this track already finding a broad completion-side
effect, not one dominated by rare extremes) -- so even setting the
backfire problem aside, the mechanism does not fix the ordinary case
either.

### Step 5 (continued) -- accounting verification, no double-charging found

Manually verified `wasted_cost_usd` for all 5 retried zh rows: computed
as `cost_usd(prompt_tokens, 1000)` using each row's real prompt-token
count (identical between attempts, reused from the retry's usage) --
matches the logged value to the cent in every case (~$0.000293-0.000301,
consistent with 1000 completion tokens at deepseek-flash's $0.28/1M
output rate plus a small prompt-token contribution). `cost_usd` (total)
matches `wasted_cost_usd` + `cost_usd(prompt_tokens, <retry's real
completion_tokens>)` exactly in every case -- no double-charging, no
under-charging, internally consistent. **One accounting note for anyone
reading this CSV later:** the `completion_tokens` column on a retried
row holds only the **retry's** token count (the tokens that actually
produced the final answer) -- the wasted first attempt's ~1000 tokens
are folded into `cost_usd` but not into `completion_tokens`. This is
intentional (the field means "tokens behind the returned answer") but
worth remembering when eyeballing a row: `completion_tokens x price`
will not reproduce `cost_usd` for a retried row on its own.

### Step 2 (reproducibility gate) -- not triggered, by design

This pass does not meet Step 2's own trigger condition ("shrinks the
tail... and the ratio drops comfortably under 1.2... without hurting
accuracy") -- it's worse than baseline, not better. Per the
pre-committed design, **no second draw was run.** Re-drawing a result
that already fails clearly and has a diagnosed causal explanation would
not change the conclusion, only spend more calls confirming it -- the
same judgment this track has applied throughout (e.g. not re-chasing
qwen3.5-flash/zh once its residual was diagnosed as noise).

### Step 4/6 -- plain verdict

**The bounded early-cutoff retry does not clear the bar, and should not
be shipped as implemented.** It is not merely ineffective -- for the
specific rows it exists to help, it plausibly makes cost *worse*,
because the completion-length tail on this cell is substantially a
per-question property, not independent per-call noise, so a same-prompt
retry mostly reproduces the same expensive behavior rather than
resampling into a short one. The "bounded, accept-as-is" design that
correctly avoids an infinite loop also means the mechanism has no way to
avoid paying twice on exactly the questions most likely to need it.

**deepseek-flash/zh remains open**, now with a sharper causal
understanding than before this entry: the driver is a small,
identifiable, largely *fixed* set of MGSM zh questions that reliably
provoke long reasoning from this model, not a uniformly-distributed
random tax across all zh calls. Every lever available within a
single-call-per-question architecture (brevity wording, a truncation-
safe max_tokens cap, temperature, and now a same-prompt bounded retry)
has been tried and ruled out with a specific, verified reason each time.
The one structural option that could plausibly work -- detecting the
tail and re-issuing with a *different* strategy (not just an identical
retry), e.g. falling back to English-only-then-translate for just the
~10% of questions that trip a length trigger -- is a larger design
change than a bounded retry and is **not** implemented or recommended
here without a separate decision; it also reintroduces the two-call
structure this track has avoided from the start, now for an even less
trivial reason (conditional branching per-question, not just per-cutoff
retry).

### File state

New this entry: this section, `harness/executor.py`
(`execute_with_cutoff_retry()`, purely additive),
`scripts/harness_hardening_iter2_zh_cutoff_retry.py`,
`results/harness_hardening_iter2_zh_cutoff_retry_draw1.csv`. No existing
results file edited or overwritten. Untouched, as always:
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every
variant), all three `decision_rule_h*.csv`, `docs/paper_draft.md`, and
every other model's already-verified results (`gemini-3.5-flash-lite`/es,
`qwen3.5-flash`/zh).

---

## 2026-09-20 -- Four-part follow-up: accuracy compilation, canonical zh tables, gpt-5.6-luna/ar retest, multi-step pilot

Full results reported in chat, in reference-table format. This entry
covers only the two parts that involved new API calls/new infrastructure
(parts 3 and 4); parts 1 (accuracy compilation) and 2 (canonical zh
tables) were pure read-only recomputation directly from existing raw
CSVs -- no new data, no files changed, sources cited inline in the chat
report.

### Part 3 -- gpt-5.6-luna/ar retested with the v2 lean-prompt fix

New file: `results/harness_hardening_gpt_luna_ar_v2.csv` (40 rows: 20
Math + 20 GAIA, 2 repeats each, matching MAPS_N_TASKS/MAPS_N_REPEATS
exactly). `scripts/harness_hardening_gpt_luna_ar_v2.py` reuses
`run_phase3.py`'s exact MAPS sampling logic (same SEED) so task_ids align
with the existing English MAPS C2 rows already in `phase3_c2_raw.csv`
(read, not modified -- English is not re-run, since it's architecturally
unaffected by the Packer template version). Math scoring replicates the
historical `\boxed{}`-extraction fix from the confirmatory study (that
fix was a one-time data patch, never merged into code, so it had to be
reproduced here -- verified against 10 known-correct `phase1_raw.csv`
Math rows, 10/10 match, before use). Spot-checked on 1 Math + 1 GAIA real
question before the batch. 40/40, 0 errors.

**Result: median 0.996x, CI [0.898, 1.209]** -- essentially at cost
parity (down from 0.999x/[0.837,1.204] originally, i.e. barely moved at
the pooled level) but the CI still, barely, fails to exclude 1.2.
Accuracy improved 40.0% -> 50.0% on the same 20 paired tasks (small N,
but no regression). Full diagnosis and recommendation in the chat
report.

### Part 4 -- multi-step pilot infrastructure + result

**Infra fix, purely additive:** `harness/executor.py`'s `_run_loop()`
unconditionally set `reasoning_effort="none"` whenever `tools` was
passed -- a gpt-5.6-luna-specific quirk that gemini's OpenAI-compat
endpoint rejects outright (400 INVALID_ARGUMENT, confirmed via direct
test). Scoped to `provider=="openai"`. Also added `"gemini"` as a
provider to `run_phase1.py`'s `get_client()`/`PRICES` (previously only
reachable via `harness_hardening_gemini.py`'s own standalone client) --
both changes purely additive, verified via a forced 2-tool-call smoke
test (47*6, then +15 -> 297, tool_calls_made=2) before the real pilot.

**New file:** `results/harness_hardening_multistep_pilot.csv`.
`scripts/harness_hardening_multistep_pilot.py`: same MGSM es/en problem
set already used throughout this project, same verified gemini-3.5-
flash-lite es v2 fix template, plus one added clause mandating a
calculator tool for every arithmetic operation (a real, registered tool
via `harness/executor.py`'s existing-but-never-exercised tool-call loop)
-- most MGSM problems need 2+ sequential operations by construction, so
this reliably forces genuine multi-turn tool use. N=30/arm, fair
(identical template + tool on both arms). Spot-checked on 2 real
questions per arm first -- correct answers, correct language, 2-3 tool
calls each. 59/60 rows clean; 1 row (en, task_id 184) hit
`MAX_TOOL_TURNS=8` without producing a final answer -- a new failure
mode that never appeared in any single-call test in this project,
reported as a real finding, not discarded.

**Result: median 1.013x, CI [0.944, 1.041]** on the 29 cleanly-paired
tasks -- the fix's near-parity cost ratio holds under multi-step
execution. Accuracy 96.6% both arms. Mean tool_calls_made ~3.0 both
arms (symmetric, confirms the mandate worked evenly). Full discussion in
the chat report.

### File state

New this entry: this section, `results/harness_hardening_gpt_luna_ar_v2.csv`,
`results/harness_hardening_multistep_pilot.csv`,
`scripts/harness_hardening_gpt_luna_ar_v2.py`,
`scripts/harness_hardening_multistep_pilot.py`. Additive-only changes to
`harness/executor.py` (provider-scoped `reasoning_effort`, already-present
`temperature`/cutoff-retry code untouched) and `scripts/run_phase1.py`
(new `"gemini"` provider branch + `PRICES` entry) -- both verified to
leave every existing caller's behavior unchanged. Untouched, as always:
`phase3_c1_raw.csv`, `phase3_c2_raw.csv`, `phase3_c4_raw.csv` (and every
variant), all three `decision_rule_h*.csv`, `docs/paper_draft.md`,
`methodology-notes.md`'s C4 pilot section.
