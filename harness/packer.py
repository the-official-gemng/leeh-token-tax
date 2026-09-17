"""
harness/packer.py -- Packer

Two selectable modes, both implemented (chosen by which Phase 3 condition
is running -- see conditions.py):

  - 'prompt': instructs the model via system prompt to reason in English
    internally but produce the final answer in the original language. No
    translation call -- just prompt construction. Used by C2 (full LEEH).

  - 'mt': machine-translates the input to English first (via a model call,
    not a separate translation API -- see _translate() below, "a
    translation API or the model itself" per spec; reusing the model
    avoids adding a third external dependency beyond OpenAI/DeepSeek),
    runs the task in English, and hands off to expander.py for the
    reverse direction. Used by C1 (naive translate-to-English baseline).

Both modes return a PackedRequest: the message list ready for
executor.py's call_model(), plus enough metadata (original_language,
original_prompt) for expander.py to do its job afterward.

Note: importing scripts/run_phase1.py for call_model() has a side effect
-- its module-level `_completed = load_completed_keys()` reads
results/phase1_raw.csv at import time (harmless, just an existing-file
read, not an API call, but worth knowing about since it means every
process that imports this module touches that CSV once on startup).
English-passthrough inputs (router.route_through_english == False) should
skip the Packer entirely -- that's conditions.py's call, not something
handled inside here.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
# call_model_with_hard_timeout, not the raw call_model -- discovered during
# a Phase 3 C1 run that the raw version has no protection against an SDK-
# level hang (the same class of bug run_phase1.py's own hard timeout was
# built to fix), and C1 makes 2 of its 3 calls through this module
# (translate-in here, translate-out in expander.py), so both need it.
from run_phase1 import call_model_with_hard_timeout as call_model, cost_usd  # reuse, don't rewrite


@dataclass
class PackedRequest:
    mode: str                                 # 'prompt' | 'mt'
    messages: list                            # ready to hand to executor.py's call_model
    original_language: str
    original_prompt: str
    translated_prompt: Optional[str] = None   # only set for mode='mt'
    # Cost/tokens/latency of the translation call itself, when mode='mt' --
    # conditions.py needs these to report each condition's TOTAL cost
    # (translation calls are real API calls with real cost; hiding them
    # would make C1/C2 look artificially cheaper than they are, which
    # directly corrupts the cost-ratio comparison the whole study is
    # about). None/0 for mode='prompt', which makes no call here.
    translation_prompt_tokens: int = 0
    translation_completion_tokens: int = 0
    translation_cost_usd: float = 0.0
    translation_latency_s: float = 0.0


# v2 (post-hoc, exploratory -- see docs/methodology-notes.md): the original
# 76-token template above was found to be a meaningful driver of C2's
# cost-ratio miss on MGSM in the confirmatory Phase 3 run, since it's added
# in full to every non-English call regardless of how short the underlying
# prompt is. Trimmed to 18 tokens (verified via tiktoken o200k_base) while
# keeping the same two obligations the executor actually depends on:
# reason in English, answer only in the target language, preserve
# numbers/formatting. Manually spot-checked on 4 real MGSM zh/es questions
# across both models before use -- correct language, correct answer, no
# mixing, formatting intact each time.
_PROMPT_MODE_SYSTEM_TEMPLATE = (
    "Think in English internally. Answer only in '{lang}'. "
    "Keep numbers/formatting exact."
)


def pack_prompt_based(original_prompt: str, original_language: str) -> PackedRequest:
    system = _PROMPT_MODE_SYSTEM_TEMPLATE.format(lang=original_language)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": original_prompt},
    ]
    return PackedRequest(
        mode="prompt", messages=messages,
        original_language=original_language, original_prompt=original_prompt,
    )


def _translate(text: str, target_lang: str, model_name: str, provider: str) -> dict:
    """Returns the raw call_model() result dict (not just the text) so
    callers can account for the translation call's own tokens/cost/latency."""
    prompt = (
        f"Translate the following text to {target_lang}. Output ONLY the "
        f"translation, no commentary, no quotes:\n\n{text}"
    )
    return call_model(model_name, provider, prompt)


def pack_mt_based(original_prompt: str, original_language: str, model_name: str, provider: str) -> PackedRequest:
    r = _translate(original_prompt, "English", model_name, provider)
    translated = r["answer_text"].strip()
    messages = [{"role": "user", "content": translated}]
    return PackedRequest(
        mode="mt", messages=messages,
        original_language=original_language, original_prompt=original_prompt,
        translated_prompt=translated,
        translation_prompt_tokens=r["prompt_tokens"],
        translation_completion_tokens=r["completion_tokens"],
        translation_cost_usd=cost_usd(model_name, r["prompt_tokens"], r["completion_tokens"]),
        translation_latency_s=r["latency_s"],
    )


def pack(mode: str, original_prompt: str, original_language: str,
         model_name: Optional[str] = None, provider: Optional[str] = None) -> PackedRequest:
    if mode == "prompt":
        return pack_prompt_based(original_prompt, original_language)
    elif mode == "mt":
        if not model_name or not provider:
            raise ValueError("mode='mt' requires model_name and provider (needs a model call to translate)")
        return pack_mt_based(original_prompt, original_language, model_name, provider)
    else:
        raise ValueError(f"unknown packer mode: {mode!r} (expected 'prompt' or 'mt')")
