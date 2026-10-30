"""Quickstart: ask two questions over the same long system prompt; the 2nd call should read the cached prefix.

uv run --env-file .env python examples/quickstart.py {anthropic|openai|gemini|litellm}"""

import sys
from pathlib import Path
from typing import Any

from cachemaxxing import Prompt, usage

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
SYSTEM = (DATA / "policy.md").read_text() + "\n\n" + (DATA / "docs.md").read_text()  # > 4,096 tokens


def ask(provider: str, question: str) -> Any:
    p = Prompt(call_site="quickstart").system(SYSTEM).user(question)
    if provider == "anthropic":
        import anthropic

        return anthropic.Anthropic().messages.create(max_tokens=64, **p.anthropic("claude-haiku-5-5"))
    if provider == "openai":
        import openai

        return openai.OpenAI().responses.create(max_output_tokens=64, **p.openai("gpt-6-luna"))
    if provider == "gemini":
        from google import genai

        client = genai.Client()  # keep a reference: a temporary Client closes its connection when collected
        kw = p.gemini("gemini-3.8-flash")
        kw["config"]["max_output_tokens"] = 64
        return client.models.generate_content(**kw)
    import litellm  # pip install "cachemaxxing[litellm]"

    return litellm.completion(max_tokens=64, **p.litellm("gemini/gemini-3.8-flash"))


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "gemini"
    for q in ("How do I reset the router?", "And how do I update its firmware?"):
        u = usage(ask(provider, q))
        print(f"{provider}: input={u.input} cache_read={u.cache_read} hit={u.hit_rate:.0%} est=${u.est_cost or 0:.6f}")
