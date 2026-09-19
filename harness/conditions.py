"""
harness/conditions.py -- wires Detector/Router/Packer/Executor/Equalizer/
Expander into the four Phase 1/3 conditions.

- C0: no intervention. This IS scripts/run_phase1.py -- not reimplemented
  here. run_c0() is a thin pass-through to run_phase1.call_model() purely
  so run_phase3.py can dispatch all four conditions through one uniform
  interface; it adds no logic of its own.

- C1: naive translate-to-English. Packer(mt) -> Executor (no equalizer)
  -> Expander (a real translation back, since the executor's output is
  genuinely in English here -- Packer translated the INPUT, not the
  output). C1 has no Detector step in the spec's architecture -- it takes
  `language` as a known/labeled parameter from the caller (run_phase3.py
  already knows each task's language from its source dataset, same as
  Phase 1 did), rather than auto-detecting it.

- C2: full LEEH. Detector -> Router -> [English: passthrough, no Packer/
  Expander needed; non-English: Packer(prompt)] -> Executor+Equalizer ->
  Expander (usually a no-op here per its own docstring -- prompt-based
  mode already asks for the answer in the original language). Unlike C1,
  C2 DOES run the Detector, per spec -- the point of a runtime harness is
  working on prompts without needing a pre-supplied language label.

- C3a: identical to C2 but disable_equalizer=True throughout every call
  (ablation for H4).

- C4 (pilot, added post-confirmatory-result -- see docs/methodology-notes.md's
  entry on the C4 pilot pre-commitment): single-call cross-lingual redesign.
  Detector -> Router(low-tax-skip check) -> [English, or a (model, language)
  pair Phase 1 already shows comfortably under the 1.2x target: passthrough;
  otherwise: one unified system+user prompt, no Packer call] -> Executor
  (no Equalizer -- there's no cross-call token budget to reconcile with a
  single call). No Expander call either -- the unified prompt's own
  instruction is the only mechanism ensuring the answer lands in the
  target language; unlike C2, there is no post-hoc language check/retranslate
  safety net on this path. C0/C1/C2/C3a above are unmodified by this
  addition -- run_c4() and should_skip_intervention() (harness/router.py)
  are new, additive code only.

Every condition function accumulates tokens/cost/latency across EVERY
model call it makes -- e.g. C1 makes up to 3 (translate-in, execute,
translate-out). The whole point of Phase 3 is comparing each condition's
TOTAL cost against Phase 1's C0 baseline; a condition that hid its
translation calls' cost would make LEEH look artificially cheaper than it
actually is.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from run_phase1 import call_model, cost_usd
from harness.detector import detect
from harness.router import route, should_skip_intervention
from harness.packer import pack
from harness.executor import execute
from harness.equalizer import execute_equalized
from harness.expander import expand

# C4 pilot only (see module docstring). Deliberately short -- no Packer/
# Expander calls on this path, so this instruction alone has to both keep
# the reasoning in English AND keep English out of the visible output;
# the original C2 prompt-mode template could rely on Expander as a
# safety net if the model didn't comply, C4 can't. Original shared
# version verified via tiktoken (36 tokens, o200k_base) and a manual
# spot-check on 2 real MGSM questions (deepseek-flash, es/zh) before use
# -- correct answer, correct language, no English leakage in either.
# Fallback for any language the per-language dict below hasn't tuned.
_C4_SYSTEM_TEMPLATE = (
    "The question below is in '{lang}'. Reason in English internally; give "
    "the final answer in '{lang}' only, no English in the output. Keep "
    "numbers/formatting exact."
)

# Pilot-continuation refinement (see docs/methodology-notes.md's C4 pilot
# continuation entry). After the first pilot run (results/phase3_c4_raw.csv,
# using the shared template above) failed the pre-committed criterion on
# both cells, decomposing the cost ratio showed the inflation was
# predominantly completion-side for both es (74.1% of the $ delta) and zh
# (89.8%) -- prompt-token overhead was a minority driver in both. Two
# independent, targeted fixes, each verified via tiktoken + a spot-check
# on the same 2 real MGSM questions before any batch run:
#   - es: the shared template above, plus one added load-bearing clause
#     ("give only the final answer... no explanation") targeting the
#     diagnosed completion-side verbosity directly. 38 tokens.
#   - zh: reuses harness/packer.py's already-validated 18-token C2
#     lean-prompt template verbatim (proven at N=50x2-models scale, not
#     just a spot-check) -- shrinking the fixed overhead itself, per
#     explicit instruction, independent of es's diagnosis-driven fix.
# zh's entry below is maintained by the post-hoc harness-hardening track
# (docs/harness_hardening_log.md, NOT part of the confirmatory C4 pilot
# in methodology-notes.md) -- iterated independently of es's, which
# stays exactly as the pilot left it.
_C4_SYSTEM_TEMPLATES_BY_LANG = {
    "es": (
        "The question below is in '{lang}'. Reason in English internally; give only "
        "the final answer in '{lang}', no explanation, no English in the output. Keep "
        "numbers/formatting exact."
    ),
    "zh": (
        "Reason in English only -- never '{lang}'. Then give only the final answer "
        "in '{lang}', no explanation. Keep numbers/formatting exact."
    ),
}


@dataclass
class ConditionResult:
    condition: str
    final_answer: Optional[str] = None
    detected_language: Optional[str] = None
    task_type: Optional[str] = None
    route_through_english: Optional[bool] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0     # summed across every sub-call this condition made
    truncated: bool = False    # from the final answer-producing call
    error: Optional[str] = None
    # Added 2026-09-18 (harness-hardening track) -- purely additive, see
    # harness/executor.py's ExecutionResult for the same fields. Only
    # populated by run_c4() currently; None for every other condition.
    reasoning_content: Optional[str] = None
    reasoning_tokens: Optional[int] = None


def _add(acc: ConditionResult, prompt_tokens: int, completion_tokens: int, latency_s: float, cost: float):
    acc.prompt_tokens += prompt_tokens
    acc.completion_tokens += completion_tokens
    acc.total_tokens += prompt_tokens + completion_tokens
    acc.latency_s += latency_s or 0
    acc.cost_usd += cost


def run_c0(model_name: str, provider: str, prompt: str) -> ConditionResult:
    result = ConditionResult(condition="c0")
    try:
        r = call_model(model_name, provider, prompt)
        result.final_answer = r["answer_text"]
        result.truncated = (r["finish_reason"] == "length")
        _add(result, r["prompt_tokens"], r["completion_tokens"], r["latency_s"],
             cost_usd(model_name, r["prompt_tokens"], r["completion_tokens"]))
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


def run_c1(model_name: str, provider: str, prompt: str, language: str) -> ConditionResult:
    result = ConditionResult(condition="c1", detected_language=language)
    try:
        packed = pack("mt", prompt, language, model_name, provider)
        _add(result, packed.translation_prompt_tokens, packed.translation_completion_tokens,
             packed.translation_latency_s, packed.translation_cost_usd)

        exec_result = execute(model_name, provider, packed.messages)
        _add(result, exec_result.prompt_tokens, exec_result.completion_tokens,
             exec_result.latency_s, exec_result.cost_usd)
        if exec_result.error:
            result.error = f"executor: {exec_result.error}"
            return result
        result.truncated = exec_result.truncated

        expanded = expand(exec_result.answer_text, language, model_name, provider)
        _add(result, expanded.prompt_tokens, expanded.completion_tokens,
             expanded.latency_s, expanded.cost_usd)
        result.final_answer = expanded.final_text
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


def _run_c2_family(model_name: str, provider: str, prompt: str,
                    task_type_hint: Optional[str], disable_equalizer: bool, condition_name: str,
                    base_max_tokens: Optional[int] = None) -> ConditionResult:
    result = ConditionResult(condition=condition_name)
    try:
        detection = detect(prompt, task_type_hint=task_type_hint)
        result.detected_language = detection.language
        result.task_type = detection.task_type

        decision = route(detection)
        result.route_through_english = decision.route_through_english

        if not decision.route_through_english:
            # English passthrough -- no Packer/Expander needed, same shape as C0.
            messages = [{"role": "user", "content": prompt}]
        else:
            packed = pack("prompt", prompt, decision.original_language)
            messages = packed.messages
            # prompt-based mode makes no translation call of its own -- nothing
            # to accumulate here, unlike C1's mt mode.

        equalizer_kwargs = {"disable_equalizer": disable_equalizer}
        if base_max_tokens is not None:
            equalizer_kwargs["base_max_tokens"] = base_max_tokens
        exec_result = execute_equalized(
            model_name, provider, messages, language=decision.original_language,
            **equalizer_kwargs,
        )
        _add(result, exec_result.prompt_tokens, exec_result.completion_tokens,
             exec_result.latency_s, exec_result.cost_usd)
        if exec_result.error:
            result.error = f"executor: {exec_result.error}"
            return result
        result.truncated = exec_result.truncated

        if not decision.route_through_english:
            result.final_answer = exec_result.answer_text
        else:
            expanded = expand(exec_result.answer_text, decision.original_language, model_name, provider)
            _add(result, expanded.prompt_tokens, expanded.completion_tokens,
                 expanded.latency_s, expanded.cost_usd)
            result.final_answer = expanded.final_text
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


def run_c2(model_name: str, provider: str, prompt: str, task_type_hint: Optional[str] = None,
           base_max_tokens: Optional[int] = None) -> ConditionResult:
    return _run_c2_family(model_name, provider, prompt, task_type_hint, disable_equalizer=False,
                           condition_name="c2", base_max_tokens=base_max_tokens)


def run_c3a(model_name: str, provider: str, prompt: str, task_type_hint: Optional[str] = None,
            base_max_tokens: Optional[int] = None) -> ConditionResult:
    return _run_c2_family(model_name, provider, prompt, task_type_hint, disable_equalizer=True,
                           condition_name="c3a", base_max_tokens=base_max_tokens)


def run_c4(model_name: str, provider: str, prompt: str, task_type_hint: Optional[str] = None) -> ConditionResult:
    """Pilot condition -- see module docstring and
    docs/methodology-notes.md's C4 pilot pre-commitment entry for the
    design rationale and the pass criterion committed before any C4 data
    was collected."""
    result = ConditionResult(condition="c4")
    try:
        detection = detect(prompt, task_type_hint=task_type_hint)
        result.detected_language = detection.language
        result.task_type = detection.task_type

        skip = detection.language == "en" or should_skip_intervention(model_name, detection.language)
        result.route_through_english = not skip
        if skip:
            # English, or a (model, language) pair Phase 1 already shows
            # comfortably under the 1.2x target -- nothing to fix, same
            # shape as C0/C2's English passthrough.
            messages = [{"role": "user", "content": prompt}]
        else:
            template = _C4_SYSTEM_TEMPLATES_BY_LANG.get(detection.language, _C4_SYSTEM_TEMPLATE)
            system = template.format(lang=detection.language)
            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

        # No max_tokens cap -- no Equalizer on this path (single call, no
        # cross-call budget to reconcile), and MGSM answers are naturally
        # short (matches C0's own uncapped MGSM calls, which truncate at
        # ~1% -- see docs/methodology-notes.md). Not validated for
        # MAPS-scale answers; this pilot doesn't run MAPS.
        exec_result = execute(model_name, provider, messages)
        _add(result, exec_result.prompt_tokens, exec_result.completion_tokens,
             exec_result.latency_s, exec_result.cost_usd)
        if exec_result.error:
            result.error = f"executor: {exec_result.error}"
            return result
        result.truncated = exec_result.truncated
        result.final_answer = exec_result.answer_text
        result.reasoning_content = exec_result.reasoning_content
        result.reasoning_tokens = exec_result.reasoning_tokens
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


def run_condition(condition: str, model_name: str, provider: str, prompt: str, **kwargs) -> ConditionResult:
    """Uniform dispatch for run_phase3.py's --condition flag."""
    if condition == "c0":
        return run_c0(model_name, provider, prompt)
    elif condition == "c1":
        language = kwargs.get("language")
        if not language:
            raise ValueError("c1 requires language= (the known/labeled input language -- c1 has no Detector step)")
        return run_c1(model_name, provider, prompt, language)
    elif condition == "c2":
        return run_c2(model_name, provider, prompt, task_type_hint=kwargs.get("task_type_hint"),
                       base_max_tokens=kwargs.get("base_max_tokens"))
    elif condition == "c3a":
        return run_c3a(model_name, provider, prompt, task_type_hint=kwargs.get("task_type_hint"),
                        base_max_tokens=kwargs.get("base_max_tokens"))
    elif condition == "c4":
        return run_c4(model_name, provider, prompt, task_type_hint=kwargs.get("task_type_hint"))
    else:
        raise ValueError(f"unknown condition: {condition!r} (expected one of c0, c1, c2, c3a, c4)")
