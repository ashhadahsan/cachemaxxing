"""A multi-turn RAG chat built with cachemaxxing.

uv run --env-file .env python examples/rag_chat.py {anthropic|openai|gemini|litellm}

Every turn retrieves fresh chunks for the question. The layout, from most to least stable:

    system policy -> FAQ + model table (static) -> chat history (append-only) -> retrieved chunks -> question

The retrieved chunks change on every turn, so they go after the history: the policy, the FAQ and the
conversation so far are cached, and the chunks never pay a cache-write premium. Each turn prints what
was read from cache, how the request differs from the previous one, and logs a JSONL line you can feed
to `cachemaxxing report`."""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from cachemaxxing import Prompt, Stats, diff, record, usage

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
POLICY = (DATA / "policy.md").read_text()
SECTIONS = [s.strip() for s in re.split(r"\n(?=## )", (DATA / "docs.md").read_text()) if s.strip()]
STATIC = [s for s in SECTIONS if s.startswith(("## Models", "## FAQ"))]  # always in context
CORPUS = [s for s in SECTIONS if s.startswith("## ") and s not in STATIC]  # retrieved per question
QUESTIONS = [
    "My AX3000 keeps dropping Wi-Fi in the evening. What should I check first?",
    "It happens mostly on the 2.4 GHz band. Which channel should I pick?",
    "Can I give my visitors a separate network that expires?",
    "Is WireGuard faster than OpenVPN on my model?",
]
MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.8-flash",
    "litellm": "anthropic/claude-haiku-5-5",
}


def words(text: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


INDEX = [(chunk, words(chunk)) for chunk in CORPUS]


def retrieve(question: str, k: int = 3) -> list[str]:
    # ponytail: keyword-overlap scoring keeps the example dependency-free; plug in your vector store here
    q = words(question)
    ranked = sorted(INDEX, key=lambda item: -sum(min(n, item[1][w]) for w, n in q.items()))
    return [chunk for chunk, _ in ranked[:k]]


def message(provider: str, role: str, text: str) -> dict[str, Any]:
    """One history turn in the provider's own message format."""
    if provider == "gemini":
        return {"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]}
    return {"role": role, "content": text}


def client_for(provider: str) -> Any:
    if provider == "anthropic":
        import anthropic

        return anthropic.Anthropic()
    if provider == "openai":
        import openai

        return openai.OpenAI()
    if provider == "gemini":
        from google import genai

        return genai.Client()
    import litellm  # pip install "cachemaxxing[litellm]"

    return litellm


def ask(provider: str, client: Any, p: Prompt) -> tuple[dict[str, Any], Any, str]:
    """Render the prompt for the provider, call it, and return (request kwargs, response, answer text)."""
    model = MODELS[provider]
    if provider == "anthropic":
        kw = p.anthropic(model)
        resp = client.messages.create(max_tokens=1024, **kw)
        return kw, resp, "".join(b.text for b in resp.content if b.type == "text")
    if provider == "openai":
        kw = p.openai(model)
        resp = client.responses.create(max_output_tokens=1024, **kw)
        return kw, resp, resp.output_text
    if provider == "gemini":
        kw = p.gemini(model)
        kw["config"]["max_output_tokens"] = 1024  # leaves room for thinking tokens
        resp = client.models.generate_content(**kw)
        return kw, resp, resp.text or ""
    kw = p.litellm(model)
    resp = client.completion(max_tokens=1024, **kw)
    return kw, resp, resp.choices[0].message.content or ""


def main(provider: str) -> None:
    client, stats = client_for(provider), Stats()
    history: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    log = Path("rag_chat.jsonl")
    with log.open("w") as f:
        for question in QUESTIONS:
            p = Prompt(call_site="rag.answer").system(POLICY).context(STATIC)
            p.history(history).retrieved(retrieve(question)).user(question)
            kw, resp, answer = ask(provider, client, p)

            u = usage(resp)
            stats.add("rag.answer", u)
            f.write(json.dumps(record("rag.answer", kw, resp)) + "\n")
            print(f"\nQ: {question}\nA: {' '.join(answer.split())[:240]}")
            cost = u.est_cost or 0
            print(f"   cache read {u.cache_read:,} of {u.input:,} input tokens ({u.hit_rate:.0%}), ~${cost:.5f}")
            if previous is not None:
                d = diff(previous, kw)
                where = "repeats it all" if d is None else f"first differs at {d.path} ({d.hint or 'content'})"
                print(f"   vs previous request: {where}")

            previous = kw
            # Keep history append-only, and keep the retrieved chunks out of it: they were per-turn context.
            history += [message(provider, "user", question), message(provider, "assistant", answer)]

    print(f"\n{stats.table()}\n\nlogged {len(QUESTIONS)} calls to {log}; run: cachemaxxing report {log}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "anthropic")
