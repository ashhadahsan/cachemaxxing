"""`cachemaxxing report LOG --html PATH`: the report as one self-contained page.

The data is embedded in the page and drawn by a little inline JavaScript: no CDN, no network requests,
so the prompts in your log never leave your machine. The page does contain ~80-character snippets of
your prompts around each divergence; share it as you would share the log."""

from __future__ import annotations

import json
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from typing import Any

from . import facts
from .diff import Divergence
from .usage import Stats, Usage


def _numbers(u: Usage) -> dict[str, Any]:
    return {
        "hit_rate": u.hit_rate,
        "input": u.input,
        "cache_read": u.cache_read,
        "cache_write": u.cache_write,
        "output": u.output,
        "est_cost": u.est_cost,
        "saved": u.saved,
    }


def _example(d: Divergence | None) -> dict[str, Any] | None:
    return None if d is None else {"path": d.path, "hint": d.hint, "a": d.a, "b": d.b, "tokens": d.prefix_chars // 4}


def data(
    source: str,
    stats: Stats,
    drift: dict[str, Counter[str]],
    examples: dict[tuple[str, str], Divergence],
    calls: list[tuple[str, Usage, str]],
    min_hit_rate: float | None,
) -> dict[str, Any]:
    """Everything the page shows, as JSON-ready data."""
    sites = sorted(stats.totals)
    shown = Counter(s for s, _, _ in calls)
    index = {s: i for i, s in enumerate(sites)}
    try:
        v = version("cachemaxxing")
    except PackageNotFoundError:  # running from a source tree
        v = ""
    return {
        "source": source,
        "version": v,
        "verified": facts.VERIFIED,
        "min_hit_rate": min_hit_rate,
        "sites": [
            {
                "name": s,
                "calls": stats.calls[s],
                "shown": shown[s],  # calls drawn in the chart
                **_numbers(stats.totals[s]),
                "drift": [
                    {"label": k, "count": n, "example": _example(examples.get((s, k)))}
                    for k, n in drift.get(s, Counter()).most_common(5)
                ],
                "misses": sorted(stats.misses.get(s, {}).items(), key=lambda kv: -kv[1]),
            }
            for s in sites
        ],
        "calls": [
            [index[s], round(u.hit_rate, 4), u.input, u.cache_read, u.cache_write, u.output, note, u.miss_reason]
            for s, u, note in calls
        ],
    }


def render(page: dict[str, Any]) -> str:
    """The dashboard HTML for `data(...)`."""
    template = (files("cachemaxxing") / "dashboard.html").read_text(encoding="utf-8")
    blob = json.dumps(page, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")  # no </script>
    return template.replace("{{DATA}}", blob, 1)
