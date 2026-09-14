# CLAUDE.md — LEEH Project

## What this project is
LEEH (Language Efficiency Equalizer Harness) — a runtime harness to close the
multilingual "token tax" for LLM agents. Full design: `docs/` (experiment
design and conduct plan).

## Current phase
**Phase 1 — Measurement study (baseline, no harness yet).**
Goal: measure token count, cost, latency, and accuracy for `gpt-5.6-luna`
and `deepseek-flash` across English/Chinese/Arabic/Spanish on MGSM, MAPS
(GAIA+MATH subsets), and GAIA-v2-LILT (Arabic slice).

## Do not touch
`pre_registration.md` is FROZEN. Never edit it directly — any change needs a
PR reviewed by both teammates and a new row in its Amendments Log. This is
enforced by CODEOWNERS + branch protection on GitHub, not just convention.

## Repo layout
- `data/` — downloaded datasets (MGSM, MAPS, GAIA-v2-LILT)
- `scripts/` — download_data.py, run_phase1.py, analyze_phase1.py
- `results/` — output CSVs from runs
- `docs/` — design doc, notes
- `harness/` — Phase 2 code only (Detector/Router/Packer/Executor/Expander/
  Equalizer) — not started yet

## Environment
- Python venv at `venv/` — activate with `venv\Scripts\activate`
- Secrets in `.env` (OPENAI_API_KEY, DEEPSEEK_API_KEY). Never print this
  file's contents back to me, never commit it.
- Packages: openai, datasets, transformers, tiktoken, pandas, scipy,
  statsmodels, python-dotenv

## Conventions
- All API calls go through `scripts/run_phase1.py`. Log every field the
  pre-registration requires: tokens, cost, latency, correctness, truncation.
- Never hardcode API keys — always `os.getenv(...)` via `.env`.
- Any deviation from the frozen plan (dropped language, infeasible dataset)
  gets flagged, not silently skipped — it needs an Amendments Log entry.

## Status
- [x] Pre-registration frozen
- [x] Repo + branch protection + CODEOWNERS set up
- [ ] Datasets downloaded
- [ ] Phase 1 baseline run
- [ ] Phase 1 stats / decision-rule check
