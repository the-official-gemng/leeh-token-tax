"""
harness/expander.py -- Expander

Takes the executor's output and produces the final answer in the original
language, preserving formatting (numbers, code blocks, final-answer
markers) exactly.

Used by:
  - C1 (naive translate-to-English): the Executor's output is genuinely in
    English (Packer's MT-based mode translated the INPUT, not the output),
    so this does a real translation pass back to the original language.
  - C2 (full LEEH): Packer's prompt-based mode already instructs the model
    to answer directly in the original language, so the Executor's output
    is *usually* already correct. Rather than unconditionally
    re-translating (extra cost, and a real risk of translation drift
    changing an already-correct answer), this reuses
    harness.detector.detect_language() to check the executor's actual
    output language first, and only translates if it doesn't already
    match the target -- i.e. the model didn't fully comply with the
    Packer's instruction. This is a documented interpretation: the spec's
    "translates it back" wording doesn't explicitly resolve what Expander
    should do when the input is already in the right language, which is
    the normal case for C2 specifically (not C1, where it never is).
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from run_phase1 import call_model_with_hard_timeout as call_model, cost_usd  # reuse, don't rewrite -- see packer.py's comment on this same swap
from harness.detector import detect_language


@dataclass
class ExpandedResult:
    final_text: str
    was_translated: bool
    detected_input_language: str
    # Cost/tokens/latency of the translation call, when was_translated=True
    # -- conditions.py needs these for each condition's TOTAL cost, same
    # reasoning as PackedRequest's translation_* fields in packer.py.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0


_EXPAND_PROMPT_TEMPLATE = (
    "Translate the following text into the language with ISO code '{lang}'. "
    "Preserve EXACTLY: all numbers and numerals as written, any code blocks "
    "(keep code untranslated, only translate surrounding prose), and any "
    "final-answer markers or delimiters (e.g. '####', 'Answer:', boxed "
    "notation) in their original form/position. Output ONLY the translated "
    "text, no commentary, no quotes.\n\n{text}"
)


def expand(executor_output: str, target_language: str, model_name: str, provider: str) -> ExpandedResult:
    if target_language == "en":
        return ExpandedResult(final_text=executor_output, was_translated=False, detected_input_language="en")

    detected_lang, _confidence = detect_language(executor_output)
    if detected_lang == target_language:
        # Already in the target language (prompt-based mode complied) --
        # don't re-translate an already-correct answer.
        return ExpandedResult(final_text=executor_output, was_translated=False, detected_input_language=detected_lang)

    prompt = _EXPAND_PROMPT_TEMPLATE.format(lang=target_language, text=executor_output)
    result = call_model(model_name, provider, prompt)
    return ExpandedResult(
        final_text=result["answer_text"].strip(), was_translated=True, detected_input_language=detected_lang,
        prompt_tokens=result["prompt_tokens"], completion_tokens=result["completion_tokens"],
        cost_usd=cost_usd(model_name, result["prompt_tokens"], result["completion_tokens"]),
        latency_s=result["latency_s"],
    )
