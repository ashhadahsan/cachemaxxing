"""Shared benchmark workload: an 8-turn support chat over a ~6k-token stable prefix.

Both arms send the same information. "naive" has the four habits from the README:
1. a timestamp and request id at the top of the system prompt,
2. tools in a different order on every call,
3. JSON (the customer profile) serialized with varying key order,
4. history re-rendered on every call ("asked Ns ago").
"cachemaxxing" lays the same content out with cachemaxxing.Prompt."""

from __future__ import annotations

import json
import random
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from cachemaxxing import Usage

DATA = Path(__file__).parent / "data"
RUN = uuid.uuid4().hex[:8]  # new static prefix per invocation, like a fresh deploy: every benchmark starts cold
POLICY = f"Knowledge base build {RUN}.\n\n" + (DATA / "policy.md").read_text(encoding="utf-8")
DOCS = (DATA / "docs.md").read_text(encoding="utf-8")
TOOLS: list[dict[str, Any]] = json.loads((DATA / "tools.json").read_text())
QUESTIONS: list[str] = json.loads((DATA / "questions.json").read_text())
PROFILE = {"plan": "pro", "region": "eu", "seats": 12, "since": "2024-03-01"}
HABITS = ["timestamp + request id atop system", "tool order varies", "JSON key order varies", "history re-rendered"]
CUSTOMERS = ["Ana", "Ben", "Chen", "Dee", "Eli"]


def questions(rep: int) -> list[str]:
    """Each rep is a different customer's conversation: histories differ, only the static prefix is shared."""
    qs = list(QUESTIONS)
    qs[0] = f"Hi, this is {CUSTOMERS[rep % len(CUSTOMERS)]}. {qs[0]}"
    return qs


def volatile() -> str:
    return f"Current time: {datetime.now(UTC).isoformat()}\nRequest id: {uuid.uuid4()}"


def naive_system() -> str:
    profile = dict(random.sample(list(PROFILE.items()), len(PROFILE)))
    return f"{volatile()}\nCustomer: {json.dumps(profile)}\n\n{POLICY}\n\n{DOCS}"


def naive_tools() -> list[dict[str, Any]]:
    return random.sample(TOOLS, len(TOOLS))


def naive_turns(turns: list[tuple[str, str, float]]) -> list[tuple[str, str]]:
    """(question, answer, asked_at) -> re-rendered with a relative age, as chat UIs often do."""
    now = time.time()
    return [(f"(asked {now - t:.0f}s ago) {q}", a) for q, a, t in turns]


class Budget:
    """Stops the run before (projected) or as soon as (running) spend exceeds max_usd."""

    def __init__(self, max_usd: float, projected: float) -> None:
        print(f"projected worst case ${projected:.4f} (cap ${max_usd})")
        if projected > max_usd:
            raise SystemExit(f"projected ${projected:.2f} exceeds --max-usd {max_usd}")
        self.max_usd, self.spent = max_usd, 0.0

    def spend(self, u: Usage) -> None:
        self.spent += u.est_cost or 0.0
        if self.spent > self.max_usd:
            raise SystemExit(f"spent ${self.spent:.4f} > --max-usd {self.max_usd}; stopping")


def projected_usd(input_price: float, output_price: float, turns: int, reps: int) -> float:
    # ponytail: 4 chars/token estimate, zero cache hits assumed, so this is an upper bound
    prefix = (len(POLICY) + len(DOCS)) // 4 + 600
    per_run = sum(prefix + 150 * i for i in range(turns)) * input_price + turns * 64 * output_price
    return 2 * reps * per_run / 1e6  # 2 arms


def summarize(runs: list[list[Usage]]) -> dict[str, Any]:
    totals = [sum(r[1:], r[0]) for r in runs]
    pct = [round(100 * t.hit_rate, 1) for t in totals]
    usd = [round(t.est_cost or 0.0, 6) for t in totals]
    return {
        "cached_pct": {"mean": round(sum(pct) / len(pct), 1), "min": min(pct), "max": max(pct)},
        "est_usd": {"mean": round(sum(usd) / len(usd), 6), "min": min(usd), "max": max(usd)},
        "runs": [
            {"input": t.input, "cache_read": t.cache_read, "cache_write": t.cache_write, "output": t.output}
            for t in totals
        ],
    }


def write_results(provider: str, model: str, sdk: str, turns: int, arms: dict[str, list[list[Usage]]]) -> Path:
    out = Path(__file__).parent / "results" / f"{provider}.json"
    out.parent.mkdir(exist_ok=True)
    doc = {
        "provider": provider,
        "model": model,
        "date": datetime.now(UTC).date().isoformat(),
        "sdk": f"{sdk} {version(sdk)}",
        "cachemaxxing": version("cachemaxxing"),
        "workload": {
            "turns": turns,
            "conversations": len(next(iter(arms.values()))),
            "note": "fresh static prefix per invocation (first conversation cold); one customer per conversation",
            "naive_habits": HABITS,
        },
        "arms": {name: summarize(runs) for name, runs in arms.items()},
    }
    out.write_text(json.dumps(doc, indent=2) + "\n")
    return out
