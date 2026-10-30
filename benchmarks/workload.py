"""Shared benchmark workloads: 8-turn support conversations over a ~6k-token stable prefix.

Workloads: "chat" (static product docs) and "rag" (static policy + FAQ, fresh retrieved chunks every turn).
Every arm sends the same information:
- "naive": the four habits from the README: a timestamp and request id at the top of the system prompt, tools
  in a different order on every call, JSON with varying key order, history re-rendered every call ("asked Ns
  ago"); in "rag" the chunks also go into the system prompt, as many apps do.
- "clean": the same content laid out well (stable system prompt, fixed tool order, append-only history,
  per-turn context in the last user message), using only the provider's built-in automatic caching.
- "cachemaxxing": the same content through cachemaxxing.Prompt."""

from __future__ import annotations

import json
import random
import re
import time
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from cachemaxxing import Usage

DATA = Path(__file__).parent / "data"
RUN = uuid.uuid4().hex[:8]  # new static prefix per invocation, like a fresh deploy: every benchmark starts cold
_POLICY = (DATA / "policy.md").read_text(encoding="utf-8")
POLICY = f"Knowledge base build {RUN}.\n\n" + _POLICY


def policy(arm: str) -> str:
    """The system policy with a per-arm build id, so no arm can read a cache another arm wrote."""
    return f"Knowledge base build {RUN}/{arm}.\n\n" + _POLICY


DOCS = (DATA / "docs.md").read_text(encoding="utf-8")
TOOLS: list[dict[str, Any]] = json.loads((DATA / "tools.json").read_text())
QUESTIONS: list[str] = json.loads((DATA / "questions.json").read_text())
PROFILE = {"plan": "pro", "region": "eu", "seats": 12, "since": "2024-03-01"}
HABITS = ["timestamp + request id atop system", "tool order varies", "JSON key order varies", "history re-rendered"]
ARMS = ("naive", "clean", "cachemaxxing")
SECTIONS = [s.strip() for s in re.split(r"\n(?=## )", DOCS) if s.strip().startswith("## ")]
RAG_STATIC = [s for s in SECTIONS if s.startswith(("## Models", "## FAQ"))]  # always in context
CORPUS = [s for s in SECTIONS if s not in RAG_STATIC]  # retrieved per question


def retrieve(question: str, k: int = 3) -> list[str]:
    q = Counter(re.findall(r"[a-z0-9]+", question.lower()))

    def score(chunk: str) -> int:
        c = Counter(re.findall(r"[a-z0-9]+", chunk.lower()))
        return sum(min(n, c[w]) for w, n in q.items())

    return sorted(CORPUS, key=lambda chunk: -score(chunk))[:k]


def layout(workload: str, question: str) -> tuple[list[str], list[str]]:
    """(static context, per-turn context) for the clean and cachemaxxing arms."""
    per_turn = [volatile(), json.dumps(PROFILE, sort_keys=True)]
    if workload == "rag":
        return RAG_STATIC, [*per_turn, *retrieve(question)]
    return [DOCS], per_turn


CUSTOMERS = ["Ana", "Ben", "Chen", "Dee", "Eli"]


def questions(rep: int) -> list[str]:
    """Each rep is a different customer's conversation: histories differ, only the static prefix is shared."""
    qs = list(QUESTIONS)
    qs[0] = f"Hi, this is {CUSTOMERS[rep % len(CUSTOMERS)]}. {qs[0]}"
    return qs


def volatile() -> str:
    return f"Current time: {datetime.now(UTC).isoformat()}\nRequest id: {uuid.uuid4()}"


def naive_system(workload: str = "chat", question: str = "") -> str:
    profile = dict(random.sample(list(PROFILE.items()), len(PROFILE)))
    head = f"{volatile()}\nCustomer: {json.dumps(profile)}\n\n{policy('naive')}\n\n"
    if workload == "rag":  # chunks in the system prompt, as many RAG apps do
        return head + "Relevant docs:\n" + "\n\n".join(retrieve(question)) + "\n\n" + "\n\n".join(RAG_STATIC)
    return head + DOCS


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


