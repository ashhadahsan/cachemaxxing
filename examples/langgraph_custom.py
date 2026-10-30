"""A hand-built LangGraph graph (model node + tool node) using cachemaxxing's cache_fields().

uv run --env-file .env python examples/langgraph_custom.py {openai|anthropic|gemini}

Middleware only runs inside create_agent. In your own nodes, call cache_fields() before the model call:
it returns the system message with the right cache marker and the extra `invoke` kwargs."""

import json
import sys
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from cachemaxxing import Stats, usage
from cachemaxxing.langchain import cache_fields

DATA = Path(__file__).parents[1] / "benchmarks" / "data"
SYSTEM = (DATA / "policy.md").read_text() + "\n\n" + (DATA / "docs.md").read_text()
MODELS = {
    "openai": "openai:gpt-6-luna",
    "anthropic": "anthropic:claude-haiku-5-5",
    "gemini": "google_genai:gemini-3.8-flash",
}


@tool
def check_warranty(serial_last4: str) -> str:
    """Warranty status for a registered device, by the last 4 characters of its serial number."""
    return json.dumps({"serial_last4": serial_last4, "status": "active", "expires": "2027-08-14"})


def build(provider: str, stats: Stats):  # type: ignore[no-untyped-def]
    llm = init_chat_model(MODELS[provider]).bind_tools([check_warranty])

    def model_node(state: MessagesState) -> dict[str, list]:
        system, extra = cache_fields(llm, SYSTEM, call_site="graph.support")
        ai = llm.invoke([system, *state["messages"]], **extra)
        stats.add("graph.support", usage(ai))
        return {"messages": [ai]}

    graph = StateGraph(MessagesState)
    graph.add_node("model", model_node)
    graph.add_node("tools", ToolNode([check_warranty]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def main(provider: str) -> None:
    stats = Stats()
    app = build(provider, stats)
    messages: list = []
    for question in [
        "My router keeps dropping Wi-Fi in the evening. What should I check first?",
        "Is my device with serial ending 4F2A still under warranty?",
        "Thanks! And how do I set up a guest network for the weekend?",
    ]:
        messages = app.invoke({"messages": [*messages, {"role": "user", "content": question}]})["messages"]
        print(f"\nQ: {question}\nA: {' '.join(messages[-1].text.split())[:200]}")
    print(f"\n{stats.table()}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "openai")
