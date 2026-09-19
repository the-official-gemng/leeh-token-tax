# LEEH: Language Efficiency Equalizer Harness — measuring and attempting to close the multilingual token tax

_Draft scaffold. Sections marked "OUTLINE" are bullet points for Lucas + teammate to write in their own voice — not filled in with generated prose. Sections marked "DRAFTED" pull directly from `pre_registration.md` and `docs/methodology-notes.md` and are close to submission-ready, pending final editing pass._

---

## Abstract — OUTLINE

- Quantify a real multilingual token tax: `deepseek-flash` pays a significant ~1.30–1.36x cost premium on Spanish/Chinese vs. English (paired, Holm-corrected significant); `gpt-5.6-luna` is close to parity (1.03–1.08x, mostly not significant).
- Built LEEH, a runtime harness (Detector → Router → Packer → Executor → Equalizer → Expander) intended to close that gap while preserving accuracy.
- Pre-registered decision rules, ran the confirmatory test: **the harness's first attempt does not clear the bar.** H1 (cost), H2 (non-inferiority), H3 (beats naive translation) all not supported.
- Diagnosed *why*: root-caused the cost shortfall to a verbose system prompt (quantified, fixed, re-tested) plus a second, larger, unexplained cost anomaly that the fix does not address.
- Honest framing for the abstract itself: this is a negative/mixed result paper, not a "harness works" paper — lead with the measured tax, show the natural first-attempt mitigation fails, explain what was diagnosed and fixed vs. what remains open. That framing is the contribution as much as the numbers are.

## Introduction — OUTLINE

- Motivate: multilingual users of LLM agents pay more per equivalent task in tokens/cost/latency than English users, purely as a function of tokenizer/language mismatch — a fairness and access issue, not just an efficiency one.
- Position LEEH: a from-scratch runtime harness (not a fine-tune, not a new model) that tries to close this gap with off-the-shelf routing/translation/budget-equalization, on the theory that this should be a tractable engineering problem if the tax is mostly tokenizer/prompting overhead rather than something fundamental to cross-lingual reasoning.
- State the pre-registration discipline used throughout (hypotheses, decision rules, and statistical plan frozen before Phase 3 data collection; amendments logged, not silently made) — relevant to how the paper reports the outcome.
- Roadmap sentence for the rest of the paper.
- (Lucas/teammate: this is where your own motivation — why this project, why these two models/four languages — belongs. Not reconstructed here.)

## Related Work — DRAFTED

**Measuring the multilingual token/cost tax:**
- Ahia, O., Kumar, S., Gonen, H., Kasai, J., Mortensen, D.R., Smith, N.A., Tsvetkov, Y. "Do All Languages Cost the Same? Tokenization in the Era of Commercial Language Models." EMNLP 2023. arXiv:2305.13707. The direct precedent for this study's core framing — establishes the tokenizer-driven cost disparity across languages that this project re-measures on two specific cheap-tier models and then tries to mitigate.

**Decomposing the tax into fixable vs. inherent components:**
- Mandarapu, M., Kunkunuru, S. "Removable and Irreducible: A Token-Cost Ledger for the Multilingual Tokenization Tax." arXiv:2609.00378, September 2026. **Unreviewed preprint** — not peer-reviewed, and the authors have no other visible publication track record on this topic. Cited as a relevant framing, not on equal footing with the peer-reviewed sources in this section. Its removable/irreducible decomposition maps closely onto this project's own split between the fixed, removable system-prompt-overhead cost component and the unexplained, so-far-irreducible-in-practice cost anomaly (see Results/Limitations) — engaged with directly in Discussion, not just listed here.

**Mitigation / efficiency systems for cross-lingual LLM use:**
- Ahuja, S., Vaddamanu, P., Patra, B. "EfficientXLang: Towards Improving Token Efficiency Through Cross-Lingual Reasoning." Findings of ACL: EMNLP 2025. arXiv:2507.00246. Reports a counterpoint finding directly relevant to this paper's own results: reasoning in some non-English languages can use *fewer* tokens than English while matching accuracy. That supports this project's own framing — the tax measured here is real for `deepseek-flash` and near-null for `gpt-5.6-luna` on the identical task set, i.e. a language×model interaction, not a fixed property of "being non-English" — worth citing as independent corroboration of that framing, not just as an adjacent system.

