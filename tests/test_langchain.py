"""CacheMiddleware against real LangChain objects, offline: the handler is a stub, nothing is sent."""

import asyncio
from typing import Any

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langchain_openai")
pytest.importorskip("langchain_anthropic")
pytest.importorskip("langchain_google_genai")

from langchain.agents.middleware import ModelRequest, ModelResponse  # noqa: E402
from langchain_anthropic import ChatAnthropic  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: E402
from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from cachemaxxing.langchain import CacheMiddleware, cache_fields  # noqa: E402

BP = {"mode": "explicit"}
CC = {"type": "ephemeral"}


def request(model: Any, system: Any = "You are helpful.", settings: dict[str, Any] | None = None) -> Any:
    return ModelRequest(
        model=model,
        messages=[HumanMessage("hi", id="random-id-1")],
        system_message=SystemMessage(system) if system is not None else None,
        tools=[{"name": "lookup", "description": "d", "input_schema": {"type": "object"}}],
        model_settings=settings or {},
    )


def reply(provider: str, model: str) -> AIMessage:
    usage = {
        "input_tokens": 2000,
        "output_tokens": 5,
        "total_tokens": 2005,
        "input_token_details": {"cache_read": 1500},
    }
    return AIMessage("ok", usage_metadata=usage, response_metadata={"model_provider": provider, "model_name": model})


def run(mw: CacheMiddleware, req: Any, ai: AIMessage) -> Any:
    seen: list[Any] = []

    def handler(r: Any) -> Any:
        seen.append(r)
        return ModelResponse(result=[ai])

    mw.wrap_model_call(req, handler)
    return seen[0]


def test_openai_gets_system_breakpoint_and_implicit_mode() -> None:
    mw = CacheMiddleware("agent")
    sent = run(mw, request(ChatOpenAI(model="gpt-6-luna", api_key="t")), reply("openai", "gpt-6-luna"))
    assert sent.system_message.content == [{"type": "text", "text": "You are helpful.", "prompt_cache_breakpoint": BP}]
    assert sent.model_settings["prompt_cache_options"] == {"mode": "implicit", "ttl": "30m"}
    assert mw.stats.calls == {"agent": 1} and mw.stats.totals["agent"].cache_read == 1500


def test_anthropic_gets_system_marker_and_automatic_tail() -> None:
    mw = CacheMiddleware("agent", ttl="1h")
    sent = run(
        mw, request(ChatAnthropic(model="claude-haiku-5-5", api_key="t")), reply("anthropic", "claude-haiku-5-5")
    )
    marker = {"type": "ephemeral", "ttl": "1h"}
    assert sent.system_message.content[-1]["cache_control"] == marker
    assert sent.model_settings["cache_control"] == marker
    assert mw.stats.totals["agent"].provider == "anthropic"


def test_gemini_and_legacy_openai() -> None:
    gemini = ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key="t")
    req = request(gemini)
    assert run(CacheMiddleware(), req, reply("google_genai", "gemini-3.8-flash")) is req  # implicit caching: untouched
    sent = run(CacheMiddleware("site"), request(ChatOpenAI(model="gpt-5.5", api_key="t")), reply("openai", "gpt-5.5"))
    assert sent.model_settings["prompt_cache_key"].startswith("site:")
    assert sent.system_message.content == "You are helpful."


def test_user_settings_win_and_empty_system_is_left_alone() -> None:
    mine = {"prompt_cache_options": {"mode": "explicit", "ttl": "12h"}}
    sent = run(
        CacheMiddleware(), request(ChatOpenAI(model="gpt-6-luna", api_key="t"), settings=mine), reply("openai", "x")
    )
    assert sent.model_settings["prompt_cache_options"] == {"mode": "explicit", "ttl": "12h"}
    sent = run(
        CacheMiddleware(), request(ChatAnthropic(model="claude-haiku-5-5", api_key="t"), system=None), reply("x", "y")
    )
    assert sent.system_message is None and sent.model_settings["cache_control"] == CC


