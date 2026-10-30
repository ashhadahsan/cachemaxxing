"""Anthropic: naive vs cachemaxxing on claude-haiku-5-5. Needs ANTHROPIC_API_KEY.

uv run --env-file .env python benchmarks/bench_anthropic.py --max-usd 1"""

import argparse
import time
from typing import Any

import anthropic
import workload as w

from cachemaxxing import Prompt, Usage, usage
from cachemaxxing.facts import MODELS

MODEL = "claude-haiku-5-5"


def tools(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in defs]


def contents(turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, a in turns:
        out += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    return out


def run(client: anthropic.Anthropic, arm: str, turns: int, budget: w.Budget) -> list[Usage]:
    done: list[tuple[str, str, float]] = []
    rows = []
    for q in w.QUESTIONS[:turns]:
        if arm == "naive":
            kw: dict[str, Any] = {
                "model": MODEL,
                "system": w.naive_system(),
                "tools": tools(w.naive_tools()),
                "messages": [*contents(w.naive_turns(done)), {"role": "user", "content": q}],
            }
        else:
            p = Prompt("bench").tools(tools(w.TOOLS)).system(w.POLICY).context(w.DOCS)
            p.history(contents([(x, a) for x, a, _ in done])).retrieved([w.volatile(), w.PROFILE]).user(q)
            kw = p.anthropic(MODEL)
        resp = client.messages.create(max_tokens=64, **kw)
        u = usage(resp)
        budget.spend(u)
        rows.append(u)
        answer = "".join(b.text for b in resp.content if b.type == "text")
        done.append((q, answer or "(no text)", time.time()))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-usd", type=float, default=1.0)
    args = ap.parse_args()
    m = MODELS[MODEL]
    budget = w.Budget(args.max_usd, w.projected_usd(m.input, m.output, args.turns, args.reps))
    client = anthropic.Anthropic()
    arms = {arm: [run(client, arm, args.turns, budget) for _ in range(args.reps)] for arm in ("naive", "cachemaxxing")}
    print(w.write_results("anthropic", MODEL, "anthropic", args.turns, arms), f"spent ~${budget.spent:.4f}")