**Cross-lingual chain-of-thought / reason-in-one-language strategies:**
- Zhang, C. et al. "Less Languages, Less Tokens: An Efficient Unified Logic Cross-lingual Chain-of-Thought Reasoning Framework." ACL 2026. arXiv:2604.20090. Cited by this title, not by "UL-XCoT" — that's the method's acronym within the paper, not the paper's title. Directly relevant prior art for `harness/packer.py`'s prompt-based mode (C2): "reason in one language internally, answer in the target language" is the same basic move this project's harness makes, evaluated there as a token-efficiency method in its own right rather than as a harness component.

---

## Methods — DRAFTED

### Pre-registration

This study's hypotheses, statistical plan, and decision rules were frozen in `pre_registration.md` before any Phase 3 (harness) data was collected or looked at, per the following excerpt:

> Written and frozen **before** any Phase 1 data is collected or looked at. Do not edit the Hypotheses, Metrics, or Decision Rules sections after freezing — log any change in the Amendments Log at the bottom instead, with a date and reason.

**Intended vs. actual process control.** The design called for this to be enforced mechanically — CODEOWNERS plus GitHub branch protection requiring a pull request reviewed by both teammates before any change to `pre_registration.md`, with the change recorded in its Amendments Log, not left to convention. In practice, branch protection was never actually active: the repository is on GitHub's free tier, which does not support the branch-protection configuration this required. All three Amendments Log entries below did go in as pull requests, as designed, but **none were merged with a completed review from either CODEOWNER** — stated plainly here rather than implied otherwise, since the original design language ("enforced... not just convention") does not describe what actually happened.

### Models

| Slot | Model | Notes |
|---|---|---|
| Western, cheap tier | `gpt-5.6-luna` | Cheapest tier of the GPT-5.6 family. Token counting: tiktoken. |
| Chinese-origin, cheap tier | `deepseek-flash` | Pairs symmetrically with Luna as the "cheap tier" slot. Token counting: `deepseek-ai/DeepSeek-V4-Flash` tokenizer. |

### Languages

English (reference), Chinese, Arabic, Spanish — as pre-registered. Two of the three Amendments Log entries below affect language coverage; the third (GAIA-v2-LILT) is a dataset-execution gap, not a language change.

### Datasets

- **Single-turn:** MGSM, ~50 problems/language, N=1 repeat.
- **Agentic:** MAPS (GAIA + MATH subsets), ~8–10 tasks/language/subset (~16–20/language total), N=2 repeats.
- **Trusted cross-check (pre-registered, not executed):** GAIA-v2-LILT, Arabic slice, was named in the frozen design as a trusted cross-check dataset. Its data was downloaded (`scripts/download_data.py` pulls it as a third MAPS config alongside Math/GAIA), but it was never included in `run_phase1.py`'s actual measurement loop (`MAPS_SUBSETS = ["Math", "GAIA"]` only) and carries no results in this study. Logged as the third Amendments Log entry below (found late, while writing this section — not a new decision).

**Amendments (`pre_registration.md` §5 — all three merged as pull requests, none with a completed CODEOWNER review; see the process note above):**

| Date | Change | Reason |
|---|---|---|
| 2026-09-14 | Dropped Arabic from MGSM (runs en/es/zh only) | `juletxara/mgsm` has no `ar` config (confirmed empirically — available: bn/de/en/es/fr/ja/ru/sw/te/th/zh). Arabic coverage for the study still comes from MAPS/GAIA (Arabic split). |
| 2026-09-14 | Dropped Chinese from MAPS (runs en/es/ar only, Math + GAIA configs) | `Fujitsu-FRE/MAPS` has no Chinese split in any config (confirmed empirically). Chinese coverage for the study still comes from MGSM. |
| 2026-09-16 | GAIA-v2-LILT never measured (data downloaded, never included in the measurement loop) | Pre-existing gap between the frozen design and what was actually run; found and logged while writing this Methods section, not a new decision. |

### Metrics

Total tokens, fertility ratio (tokens[language] ÷ tokens[English]), dollar cost, wall-clock latency, exact-match accuracy, tool-call count, truncation-failure rate.

### The LEEH harness

LEEH wires six modules into a runtime pipeline:

