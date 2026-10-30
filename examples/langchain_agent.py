"""A LangChain / LangGraph agent with cachemaxxing's CacheMiddleware.

uv run --env-file .env python examples/langchain_agent.py {openai|anthropic|gemini}
(needs `pip install "cachemaxxing[langchain]" langchain-openai` / `langchain-anthropic` / `langchain-google-genai`)

The middleware adds the right cache fields to every model call the agent makes (tool loops included),
records usage per call site, and hands each call to `on_record` for a JSONL log you can feed to
`cachemaxxing report`."""

import json
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import tool

from cachemaxxing.langchain import CacheMiddleware

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
SYSTEM = (DATA / "policy.md").read_text() + "\n\n" + (DATA / "docs.md").read_text()  # a large, stable prefix
MODELS = {
    "openai": "openai:gpt-6-luna",
    "anthropic": "anthropic:claude-haiku-5-5",
    "gemini": "google_genai:gemini-3.8-flash",
}
QUESTIONS = [
    "My router keeps dropping Wi-Fi in the evening. What should I check first?",
    "Is my device with serial ending 4F2A still under warranty?",
    "Thanks! And how do I set up a guest network for the weekend?",
]


@tool
def check_warranty(serial_last4: str) -> str:
    """Warranty status for a registered device, by the last 4 characters of its serial number."""
    return json.dumps({"serial_last4": serial_last4, "status": "active", "expires": "2027-08-14"})


def main(provider: str) -> None:
    with open("agent_calls.jsonl", "w") as log:
        cache = CacheMiddleware("support.agent", on_record=lambda r: log.write(json.dumps(r) + "\n"))
        agent = create_agent(MODELS[provider], tools=[check_warranty], system_prompt=SYSTEM, middleware=[cache])
        messages: list = []
        for question in QUESTIONS:
            messages.append({"role": "user", "content": question})
            messages = agent.invoke({"messages": messages})["messages"]
            print(f"\nQ: {question}\nA: {' '.join(messages[-1].text.split())[:200]}")
    print(f"\n{cache.stats.table()}\n\nper-call log: agent_calls.jsonl -> cachemaxxing report agent_calls.jsonl")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "openai")
