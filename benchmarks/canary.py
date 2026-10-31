"""Nightly live check: the provider APIs, their SDKs and cachemaxxing still agree.

uv run --env-file .env python benchmarks/canary.py     (CI: .github/workflows/canary.yml)

Two turns of examples/chat.py per provider, and two of LangChain's CachedModel on OpenAI. It fails when a
second turn reads nothing from cache on Anthropic or OpenAI, or when usage(), record() or the report can't
read a reply. Gemini's implicit caching is best-effort, so a Gemini miss only warns. About $0.02 per run."""

import json
import sys
from pathlib import Path

import workload as w

sys.path.insert(0, str(Path(__file__).parents[1] / "examples"))
from chat import SYSTEM, ask  # noqa: E402

from cachemaxxing import facts, record, usage  # noqa: E402
from cachemaxxing.cli import main  # noqa: E402

QUESTIONS = ["How do I reset my router?", "And how do I update its firmware?"]
BEST_EFFORT = {"gemini"}
LOG = Path("canary.jsonl")


def projected() -> float:
    tokens = len(SYSTEM) // 3 + 200  # ponytail: 3 chars/token and no cache hits, so an upper bound
    models = ["claude-haiku-5-5", "gpt-6-luna", "gemini-3.8-flash", "gpt-6-luna"]
    return sum(2 * (tokens * facts.MODELS[m].input + 1024 * facts.MODELS[m].output) for m in models) / 1e6


def provider(name: str, budget: w.Budget, log: list[str]) -> int:
    chat = [{"role": "system", "content": SYSTEM}]
    reads = []
    for q in QUESTIONS:
        chat.append({"role": "user", "content": q})
        response, answer = ask(name, chat)
        u = usage(response)
        budget.spend(u)
        log.append(json.dumps(record(f"canary.{name}", {"messages": list(chat)}, response)))
        chat.append({"role": "assistant", "content": answer})
        reads.append(u.cache_read)
    print(f"{name}: input {u.input:,}, cache read per turn {reads}")
    return reads[-1]


def langchain(budget: w.Budget, log: list[str]) -> int:
    from langchain.chat_models import init_chat_model
    from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

    from cachemaxxing.langchain import CachedModel

    llm = CachedModel(
        init_chat_model("openai:gpt-6-luna"),
        call_site="canary.langchain",
        on_record=lambda r: log.append(json.dumps(r)),
    )
    messages: list[BaseMessage] = [SystemMessage(SYSTEM)]
    reads = []
    for q in QUESTIONS:
        messages.append(HumanMessage(q))
        reply = llm.invoke(messages)
        messages.append(reply)
        budget.spend(usage(reply))
        reads.append(reply.response_metadata["cachemaxxing"]["cache_read_tokens"])  # missing if measuring failed
    print(f"langchain/openai: cache read per turn {reads}")
    return reads[-1]


if __name__ == "__main__":
    budget = w.Budget(0.05, projected())
    log: list[str] = []
    misses = [name for name in ("anthropic", "openai", "gemini") if not provider(name, budget, log)]
    if not langchain(budget, log):
        misses.append("langchain/openai")
    LOG.write_text("\n".join(log) + "\n")
    assert main(["report", str(LOG), "--strict", "--html", "canary.html"]) == 0, "report failed on live replies"
    print(f"spent ~${budget.spent:.4f}")
    for name in misses:
        print(f"{'warning' if name in BEST_EFFORT else 'FAIL'}: {name} read nothing from cache on turn 2")
    sys.exit(1 if set(misses) - BEST_EFFORT else 0)