- **Detector** — language and task-type detection (via `langdetect`), normalizing script variants (e.g. zh-cn/zh-tw → zh).
- **Router** — decides whether a request should be routed through an English-mediated path; in this implementation, every non-English input routes through English regardless of detected task type.
- **Packer** — prepares the outgoing request in one of two modes: *prompt-based* (a system-prompt instruction to reason internally in English but answer in the original language, no extra model call) or *MT-based* (a real translation call to English first).
- **Executor** — a generic tool-call agent loop (functional but no concrete tools were registered for this study, so agentic tasks run single-shot in practice) wrapping each model call in a hard wall-clock timeout.
- **Equalizer** — cross-cutting: scales `max_tokens` up per language by that language's measured fertility ratio from Phase 1 (e.g. a language needing 1.3x as many tokens to express the same content gets 1.3x English's token budget), so high-fertility languages aren't unfairly truncated relative to English.
- **Expander** — translates the executor's output back to the original language when needed (a no-op when the model already answered in the target language directly, which is the common case under prompt-based mode).

**Four conditions**, evaluated against the same pre-registered task set:

- **C0 — no intervention.** Raw model call, no harness. This is Phase 1's own baseline measurement, reused directly (not re-run) as the Phase 3 comparison point.
- **C1 — naive translate-to-English.** Packer (MT-mode, a real translation call) → Executor (no Equalizer) → Expander (a real translation call back). Language is a known/labeled input parameter here, not auto-detected — C1 has no Detector step by design, since it represents the "obvious naive baseline" a team might reach for without building a full harness.
- **C2 — full LEEH.** Detector → Router → (English: passthrough; non-English: Packer prompt-mode) → Executor+Equalizer → Expander (usually a no-op, per above). This is the harness's actual proposal, and the primary object of evaluation. **Six pipeline stages, not six API calls:** Detector, Router, and Packer's prompt-based mode are pure local logic — zero model calls. C2 makes **at most two** model calls per task: one mandatory (Executor+Equalizer, with the translate-in instruction embedded directly in its prompt, not a separate call) and one conditional (Expander, firing only when the model's answer isn't already in the target language). Stated explicitly here because the six-stage pipeline diagram invites the opposite reading.
- **C3a — ablation.** Identical to C2 with the Equalizer disabled throughout (`disable_equalizer=True`), isolating the Equalizer's specific contribution (tests H4). **Not run in this study** — marked a stretch goal in the original design ("only if time allows") and time did not allow; H4 is accordingly not evaluated below.

Every condition accumulates tokens/cost/latency across *every* model call it makes (e.g. C1 makes up to 3 calls: translate-in, execute, translate-out) — so a condition's reported total cost reflects its full real cost, not just the final answering call, which matters directly for the cost-ratio comparisons in Results.

### Statistical plan (Phase 1 baseline characterization)

- Primary test: paired Wilcoxon signed-rank, English vs. language X, per model, on matched task instances.
- Multiple-comparison correction: Holm–Bonferroni across 2 models × 3 non-English languages = 6 pairwise tests.
- Effect sizes: bootstrap 95% CI (BCa, ≥10,000 resamples) reported alongside every ratio.
- Significance level: α = 0.05 (corrected).

### Decision rules (Phase 3 confirmatory test, frozen in advance)

- **H1** supported if the cost ratio's 95% CI upper bound is ≤1.2x for at least 2 of the 3 non-English languages (statistic: bootstrap CI of the *median* per-task cost ratio).
- **H2** (non-inferiority) supported if the accuracy difference (C2 − C0) CI lower bound is > −2.0 points.
- **H3** supported if C2's accuracy exceeds C1's, Wilcoxon-significant at α=0.05 after Holm correction.
- **H4** (stretch) — not evaluated; C3a was not run (see above).

---

## Results — DRAFTED

### Phase 1: baseline measurement (no harness)

**Cost ratio (non-English / English), paired by task_id, Holm-Bonferroni corrected across 6 tests:**

| model | language | median ratio | 95% BCa CI | Holm-significant |
|---|---|---|---|---|
| deepseek-flash | es | 1.36x | [1.27, 1.45] | **yes** (p=2.5e-7) |
| deepseek-flash | zh | 1.30x | [1.21, 1.38] | **yes** (p=6.3e-5) |
| deepseek-flash | ar | 1.07x | [0.95, 1.39] | no |
| gpt-5.6-luna | zh | 1.08x | [1.03, 1.17] | **yes** (p=0.007) |
| gpt-5.6-luna | es | 1.06x | [1.01, 1.08] | no |
| gpt-5.6-luna | ar | 1.03x | [0.88, 1.14] | no |

