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
from harness.router import route
from harness.packer import pack
from harness.executor import execute
from harness.equalizer import execute_equalized
from harness.expander import expand


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
                    task_type_hint: Optional[str], disable_equalizer: bool, condition_name: str) -> ConditionResult:
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

        exec_result = execute_equalized(
            model_name, provider, messages, language=decision.original_language,
            disable_equalizer=disable_equalizer,
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


def run_c2(model_name: str, provider: str, prompt: str, task_type_hint: Optional[str] = None) -> ConditionResult:
    return _run_c2_family(model_name, provider, prompt, task_type_hint, disable_equalizer=False, condition_name="c2")


def run_c3a(model_name: str, provider: str, prompt: str, task_type_hint: Optional[str] = None) -> ConditionResult:
    return _run_c2_family(model_name, provider, prompt, task_type_hint, disable_equalizer=True, condition_name="c3a")


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
        return run_c2(model_name, provider, prompt, task_type_hint=kwargs.get("task_type_hint"))
    elif condition == "c3a":
        return run_c3a(model_name, provider, prompt, task_type_hint=kwargs.get("task_type_hint"))
    else:
        raise ValueError(f"unknown condition: {condition!r} (expected one of c0, c1, c2, c3a)")
