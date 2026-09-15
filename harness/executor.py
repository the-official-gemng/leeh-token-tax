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


def _run_loop(model_name: str, provider: str, messages: list,
               tools: Optional[list], tool_executor: Optional[dict],
               max_tokens: Optional[int] = None) -> ExecutionResult:
    messages = list(messages)  # don't mutate the caller's list
    client = get_client(provider)
    tool_executor = tool_executor or {}
    total_prompt = total_completion = 0
    tool_calls_made = 0
    start = time.monotonic()

    for _turn in range(MAX_TOOL_TURNS):
        kwargs = {"model": model_name, "messages": messages}
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
            # completely unaffected.
            kwargs["reasoning_effort"] = "none"
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = resp.usage
        total_prompt += usage.prompt_tokens
        total_completion += usage.completion_tokens

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
            max_tokens: Optional[int] = None,
            hard_timeout_s: float = HARD_TIMEOUT_S) -> ExecutionResult:
    """Same hard-timeout-via-abandoned-thread pattern as Phase 1's
    call_model_with_hard_timeout -- bounds the whole loop (all turns, all
    tool calls) to hard_timeout_s wall-clock seconds, regardless of what
    the SDK's own retry/backoff is doing internally.

    max_tokens is passed through to every turn of the underlying API call
    unmodified -- it's None (provider default) unless a caller sets it.
    harness/equalizer.py is what actually computes a per-language value
    and passes it in; this function doesn't have an opinion about the
    right value, only about passing one through when given."""
    ex = ThreadPoolExecutor(max_workers=1)
    future = ex.submit(_run_loop, model_name, provider, messages, tools, tool_executor, max_tokens)
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
