"""Gemini: naive vs cachemaxxing on gemini-3.8-flash. Needs GEMINI_API_KEY.

uv run --env-file .env python benchmarks/bench_gemini.py --max-usd 1"""

import argparse
import time
from typing import Any

import workload as w
from google import genai

from cachemaxxing import Prompt, Usage, usage
from cachemaxxing.facts import MODELS

MODEL = "gemini-3.8-flash"


def contents(turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, a in turns:
        out += [{"role": "user", "parts": [{"text": q}]}, {"role": "model", "parts": [{"text": a}]}]
    return out


def run(client: genai.Client, arm: str, turns: int, budget: w.Budget, rep: int) -> list[Usage]:
    done: list[tuple[str, str, float]] = []
    rows = []
    for q in w.questions(rep)[:turns]:
        if arm == "naive":
            history = contents(w.naive_turns(done))
            kw: dict[str, Any] = {
                "model": MODEL,
                "contents": [*history, {"role": "user", "parts": [{"text": q}]}],
                "config": {
                    "system_instruction": w.naive_system(),
                    "tools": [{"function_declarations": w.naive_tools()}],
                },
            }
        else:
            p = Prompt("bench").tools([{"function_declarations": w.TOOLS}]).system(w.POLICY).context(w.DOCS)
            p.history(contents([(x, a) for x, a, _ in done])).retrieved([w.volatile(), w.PROFILE]).user(q)
            kw = p.gemini(MODEL)
        kw["config"]["max_output_tokens"] = 64
        resp = client.models.generate_content(**kw)
        u = usage(resp)
        budget.spend(u)
        rows.append(u)
        done.append((q, resp.text or "", time.time()))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=8)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-usd", type=float, default=1.0)
    args = ap.parse_args()
    m = MODELS[MODEL]
    budget = w.Budget(args.max_usd, w.projected_usd(m.input, m.output, args.turns, args.reps))
    client = genai.Client()
    arms = {
        arm: [run(client, arm, args.turns, budget, rep) for rep in range(args.reps)]
        for arm in ("naive", "cachemaxxing")
    }
    print(w.write_results("gemini", MODEL, "google-genai", args.turns, arms), f"spent ~${budget.spent:.4f}")
