# LEEH harness

A runtime harness that tries to reduce the "token tax" non-English prompts pay with LLM agents — routing, prompt construction, and per-language token-budget equalization, wired around off-the-shelf chat-completions calls. No fine-tuning, no new model.

> **Read this before using this code for anything beyond reference.** This harness was evaluated against a pre-registered decision rule, and the confirmatory result is **H1 (cost reduction) not supported**, for either model tested — under the full harness (condition C2), cost went *up* relative to no intervention in 5 of 6 tested (model, language) cells, not down. H2 (accuracy non-inferiority) and H3 (beats naive translation) are also not supported. Root causes for part of the cost increase were diagnosed and partly fixed (see below); a second, larger driver remains unexplained. **Do not take this code's existence, or a bare read of it, to imply it achieves its design goal.** Full results, methodology, and the debugging trail: [`../docs/methodology-notes.md`](../docs/methodology-notes.md) and [`../docs/paper_draft.md`](../docs/paper_draft.md).

## Architecture

Six modules, wired together by `conditions.py`:

```
prompt ──▶ Detector ──▶ Router ──▶ Packer ──▶ Executor ──▶ Expander ──▶ final answer
                                  (via Equalizer)
```

- **`detector.py`** — given a raw prompt, detects language (`langdetect`, seeded for determinism, ISO codes normalized to `en`/`es`/`ar`/`zh` etc.) and task type (`single_turn` vs. `agentic`, via a cheap keyword heuristic — pass `task_type_hint` when the caller already knows, which every condition in this study does).
- **`router.py`** — decides whether to route through English. Current policy: English input passes through untouched; any non-English input routes through English, regardless of task type.
- **`packer.py`** — prepares the outgoing request in one of two modes: **prompt-based** (a system-prompt instruction to reason internally in English but answer in the original language — no extra model call) or **MT-based** (a real translation call to English first, via the model itself, not a separate translation API).
- **`executor.py`** — makes the actual model call(s). A real, generic tool-call loop (`MAX_TOOL_TURNS = 8`) — functional, but no concrete tools were registered for this study, so every call in practice runs single-shot. Wraps every call in a hard wall-clock timeout (a separate, abandoned-on-timeout thread — not just the API client's own timeout, which isn't sufficient on its own; see the comment on `HARD_TIMEOUT_S` in `scripts/run_phase1.py`).
- **`equalizer.py`** — cross-cutting wrapper around the Executor. Scales `max_tokens` up per language by that language's measured *fertility ratio* (tokens needed vs. English for equivalent content), loaded from `results/phase1_fertility_ratios.csv`. Falls back to no adjustment (multiplier 1.0) for any `(model, language)` pair not in that file, rather than guessing.
- **`expander.py`** — translates the Executor's output back to the original language, but only if it isn't already there (checks via `detector.detect_language()` first) — skips the extra call when the model already complied with the Packer's instruction, which is the common case under prompt-based mode.

## The four conditions

Dispatched uniformly via `conditions.run_condition(condition, model_name, provider, prompt, **kwargs)`:

| Condition | What it is | Pipeline |
|---|---|---|
| **C0** | No intervention (baseline) | Raw model call. Not reimplemented here — `run_c0()` is a thin pass-through to `scripts/run_phase1.call_model()`, purely so all four conditions share one dispatch interface. |
| **C1** | Naive translate-to-English | Packer (MT mode, real translation call) → Executor (no Equalizer) → Expander (real translation call back). No Detector step — `language` is a required, known/labeled input, representing the "obvious" baseline a team might reach for without building a harness. |
| **C2** | Full LEEH (the harness's actual proposal) | Detector → Router → (English: passthrough; non-English: Packer prompt mode) → Executor+Equalizer → Expander (usually a no-op). This is what "the harness" means everywhere in the results. **At most two model calls per task, not six** — Detector/Router/Packer's prompt mode are local logic, zero calls; Executor+Equalizer is one mandatory call (translate-in instruction embedded in its prompt); Expander is one conditional call, firing only when the answer isn't already in the target language. |
| **C3a** | Ablation: C2 with the Equalizer forced off (`disable_equalizer=True`) | Isolates the Equalizer's specific contribution, for testing H4 (does removing it increase truncation on high-fertility languages?). **Mechanically implemented and functional, but never actually run in this study** — out of time, marked a stretch goal from the start. Don't infer an H4 result from its presence in the code. |

Every condition accumulates tokens/cost/latency across *every* model call it makes (C1 makes up to 3: translate-in, execute, translate-out; C2 makes at most 2, see above) — a condition's reported cost is its real total cost, not just the final answering call.

## Running it

Requires: Python 3.12, `pip install -r requirements.txt`, and `data/` populated via `scripts/download_data.py` first. The Equalizer also expects `results/phase1_fertility_ratios.csv` to exist (from a completed Phase 1 baseline run + `scripts/analyze_phase1.py`) — without it, every language silently gets multiplier 1.0 (no equalization), not an error.

```bash
# one condition, all pre-registered models/languages/datasets
python scripts/run_phase3.py --condition c2

# restrict to one model
python scripts/run_phase3.py --condition c1 --models gpt-5.6-luna

# keep retrying incomplete cells until filled (or a round/time cap is hit)
python scripts/run_phase3.py --condition c2 --retry-until-filled

# scope to one dataset block and write to a separate output file
# (used for this project's own post-hoc lean-prompt re-test)
python scripts/run_phase3.py --condition c2 --datasets MGSM --output-suffix _v2_leanprompt
```

Output goes to `results/phase3_<condition>_raw<suffix>.csv`. The run is resumable — it skips any `(model, dataset, subset, language, task_id, repeat_index)` key already recorded successfully in that file, so an interrupted run can just be restarted.

Calling the modules directly (e.g. from a notebook or another script) rather than through `run_phase3.py`: there's no `harness/__init__.py`-based packaging — each module does its own `sys.path.insert(...)` assuming the project root is importable. Run from, or add to `sys.path`, the repository root, not `harness/` itself.

## Required environment variables (names only — see `.env`, never committed)

The harness itself (everything above) needs:
- `OPENAI_API_KEY` — for `gpt-5.6-luna`
- `DEEPSEEK_API_KEY` — for `deepseek-flash`

Two more are used by a separate, standalone script (`scripts/run_generalization_check.py`) that is **not** part of the harness pipeline above — it baseline-tests two additional models but never runs them through `conditions.py`:
- `GEMINI_API_KEY`
- `QWEN_API_KEY`

All four are read via `os.getenv(...)` from a local `.env` (see `python-dotenv` in `requirements.txt`) — never hardcoded, never logged, never printed by any script in this repo.
