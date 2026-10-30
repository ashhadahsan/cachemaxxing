"""Gemini explicit caches through your own google-genai client: the library's only I/O."""

from __future__ import annotations

import time
from typing import Any

from .economics import should_cache
from .prompt import Prompt

_LIVE: dict[str, tuple[str, float]] = {}  # ponytail: per-process memo; other processes match on display_name
_MARGIN = 30.0  # seconds a cache must still live to be reused


def _plan(
    p: Prompt, model: str, reuses: int, interval_s: float, tokens: int | None
) -> tuple[str, dict[str, Any]] | None:
    d = should_cache(tokens or p.est_prefix_tokens(), reuses, "gemini", model, interval_s=interval_s)
    if not d.cache or d.ttl is None:
        return None
    key = f"cmx-{p.call_site}-{model.rsplit('/', 1)[-1]}-{p.prefix_hash()}"
    return key, {"display_name": key, "ttl": d.ttl, **p.gemini_prefix()}


def _alive(c: Any, key: str) -> bool:
    exp = getattr(c, "expire_time", None)
    return getattr(c, "display_name", None) == key and exp is not None and exp.timestamp() - time.time() > _MARGIN


def _remember(key: str, c: Any) -> str:
    _LIVE[key] = (str(c.name), c.expire_time.timestamp())
    return str(c.name)


def _memo(key: str) -> str | None:
    hit = _LIVE.get(key)
    return hit[0] if hit and hit[1] - time.time() > _MARGIN else None


def gemini_cache(
    client: Any,
    p: Prompt,
    model: str,
    *,
    expected_reuses: int,
    interval_s: float = 60.0,
    prefix_tokens: int | None = None,
) -> str | None:
    """Name of a live explicit cache holding p's static prefix, created only if should_cache() says it pays.
    Use it as p.gemini(model, cached_content=name). None means stay on implicit caching."""
    plan = _plan(p, model, expected_reuses, interval_s, prefix_tokens)
    if plan is None:
        return None
    key, config = plan
    if name := _memo(key):
        return name
    for c in client.caches.list():
        if _alive(c, key):
            return _remember(key, c)
    return _remember(key, client.caches.create(model=model, config=config))


async def gemini_cache_async(
    client: Any,
    p: Prompt,
    model: str,
    *,
    expected_reuses: int,
    interval_s: float = 60.0,
    prefix_tokens: int | None = None,
) -> str | None:
    """Async twin of gemini_cache, using client.aio."""
    plan = _plan(p, model, expected_reuses, interval_s, prefix_tokens)
    if plan is None:
        return None
    key, config = plan
    if name := _memo(key):
        return name
    async for c in await client.aio.caches.list():
        if _alive(c, key):
            return _remember(key, c)
    return _remember(key, await client.aio.caches.create(model=model, config=config))
