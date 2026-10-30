"""Does explicit caching pay? Pure arithmetic over facts.MODELS."""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import facts

TTL_SECONDS = {"5m": 300, "1h": 3600, "30m": 1800, "12h": 43200}


@dataclass(frozen=True)
class Decision:
    cache: bool
    ttl: str | None  # "5m"/"1h" (Anthropic), "30m"/"12h" (OpenAI), "<n>s" (Gemini explicit cache)
    saving: float  # expected USD saved versus not caching; negative means caching loses money
    reason: str


def should_cache(
    prefix_tokens: int, expected_reuses: int, provider: str, model: str, *, interval_s: float = 60.0
) -> Decision:
    """Whether caching a prefix of `prefix_tokens` pays when it is reused `expected_reuses` times,
    `interval_s` seconds apart (start to start)."""
    m = facts.find(model)
    if m is None or m.provider != provider:
        raise ValueError(f"unknown {provider} model {model!r}; add it to cachemaxxing.facts.MODELS")
    if m.long_context and prefix_tokens > m.long_context[0]:
        m = m.long_context[1]
    if prefix_tokens < m.min_tokens:
        return Decision(False, None, 0.0, f"{prefix_tokens} tokens is below the {m.min_tokens}-token minimum")
    t, n = prefix_tokens / 1e6, expected_reuses
    ttl: str | None
    if provider == "gemini":
        if m.storage_hour is None:
            return Decision(False, None, 0.0, f"{model} has no explicit caching; implicit caching is automatic")
        seconds = max(60, math.ceil(interval_s * n))
        ttl, cost = f"{seconds}s", t * m.input + n * t * m.cache_read + t * m.storage_hour * seconds / 3600
    elif not m.cache_write:  # automatic caching without a write premium
        ttl, cost = None, t * m.input + n * t * m.cache_read
    else:
        fits = [k for k in m.cache_write if TTL_SECONDS[k] >= interval_s]
        if not fits:
            return Decision(False, None, 0.0, f"reuses {interval_s:g}s apart outlive the longest TTL")
        ttl = min(fits, key=TTL_SECONDS.__getitem__)
        cost = t * m.cache_write[ttl] + n * t * m.cache_read
    saving = (1 + n) * t * m.input - cost
    if saving <= 0:
        return Decision(False, None, saving, f"caching costs ${-saving:.6f} more than not caching")
    return Decision(True, ttl, saving, f"saves ${saving:.6f} over {n} reuses")
