"""The simplest LangChain use: SystemMessage, HumanMessage and AIMessage in a list, cached on every turn.

uv run --env-file .env python examples/langchain_chat.py {openai|anthropic|gemini}

Wrap the chat model once with CachedModel and call it with the message list, as you would call the model."""

import sys
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from cachemaxxing.langchain import CachedModel

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
SYSTEM = (DATA / "policy.md").read_text() + "\n\n" + (DATA / "docs.md").read_text()  # long and fixed: worth caching
MODELS = {
    "openai": "openai:gpt-6-luna",
    "anthropic": "anthropic:claude-haiku-5-5",
    "gemini": "google_genai:gemini-3.8-flash",
}

if __name__ == "__main__":
    llm = CachedModel(init_chat_model(MODELS[sys.argv[1] if len(sys.argv) > 1 else "openai"]), call_site="chat")
    messages = [SystemMessage(SYSTEM)]
    for question in ["How do I reset my router?", "And how do I update its firmware?", "Thanks! Is that safe?"]:
        messages.append(HumanMessage(question))
        reply = llm.invoke(messages)  # an AIMessage
        messages.append(reply)
        m = reply.response_metadata["cachemaxxing"]
        print(f"{question:<36} {m['input_tokens']:>6,} input tokens, {m['cache_read_tokens']:>6,} from cache")
    print(f"\n{llm.stats.table()}")
