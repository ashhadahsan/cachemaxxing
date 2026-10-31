"""The tutorial's app: a support bot with the most common prompt-cache bug, then the same bot fixed.

uv run --env-file .env python examples/tutorial.py               # as many apps start: the time at the top
uv run --env-file .env python examples/tutorial.py --fixed       # the same bot through cachemaxxing.Prompt
add --log calls.jsonl to either to keep a log for `cachemaxxing report`

Walkthrough: https://ashhadahsan.github.io/cachemaxxing/tutorial/"""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI

from cachemaxxing import Prompt, Stats, record, usage

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
POLICY = (DATA / "policy.md").read_text()  # long and the same on every call: worth caching
DOCS = (DATA / "docs.md").read_text()
MODEL = "gpt-6-luna"
QUESTIONS = ["How do I reset my router?", "And how do I update its firmware?", "Thanks! Is that safe?"]


def before(chat: list[dict[str, str]]) -> dict[str, object]:
    """The bot as many apps start: the current time at the top of the system prompt."""
    system = f"Current time: {datetime.now(UTC).isoformat()}\n\n{POLICY}\n\n{DOCS}"
    return {"model": MODEL, "messages": [{"role": "system", "content": system}, *chat]}


def fixed(chat: list[dict[str, str]]) -> dict[str, object]:
    """The same bot through Prompt: what never changes first, the time after the conversation."""
    *history, question = chat
    p = Prompt("support.answer").system(POLICY).context(DOCS).history(history)
    p.retrieved(f"Current time: {datetime.now(UTC).isoformat()}").user(question["content"])
    return p.openai_chat(MODEL)


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")  # show cachemaxxing's warnings
    build = fixed if "--fixed" in sys.argv else before
    log = open(sys.argv[sys.argv.index("--log") + 1], "a") if "--log" in sys.argv else None
    client, stats = OpenAI(), Stats()
    chat: list[dict[str, str]] = []
    for question in QUESTIONS:
        chat.append({"role": "user", "content": question})
        kw = build(chat)
        resp = client.chat.completions.create(**kw)  # type: ignore[call-overload]
        chat.append({"role": "assistant", "content": resp.choices[0].message.content or ""})
        u = usage(resp)
        stats.add("support.answer", u, request=kw)  # measures, and diagnoses a broken prefix
        if log:
            log.write(json.dumps(record("support.answer", kw, resp)) + "\n")
        print(f"{question:<36} {u.input:>6,} input tokens, {u.cache_read:>6,} from cache ({u.hit_rate:.0%})")
    print()
    print(stats.table())
