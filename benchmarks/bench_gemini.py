"""Gemini benchmark: naive vs clean (implicit caching) vs cachemaxxing. Needs GEMINI_API_KEY.

The cachemaxxing arm follows the library's Gemini strategy: an explicit cache via gemini_cache() when
should_cache() says it pays, implicit caching otherwise. Cache creation and storage are charged to the arm,
and the caches are deleted afterwards.

uv run --env-file .env python benchmarks/bench_gemini.py --workload chat|rag"""

from typing import Any

import workload as w
from google import genai

from cachemaxxing import Prompt, gemini_cache

CACHES: set[str] = set()


def history(turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, a in turns:
        out += [{"role": "user", "parts": [{"text": q}]}, {"role": "model", "parts": [{"text": a}]}]
    return out


def request(client: Any, arm: str, workload: str, model: str, q: str, done: list, reuses: int) -> dict[str, Any]:
    plain = [(x, a) for x, a, _ in done]
    if arm == "naive":
        config = {
            "system_instruction": w.naive_system(workload, q),
            "tools": [{"function_declarations": w.naive_tools()}],
        }
        contents = [*history(w.naive_turns(done)), {"role": "user", "parts": [{"text": q}]}]
        return {"model": model, "contents": contents, "config": config}
    static, per_turn = w.layout(workload, q)
    if arm == "clean":  # the same content laid out well, with Gemini's implicit caching only
        config = {
            "system_instruction": "\n\n".join([w.policy("clean"), *static]),
            "tools": [{"function_declarations": w.TOOLS}],
        }
        last = {"role": "user", "parts": [{"text": t} for t in [*per_turn, q]]}
        return {"model": model, "contents": [*history(plain), last], "config": config}
    p = Prompt("bench").tools([{"function_declarations": w.TOOLS}]).system(w.policy("cachemaxxing")).context(static)
    p.history(history(plain)).retrieved(per_turn).user(q)
    name = gemini_cache(client, p, model, expected_reuses=reuses, interval_s=10)
    if name:
        CACHES.add(name)
    return p.gemini(model, cached_content=name)


def call(client: Any, kw: dict[str, Any]) -> Any:
    kw["config"]["max_output_tokens"] = 64
    return client.models.generate_content(**kw)


def overhead(client: Any, m: Any) -> dict[str, float]:
    """Explicit-cache creation (input rate) + storage for each cache's whole lifetime; then delete the caches."""
    total = 0.0
    for name in CACHES:
        c = client.caches.get(name=name)
        tokens = (c.usage_metadata.total_token_count if c.usage_metadata else 0) or 0
        hours = (c.expire_time - c.create_time).total_seconds() / 3600 if c.expire_time and c.create_time else 1.0
        total += tokens * (m.input + (m.storage_hour or 0.0) * hours) / 1e6
        client.caches.delete(name=name)
    return {"cachemaxxing": round(total, 6)} if CACHES else {}


if __name__ == "__main__":
    w.run_benchmark(
        "gemini", "gemini-3.8-flash", "google-genai", genai.Client, request, call, lambda r: r.text or "", overhead
    )
