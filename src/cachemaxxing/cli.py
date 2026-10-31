"""cachemaxxing diff A.json B.json | cachemaxxing report LOG.jsonl [--min-hit-rate X] [--html PATH] [--strict]"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from collections.abc import Iterator
from itertools import chain
from pathlib import Path
from typing import Any

from . import dashboard
from .diff import NO_READ, NO_READ_WHY, diff
from .usage import Stats, Usage, _label, usage

CHART_CALLS = 5000  # calls per call site drawn in the dashboard; keeps the page small for any log size


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _records(log: str, strict: bool) -> Iterator[tuple[str, dict[str, Any], Usage]]:
    """(call site, request, usage) per readable line, streamed. Unreadable lines are skipped and counted,
    or fatal with strict; a writer may still be appending the last line."""
    skipped, first = 0, ""
    with open(log, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                request = rec["request"]
                if not isinstance(request, dict):
                    raise ValueError("request is not an object")
                yield str(rec.get("call_site", "default")), request, usage(rec["response"])
            except (ValueError, KeyError, AttributeError, TypeError) as e:
                why = f"line {n}: {type(e).__name__}: {e}"
                if strict:
                    raise ValueError(f"{log} {why}") from e
                skipped, first = skipped + 1, first or why
    if skipped:
        print(f"cachemaxxing: skipped {skipped} unreadable line(s) in {log} (first: {first})", file=sys.stderr)


def _report(log: str, min_hit_rate: float | None, html: str | None = None, strict: bool = False) -> int:
    stats = Stats(warn=False)  # the diagnosis is printed below the table instead
    recent: dict[str, deque[tuple[int, str, Usage, str]]] = {}
    for i, (site, request, u) in enumerate(_records(log, strict)):
        div = stats.add(site, u, request=request)
        follow_up_miss = stats.calls[site] > 1 and u.cache_read == 0
        note = _label(div) if div else NO_READ if follow_up_miss else ""
        recent.setdefault(site, deque(maxlen=CHART_CALLS)).append((i, site, u, note))
    if not stats.totals:
        raise ValueError(f"no records in {log}")
    print(stats.table())
    for site, causes in sorted(stats.drift.items()):
        cause, n = causes.most_common(1)[0]
        example = stats._examples.get((site, cause))
        print(f"\n{site}: {cause} on {n} of {stats.calls[site] - 1} follow-up calls")
        print(f"  {example}" if example else f"  {NO_READ_WHY}")
    if html:
        calls = [(site, u, note) for _, site, u, note in sorted(chain(*recent.values()), key=lambda c: c[0])]
        page = dashboard.data(Path(log).name, stats, calls, min_hit_rate)
        Path(html).write_text(dashboard.render(page), encoding="utf-8")
        print(f"wrote {html}", file=sys.stderr)
    low = sorted(s for s, u in stats.totals.items() if min_hit_rate is not None and u.hit_rate < min_hit_rate)
    for s in low:
        print(f"{s}: hit rate {stats.totals[s].hit_rate:.1%} is below --min-hit-rate {min_hit_rate}", file=sys.stderr)
    return 1 if low else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cachemaxxing", description="Find and price prompt-cache misses.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff", help="first point where request B stops repeating request A")
    d.add_argument("a")
    d.add_argument("b")
    r = sub.add_parser("report", help="hit rate, $ and top drift per call site from a JSONL log")
    r.add_argument("log")
    r.add_argument("--min-hit-rate", type=float, help="exit 1 if any call site is below this (0-1)")
    r.add_argument("--html", metavar="PATH", help="also write a self-contained dashboard page here")
    r.add_argument("--strict", action="store_true", help="exit 2 on the first unreadable line instead of skipping it")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "diff":
            div = diff(_load(args.a), _load(args.b))
            print(div if div else "no divergence: B repeats all of A")
            return 1 if div else 0
        return _report(args.log, args.min_hit_rate, args.html, args.strict)
    except (OSError, ValueError, KeyError) as e:
        print(f"cachemaxxing: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
