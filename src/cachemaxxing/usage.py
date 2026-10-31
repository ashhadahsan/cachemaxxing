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
    saved: float | None = None  # USD saved versus the same call with no caching (negative: writes cost more)
    miss_reason: str | None = None  # the provider's own verdict when diagnostics were requested

    @property
    def hit_rate(self) -> float:
        return self.cache_read / self.input if self.input else 0.0

    def attributes(
        self, call_site: str | None = None, *, prefix: str = "cachemaxxing."
    ) -> dict[str, str | int | float]:
        """Flat metrics for a trace: Langfuse or LangSmith metadata, OpenTelemetry span attributes
        (`span.set_attributes(u.attributes("support.answer"))`). Unknown values are left out."""
        values = {
            "call_site": call_site,
            "provider": self.provider,
            "model": self.model,
            "hit_rate": self.hit_rate,
            "input_tokens": self.input,
            "cache_read_tokens": self.cache_read,
            "cache_write_tokens": self.cache_write,
            "output_tokens": self.output,
            "est_cost_usd": self.est_cost,
            "saved_usd": self.saved,
            "miss_reason": self.miss_reason,
        }
        return {prefix + k: v for k, v in values.items() if v is not None}

    def __add__(self, other: Usage) -> Usage:
        cost = None if self.est_cost is None or other.est_cost is None else self.est_cost + other.est_cost
        saved = None if self.saved is None or other.saved is None else self.saved + other.saved
        return replace(
            self,
            input=self.input + other.input,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write,
            output=self.output + other.output,
            est_cost=cost,
            saved=saved,
            miss_reason=None,
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


def _miss(d: dict[str, Any]) -> str | None:
    """Anthropic `diagnostics.cache_miss_reason.type` or OpenAI `prompt_cache_diagnostics` reason, if any."""
    diag = d.get("diagnostics")
    if isinstance(diag, dict) and isinstance(diag.get("cache_miss_reason"), dict):
        return str(diag["cache_miss_reason"].get("type") or "") or None
    oc = d.get("prompt_cache_diagnostics")
    if isinstance(oc, dict) and oc.get("type") not in (None, "cache_hit"):
        return str(oc.get("reason") or oc.get("type"))
    return None


def usage(response: Any, model: str | None = None) -> Usage:
    """Normalize an Anthropic, OpenAI (Responses or Chat), Gemini, LiteLLM or LangChain AIMessage response."""
    d = plain(response)
    if not isinstance(d, dict):
        raise ValueError("unrecognised response: expected an SDK response object or dict")
    u = _usage(d, model)
    reason = _miss(d)
    return replace(u, miss_reason=reason) if reason else u


def _usage(d: dict[str, Any], model: str | None) -> Usage:
    name = str(model or d.get("model") or d.get("model_version") or d.get("modelVersion") or "")
    lc = d.get("usage_metadata")
    if isinstance(lc, dict) and "input_tokens" in lc:  # LangChain AIMessage: input_tokens includes cache tokens
        return _langchain(d, lc, model)
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


def _langchain(d: dict[str, Any], lc: dict[str, Any], model: str | None) -> Usage:
    rm = d.get("response_metadata") or {}
    name = str(model or rm.get("model_name") or rm.get("model") or "")
    # priority/flex tiers prefix the keys; Anthropic reports TTL-split writes and then sets cache_creation to 0
    det = {
        k.removeprefix("priority_").removeprefix("flex_"): v for k, v in (lc.get("input_token_details") or {}).items()
    }
    long_write = _n(det, "ephemeral_1h_input_tokens")
    write = _n(det, "cache_creation") + _n(det, "ephemeral_5m_input_tokens") + long_write
    provider = {"google_genai": "gemini"}.get(rm.get("model_provider", ""), rm.get("model_provider", ""))
    # ponytail: LangChain doesn't split OpenAI 12h writes from 30m ones, so they're priced at the 30m rate
    out = _n(lc, "output_tokens")
    return _priced(
        provider or facts.provider_of(name), name, _n(lc, "input_tokens"), _n(det, "cache_read"), write, out, long_write
    )


def _priced(provider: str, model: str, total: int, read: int, write: int, out: int, long_write: int = 0) -> Usage:
    m = facts.find(model)
    cost = saved = None
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
        # ponytail: Gemini explicit-cache storage is billed hourly, not per call, so it isn't in est_cost/saved
        saved = (total * m.input + out * m.output) / 1e6 - cost
    return Usage(provider, model, total, read, write, out, cost, saved)


_HEADER = (
    "call site",
    "calls",
    "hit rate",
    "input",
    "cache read",
    "cache write",
    "output",
    "est $",
    "saved $",
    "top drift",
)


class Stats:
    """Usage totals per call site, in memory."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.totals: dict[str, Usage] = {}
        self.misses: dict[str, dict[str, int]] = {}  # provider-reported miss reasons per call site

    def add(self, call_site: str, u: Usage) -> None:
        self.calls[call_site] = self.calls.get(call_site, 0) + 1
        self.totals[call_site] = (
            self.totals[call_site] + u if call_site in self.totals else replace(u, miss_reason=None)
        )
        if u.miss_reason:
            counts = self.misses.setdefault(call_site, {})
            counts[u.miss_reason] = counts.get(u.miss_reason, 0) + 1

    def _note(self, site: str, note: str) -> str:
        provider = _top(self.misses[site]) if self.misses.get(site) else ""
        return " | ".join(n for n in (note, provider) if n)

    def table(self, notes: dict[str, str] | None = None) -> str:
        rows = [list(_HEADER)]
        for site, u in sorted(self.totals.items()):
            cost = "n/a" if u.est_cost is None else f"{u.est_cost:.4f}"
            saved = "n/a" if u.saved is None else f"{u.saved:.4f}"
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
                    saved,
                    self._note(site, (notes or {}).get(site, "")),
                ]
            )
        widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
        return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows)


def _top(counts: dict[str, int]) -> str:
    reason, n = max(counts.items(), key=lambda kv: kv[1])
    return f"provider: {reason} x{n}"


def record(call_site: str, request: Any, response: Any) -> dict[str, Any]:
    """One JSONL line for `cachemaxxing report`. The library never writes files; you do."""
    return {"call_site": call_site, "request": jsonable(request), "response": jsonable(response)}
