"""Normalize provider usage into one shape, price it, aggregate it per call site."""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Any

from . import facts
from .canon import jsonable, plain
from .diff import NO_READ, NO_READ_WHY, Divergence, diff

_log = logging.getLogger("cachemaxxing")


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
    """Normalize an Anthropic, OpenAI (Responses or Chat), Gemini, LiteLLM or LangChain AIMessage response.
    Raises ValueError for anything it can't read."""
    d = plain(response)
    if not isinstance(d, dict):
        raise ValueError("unrecognised response: expected an SDK response object or dict")
    try:
        u = _usage(d, model)
    except (AttributeError, TypeError) as e:  # a field of an unexpected type
        raise ValueError(f"unrecognised response: {e}") from e
    reason = _miss(d)
    return replace(u, miss_reason=reason) if reason else u


def _usage(d: dict[str, Any], model: str | None) -> Usage:
    stored = d.get("cachemaxxing_usage")
    if isinstance(stored, dict):  # a response that record(..., redact=...) reduced to its counts
        return Usage(**stored)
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
    """Usage totals per call site, in memory. Safe to share between threads.

    Give `add` each call's request too and Stats diagnoses misses as they happen: it compares the request with
    the previous one from the same call site, counts what broke the cached prefix in `drift`, shows the top
    cause in `table()`, and logs a warning with the exact change and the fix the first time each cause shows
    up for a call site. `warn=False` keeps the diagnosis and drops the warnings."""

    def __init__(self, *, warn: bool = True) -> None:
        self.calls: dict[str, int] = {}
        self.totals: dict[str, Usage] = {}
        self.misses: dict[str, dict[str, int]] = {}  # provider-reported miss reasons per call site
        self.drift: dict[str, Counter[str]] = {}  # what broke the cached prefix, per call site
        self.warn = warn
        self._examples: dict[tuple[str, str], Divergence] = {}  # first example of each drift
        self._last: dict[str, Any] = {}  # previous request per call site
        self._lock = threading.Lock()

    def add(self, call_site: str, u: Usage, request: Any = None) -> Divergence | None:
        """Count one call. With `request` (the kwargs you sent), also diagnose it: returns the Divergence when
        this request broke the previous one's cached prefix, else None."""
        current = None if request is None else jsonable(request)  # a copy: callers often edit their lists later
        with self._lock:
            self.calls[call_site] = self.calls.get(call_site, 0) + 1
            self.totals[call_site] = (
                self.totals[call_site] + u if call_site in self.totals else replace(u, miss_reason=None)
            )
            if u.miss_reason:
                counts = self.misses.setdefault(call_site, {})
                counts[u.miss_reason] = counts.get(u.miss_reason, 0) + 1
            previous = self._last.get(call_site)
            if current is not None:
                self._last[call_site] = current
        if previous is None or current is None:
            return None
        div = diff(previous, current)
        if div is not None and div.hint != "last turn":
            note, why = _label(div), f"the cached prefix broke: {div}"
        elif u.cache_read == 0:
            note, why, div = NO_READ, f"{NO_READ}. {NO_READ_WHY}", None
        else:
            return None
        with self._lock:
            seen = self.drift.setdefault(call_site, Counter())
            first = note not in seen
            seen[note] += 1
            if div is not None:
                self._examples.setdefault((call_site, note), div)
        if first and self.warn:
            _log.warning("%s: %s", call_site, why)
        return div

    def _note(self, site: str, note: str) -> str:
        provider = _top(self.misses[site]) if self.misses.get(site) else ""
        return " | ".join(n for n in (note, provider) if n)

    def table(self, notes: dict[str, str] | None = None) -> str:
        rows = [list(_HEADER)]
        with self._lock:
            totals, calls = sorted(self.totals.items()), dict(self.calls)
            top = {site: f"{key} x{n}" for site, c in self.drift.items() for key, n in c.most_common(1)}
        notes = {**top, **(notes or {})}
        for site, u in totals:
            cost = "n/a" if u.est_cost is None else f"{u.est_cost:.4f}"
            saved = "n/a" if u.saved is None else f"{u.saved:.4f}"
            rows.append(
                [
                    site,
                    str(calls[site]),
                    f"{u.hit_rate:.1%}",
                    f"{u.input:,}",
                    f"{u.cache_read:,}",
                    f"{u.cache_write:,}",
                    f"{u.output:,}",
                    cost,
                    saved,
                    self._note(site, notes.get(site, "")),
                ]
            )
        widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
        return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows)


def _label(div: Divergence) -> str:
    """A drift's name in reports: its path without list indexes, so a growing conversation groups together."""
    path = re.sub(r"\[\d+\]", "[]", div.path)
    return f"{path} ({div.hint or '?'})"


def _top(counts: dict[str, int]) -> str:
    reason, n = max(counts.items(), key=lambda kv: kv[1])
    return f"provider: {reason} x{n}"


_KEEP = {"model", "role", "type"}  # values diff needs to line requests up; never prompt text


def _redacted(x: Any, redact: Callable[[str], str], keep: set[str] = _KEEP) -> Any:
    if isinstance(x, dict):
        return {
            k: v
            if k in keep and isinstance(v, str)
            else _redacted(v, redact, keep | {"name"} if k == "tools" else keep)
            for k, v in x.items()
        }
    if isinstance(x, list):
        return [_redacted(v, redact, keep) for v in x]
    return redact(x) if isinstance(x, str) else x


def record(
    call_site: str, request: Any, response: Any, *, redact: Callable[[str], str] | None = None
) -> dict[str, Any]:
    """One JSONL line for `cachemaxxing report`. The library never writes files; you do.
    `call_site` is your name for the place in your code that made the call (see `Prompt`).

    With `redact`, the line holds no prompt or output text: every string in the request goes through
    `redact` (except model names, roles, block types and tool names), and the response is reduced to its
    token counts and cost. Raises ValueError if the response can't be read (see `usage`)."""
    if redact is None:
        return {"call_site": call_site, "request": jsonable(request), "response": jsonable(response)}
    counts = asdict(usage(response))
    return {
        "call_site": call_site,
        "request": _redacted(jsonable(request), redact),
        "response": {"cachemaxxing_usage": counts},
    }
