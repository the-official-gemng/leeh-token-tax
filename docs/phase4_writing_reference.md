# Phase 4 writing reference

A consolidated lookup doc for drafting Abstract/Introduction/Discussion/Conclusion — not new analysis, not paper prose. Everything below is pulled verbatim from source files, each named at point of use. If this doc and a source file ever disagree, the source file is correct and this doc is stale — fix this doc, don't trust it over the source.

---

## Section A — Framing decisions already settled

Hold these while writing. Don't re-litigate them; they were decided in prior passes, not up for reconsideration during drafting.

1. **Scope is a case study**, not a universality claim. The demonstrated tax is `deepseek-flash`×{es, zh} specifically (Holm-significant, 1.30–1.36x — Section B1). Everything else (gpt-5.6-luna's smaller zh effect, the generalization spot-check, MAPS/GAIA) is context and robustness-checking around that one case, not additional primary claims of the same weight.

2. **H1/H2/H3 are genuinely not supported.** Report this plainly — no softening, no burying in a subclause. Every table in Section B3 backs this; there is no hedge available in the actual numbers.

3. **The generalization spot-check's finding is "language×model interaction, not lab-of-origin."** Say that, not "Chinese vs. Western models." Evidence: `qwen3.5-flash` (Chinese-origin, like `deepseek-flash`) tracks *gpt-5.6-luna's* near-null pattern, not `deepseek-flash`'s tax (es ratio 0.823x — actually *below* 1.0; Section B6) — lab-of-origin does not predict which pattern a model follows.

4. **The constructive forward-looking point is a Router low-tax-skip design** — i.e., the Router should be able to skip harness intervention entirely for a (model, language) pair with a known near-null baseline tax, rather than applying the same routing/packing overhead uniformly to every non-English input regardless of whether that specific model needs it. Motivated directly by the near-null baseline results: `gpt-5.6-luna` (1.03–1.08x across all three non-English languages, Section B1) and `qwen3.5-flash` (0.823–1.382x, mixed but often near or below parity, Section B6). **This idea does not yet exist in `paper_draft.md`** — it was not in any prior draft pass; this is the first place it's recorded. Add it to the Discussion outline when drafting.

5. **Methods must state branch protection was never actually active**, and that all three Amendments Log PRs merged without a completed CODEOWNER review. Don't imply mechanical enforcement that didn't happen. `paper_draft.md`'s Methods section already says this correctly (§"Intended vs. actual process control") — carry the same framing into Abstract/Intro/Discussion if pre-registration integrity comes up there; don't revert to the earlier "enforced... not just convention" framing from `pre_registration.md` itself, which describes the *intent*, not what actually happened.

6. **One open interpretive question is explicitly left for the authors**: is the unexplained C2 cost anomaly (Section B5) "irreducible" (as the Mandarapu & Kunkunuru preprint's framing would suggest) or just "not yet diagnosed" (i.e., a limitation of this study's visibility, not a property of the underlying system)? No prior draft answers this — `paper_draft.md`'s Discussion outline poses it as a question and explicitly assigns it to Lucas/teammate. **Flag it as unanswered here too. Do not invent an answer while drafting.**

7. **Target venue is still undecided.** This blocks two concrete things: final citation format (the citations in Section C are complete in content but not formatted to any specific venue's style), and how much of the exploratory material (generalization spot-check, lean-prompt v2, the H1 recheck/retraction) belongs in the main paper body vs. an appendix/supplementary section. **This is an open blocking decision — don't guess a venue or a placement to resolve it while drafting.**

---

## Section B — Tables, verbatim from source

### B1. Phase 1 cost-ratio table (all 6 cells)
Source: `results/phase1_cost_ratios.csv`

| model | language | n_pairs | median_ratio | ci_low | ci_high | wilcoxon_p | p_holm | significant_holm |
|---|---|---|---|---|---|---|---|---|
| gpt-5.6-luna | es | 70 | 1.0602602795436544 | 1.0115705623588158 | 1.0837141888374715 | 0.05381751987257034 | 0.16145255961771102 | False |
| gpt-5.6-luna | zh | 50 | 1.075938104165983 | 1.0334302325588904 | 1.1677704194260485 | 0.0018503612977608574 | 0.00740144519104343 | **True** |
| gpt-5.6-luna | ar | 20 | 1.032207697435978 | 0.8809351223065424 | 1.141400490579577 | 0.5958194732666016 | 1.0 | False |
| deepseek-flash | es | 70 | 1.359729172799529 | 1.2650539808658348 | 1.4532154105324837 | 4.101309875485371e-08 | 2.4607859252912223e-07 | **True** |
| deepseek-flash | zh | 50 | 1.3013726556129384 | 1.2095731422339928 | 1.3778061096945153 | 1.2531257944866529e-05 | 6.265628972433265e-05 | **True** |
| deepseek-flash | ar | 20 | 1.0684670779321643 | 0.9548272321321967 | 1.390191300268446 | 0.5958194732666016 | 1.0 | False |

`coverage` column (per-row dataset/subset success-rate breakdown, omitted above for width) is in the source file — pull it in directly if a table footnote needs it, don't retype it from memory.

### B2. Phase 1 accuracy tables
Sources: `results/phase1_raw.csv` (raw per-cell accuracy, recomputed fresh from the merged/corrected file) and `results/phase1_accuracy_diffs.csv` (paired diff + significance).

**MGSM (clean baseline, no scoring-fix needed), from `phase1_raw.csv`:**

| model | language | n | accuracy |
|---|---|---|---|
| deepseek-flash | en | 50 | 96.0% |
| deepseek-flash | es | 50 | 90.0% |
| deepseek-flash | zh | 50 | 94.0% |
| gpt-5.6-luna | en | 50 | 90.0% |
| gpt-5.6-luna | es | 50 | 96.0% |
| gpt-5.6-luna | zh | 50 | 92.0% |

**MAPS/Math (corrected, post boxed-answer-extraction fix), from `phase1_raw.csv`:**

| model | language | n | accuracy |
|---|---|---|---|
| deepseek-flash | ar | 20 | 80.0% |
| deepseek-flash | en | 20 | 80.0% |
| deepseek-flash | es | 20 | 70.0% |
| gpt-5.6-luna | ar | 20 | 60.0% |
| gpt-5.6-luna | en | 20 | 70.0% |
| gpt-5.6-luna | es | 20 | 50.0% |

**MAPS/GAIA (clean baseline, no scoring-fix needed — carries the survivorship-bias caveat, see `methodology-notes.md`'s 2026-09-15 entry), from `phase1_raw.csv`:**

| model | language | n | accuracy |
|---|---|---|---|
| deepseek-flash | ar | 20 | 35.0% |
| deepseek-flash | en | 19 | 31.6% |
| deepseek-flash | es | 19 | 31.6% |
| gpt-5.6-luna | ar | 20 | 20.0% |
| gpt-5.6-luna | en | 20 | 20.0% |
| gpt-5.6-luna | es | 20 | 30.0% |

**Paired accuracy diffs (English vs. language, pooled across MGSM+MAPS, Wilcoxon + Holm), from `phase1_accuracy_diffs.csv`:**

| model | language | n_pairs | en_accuracy | lang_accuracy | diff_points | ci_low | ci_high | p_holm | significant_holm |
|---|---|---|---|---|---|---|---|---|---|
| gpt-5.6-luna | es | 70 | 77.14 | 80.0 | +2.86 | −4.29 | 10.71 | 1.0 | False |
| gpt-5.6-luna | zh | 50 | 90.0 | 92.0 | +2.0 | −4.0 | 10.0 | 1.0 | False |
| gpt-5.6-luna | ar | 20 | 45.0 | 40.0 | −5.0 | −15.0 | 2.5 | 1.0 | False |
| deepseek-flash | es | 70 | 85.0 | 78.57 | −6.43 | −14.29 | −0.71 | 0.5162423747074056 | False |
| deepseek-flash | zh | 50 | 96.0 | 94.0 | −2.0 | −10.0 | 4.0 | 1.0 | False |
| deepseek-flash | ar | 20 | 57.5 | 57.5 | 0.0 | −7.5 | 17.5 | 1.0 | False |

No cell reaches Holm significance in either direction.

### B3. Phase 3 confirmatory H1/H2/H3 tables

**H1** — source: `results/decision_rule_h1.csv` (cost ratio ≤1.2x CI upper bound, ≥2/3 non-English languages; no p-value column in this file — the statistic is a bootstrap CI, not a hypothesis test):

| model | language | n | median_ratio | ci_low | ci_high | meets_h1_target |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | es | 70 | 1.1728295721744786 | 1.1187002096430816 | 1.2228034892304627 | False |
| gpt-5.6-luna | zh | 50 | 1.4722123674263208 | 1.3118564777509176 | 1.7106353524186355 | False |
| gpt-5.6-luna | ar | 20 | 0.9985485870350859 | 0.8368211385754591 | 1.2035192426424453 | False |
| deepseek-flash | es | 70 | 1.5304732945531463 | 1.2887323943661972 | 1.6192500966370311 | False |
| deepseek-flash | zh | 50 | 1.8672426325832148 | 1.5458579881656804 | 2.0867579908675795 | False |
| deepseek-flash | ar | 20 | 1.053531325364765 | 0.864499633841209 | 1.3352737799522392 | False |

**H2** — source: `results/decision_rule_h2.csv` (non-inferiority, CI lower bound > −2.0; also no p-value column — mean diff + bootstrap CI):

| model | language | n | mean_diff | ci_low | ci_high | h2_supported |
|---|---|---|---|---|---|---|
| gpt-5.6-luna | en | 70 | −1.4285714285714286 | −6.428571428571429 | 0.7142857142857143 | False |
| gpt-5.6-luna | es | 70 | −0.7142857142857143 | −5.714285714285714 | 2.857142857142857 | False |
| gpt-5.6-luna | zh | 50 | 0.0 | −6.0 | 6.0 | False |
| gpt-5.6-luna | ar | 20 | 0.0 | −12.5 | 12.5 | False |
| deepseek-flash | en | 70 | −3.5714285714285716 | −9.285714285714286 | 0.0 | False |
| deepseek-flash | es | 70 | −0.7142857142857143 | −7.142857142857143 | 5.714285714285714 | False |
| deepseek-flash | zh | 50 | −4.0 | −13.836771192962637 | 0.0 | False |
| deepseek-flash | ar | 20 | −17.5 | −37.5 | −7.5 | False |

**H3** — source: `results/decision_rule_h3.csv` (C2 beats C1, Wilcoxon + Holm):

| model | language | n | c1_accuracy | c2_accuracy | c2_beats_c1 | wilcoxon_p | p_holm | significant_holm |
|---|---|---|---|---|---|---|---|---|
| gpt-5.6-luna | en | 70 | 78.57142857142857 | 75.71428571428571 | False | 0.3401742745401122 | 1.0 | False |
| gpt-5.6-luna | es | 70 | 75.71428571428571 | 79.28571428571428 | True | 0.22219460822417114 | 1.0 | False |
| gpt-5.6-luna | zh | 50 | 84.0 | 92.0 | True | 0.04550026389635839 | 0.3185018472745087 | False |
| gpt-5.6-luna | ar | 20 | 47.5 | 40.0 | False | 0.40762594770278093 | 1.0 | False |
| deepseek-flash | en | 70 | 82.14285714285714 | 81.42857142857143 | False | 0.7825279247400674 | 1.0 | False |
| deepseek-flash | es | 70 | 80.0 | 77.85714285714286 | False | 0.45296640275106703 | 1.0 | False |
| deepseek-flash | zh | 50 | 90.0 | 90.0 | False | 1.0 | 1.0 | False |
| deepseek-flash | ar | 19 | 60.526315789473685 | 42.10526315789473 | False | 0.03843393023678171 | 0.3074714418942537 | False |

Zero cells supported in any of the three tables.

### B4. Corrected-vs-wrong-statistic comparison table
Source: `docs/methodology-notes.md`, entry "2026-09-16 — H1 recheck under the real decision rule, a corrected statistic, and a retraction," point 3.

| model | lang | reported (wrong: ratio-of-means) | correct (median-ratio + CI) |
|---|---|---|---|
| gpt-5.6-luna | es, v1 | 1.140x | 1.173x, CI [1.119, 1.223] — fails |
| gpt-5.6-luna | es, v2 | 0.975x | 1.017x, CI [0.972, 1.111] — **passes** |
| gpt-5.6-luna | zh, v1 | 1.477x | 1.472x, CI [1.312, 1.711] — fails |
| gpt-5.6-luna | zh, v2 | 1.260x | 1.209x, CI [1.078, 1.794] — fails |
| deepseek-flash | es, v1 | 0.999x ("already passing") | 1.530x, CI [1.289, 1.619] — **fails clearly** |
| deepseek-flash | es, v2 | 1.071x | 1.304x, CI [1.200, 1.419] — fails clearly |
| deepseek-flash | zh, v1 | 1.230x | 1.867x, CI [1.546, 2.087] — fails clearly |
| deepseek-flash | zh, v2 | 1.350x | 1.677x, CI [1.390, 2.257] — fails clearly |

**Do not cite the "reported" column for anything** — it used the wrong statistic (ratio of mean costs, not H1's actual median-per-task-ratio + bootstrap CI). Kept here only so it's never silently reused.

### B5. Lean-prompt v1→v2 table and anomalous-subset severity table
Source: `docs/methodology-notes.md`, entries "2026-09-16 — Post-hoc exploratory follow-up: lean system prompt (v2), MGSM only" and the H1-recheck entry, point 5.

**v1 → v2 cost ratio (C2/C0):**

| model | lang | v1 ratio | v2 ratio | cleared 1.2x? |
|---|---|---|---|---|
| gpt-5.6-luna | es | 1.140x | 0.975x | yes (already close in v1, now clearly under) |
| gpt-5.6-luna | zh | 1.477x | 1.260x | no — improved but still above 1.2x |
| deepseek-flash | es | 0.999x | 1.071x | yes (was already under in v1) |
| deepseek-flash | zh | 1.230x | 1.350x | no — moved further from 1.2x |

(Note: this table uses the same ratio-of-means statistic flagged as wrong in B4 — kept here in its original v1/v2-comparison form since that's what it was; use B4's "correct" column for any actual pass/fail claim.)

**Anomalous-subset (delta > that run's own median + 40) prompt-token severity, v1 vs v2:**

| model | v1 mean / median (n) | v2 mean / median (n) |
|---|---|---|
| gpt-5.6-luna (es+zh pooled) | 256.2 / 248.5 (n=20) | 181.0 / 186.0 (n=25) |
| deepseek-flash (es+zh pooled) | 256.1 / 265.0 (n=17) | 212.7 / 195.0 (n=18) |

Severity went *down* v1→v2 for both models — the retracted explanation ("anomaly severity is roughly equal, deepseek's regression is pure noise") is disproven by this table, not supported by it. See Section A point 6 / Section D.

### B6. Generalization spot-check table (exploratory, N=30/language/model)
Source: `results/generalization_check_summary.csv`, verbatim, all 6 rows (includes the `en` denominator row per model; the "4 cells" of actual interest are the es/zh rows):

| model | language | N | accuracy_pct | median_cost_ratio | ci_low | ci_high |
|---|---|---|---|---|---|---|
| qwen3.5-flash | en | 30 | 96.67 | 1.0 | 1.0 | 1.0 |
| qwen3.5-flash | es | 30 | 96.67 | 0.8228701514753525 | 0.6538874310719562 | 1.0482444619560458 |
| qwen3.5-flash | zh | 30 | 96.67 | 1.3822782593468173 | 0.966640399264425 | 2.3934856842657384 |
| gemini-3.5-flash-lite | en | 30 | 96.67 | 1.0 | 1.0 | 1.0 |
| gemini-3.5-flash-lite | es | 30 | 90.0 | 1.2489430734440075 | 1.0264477435847017 | 1.4497099596892145 |
| gemini-3.5-flash-lite | zh | 30 | 93.33 | 1.1335168616655196 | 0.9016812506143939 | 1.2718513420509292 |

Underpowered by design (N=30, one dataset, no repeats, no multiple-comparison correction) — read directionally, not as a confirmatory result. This is the table behind Section A point 3 (`qwen3.5-flash`/es at 0.823x, below parity, tracking `gpt-5.6-luna`'s pattern rather than `deepseek-flash`'s despite shared Chinese origin).

---

## Section C — Citations, full detail + reliability tier

Source: `docs/paper_draft.md`, Related Work section (already verified in that pass — not re-searched here).

1. **Ahia, O., Kumar, S., Gonen, H., Kasai, J., Mortensen, D.R., Smith, N.A., Tsvetkov, Y.** "Do All Languages Cost the Same? Tokenization in the Era of Commercial Language Models." EMNLP 2023. arXiv:2305.13707.
   **Tier: peer-reviewed** (EMNLP main conference). Role: direct precedent for this study's core framing.

2. **Mandarapu, M., Kunkunuru, S.** "Removable and Irreducible: A Token-Cost Ledger for the Multilingual Tokenization Tax." arXiv:2609.00378, September 2026.
   **Tier: unreviewed preprint** — not peer-reviewed; authors have no other visible publication track record on this topic. Cited as framing, not as equal-footing evidence. Role: its removable/irreducible decomposition maps onto this project's own template-overhead-vs-anomaly split (Section A point 6). **See Section D — re-verify currency before submission.**

3. **Ahuja, S., Vaddamanu, P., Patra, B.** "EfficientXLang: Towards Improving Token Efficiency Through Cross-Lingual Reasoning." Findings of ACL: EMNLP 2025. arXiv:2507.00246.
   **Tier: peer-reviewed** (Findings of ACL). Role: counterpoint finding (some non-English reasoning is *more* token-efficient than English) that independently supports this project's language×model-interaction framing (Section A point 3).

4. **Zhang, C. et al.** "Less Languages, Less Tokens: An Efficient Unified Logic Cross-lingual Chain-of-Thought Reasoning Framework." ACL 2026. arXiv:2604.20090.
   **Tier: peer-reviewed** (ACL main conference). Role: direct prior art for the Packer's prompt-based mode (reason in one language internally, answer in the target language). Cite by this title — "UL-XCoT" is the method's internal acronym, not the paper's title.

---

## Section D — Pitfalls: what the paper must not overclaim

1. **Don't say** the pre-registered design (including GAIA-v2-LILT) was fully executed. **The actual state:** GAIA-v2-LILT was named in `pre_registration.md` §1 as the "trusted cross-check" dataset, its data was downloaded, but it was never included in `run_phase1.py`'s measurement loop (`MAPS_SUBSETS = ["Math", "GAIA"]` only) — zero results exist for it. Logged as Amendments Log entry 3, dated 2026-09-16, found late while drafting Methods.

2. **Don't say** the pre-registration process was mechanically enforced. **The actual state:** branch protection was never actually active (GitHub free-tier limitation), and all three Amendments Log PRs merged without a completed review from either CODEOWNER. `paper_draft.md`'s Methods section already states this correctly — don't revert to `pre_registration.md`'s own "enforced... not just convention" language when describing what happened, only when describing what was intended.

3. **Don't say** the harness was tested on, validated against, or shown to generalize to `qwen3.5-flash` or `gemini-3.5-flash-lite`. **The actual state:** both were baseline-tested only (C0-equivalent, N=30/language, MGSM-only, exploratory) — neither was ever run through `conditions.py` (no C1, C2, or C3a data exists for either). Any claim about the *harness* extending beyond `gpt-5.6-luna`/`deepseek-flash` is unsupported by this study.

4. **Don't treat** the Mandarapu & Kunkunuru "Removable and Irreducible" preprint as settled, citable-as-fact literature without a fresh check. **The actual state, as of this drafting pass:** unreviewed arXiv preprint, Sept 2026, authors with no other visible track record. Its status (published elsewhere? withdrawn? authors' track record changed?) can move between now and submission — **re-verify immediately before submission, not now.** Don't let this reference doc's citation tier (Section C) go stale by assuming it hasn't changed.

---

## Section E — File map

One line per file — where a fact lives, so an edit goes to the right place instead of spawning a sixth document.

- **`pre_registration.md`** — the frozen hypotheses (H1–H4), statistical plan, and decision rules, plus the Amendments Log (3 entries: MGSM/Arabic, MAPS/Chinese, GAIA-v2-LILT). CODEOWNERS-gated; any edit needs a PR, not a direct commit.
- **`docs/methodology-notes.md`** — the full dated implementation/debugging log: every bug found and fixed (GAIA timeout, MAPS/Math scoring, Equalizer token budget, `analyze_decision_rules.py`'s NaN-key bug), plus every exploratory follow-up (generalization spot-check, lean-prompt v2, the H1 recheck + retraction). Primary source for Sections B4, B5, and D of this doc.
- **`docs/findings_summary.md`** — *(not in your named list, added here since it's a real file that could otherwise confuse an editor)* a shorter, Phase-1-only summary (cost ratio + accuracy tables, threats to validity). Its numbers are current (reconciled in a prior pass) but it's now largely superseded by `paper_draft.md`'s own Results section — if you edit a Phase 1 number, check both files, or consider retiring this one.
- **`docs/paper_draft.md`** — the actual paper scaffold. Abstract/Introduction/Discussion/Conclusion are bullet outlines (Lucas/teammate's own voice, not generated prose). Related Work/Methods/Results/Limitations are drafted and close to final. **This is what Phase 4 writing edits — not this reference doc.**
- **`harness/README.md`** — code-facing documentation for anyone reading `harness/`: architecture, the four conditions, how to run it, required env var names (never values), and an explicit pointer to the confirmatory result so the code isn't read as if it achieved its design goal.
- **`results/phase1_raw.csv`** — every individual Phase 1 (C0) API call, all models/datasets/languages/repeats, with the GAIA-timeout and MAPS/Math-scoring fixes already applied in place.
- **`results/phase1_cost_ratios.csv`** — Phase 1's paired cost-ratio statistical table (Wilcoxon + Holm + bootstrap CI). Source of Section B1.
- **`results/phase1_accuracy_diffs.csv`** — Phase 1's paired accuracy-diff statistical table, same shape. Source of Section B2's paired table.
- **`results/phase1_fertility_ratios.csv`** — per-(model, language) token fertility multipliers; read at runtime by `harness/equalizer.py`.
- **`results/phase3_c1_raw.csv`** — every C1 (naive translate-to-English) call.
- **`results/phase3_c2_raw.csv`** — every C2 (full LEEH) call, the v1/confirmatory run. `decision_rule_h{1,2,3}.csv` are computed from this file (plus `phase1_raw.csv` as C0, and `phase3_c1_raw.csv` for H3).
- **`results/phase3_c2_raw_v2_leanprompt.csv`** — the post-hoc lean-system-prompt re-test, MGSM-only. Kept separate, never merged into the v1 file above.
- **`results/decision_rule_h1.csv`, `_h2.csv`, `_h3.csv`** — the confirmatory H1/H2/H3 verdicts per (model, language). **The canonical Phase 3 result** — source of Section B3.
- **`results/generalization_check.csv`** — raw per-call data for the exploratory Qwen/Gemini spot-check.
- **`results/generalization_check_summary.csv`** — the summarized 6-row table for that spot-check. Source of Section B6.
