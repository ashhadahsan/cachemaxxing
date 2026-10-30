"""OpenAI benchmark (Responses API): naive vs clean (implicit caching) vs cachemaxxing. Needs OPENAI_API_KEY.

uv run --env-file .env python benchmarks/bench_openai.py --workload chat|rag [--model gpt-6.1-sol]"""

from typing import Any

import openai
import workload as w

from cachemaxxing import Prompt


def tools(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"type": "function", **t} for t in defs]


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
            "instructions": w.naive_system(workload, q),
            "tools": tools(w.naive_tools()),
            "input": msgs,
        }
    static, per_turn = w.layout(workload, q)
    if arm == "clean":  # the same content laid out well, with OpenAI's default (implicit) caching only
        last = {"role": "user", "content": "\n\n".join([*per_turn, q])}
        return {
            "model": model,
            "instructions": "\n\n".join([w.policy("clean"), *static]),
            "tools": tools(w.TOOLS),
            "input": [*history(plain), last],
        }
    p = Prompt("bench").tools(tools(w.TOOLS)).system(w.policy("cachemaxxing")).context(static)
    return p.history(history(plain)).retrieved(per_turn).user(q).openai(model)


if __name__ == "__main__":
    w.run_benchmark(
        "openai",
        "gpt-6-luna",
        "openai",
        openai.OpenAI,
        request,
        lambda client, kw: client.responses.create(max_output_tokens=64, **kw),
        lambda r: r.output_text,
    )
