"""Gemini: naive vs cachemaxxing on gemini-3.8-flash. Needs GEMINI_API_KEY.

The cachemaxxing arm follows the library's Gemini strategy: an explicit cache via gemini_cache() when
should_cache() says it pays (it does here), implicit caching otherwise. Cache creation and storage are
charged to the arm, and the cache is deleted afterwards.

uv run --env-file .env python benchmarks/bench_gemini.py --max-usd 1"""

import argparse
import time
from typing import Any

import workload as w
from google import genai

from cachemaxxing import Prompt, Usage, gemini_cache, usage
from cachemaxxing.facts import MODELS

MODEL = "gemini-3.8-flash"


def contents(turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, a in turns:
        out += [{"role": "user", "parts": [{"text": q}]}, {"role": "model", "parts": [{"text": a}]}]
    return out


CACHES: set[str] = set()


def run(client: genai.Client, arm: str, turns: int, budget: w.Budget, rep: int, reuses: int) -> list[Usage]:
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
            name = gemini_cache(client, p, MODEL, expected_reuses=reuses, interval_s=10)
            if name:
                CACHES.add(name)
            kw = p.gemini(MODEL, cached_content=name)
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
        arm: [run(client, arm, args.turns, budget, rep, args.turns * args.reps) for rep in range(args.reps)]
        for arm in ("naive", "cachemaxxing")
    }
    overhead = 0.0
    for name in CACHES:  # creation at the input rate + storage for the cache's whole lifetime, then delete it
        c = client.caches.get(name=name)
        tokens = (c.usage_metadata.total_token_count if c.usage_metadata else 0) or 0
        hours = (c.expire_time - c.create_time).total_seconds() / 3600 if c.expire_time and c.create_time else 1.0
        overhead += tokens * (m.input + (m.storage_hour or 0.0) * hours) / 1e6
        client.caches.delete(name=name)
    out = w.write_results("gemini", MODEL, "google-genai", args.turns, arms, {"cachemaxxing": round(overhead, 6)})
    print(out, f"spent ~${budget.spent + overhead:.4f} (explicit cache overhead ${overhead:.4f})")
