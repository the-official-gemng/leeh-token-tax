# LEEH — Language Efficiency Equalizer Harness

A runtime harness that attempts to close the multilingual "token tax" — the phenomenon where LLMs consume more tokens (and therefore cost and latency) to answer the same question in a non-English language than in English.

Prior work ([Ahia et al., EMNLP 2023](https://arxiv.org/abs/2305.13707)) established that this tax exists across commercial tokenizers. LEEH measures it directly on two cheap-tier models, tests whether a from-scratch runtime harness (detect → route → translate/prompt → equalize token budgets → expand) can close it while holding accuracy, and reports what happened — including where the harness's first attempt failed its own pre-registered bar, and what later exploratory work did and didn't fix. This matters beyond cost accounting: a persistent multilingual tax is a fairness and access problem, not just an efficiency one.

## Two tracks — read this before reading any number below

This repo contains two methodologically distinct bodies of work, and every result in it belongs to exactly one of them. Conflating them is the single easiest way to misread this project.

| | Track A — Confirmatory | Track B — Exploratory hardening |
|---|---|---|
| **What it is** | Pre-registered science: hypotheses and decision rules frozen *before* data collection, tested once, reported as-is | Post-hoc engineering: iterate on the architecture and prompts to see what can be fixed, no pre-registration |
| **Can a result change after it's reported?** | No — `pre_registration.md`'s Hypotheses/Metrics/Decision Rules sections are frozen; any change is a dated Amendments Log entry, the original text stays on file | Yes, but every revision is appended as a new dated section in the log — nothing is silently edited, old numbers stay on file |
| **Source of truth** | `pre_registration.md`, `results/decision_rule_h{1,2,3}.csv`, `results/phase3_c{1,2}_raw.csv`, `docs/methodology-notes.md`'s C4 pilot section, `docs/paper_draft.md` | `docs/harness_hardening_log.md` |
| **Scope** | 2 models (`deepseek-flash`, `gpt-5.6-luna`) × 3 non-English languages (es/zh/ar), conditions C0–C3a | The C4 single-call architecture, plus targeted prompt/parameter iteration; extended informally to 2 more models (`gemini-3.5-flash-lite`, `qwen3.5-flash`) |
| **Headline verdict** | H1/H2/H3 all **not supported** — the harness's first full attempt does not clear its own bar | Mixed: two languages/models resolved, Chinese remains open, one cell borderline |

If you only read one document to understand what's actually established here, read `docs/methodology-notes.md`'s Phase 3 confirmatory section (Track A) and `docs/harness_hardening_log.md` (Track B) — not this README, which only summarizes both.

## Headline results

### Track A — confirmatory decision rules (source: `results/decision_rule_h{1,2,3}.csv`)

| Hypothesis | Rule | Result |
|---|---|---|
| H1 — cost ratio (C2/C0) ≤1.2x, CI upper bound, for ≥2/3 non-English languages | Per model | **Not supported**, either model — 0/6 (model × language) cells clear the bar |
| H2 — accuracy non-inferiority, C2 vs C0, CI lower bound > −2.0 pts | Per cell | **Not supported** — 0/8 cells, including English |
| H3 — C2 accuracy beats C1's, Wilcoxon significant (Holm-corrected) | Per cell | **Not supported** — 0/8 cells significant after correction |

Full per-language numbers are in `docs/paper_draft.md`'s Results section and the three CSVs above — not reproduced in full here to avoid a second, driftable copy of frozen numbers.

### C4 pilot — a single-call architecture, tested post-hoc (source: `docs/methodology-notes.md`, `results/phase3_c4_raw.csv`, `results/c4_pilot_v2_cost_ratio.csv`)

After the confirmatory result, a redesigned single-call architecture (no Packer/Equalizer/Expander calls) was piloted on `deepseek-flash` only, against its own pre-committed, stricter bar (CI upper bound strictly <1.2x):

| model | language | median ratio | 95% CI | verdict |
|---|---|---|---|---|
| deepseek-flash | es | 1.008x | [0.951, 1.089] | Pass (later found to use an unfair English baseline — see Track B) |
| deepseek-flash | zh | 1.312x | [1.136, 1.405] | Fail |

**Cost-spike anomaly rate, C2 vs. C4:** the unexplained 2–4x cost-spike anomaly that affected 30–36% of C2's zh rows (`methodology-notes.md`, prompt-token-delta bimodality finding) did not reappear under C4 — **0% (0/50) on both es and zh.** This was one of three checks committed in writing before the pilot ran.

### Track B — final per-cell results (source: `docs/harness_hardening_log.md`; every ratio below is a fair comparison — the fix's exact wording, applied identically to the target-language and English arms, same round)

| model | language | median ratio | 95% CI | accuracy (target/en) | status |
|---|---|---|---|---|---|
| deepseek-flash | es | 1.006x | [0.853, 1.181] | 92.0% / 96.0% | Resolved — thin margin |
| deepseek-flash | zh | 1.149x | [1.098, 1.258] | 88.0% / 92.0% | **Open — not resolved** |
| gemini-3.5-flash-lite | es | 0.981x | [0.920, 1.028] | 92.0% / 94.0% | Resolved |
| qwen3.5-flash | zh | 1.116x | [0.946, 1.390] | 92.0% / 94.0% | Resolved as non-issue (see below) |
| gpt-5.6-luna | ar | 0.996x | [0.898, 1.209] | 50.0% / 40.0% | Borderline — CI narrowly fails to exclude 1.2x |

`deepseek-flash`/zh's number above is one draw of several (five independent measurements across this track land in the same 1.15–1.19x median / 1.23–1.35x CI-upper-bound band — see `harness_hardening_log.md` for all of them); it was never fixed, not that it was fixed once and this is stale.

## Key findings, in plain language

1. **The harness's first full attempt (Track A, condition C2) does not work.** Cost went *up* relative to English on 5 of 6 model×language cells, not down. This is the project's primary, pre-registered finding — everything else in this repo is diagnostic follow-up on *why*, done after that result was already final.
2. **Spanish closes reliably, across models and architectures, and holds under multi-step tool use.** `gemini-3.5-flash-lite`/es (0.981x, Track B), `deepseek-flash`/es (1.006x, Track B), and `gpt-5.6-luna`/es (1.017x, pre-Track-B C2 lean-prompt fix, `methodology-notes.md`) all land near parity, via different fixes on different architectures. A small pilot (N=29 paired, `gemini-3.5-flash-lite`/es, forced into genuine multi-turn tool calls via a real calculator tool) held at 1.013x, CI [0.944, 1.041] — the gain does not evaporate once a task needs more than one internal step.
3. **Chinese remains a real, characterized limitation — two distinct mechanisms, not one unexplained gap.** `deepseek-flash`/zh's cost driver is a persistent completion-length tail on a largely fixed subset of questions (confirmed by a bounded-retry experiment: every retried row re-crossed the same threshold on its retry, meaning the same prompt reliably provokes the same long reasoning on those specific questions) — no prompt wording, token cap, temperature setting, or single retry closed it. `qwen3.5-flash`/zh's apparent tax turned out to be a *different* mechanism entirely: generic verbosity/looping already present in its English responses, not a translation-specific cost at all — once tested fairly, no statistically confident zh-specific tax remained.
4. **Arabic is inconclusive, not failed.** `gpt-5.6-luna`/ar's median sits at parity (0.999x → 0.996x after a later retest) but its CI is wide enough to cross 1.2x. That width traces to MAPS's small per-language sample (10 tasks × 2 subsets = 20 pairs) combined with GAIA and Math pulling in opposite directions (GAIA cheaper in Arabic, Math more expensive) — a real small-N + opposing-subset effect, not a cost blowup like zh's.

## Repo structure

```
pre_registration.md          Track A: frozen hypotheses/metrics/decision rules (do not edit directly)
docs/
  methodology-notes.md       Track A + the original C4 pilot: full working log, frozen sections included
  harness_hardening_log.md   Track B: append-only post-hoc engineering log
  paper_draft.md             Draft manuscript pulling from both tracks (in progress, not submission-ready)
  findings_summary.md        Short-form summary
  phase4_writing_reference.md
harness/                     The LEEH harness itself (Detector, Router, Packer, Executor, Equalizer, Expander)
scripts/
  download_data.py           Pulls MGSM/MAPS/GAIA-v2-LILT
  run_phase1.py               C0 baseline measurement (Track A)
  run_phase3.py               C1/C2/C3a/C4 harness runs (Track A + C4 pilot)
  analyze_decision_rules.py  H1/H2/H3 statistics (the frozen decision rule itself)
  analyze_c4_pilot*.py       C4 pilot criterion checks
  harness_hardening_*.py     Track B: one script per exploratory experiment, not part of the frozen pipeline
data/                        Downloaded datasets (MGSM, MAPS, GAIA-v2-LILT); not committed, see download_data.py
results/                     Output CSVs. phase1_raw.csv, phase3_c1/c2/c4_raw.csv, decision_rule_h*.csv are
                              Track A / frozen. Everything under harness_hardening_*.csv is Track B.
```

## Setup / reproducing a result

```bash
python -m venv venv
venv\Scripts\activate            # Windows; `source venv/bin/activate` on Linux/Mac
pip install -r requirements.txt
```

Set `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` in `.env` (add `GEMINI_API_KEY`/`QWEN_API_KEY` if reproducing Track B's extension models). Never commit `.env`.

```bash
python scripts/download_data.py                                  # pulls MGSM/MAPS/GAIA-v2-LILT into data/
python scripts/run_phase1.py --retry-until-filled                # Track A baseline (C0)
python scripts/run_phase3.py --condition c2 --retry-until-filled # Track A harness run (any of c1/c2/c3a/c4)
python scripts/analyze_decision_rules.py                         # recomputes H1/H2/H3 from the raw CSVs
```

Track B's scripts (`scripts/harness_hardening_*.py`) are each self-contained and documented in their own docstring; run any of them directly once the corresponding CSVs from the steps above exist. See `docs/harness_hardening_log.md` for which script produced which result.

## Limitations

- **Time-boxed.** Both the confirmatory study and the C4 pilot were run under explicit time constraints (stated in their own design entries) — depth in some areas (e.g. MAPS sample size, H4/C3a) was traded for breadth.
- **Chinese is unresolved on `deepseek-flash`**, the harness's own single-call architecture (C4) included — see Key Finding 3. No fix tried in this repo closes it.
- **Arabic is underpowered** (N=20 paired per model, MAPS only) — see Key Finding 4. Wider CIs are expected, not just observed; a larger MAPS sample would be needed to resolve it either way.
- **A real machine-translation-engine hybrid (e.g. Google Translate API) was proposed and explicitly scoped as future work, not built.** It would require a new external API key/account this repo does not currently provision (see the relevant `harness_hardening_log.md` entry) and remains out of scope until that decision is made.
- **`gemini-3.5-flash-lite` and `qwen3.5-flash` were never run through Track A's C1/C2/C3a conditions** — their results are Track B only (baseline + C4-style single-call fixes). No Track A claim in this repo extends to them.
- Additional, more granular limitations (a scoring bug, a timeout-ceiling artifact, a statistic error in an intermediate chat report, a NaN-key pairing bug — all found, fixed, and documented rather than silently corrected) are in `docs/paper_draft.md`'s Limitations section and `docs/methodology-notes.md` in full.

## Status / roadmap

Track A's confirmatory result is final and will not change. Track B is ongoing exploratory work; `docs/harness_hardening_log.md` is the current record of what's been tried. `docs/paper_draft.md` is a draft manuscript — some sections are near submission-ready (Methods, Results, Limitations), others are outlined but not written (Introduction, Discussion, Conclusion). No paper has been submitted or published yet.

## Citation

No publication exists yet. If citing this repository directly in the meantime:

```bibtex
@misc{leeh2026,
  title  = {LEEH: Language Efficiency Equalizer Harness --- measuring and attempting to close the multilingual token tax},
  author = {{LEEH project contributors}},
  year   = {2026},
  howpublished = {\url{https://github.com/the-official-gemng/leeh-token-tax}},
  note   = {Confirmatory result (Track A) frozen; exploratory hardening (Track B) ongoing. See docs/paper_draft.md for the draft manuscript.}
}
```

## License

MIT — see `LICENSE`.
