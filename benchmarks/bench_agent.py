"""LangChain agent benchmark: default create_agent vs the provider's own caching middleware vs CacheMiddleware.

uv run --env-file .env python benchmarks/bench_agent.py anthropic|openai
Three customers each ask three questions (one needs a tool call); every model call the agent makes is measured.
OpenAI has no first-party caching middleware, so its "clean" arm is skipped."""

import json
import sys
from typing import Any

import workload as w
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from cachemaxxing import Usage, usage
from cachemaxxing.facts import MODELS
from cachemaxxing.langchain import CacheMiddleware

AGENTS = {"anthropic": "anthropic:claude-haiku-5-5", "openai": "openai:gpt-6-luna"}
QUESTIONS = [
    "My router keeps dropping Wi-Fi in the evening. What should I check first?",
    "Is my device with serial ending 4F2A still under warranty?",
    "Thanks! And how do I set up a guest network for the weekend?",
]


@tool
def check_warranty(serial_last4: str) -> str:
    """Warranty status for a registered device, by the last 4 characters of its serial number."""
    return json.dumps({"serial_last4": serial_last4, "status": "active", "expires": "2027-08-14"})


def middleware(provider: str, arm: str) -> list[Any]:
    if arm == "cachemaxxing":
        return [CacheMiddleware("bench.agent")]
    if arm == "clean":
        from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

        return [AnthropicPromptCachingMiddleware()]
    return []


def conversation(provider: str, arm: str, rep: int, budget: w.Budget) -> list[Usage]:
    agent = create_agent(
        AGENTS[provider],
        tools=[check_warranty],
        system_prompt=w.policy(arm) + "\n\n" + w.DOCS,
        middleware=middleware(provider, arm),
    )
    messages: list[Any] = []
    rows: list[Usage] = []
    for i, q in enumerate(QUESTIONS):
        q = f"Hi, this is {w.CUSTOMERS[rep]}. {q}" if i == 0 else q
        before = len(messages)
        messages = agent.invoke({"messages": [*messages, {"role": "user", "content": q}]})["messages"]
        for m in messages[before:]:
            if isinstance(m, AIMessage) and m.usage_metadata:
                u = usage(m)
                budget.spend(u)
                rows.append(u)
    return rows


if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "anthropic"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    model = AGENTS[provider].split(":", 1)[1]
    arms = ["naive", "clean", "cachemaxxing"] if provider == "anthropic" else ["naive", "cachemaxxing"]
    m = MODELS[model]
    budget = w.Budget(0.5, w.projected_usd(m.input, m.output, 4, reps, len(arms)))
    results = {arm: [conversation(provider, arm, rep, budget) for rep in range(reps)] for arm in arms}
    meaning = {
        "naive": "LangChain create_agent, no caching middleware",
        "clean": "create_agent + langchain-anthropic AnthropicPromptCachingMiddleware",
        "cachemaxxing": "create_agent + cachemaxxing CacheMiddleware",
    }
    out = w.write_results(provider, model, "langchain", len(QUESTIONS), results, workload="agent", arms_meaning=meaning)
    print(out, f"spent ~${budget.spent:.4f}")
