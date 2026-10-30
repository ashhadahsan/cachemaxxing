"""Normalize provider usage into one shape, price it, aggregate it per call site."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from . import facts
from .canon import jsonable, plain


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    input: int = 0  # every prompt token: uncached + cache read + cache write
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0  # includes thinking / reasoning tokens
    est_cost: float | None = None  # USD at list price as of facts.VERIFIED; None for unknown models

    @property
    def hit_rate(self) -> float:
        return self.cache_read / self.input if self.input else 0.0

    def __add__(self, other: Usage) -> Usage:
        cost = None if self.est_cost is None or other.est_cost is None else self.est_cost + other.est_cost
        return replace(
            self,
            input=self.input + other.input,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write,
            output=self.output + other.output,
            est_cost=cost,
        )


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(w.title() for w in rest)


def _n(d: Any, *keys: str) -> int:
    """First non-zero count among keys (snake_case or camelCase) of dict d; 0 if none."""
    if isinstance(d, dict):
        for k in keys:
            for key in (k, _camel(k)):
                if d.get(key):
                    return int(d[key])
    return 0


def usage(response: Any, model: str | None = None) -> Usage:
    """Normalize an Anthropic, OpenAI (Responses or Chat), Gemini or LiteLLM response (object or dict)."""
    d = plain(response)
    if not isinstance(d, dict):
        raise ValueError("unrecognised response: expected an SDK response object or dict")
    name = str(model or d.get("model") or d.get("model_version") or d.get("modelVersion") or "")
    meta = d.get("usage_metadata") or d.get("usageMetadata")
    if meta is not None or "candidates" in d:  # Gemini: prompt_token_count includes cached tokens
        total = _n(meta, "prompt_token_count") + _n(meta, "tool_use_prompt_token_count")
        out = _n(meta, "candidates_token_count") + _n(meta, "thoughts_token_count")
        return _priced("gemini", name, total, _n(meta, "cached_content_token_count"), 0, out)
    u = d.get("usage") or {}
    if d.get("type") == "message":  # Anthropic: input_tokens EXCLUDES cache tokens
        read, write = _n(u, "cache_read_input_tokens"), _n(u, "cache_creation_input_tokens")
        long_write = _n(u.get("cache_creation"), "ephemeral_1h_input_tokens")
        total = _n(u, "input_tokens") + read + write
        return _priced("anthropic", name, total, read, write, _n(u, "output_tokens"), long_write)
    if "prompt_tokens" in u:  # OpenAI Chat and LiteLLM: prompt_tokens includes cache tokens
        det = u.get("prompt_tokens_details") or {}
        write = _n(det, "cache_write_tokens", "cache_creation_tokens") or _n(u, "cache_creation_input_tokens")
        long_write = _n(det.get("cache_write_tokens_details"), "ttl_12h_tokens")
        read, out = _n(det, "cached_tokens"), _n(u, "completion_tokens")
        return _priced(facts.provider_of(name), name, _n(u, "prompt_tokens"), read, write, out, long_write)
    if "input_tokens" in u:  # OpenAI Responses: input_tokens includes cache tokens
        det = u.get("input_tokens_details") or {}
        long_write = _n(det.get("cache_write_tokens_details"), "ttl_12h_tokens")
        read, write = _n(det, "cached_tokens"), _n(det, "cache_write_tokens")
        return _priced("openai", name, _n(u, "input_tokens"), read, write, _n(u, "output_tokens"), long_write)
    raise ValueError("unrecognised response: expected Anthropic, OpenAI, Gemini or LiteLLM")


def _priced(provider: str, model: str, total: int, read: int, write: int, out: int, long_write: int = 0) -> Usage:
    m = facts.find(model)
    cost = None
    if m is not None:
        if m.long_context and total > m.long_context[0]:
            m = m.long_context[1]
        writes = list(m.cache_write.values()) or [m.input]  # [short TTL, long TTL]
        uncached = total - read - write
        cost = (
            uncached * m.input
            + read * m.cache_read
            + (write - long_write) * writes[0]
            + long_write * writes[-1]
            + out * m.output
        ) / 1e6
    return Usage(provider, model, total, read, write, out, cost)


_HEADER = ("call site", "calls", "hit rate", "input", "cache read", "cache write", "output", "est $", "top drift")


class Stats:
    """Usage totals per call site, in memory."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.totals: dict[str, Usage] = {}

    def add(self, call_site: str, u: Usage) -> None:
        self.calls[call_site] = self.calls.get(call_site, 0) + 1
        self.totals[call_site] = self.totals[call_site] + u if call_site in self.totals else u

    def table(self, notes: dict[str, str] | None = None) -> str:
        rows = [list(_HEADER)]
        for site, u in sorted(self.totals.items()):
            cost = "n/a" if u.est_cost is None else f"{u.est_cost:.4f}"
            rows.append(
                [
                    site,
                    str(self.calls[site]),
                    f"{u.hit_rate:.1%}",
                    f"{u.input:,}",
                    f"{u.cache_read:,}",
                    f"{u.cache_write:,}",
                    f"{u.output:,}",
                    cost,
                    (notes or {}).get(site, ""),
                ]
            )
        widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
        return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows)


def record(call_site: str, request: Any, response: Any) -> dict[str, Any]:
    """One JSONL line for `cachemaxxing report`. The library never writes files; you do."""
    return {"call_site": call_site, "request": jsonable(request), "response": jsonable(response)}
