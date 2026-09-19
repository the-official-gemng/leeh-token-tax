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