`deepseek-flash` shows a real, statistically significant baseline token tax on Spanish and Chinese (1.30–1.36x). `gpt-5.6-luna` is close to parity across all three non-English languages, reaching significance only on Chinese and only at a small effect size (1.08x). This split — real for one model, near-null for the other, on the *same* task set and languages — is itself a finding: the tax is not a fixed property of "being non-English," it's model/tokenizer-specific.

**Accuracy, by dataset (successful attempts only):**

| model | dataset | language | accuracy |
|---|---|---|---|
| gpt-5.6-luna | MGSM | en / es / zh | 90 / 96 / 92% |
| deepseek-flash | MGSM | en / es / zh | 96 / 90 / 94% |
| gpt-5.6-luna | MAPS/GAIA | en / es / ar | 20 / 30 / 20% |
| deepseek-flash | MAPS/GAIA | en / es / ar | 31.6 / 31.6 / 35% |
| gpt-5.6-luna | MAPS/Math | en / es / ar | 70 / 50 / 60% |
| deepseek-flash | MAPS/Math | en / es / ar | 80 / 70 / 80% |

MGSM and MAPS/GAIA use clean short-answer ground truth and are reliable as measured. **MAPS/Math required a scoring fix** (see Limitations) — the numbers above are post-fix and final. Paired English-vs-non-English Wilcoxon tests on accuracy (`results/phase1_accuracy_diffs.csv`) did not reach significance for any language/model after Holm-Bonferroni correction, on the corrected data.