def test_on_record_gets_a_diffable_request_without_message_ids() -> None:
    records: list[dict[str, Any]] = []
    mw = CacheMiddleware("agent", on_record=records.append)
    run(mw, request(ChatOpenAI(model="gpt-6-luna", api_key="t")), reply("openai", "gpt-6-luna"))
    rec = records[0]
    assert rec["call_site"] == "agent" and rec["request"]["model"] == "gpt-6-luna"
    assert rec["request"]["tools"] == ["lookup"] and "random-id-1" not in str(rec["request"])
    assert rec["response"]["usage_metadata"]["input_tokens"] == 2000


def test_async_variant() -> None:
    mw = CacheMiddleware("agent")

    async def handler(r: Any) -> Any:
        return ModelResponse(result=[reply("openai", "gpt-6-luna")])

    asyncio.run(mw.awrap_model_call(request(ChatOpenAI(model="gpt-6-luna", api_key="t")), handler))
    assert mw.stats.calls == {"agent": 1}


def test_cache_fields_for_custom_graph_nodes() -> None:
    tool = {"name": "lookup", "description": "d", "input_schema": {"type": "object"}}
    bound = ChatOpenAI(model="gpt-6-luna", api_key="t").bind_tools([tool])  # a RunnableBinding is unwrapped
    system, extra = cache_fields(bound, "You are helpful.")
    assert system is not None and system.content[-1]["prompt_cache_breakpoint"] == BP
    assert extra == {"prompt_cache_options": {"mode": "implicit", "ttl": "30m"}}
    system, extra = cache_fields(ChatAnthropic(model="claude-haiku-5-5", api_key="t"), SystemMessage("S"), ttl="1h")
    assert extra == {"cache_control": {"type": "ephemeral", "ttl": "1h"}}
    assert system is not None and system.content[-1]["cache_control"] == extra["cache_control"]
    plain = SystemMessage("S")
    assert cache_fields(ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key="t"), plain) == (plain, {})
    system, extra = cache_fields(ChatOpenAI(model="gpt-5.5", api_key="t"), "S", call_site="node", tools=[tool])
    assert extra["prompt_cache_key"].startswith("node:")


def mock_openai(seen: list[Any]) -> Any:
    import json as _json
    from pathlib import Path

    import httpx

    fixtures = Path(__file__).parent / "fixtures"

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(_json.loads(req.content))
        name = "openai_response.json" if req.url.path.endswith("/responses") else "openai_chat.json"
        return httpx.Response(200, json=_json.loads((fixtures / name).read_text()))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_cached_model_through_langchain_and_the_openai_sdk() -> None:
    from cachemaxxing.langchain import CachedModel

    seen: list[Any] = []
    llm = ChatOpenAI(model="gpt-6-luna", api_key="t", http_client=mock_openai(seen))
    records: list[dict[str, Any]] = []
    cm = CachedModel(llm, system="You are helpful.", call_site="graph", on_record=records.append)
    ai = cm.invoke([HumanMessage("hi")])
    body = seen[0]
    system = body.get("messages", body.get("input"))[0]
    assert system["content"][-1]["prompt_cache_breakpoint"] == BP
    assert body["prompt_cache_options"] == {"mode": "implicit", "ttl": "30m"}
    assert isinstance(ai, AIMessage) and cm.stats.calls == {"graph": 1} and cm.stats.totals["graph"].cache_read == 1024
    assert records[0]["request"]["messages"][0]["type"] == "system"
    cm.invoke(
        [SystemMessage("Own system prompt."), HumanMessage("hi")]
    )  # a leading system message is used, not doubled
    second = seen[1].get("messages", seen[1].get("input"))
    assert [m["role"] for m in second][:2] in (["system", "user"], ["developer", "user"])
    assert second[0]["content"][-1]["text"] == "Own system prompt."
