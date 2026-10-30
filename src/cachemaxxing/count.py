"""Exact token counts for a Prompt's cacheable prefix, counted by the provider through your own client.

One cheap API call. Use it instead of the ~4-characters-per-token estimate when a decision is close:

    from cachemaxxing.count import prefix_tokens
    should_cache(prefix_tokens(client, p, model), expected_reuses=20, provider="anthropic", model=model)"""

from __future__ import annotations

from typing import Any

from .prompt import Prompt


def _prefix_only(p: Prompt) -> Prompt:
    q = Prompt(p.call_site).user(".")  # a minimal turn: providers need one message to count
    q._tools, q._system, q._context, q._examples = p._tools, p._system, p._context, p._examples
    return q


def prefix_tokens(client: Any, p: Prompt, model: str) -> int:
    """Tokens in p's tools + system/context/examples, counted by an Anthropic, OpenAI or google-genai client."""
    q = _prefix_only(p)
    if hasattr(getattr(client, "messages", None), "count_tokens"):  # anthropic.Anthropic
        kw = q.anthropic(model)
        return int(
            client.messages.count_tokens(
                **{k: kw[k] for k in ("model", "system", "tools", "messages") if k in kw}
            ).input_tokens
        )
    if hasattr(getattr(client, "responses", None), "input_tokens"):  # openai.OpenAI
        kw = q.openai(model)
        sent = {k: kw[k] for k in ("model", "input", "tools") if k in kw}
        return int(client.responses.input_tokens.count(**sent).input_tokens)
    if hasattr(getattr(client, "models", None), "count_tokens"):  # google.genai.Client
        # ponytail: counts the static text as contents; tool declarations aren't included
        contents = [{"role": "user", "parts": [{"text": t} for t in p.static] or [{"text": "."}]}]
        return int(client.models.count_tokens(model=model, contents=contents).total_tokens)
    raise TypeError("prefix_tokens needs an anthropic.Anthropic, openai.OpenAI or google.genai.Client")


async def prefix_tokens_async(client: Any, p: Prompt, model: str) -> int:
    """Async twin for google-genai (client.aio); other clients are counted synchronously."""
    aio: Any = getattr(getattr(client, "aio", None), "models", None)
    if hasattr(aio, "count_tokens"):
        contents = [{"role": "user", "parts": [{"text": t} for t in p.static] or [{"text": "."}]}]
        return int((await aio.count_tokens(model=model, contents=contents)).total_tokens)
    return prefix_tokens(client, p, model)