**Caveat carried into every `deepseek-flash`/MAPS/GAIA number above:** completion rates for this model/dataset are low (es 11%, en 15%, ar 21%, vs. `gpt-5.6-luna`'s healthy 65–74% on the same dataset) — see Limitations for the survivorship-bias risk this creates.

### Phase 3: confirmatory decision-rule test (primary evaluation finding)

This is the pre-registered, primary evaluation result. Stated plainly, no hedging: **H1, H2, and H3 are all not supported.**

**H1 — cost ratio (C2 / C0), CI upper bound ≤1.2x for ≥2/3 non-English languages:**

| model | language | median ratio | 95% CI | ≤1.2x? |
|---|---|---|---|---|
| gpt-5.6-luna | es | 1.173x | [1.119, 1.223] | No |
| gpt-5.6-luna | zh | 1.472x | [1.312, 1.711] | No |
| gpt-5.6-luna | ar | 0.999x | [0.837, 1.204] | No |
| deepseek-flash | es | 1.530x | [1.289, 1.619] | No |
| deepseek-flash | zh | 1.867x | [1.546, 2.087] | No |
| deepseek-flash | ar | 1.054x | [0.864, 1.335] | No |

0/3 languages clear the bar for either model. **H1 not supported.** Under the full harness, cost went *up* relative to English on 5 of 6 cells, not down — the opposite of the design goal. (gpt-5.6-luna/ar's CI upper bound of 1.204 is a near-miss, the closest any cell comes.)

**H2 — accuracy non-inferiority (C2 − C0), CI lower bound > −2.0 points:**

| model | language | mean diff (pts) | 95% CI | supported? |
|---|---|---|---|---|
| gpt-5.6-luna | en | −1.4 | [−6.4, 0.7] | No |
| gpt-5.6-luna | es | −0.7 | [−5.7, 2.9] | No |
| gpt-5.6-luna | zh | 0.0 | [−6.0, 6.0] | No |
| gpt-5.6-luna | ar | 0.0 | [−12.5, 12.5] | No |
| deepseek-flash | en | −3.6 | [−9.3, 0.0] | No |
| deepseek-flash | es | −0.7 | [−7.1, 5.7] | No |
| deepseek-flash | zh | −4.0 | [−13.8, 0.0] | No |
| deepseek-flash | ar | **−17.5** | [−37.5, −7.5] | No |

**H2 not supported for any cell, including English** — every CI lower bound sits below the −2.0 non-inferiority margin, driven mostly by CI width at these sample sizes (n=20–70) rather than large point-estimate drops, with one clear exception: `deepseek-flash`/ar shows a real, substantial accuracy drop under C2 (−17.5 points, CI entirely below −2.0) that is not a width artifact.

**H3 — C2 accuracy exceeds C1's, Wilcoxon significant after Holm correction:**

| model | language | C1 acc. | C2 acc. | C2 > C1? | p (Holm) | significant? |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | en | 78.6% | 75.7% | No | 1.0 | No |
| gpt-5.6-luna | es | 75.7% | 79.3% | Yes | 1.0 | No |
| gpt-5.6-luna | zh | 84.0% | 92.0% | Yes | 0.319 | No |
| gpt-5.6-luna | ar | 47.5% | 40.0% | No | 1.0 | No |
| deepseek-flash | en | 82.1% | 81.4% | No | 1.0 | No |
| deepseek-flash | es | 80.0% | 77.9% | No | 1.0 | No |
| deepseek-flash | zh | 90.0% | 90.0% | No | 1.0 | No |
| deepseek-flash | ar | 60.5% | 42.1% | No | 0.307 | No |

**H3 not supported for any cell.** C2 numerically beats C1 in 2/8 cells (both gpt-5.6-luna, es and zh), neither significant after correction.

**Net result: the full LEEH harness, as first built and confirmatorily tested, does not clear any of its three primary pre-registered bars.** See Limitations for the post-hoc diagnostic work this motivated and what it did and didn't resolve.

---

## Limitations — DRAFTED

A full accounting of what was found and fixed during this study, not a general disclaimer. Ordered roughly by when each was found.

**GAIA timeout ceiling too tight, initially undercounting successes.** `HARD_TIMEOUT_S` was set to 30s (while tuning around an unrelated DeepSeek outage) and was too tight for MAPS/GAIA specifically, which needs longer generations even from an unaffected model — GAIA success rate was 41.7% (n=120) at that ceiling vs. 82.4% (n=499) for everything else, including on `gpt-5.6-luna`, which had zero outage-related failures anywhere else. Fixed by raising the ceiling to 120s uniformly across all datasets.

**MAPS/Math accuracy scoring bug.** `expected_answer` for Math was the full worked `solution` text, and correctness was a verbatim substring match against it — which essentially never matches even correct model answers, since models paraphrase their derivation. This produced a flat 0.0% accuracy for MAPS/Math across every model and language in the initial data, a measurement artifact rather than a real result. Fixed by extracting the final answer from the reference solution's `\boxed{...}` (Hendrycks MATH convention; a balanced-brace parser, not a naive regex, since answers can contain nested braces like `\boxed{\frac{121}{25}}`) and matching that short value against the already-saved model answer, with no API calls re-run. The same bug, and the same fix, had to be separately applied to `phase3_c1_raw.csv` and `phase3_c2_raw.csv` — they had been generated with the same broken scoring and were not automatically caught by fixing Phase 1's data alone; this was caught before trusting the H1/H2/H3 report, not after.

**`deepseek-flash`/MAPS/GAIA survivorship-bias risk, all three languages.** An earlier informal characterization of this risk was Arabic-specific; that was wrong. Completion rates are low across the board (es 11%, en 15%, ar 21% — es and en are actually *worse* than ar) and low enough that the ~19–20 tasks surviving into the paired sample per language may be a biased (easier/shorter) subset of the full attempted set, which would make this model's measured GAIA cost ratio, fertility ratio, and accuracy all look better than its true performance on the full task distribution. `gpt-5.6-luna`'s GAIA completion rate (65–74%) does not carry this caveat — it is model-specific, not a property of GAIA or of any language. Not fixed; carried as a caveat on every `deepseek-flash`/MAPS/GAIA number in this paper.

**A suspected `tools`/`reasoning_effort` confound was investigated and ruled out, not found.** A working hypothesis at one point held that `gpt-5.6-luna`'s C0 and C2 calls might not be directly comparable because passing function `tools` forces `reasoning_effort="none"` for this model (a real, separate finding — see `harness/executor.py`), and C2 might exercise that code path while C0 never did. Checked directly against the code rather than assumed: neither C0 nor C2 ever passes `tools` to the executor in this study (confirmed via direct inspection of `harness/conditions.py`), so this confound does not apply to any comparison in this paper. Recorded here specifically so it isn't silently re-assumed as fact in a later draft.

**Equalizer `BASE_MAX_TOKENS` drastically undersized for MAPS.** `BASE_MAX_TOKENS = 2048` was an unvalidated guess made when building the Equalizer module, never checked against real data. Phase 1's own uncapped C0 data shows MAPS completion_tokens averaging 4702 with a max of 28778 — even after the fertility multiplier, the resulting C2 budgets (2048–2735 tokens) were a small fraction of that. The first full C2 run truncated 41.7% of MAPS answers mid-generation (vs. 0% in C0), which corrupted the first H1/H2/H3 pass: both the apparent accuracy collapse and the apparent cost *increase* under C2 in that first pass were substantially truncation artifacts, not a real reflection of the harness's design. Fixed by calibrating `max_tokens` per dataset from C0's own observed distribution (MGSM: 8192, MAPS: 32768) rather than guessing again, and re-running C2 to completion (540/540 successes, 0.56% truncation). **The H1/H2/H3 numbers reported in Results above are from this corrected, re-run data** — not the truncation-corrupted first pass.

**A mean-vs-median statistic error affected an informal chat report, not the confirmatory result.** During post-hoc diagnostic work, a chat-reported "v1 vs v2 cost ratio" table used ratio-of-mean-costs rather than H1's actual pre-registered statistic (bootstrap CI of the *median* per-task ratio). All four cells in that informal table were affected; the worst case, `deepseek-flash`/es, was reported as "already passing" at 0.999x and was actually 1.530x with a CI entirely above 1.2 — a clear fail. The confirmatory H1 table in Results above was never affected by this (it was always computed with the correct statistic via `scripts/analyze_decision_rules.py`); the error was confined to an intermediate chat-only summary during the lean-prompt diagnostic work described next, and is recorded here so it is never reused in a future draft.

**Post-hoc exploratory follow-up: a "lean system prompt" fix, verified real but verified insufficient.** After the confirmatory H1/H2/H3 result (Results, above), diagnostic work traced part of C2's cost inflation on MGSM to `harness/packer.py`'s prompt-based-mode system prompt: a 76-token fixed template added to every non-English call, disproportionately large against MGSM's short (66–105 token) baseline prompts. This was trimmed to 18 tokens (verified via tiktoken, and manually spot-checked for continued correctness — right language, right answer, no language mixing, formatting intact — on 4 real questions across both models before the full re-run). The fix is real: the *median* prompt-token overhead dropped in exact proportion to the template shrink for both models, and accuracy held steady across every re-tested cell. **It is explicitly labeled exploratory and post-hoc, scoped to MGSM only (en/es/zh), saved to a separate file (`results/phase3_c2_raw_v2_leanprompt.csv`) never merged into the confirmatory `phase3_c2_raw.csv` — it does not revise the H1/H2/H3 result in Results above.** Re-evaluated under H1's actual statistic (median-ratio + bootstrap CI): `gpt-5.6-luna` reaches 1/3 languages clearing ≤1.2x (es only, now 1.017x); `deepseek-flash` reaches 0/3. **H1 remains not supported for either model even with the fix applied.**

**The system-prompt fix does not explain the majority of the cost gap; the larger driver is an unresolved, non-reproducible anomaly.** Diagnostic work found the prompt-token overhead was bimodal, not uniform: a majority of rows (~65–70%) showed a constant delta matching the system-prompt template almost exactly, but a substantial minority (~30–36%) showed a much larger delta (+205 to +398 tokens) correlated with real jumps in completion tokens and latency, not explained by the template. This anomalous group was investigated directly — 32 fresh repeat API calls against known-anomalous inputs never reproduced it, and `tool_calls` was never present in any response (ruling out a hidden multi-turn loop in `harness/executor.py`, the only code path that could otherwise double-count prompt tokens). It is most likely transient provider-side variance in prompt-token billing, not a bug in this codebase, but it was not resolved.

A follow-up hypothesis — that this anomalous group's *severity* varied between runs and explained why `deepseek-flash` looked worse after the prompt fix while `gpt-5.6-luna` looked better — was tested directly and is **false, retracted here explicitly**: the anomalous subset's mean and median token delta actually *decreased* from the pre-fix to post-fix draw for *both* models (`gpt-5.6-luna`: 256.2/248.5 → 181.0/186.0; `deepseek-flash`: 256.1/265.0 → 212.7/195.0), so it cannot be what drove `deepseek-flash`'s regression. **The real cause of `deepseek-flash`'s es/zh cost regression after the prompt fix is unidentified.** One untested, pointed-to lead for future work: whether the *non-anomalous majority* group's completion tokens or cost shifted between the two draws for `deepseek-flash` specifically — not investigated in this study.

**`analyze_decision_rules.py`'s task-pairing helper had a latent NaN-matching bug, now fixed.** The helper used to pair C0/C1/C2 rows by `(dataset, subset, task_id)`, including for MGSM, which has no `subset` value (stored as a missing/NaN cell). Two separate calls to the helper could return non-identical NaN float objects for that column, and since NaN ≠ NaN unless it is the literal same object, `(dataset, NaN, task_id)` keys from two different calls could fail to match — as tuples — while printing as identical, silently returning zero paired tasks. This happened not to bite the original confirmatory H1 computation (by chance, not design), which is exactly why it went unnoticed until a later MGSM-only re-analysis hit it directly. Fixed by grouping on a fixed string sentinel instead of the raw missing value, with an automatic self-test added to catch a future regression loudly instead of silently returning what looks like "not enough data."

**Two additional models were baseline-tested only, never run through the harness.** `qwen3.5-flash` and `gemini-3.5-flash-lite` (substituted for the originally-named `gemini-2.5-flash-lite`, which returned `404 Not Found` — retired) were added in an exploratory, underpowered spot-check (N=30/language/model, MGSM only, no repeats — vs. this study's own N=50 MGSM design) to test whether the `deepseek-flash`-shows-a-tax / `gpt-5.6-luna`-near-null split reflects something about tokenizer family or is idiosyncratic to those two models. Both were evaluated for baseline (C0-equivalent) token tax only — **neither was ever run through the LEEH harness (C1/C2/C3a)**, so no harness-mitigation claim in this paper extends to them.

## Discussion — OUTLINE

- The core empirical finding (`deepseek-flash` real tax, `gpt-5.6-luna` near-null, same task set) suggests the tax is not inherent to "being non-English" — frame against Ahuja et al.'s EfficientXLang counterpoint (Related Work) that some non-English reasoning can be *more* token-efficient than English, not just less.
- **Engage directly with Mandarapu & Kunkunuru's removable/irreducible framing (Related Work — noting again it's an unreviewed preprint, cited as framing rather than as established evidence).** This project's own results split the same way, empirically rather than by construction: the system-prompt-overhead component of C2's cost gap was cleanly removable (fixed, verified via the exact-proportion median-delta match in Results/Limitations) while the larger anomalous cost component resisted every attempt to explain or reproduce it and, so far, looks irreducible with the visibility this study had. Worth stating explicitly whether this project's data is read as a case study supporting that paper's decomposition, or as a caution that "irreducible" may sometimes just mean "not yet diagnosed" rather than structurally inherent — that's an interpretive call for Lucas/teammate, not something to resolve here.
- Why might a natural first-attempt mitigation (reason in English, answer in target language, equalize token budgets) fail to reduce cost even though it's the "obvious" fix? Worth discussing the system-prompt-overhead finding as a general lesson (fixed-cost instructions dominate on short-prompt tasks) separately from the larger unexplained anomaly (a real limitation of what this study could establish with API-level visibility alone).
- Whether/how the `deepseek-flash`/ar accuracy drop under C2 (−17.5 points, real) changes how the harness should be scoped or gated per-language rather than applied uniformly.
- What "success" would have looked like, and how close/far this result is from it in practical terms (e.g. is 1.2–1.5x cost with intact accuracy still a deployable improvement over doing nothing, even though it misses the pre-registered bar?).
- (Lucas/teammate: your interpretive judgment belongs here — not reconstructed from the numbers alone.)

## Conclusion — OUTLINE

- Restate the two-part finding: real, model-specific multilingual token tax confirmed; first-attempt harness mitigation confirmatorily fails its own pre-registered bar.
- What's actually resolved vs. still open (system-prompt overhead: resolved; the larger cost anomaly: open; `deepseek-flash`/ar accuracy drop: open; generalization beyond two models: untested for the harness specifically).
- Concrete next steps if this work continues (e.g., chasing the unresolved cost anomaly with provider-level visibility this study didn't have; running C3a/H4; running the harness — not just baseline — on the two additional models).
- One line on what a reader should take away even from the negative result (e.g. the value of a pre-registered decision rule catching a plausible-looking harness at the confirmatory stage rather than after publication).
- (Lucas/teammate: closing framing and any forward-looking commitments are yours to set.)
