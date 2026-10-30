"""cachemaxxing diff A.json B.json | cachemaxxing report LOG.jsonl [--min-hit-rate X]"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .diff import diff
from .usage import Stats, usage

NO_READ = "prefix ok, no cache read (TTL expired, below minimum, or routing)"


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _report(log: str, min_hit_rate: float | None) -> int:
    stats = Stats()
    last: dict[str, Any] = {}
    drift: dict[str, Counter[str]] = {}
    for line in Path(log).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        site, u = rec.get("call_site", "default"), usage(rec["response"])
        stats.add(site, u)
        if site in last:
            div = diff(last[site], rec["request"])
            if (div is None or div.hint == "last turn") and u.cache_read == 0:
                drift.setdefault(site, Counter())[NO_READ] += 1
            elif div is not None and div.hint != "last turn":
                path = re.sub(r"\[\d+\]", "[]", div.path)  # group growing conversations together
                drift.setdefault(site, Counter())[f"{path} ({div.hint or '?'})"] += 1
        last[site] = rec["request"]
    if not stats.totals:
        raise ValueError(f"no records in {log}")
    notes = {site: f"{key} x{n}" for site, c in drift.items() for key, n in c.most_common(1)}
    print(stats.table(notes))
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
    args = ap.parse_args(argv)
    try:
        if args.cmd == "diff":
            div = diff(_load(args.a), _load(args.b))
            print(div if div else "no divergence: B repeats all of A")
            return 1 if div else 0
        return _report(args.log, args.min_hit_rate)
    except (OSError, ValueError, KeyError) as e:
        print(f"cachemaxxing: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
