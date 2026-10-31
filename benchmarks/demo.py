"""A real log for the demo dashboard on the docs site: four call sites, live calls, about $0.05.

uv run --env-file .env python benchmarks/demo.py demo.jsonl      # live calls; appends record() lines
uv run cachemaxxing report demo.jsonl --min-hit-rate 0.6 --html docs/demo.html
uv run python benchmarks/demo.py --rerender                      # after a dashboard template change; no API calls
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import workload as w

from cachemaxxing import Prompt, record
from cachemaxxing.dashboard import render

PAGE = Path(__file__).parents[1] / "docs" / "demo.html"
TICKETS = [
    "Router reboots every night at 2am.",
    "Guest Wi-Fi password not accepted.",
    "Firmware update stuck at 90%.",
    "Parental controls block homework sites.",
    "Mesh node keeps going offline.",
]


def rerender() -> None:
    page = PAGE.read_text(encoding="utf-8")
    blob = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    assert blob is not None, f"no embedded data in {PAGE}"
    PAGE.write_text(render(json.loads(blob[1])), encoding="utf-8")


def live(path: str) -> None:
    import anthropic
    import openai
    from google import genai

    claude, gpt, gemini = anthropic.Anthropic(), openai.OpenAI(), genai.Client()
    with open(path, "a", encoding="utf-8") as log:

        def keep(site: str, kw: dict, resp: object) -> None:
            log.write(json.dumps(record(site, kw, resp)) + "\n")

        # support.chat: a chat kept as a plain message list, on OpenAI. Healthy.
        chat = [{"role": "system", "content": w.POLICY + "\n\n" + w.DOCS}]
        for q in w.QUESTIONS[:6]:
            chat.append({"role": "user", "content": q})
            kw = Prompt("support.chat").messages(chat).openai_chat("gpt-6-luna")
            r = gpt.chat.completions.create(**kw)
            keep("support.chat", kw, r)
            chat.append({"role": "assistant", "content": r.choices[0].message.content or ""})

        # rag.answer: fixed prompt, growing history, fresh chunks every turn, on Anthropic. Healthy.
        history: list[dict[str, str]] = []
        for q in w.QUESTIONS[:5]:
            p = Prompt("rag.answer").system(w.POLICY).context(w.RAG_STATIC).history(history)
            kw = p.retrieved(w.retrieve(q)).user(q).anthropic("claude-haiku-5-5")
            r = claude.messages.create(max_tokens=1024, **kw)
            keep("rag.answer", kw, r)
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": r.content[-1].text}]

        # ticket.triage: the classic bug, the current time at the top of the system prompt. Diagnosed by Anthropic.
        previous: str | bool = True
        for t in TICKETS:
            system = f"Current time: {datetime.now(UTC).isoformat()}\n\n{w.POLICY}"
            p = Prompt("ticket.triage").system(system).user(f"Triage this ticket in one line: {t}")
            kw = p.anthropic("claude-haiku-5-5", diagnose=previous)
            r = claude.messages.create(max_tokens=512, **kw)
            keep("ticket.triage", kw, r)
            previous = r.id

        # faq.gemini: Gemini's implicit caching, best-effort.
        turns: list[dict[str, str]] = []
        for q in w.QUESTIONS[:4]:
            kw = (
                Prompt("faq.gemini")
                .system(w.POLICY + "\n\n" + w.DOCS)
                .history(turns)
                .user(q)
                .gemini("gemini-3.8-flash")
            )
            r = gemini.models.generate_content(**kw)
            keep("faq.gemini", kw, r)
            turns += [{"role": "user", "content": q}, {"role": "assistant", "content": r.text or ""}]


if __name__ == "__main__":
    rerender() if sys.argv[1:] == ["--rerender"] else live(sys.argv[1])
