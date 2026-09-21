"""
harness/executor.py -- Agent Loop Executor

Wraps scripts/run_phase1.py's get_client()/cost_usd() (reused, not
rewritten) with:

  - a generic, pluggable tool-call loop for agentic tasks (MAPS/GAIA). The
    loop mechanism itself is real and functional (OpenAI-style `tools` /
    `tool_calls`, runs until the model stops requesting tools or
    MAX_TOOL_TURNS is hit) -- but no concrete tools (web search, code
    execution, file access, etc.) are registered here, since none were
    specified for this harness. Pass `tools` (an OpenAI tool-schema list)
    and `tool_executor` (a dict of tool name -> callable) to actually wire
    real tools in. Without them, an agentic task still runs through the
    loop for real, it just never receives a tool_call to act on, so it
    exits after one turn -- identical behavior to Phase 1's single-shot
    call_model(). This keeps the mechanism honest rather than faking
    tool-use that doesn't exist.

  - the same hard wall-clock ceiling Phase 1 uses (see run_phase1.py's
    HARD_TIMEOUT_S comment for why a plain client-side timeout alone isn't
    enough), and the same result fields (tokens, cost, latency,
    correctness is left to the caller same as Phase 1, truncation) so
    Phase 3 results are directly comparable to Phase 1's C0 baseline.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from run_phase1 import get_client, cost_usd, HARD_TIMEOUT_S  # reuse, don't rewrite

MAX_TOOL_TURNS = 8  # safety cap so a misbehaving/looping model can't run forever


@dataclass
class ExecutionResult:
    answer_text: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: Optional[float] = None
    truncated: bool = False
    tool_calls_made: int = 0
    error: Optional[str] = None
    # Added 2026-09-18 (harness-hardening track, docs/harness_hardening_log.md)
    # -- purely additive, doesn't change prompt_tokens/completion_tokens/
    # cost_usd/any existing field's value for any existing caller.
    # reasoning_tokens was ALREADY included inside completion_tokens (and
    # therefore already correctly billed in cost_usd) before this change --
    # verified empirically, not assumed -- some providers (deepseek-flash
    # confirmed; gpt-5.6-luna not checked) additionally expose the
    # reasoning *text* itself via a non-standard `reasoning_content`
    # field on the response message, absent from the OpenAI SDK's typed
    # Message model but present in the raw payload -- captured here via
    # getattr with a None default so providers without it are unaffected.
    reasoning_content: Optional[str] = None
    reasoning_tokens: Optional[int] = None
    # Added 2026-09-19 (harness-hardening track, bounded early-cutoff retry
    # for deepseek-flash/zh) -- purely additive, only ever set by
    # execute_with_cutoff_retry() below. Every other caller/condition gets
    # the defaults (False/None) and is completely unaffected.
    retry_fired: bool = False
    cutoff_hit_first: bool = False
    cutoff_hit_second: bool = False
    est_completion_tokens_first: Optional[int] = None
    wasted_cost_usd: Optional[float] = None


def _run_loop(model_name: str, provider: str, messages: list,
               tools: Optional[list], tool_executor: Optional[dict],
               max_tokens: Optional[int] = None,
               temperature: Optional[float] = None) -> ExecutionResult:
    messages = list(messages)  # don't mutate the caller's list
    client = get_client(provider)
    tool_executor = tool_executor or {}
    total_prompt = total_completion = 0
    total_reasoning_tokens = 0
    last_reasoning_content = None
    tool_calls_made = 0
    start = time.monotonic()

    for _turn in range(MAX_TOOL_TURNS):
        kwargs = {"model": model_name, "messages": messages}
        if temperature is not None:
            # Purely additive, same passthrough pattern as max_tokens below --
            # None (this branch skipped) preserves the provider default for
            # every existing caller. Added 2026-09-19 (harness-hardening
            # track) to test whether lower temperature shrinks deepseek-flash/
            # zh's completion-length tail (docs/harness_hardening_log.md).
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            # OpenAI's newer models (gpt-5.6-luna included) reject the
            # classic `max_tokens` outright -- "Unsupported parameter:
            # 'max_tokens' is not supported with this model. Use
            # 'max_completion_tokens' instead" -- while DeepSeek's API
            # still wants the old name and doesn't know the new one
            # (confirmed empirically, not documented anywhere). Branch on
            # provider, not model name, since it's an endpoint/API-version
            # distinction, not a per-model one.
            kwargs["max_completion_tokens" if provider == "openai" else "max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
            # gpt-5.6-luna (and presumably its Sol/Terra siblings) rejects
            # function tools on /v1/chat/completions while reasoning_effort
            # is active -- "Function tools with reasoning_effort are not
            # supported... set reasoning_effort to 'none'" (discovered via
            # smoke test, not documented anywhere in this repo beforehand).
            # Only set this when tools are actually in play, so the
            # tools=None path (everything Phase 1 already validated) is
            # completely unaffected. Scoped to provider=="openai" (added
            # 2026-09-20, multi-step pilot) -- confirmed empirically that
            # gemini's OpenAI-compat endpoint rejects `reasoning_effort`
            # outright (400 INVALID_ARGUMENT) when tools are also present;
            # this param is an openai-specific quirk, not a general one.
            if provider == "openai":
                kwargs["reasoning_effort"] = "none"
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = resp.usage
        total_prompt += usage.prompt_tokens
        total_completion += usage.completion_tokens

        # Non-standard field some providers (deepseek-flash confirmed) add
        # to the message payload -- not in the OpenAI SDK's typed Message
        # model, so getattr (not choice.message.reasoning_content
        # directly) to avoid an AttributeError on providers that omit it.
        last_reasoning_content = getattr(choice.message, "reasoning_content", None) or last_reasoning_content
        details = getattr(usage, "completion_tokens_details", None)
        rt = getattr(details, "reasoning_tokens", None) if details else None
        if rt:
            total_reasoning_tokens += rt

        tool_calls = getattr(choice.message, "tool_calls", None)
        if not tool_calls:
            return ExecutionResult(
                answer_text=choice.message.content,
                prompt_tokens=total_prompt, completion_tokens=total_completion,
                total_tokens=total_prompt + total_completion,
                cost_usd=cost_usd(model_name, total_prompt, total_completion),
                latency_s=time.monotonic() - start,
                truncated=(choice.finish_reason == "length"),
                tool_calls_made=tool_calls_made,
                reasoning_content=last_reasoning_content,
                reasoning_tokens=total_reasoning_tokens or None,
            )

        messages.append({"role": "assistant", "content": choice.message.content, "tool_calls": tool_calls})
        for tc in tool_calls:
            tool_calls_made += 1
            fn_name = tc.function.name
            if fn_name in tool_executor:
                try:
                    result = tool_executor[fn_name](tc.function.arguments)
                except Exception as e:
                    result = f"[tool error: {e}]"
            else:
                result = f"[no implementation registered for tool '{fn_name}']"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return ExecutionResult(
        answer_text=None, prompt_tokens=total_prompt, completion_tokens=total_completion,
        total_tokens=total_prompt + total_completion,
        cost_usd=cost_usd(model_name, total_prompt, total_completion),
        latency_s=time.monotonic() - start, truncated=True, tool_calls_made=tool_calls_made,
        error=f"exceeded MAX_TOOL_TURNS={MAX_TOOL_TURNS} without a final answer",
    )


def execute(model_name: str, provider: str, messages: list,
            tools: Optional[list] = None, tool_executor: Optional[dict] = None,
            max_tokens: Optional[int] = None, temperature: Optional[float] = None,
            hard_timeout_s: float = HARD_TIMEOUT_S) -> ExecutionResult:
    """Same hard-timeout-via-abandoned-thread pattern as Phase 1's
    call_model_with_hard_timeout -- bounds the whole loop (all turns, all
    tool calls) to hard_timeout_s wall-clock seconds, regardless of what
    the SDK's own retry/backoff is doing internally.

    max_tokens and temperature are passed through to every turn of the
    underlying API call unmodified -- each is None (provider default)
    unless a caller sets it. harness/equalizer.py is what actually
    computes a per-language max_tokens value and passes it in; this
    function doesn't have an opinion about the right value for either,
    only about passing one through when given."""
    ex = ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_run_loop, model_name, provider, messages, tools, tool_executor,
                        max_tokens, temperature)
    try:
        return future.result(timeout=hard_timeout_s)
    except FutureTimeoutError:
        return ExecutionResult(
            error=f"Hard timeout: no response within {hard_timeout_s}s (thread abandoned)",
            latency_s=hard_timeout_s,
        )
    except Exception as e:
        return ExecutionResult(error=f"{type(e).__name__}: {e}")
    finally:
        ex.shutdown(wait=False)


# --- Bounded early-cutoff retry (added 2026-09-19, harness-hardening --------
# track, docs/harness_hardening_log.md) --------------------------------------
#
# Single-shot only -- no tool-call loop, no max_tokens interaction (a
# separate, narrower code path from _run_loop()/execute() above, which are
# completely untouched by any of this). Purpose: deepseek-flash/zh's
# completion-length tail (~8-10% of calls) is what's driving its cost ratio
# over 1.2x -- not a rare catastrophic spike a max_tokens cap could safely
# clip (that was tried and ruled out), but not something temperature fixes
# either (also tried and ruled out). This monitors the stream as it
# generates and cancels + retries once if it's heading into the tail,
# rather than paying for the whole thing.
#
# Token counting during the stream uses tiktoken (o200k_base) as an
# approximate proxy -- deepseek's real tokenizer isn't o200k_base, so this
# is consistent with (not more precise than) the same approximation this
# project already uses elsewhere to sanity-check prompt template lengths
# (harness/conditions.py, harness/packer.py). It is ONLY used to estimate
# the completion-token count of an ABORTED call, which never receives a
# real usage object from the API (usage only arrives on the final chunk
# of a stream that finishes normally). A completed call (first attempt
# under threshold, or the retry, win or lose) always uses the API's own
# real `usage`, never the tiktoken estimate.
#
# Billing-semantics caveat, stated plainly rather than assumed: closing
# the stream's underlying connection is the standard client-side signal
# for "stop generating", and empirically the aborted request returns in a
# fraction of the time a full generation would take (~0.8s to detect and
# close at a 15-token test threshold vs. ~12.7s for an uncut ~1700-token
# response on the same client) -- consistent with the provider halting
# generation on disconnect. This project has no visibility into
# DeepSeek's actual billing meter, so that consistency is the strongest
# verification available from the client side, not proof. If DeepSeek
# in fact bills the full originally-intended generation regardless of
# disconnect, the true savings would be smaller than reported here
# (worst case zero) -- flagged, not swept under the rug.

import tiktoken  # noqa: E402  (local import section, keeps this block self-contained)

_TOKENIZER = None


def _approx_tokens(text: str) -> int:
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = tiktoken.get_encoding("o200k_base")
    return len(_TOKENIZER.encode(text)) if text else 0


def _stream_once(client, model_name: str, messages: list,
                  cutoff_tokens: int, temperature: Optional[float],
                  enforce_cutoff: bool) -> dict:
    """Runs one streaming completion. If enforce_cutoff, cancels the
    instant the running content+reasoning token estimate reaches
    cutoff_tokens (no real `usage` in that case -- crossed=True signals
    the caller to fall back to the tiktoken estimate). If not
    enforce_cutoff, still tracks whether it *would* have crossed
    (`crossed`) for reporting, but always lets the stream finish
    naturally and returns the real `usage`."""
    kwargs = {"model": model_name, "messages": messages, "stream": True,
              "stream_options": {"include_usage": True}}
    if temperature is not None:
        kwargs["temperature"] = temperature
    start = time.monotonic()
    content_parts, reasoning_parts = [], []
    usage = None
    finish_reason = None
    crossed = False
    stream = client.chat.completions.create(**kwargs)
    try:
        for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta
                c = getattr(delta, "content", None)
                if c:
                    content_parts.append(c)
                rc = getattr(delta, "reasoning_content", None)
                if rc:
                    reasoning_parts.append(rc)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            if not crossed:
                running = "".join(content_parts) + "".join(reasoning_parts)
                if _approx_tokens(running) >= cutoff_tokens:
                    crossed = True
                    if enforce_cutoff:
                        break
    finally:
        stream.close()
    return {
        "text": "".join(content_parts),
        "reasoning_text": "".join(reasoning_parts) or None,
        "usage": usage,
        "finish_reason": finish_reason,
        "crossed": crossed,
        "latency_s": time.monotonic() - start,
        "est_tokens": _approx_tokens("".join(content_parts) + "".join(reasoning_parts)),
    }


def execute_with_cutoff_retry(model_name: str, provider: str, messages: list,
                               cutoff_tokens: int, temperature: Optional[float] = None,
                               hard_timeout_s: float = HARD_TIMEOUT_S) -> ExecutionResult:
    """Bounded, early-cutoff retry: stream the completion; if the running
    content+reasoning token estimate crosses cutoff_tokens before the
    model finishes, cancel immediately (paying only for tokens generated
    up to that point) and re-issue the identical call once. If the retry
    ALSO crosses the threshold, accept it as-is -- one retry maximum, no
    loop. Applies identically regardless of arm language; the same
    cutoff_tokens value should be passed for the English arm as for the
    target language, to keep the fair-comparison discipline intact (it
    should just rarely/never fire there)."""
    client = get_client(provider)

    def _attempt(enforce_cutoff):
        return _stream_once(client, model_name, messages, cutoff_tokens, temperature, enforce_cutoff)

    ex = ThreadPoolExecutor(max_workers=1)
    try:
        first = ex.submit(_attempt, True).result(timeout=hard_timeout_s)
    except FutureTimeoutError:
        return ExecutionResult(error=f"Hard timeout: no response within {hard_timeout_s}s (thread abandoned)",
                                latency_s=hard_timeout_s)
    except Exception as e:
        return ExecutionResult(error=f"{type(e).__name__}: {e}")
    finally:
        ex.shutdown(wait=False)

    if not first["crossed"]:
        u = first["usage"]
        return ExecutionResult(
            answer_text=first["text"], prompt_tokens=u.prompt_tokens, completion_tokens=u.completion_tokens,
            total_tokens=u.prompt_tokens + u.completion_tokens,
            cost_usd=cost_usd(model_name, u.prompt_tokens, u.completion_tokens),
            latency_s=first["latency_s"], truncated=(first["finish_reason"] == "length"),
            reasoning_content=first["reasoning_text"], retry_fired=False, cutoff_hit_first=False,
        )

    # First attempt crossed the threshold and was cancelled -- retry once,
    # letting it run to completion regardless of outcome (bounded = one
    # retry max). Real usage from the retry gives us its exact prompt
    # token count, which is identical to the first attempt's (same
    # messages) -- reused rather than re-estimated, so only the aborted
    # call's COMPLETION side needs the tiktoken estimate.
    ex2 = ThreadPoolExecutor(max_workers=1)
    try:
        second = ex2.submit(_attempt, False).result(timeout=hard_timeout_s)
    except FutureTimeoutError:
        return ExecutionResult(error=f"Hard timeout on retry: no response within {hard_timeout_s}s",
                                latency_s=first["latency_s"] + hard_timeout_s,
                                retry_fired=True, cutoff_hit_first=True)
    except Exception as e:
        return ExecutionResult(error=f"{type(e).__name__}: {e}", retry_fired=True, cutoff_hit_first=True)
    finally:
        ex2.shutdown(wait=False)

    u = second["usage"]
    wasted_cost = cost_usd(model_name, u.prompt_tokens, first["est_tokens"])
    real_cost = cost_usd(model_name, u.prompt_tokens, u.completion_tokens)
    return ExecutionResult(
        answer_text=second["text"], prompt_tokens=u.prompt_tokens, completion_tokens=u.completion_tokens,
        total_tokens=u.prompt_tokens + u.completion_tokens,
        cost_usd=wasted_cost + real_cost,
        latency_s=first["latency_s"] + second["latency_s"], truncated=(second["finish_reason"] == "length"),
        reasoning_content=second["reasoning_text"], retry_fired=True, cutoff_hit_first=True,
        cutoff_hit_second=second["crossed"], est_completion_tokens_first=first["est_tokens"],
        wasted_cost_usd=wasted_cost,
    )
