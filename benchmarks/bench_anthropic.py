"""Anthropic benchmark: naive vs clean (automatic caching) vs cachemaxxing. Needs ANTHROPIC_API_KEY.

uv run --env-file .env python benchmarks/bench_anthropic.py --workload chat|rag [--model claude-sonnet-5-5]"""

from typing import Any

import anthropic
import workload as w

from cachemaxxing import Prompt


def tools(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in defs]


def history(turns: list[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for q, a in turns:
        out += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    return out


def request(client: Any, arm: str, workload: str, model: str, q: str, done: list, reuses: int) -> dict[str, Any]:
    plain = [(x, a) for x, a, _ in done]
    if arm == "naive":
        msgs = [*history(w.naive_turns(done)), {"role": "user", "content": q}]
        return {
            "model": model,
            "system": w.naive_system(workload, q),
            "tools": tools(w.naive_tools()),
            "messages": msgs,
        }
    static, per_turn = w.layout(workload, q)
    if arm == "clean":  # the same content laid out well, with Anthropic's automatic caching only
        last = {"role": "user", "content": "\n\n".join([*per_turn, q])}
        system = "\n\n".join([w.policy("clean"), *static])
        return {
            "model": model,
            "cache_control": {"type": "ephemeral"},
            "system": system,
            "tools": tools(w.TOOLS),
            "messages": [*history(plain), last],
        }
    p = Prompt("bench").tools(tools(w.TOOLS)).system(w.policy("cachemaxxing")).context(static)
    return p.history(history(plain)).retrieved(per_turn).user(q).anthropic(model)


def text(resp: Any) -> str:
    return "".join(b.text for b in resp.content if b.type == "text")


if __name__ == "__main__":
    w.run_benchmark(
        "anthropic",
        "claude-haiku-5-5",
        "anthropic",
        anthropic.Anthropic,
        request,
        lambda client, kw: client.messages.create(max_tokens=64, **kw),
        text,
    )