def projected_usd(input_price: float, output_price: float, turns: int, reps: int, arms: int = 3) -> float:
    # ponytail: 3 chars/token (conservative), zero cache hits assumed, so this is an upper bound
    prefix = (len(POLICY) + len(DOCS)) // 3 + 600
    per_run = sum(prefix + 150 * i for i in range(turns)) * input_price + turns * 64 * output_price
    return arms * reps * per_run / 1e6


def summarize(runs: list[list[Usage]], overhead_usd: float = 0.0) -> dict[str, Any]:
    """Per-arm summary; overhead_usd (e.g. explicit-cache creation + storage) is spread over the conversations."""
    totals = [sum(r[1:], r[0]) for r in runs]
    pct = [round(100 * t.hit_rate, 1) for t in totals]
    usd = [round((t.est_cost or 0.0) + overhead_usd / len(runs), 6) for t in totals]
    return {
        "cached_pct": {"mean": round(sum(pct) / len(pct), 1), "min": min(pct), "max": max(pct)},
        "est_usd": {"mean": round(sum(usd) / len(usd), 6), "min": min(usd), "max": max(usd)},
        "runs": [
            {"input": t.input, "cache_read": t.cache_read, "cache_write": t.cache_write, "output": t.output}
            for t in totals
        ],
    }


def write_results(
    provider: str,
    model: str,
    sdk: str,
    turns: int,
    arms: dict[str, list[list[Usage]]],
    overhead_usd: dict[str, float] | None = None,
    workload: str = "chat",
    arms_meaning: dict[str, str] | None = None,
) -> Path:
    out = Path(__file__).parent / "results" / workload / f"{model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "provider": provider,
        "model": model,
        "workload": workload,
        "date": datetime.now(UTC).date().isoformat(),
        "sdk": f"{sdk} {version(sdk)}",
        "cachemaxxing": version("cachemaxxing"),
        "setup": {
            "turns": turns,
            "conversations": len(next(iter(arms.values()))),
            "note": "fresh static prefix per invocation (first conversation cold); one customer per conversation",
            "naive_habits": HABITS,
            "arms": arms_meaning
            or {
                "naive": "the four habits",
                "clean": "same content, stable layout, provider's automatic caching only",
                "cachemaxxing": "cachemaxxing.Prompt adapters",
            },
        },
        "arms": {name: summarize(runs, (overhead_usd or {}).get(name, 0.0)) for name, runs in arms.items()},
    }
    if overhead_usd:
        doc["explicit_cache_overhead_usd"] = overhead_usd
    out.write_text(json.dumps(doc, indent=2) + "\n")
    return out


def run_benchmark(
    provider: str,
    default_model: str,
    sdk: str,
    make_client: Callable[[], Any],
    request: Callable[[Any, str, str, str, str, list[tuple[str, str, float]], int], dict[str, Any]],
    call: Callable[[Any, dict[str, Any]], Any],
    text: Callable[[Any], str],
    overhead: Callable[[Any, Any], dict[str, float]] | None = None,
) -> None:
    """CLI shared by the bench_<provider>.py scripts: every arm, `reps` conversations of `turns` turns each."""
    import argparse

    from cachemaxxing import usage
    from cachemaxxing.facts import MODELS

    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", choices=("chat", "rag"), default="chat")
    ap.add_argument("--model", default=default_model)
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--max-usd", type=float, default=1.0)
    args = ap.parse_args()
    arms = args.arms.split(",")
    m = MODELS[args.model]
    budget = Budget(args.max_usd, projected_usd(m.input, m.output, args.turns, args.reps, len(arms)))
    client = make_client()
    results: dict[str, list[list[Usage]]] = {}
    for arm in arms:
        runs = []
        for rep in range(args.reps):
            done: list[tuple[str, str, float]] = []
            rows: list[Usage] = []
            for q in questions(rep)[: args.turns]:
                kw = request(client, arm, args.workload, args.model, q, done, args.turns * args.reps)
                resp = call(client, kw)
                u = usage(resp)
                budget.spend(u)
                rows.append(u)
                done.append((q, text(resp) or "(no answer)", time.time()))
            runs.append(rows)
        results[arm] = runs
    extra = overhead(client, m) if overhead else {}
    out = write_results(provider, args.model, sdk, args.turns, results, extra or None, args.workload)
    print(out, f"spent ~${budget.spent + sum(extra.values()):.4f}")
