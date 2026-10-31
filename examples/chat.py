"""The simplest use: a chat kept as a plain list of {"role", "content"} messages, cached on every turn.

uv run --env-file .env python examples/chat.py {openai|anthropic|gemini}

Prompt().messages(chat) takes the list as you would send it to OpenAI and builds the request for any provider:
the system message becomes the cached system prompt, and the conversation is cached up to the latest question,
so the next turn reads all of it from cache."""

import sys
from pathlib import Path

from cachemaxxing import Prompt, usage

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
SYSTEM = (DATA / "policy.md").read_text() + "\n\n" + (DATA / "docs.md").read_text()  # long and fixed: worth caching


def ask(provider: str, chat: list[dict[str, str]]) -> tuple[object, str]:
    p = Prompt("chat").messages(chat)
    if provider == "openai":
        from openai import OpenAI

        r = OpenAI().chat.completions.create(**p.openai_chat("gpt-6-luna"))
        return r, r.choices[0].message.content or ""
    if provider == "anthropic":
        from anthropic import Anthropic

        r = Anthropic().messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))
        return r, "".join(b.text for b in r.content if b.type == "text")
    from google import genai

    client = genai.Client()  # keep a reference: a temporary client is closed before the call finishes
    r = client.models.generate_content(**p.gemini("gemini-3.8-flash"))
    return r, r.text or ""


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "openai"
    chat = [{"role": "system", "content": SYSTEM}]
    for question in ["How do I reset my router?", "And how do I update its firmware?", "Thanks! Is that safe?"]:
        chat.append({"role": "user", "content": question})
        response, answer = ask(provider, chat)
        chat.append({"role": "assistant", "content": answer})
        u = usage(response)
        print(f"{question:<36} {u.input:>6,} input tokens, {u.cache_read:>6,} from cache ({u.hit_rate:.0%})")
