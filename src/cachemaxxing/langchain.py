"""LangChain 1.x / LangGraph agent middleware: provider-aware cache markers and usage per call site.

    from langchain.agents import create_agent
    from cachemaxxing.langchain import CacheMiddleware

    cache = CacheMiddleware(call_site="support.agent")
    agent = create_agent("openai:gpt-6-luna", tools=[...], system_prompt=SYSTEM, middleware=[cache])
    agent.invoke({"messages": [{"role": "user", "content": "..."}]})
    print(cache.stats.table())

Per model call, and only for that call (agent state is never modified):
- OpenAI GPT-5.6+: an explicit breakpoint on the system prompt, implicit mode for the growing conversation.
- OpenAI before 5.6: a `prompt_cache_key` derived from the call site and the system prompt + tools.
- Anthropic: a marker on the system prompt and automatic caching for the conversation tail. Use this or
  langchain-anthropic's AnthropicPromptCachingMiddleware, not both.
- Gemini and anything else: left as is (Gemini caches implicitly).
Your own `model_settings` always win. Needs `pip install "cachemaxxing[langchain]"`; `import cachemaxxing` alone
never imports LangChain."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, convert_to_messages
from langchain_core.runnables import Runnable, RunnableConfig

from .canon import canonical_json, jsonable
from .prompt import _cc, _check_ttl, openai_explicit
from .usage import Stats, record, usage

_KEEP = ("type", "content", "tool_calls", "tool_call_id", "name")  # what a provider sees; LangChain ids are not


def _provider(model: Any) -> tuple[str, str]:
    while hasattr(model, "bound"):  # llm.bind_tools(...) / .bind(...) wrap the chat model in a RunnableBinding
        model = model.bound
    name = str(getattr(model, "model_name", None) or getattr(model, "model", None) or "")
    kind = type(model).__name__
    if "Anthropic" in kind:
        return "anthropic", name
    if kind == "ChatOpenAI":  # Azure and other OpenAI-compatible classes may not accept the new cache fields
        return "openai", name
    if "Google" in kind:
        return "gemini", name
    return "other", name


def _mark(msg: SystemMessage | None, key: str, marker: dict[str, Any]) -> SystemMessage | None:
    """A copy of the system message with `marker` on its last non-empty text block."""
    if msg is None:
        return None
    content = msg.content
    if isinstance(content, str):
        blocks: list[Any] = [{"type": "text", "text": content, key: marker}] if content.strip() else []
    else:
        blocks = [dict(b) if isinstance(b, dict) else b for b in content]
        for i in range(len(blocks) - 1, -1, -1):
            b = blocks[i]
            if isinstance(b, dict) and b.get("type") == "text" and str(b.get("text", "")).strip():
                blocks[i] = {**b, key: marker}
                break
        else:
            blocks = []
    return msg.model_copy(update={"content": blocks}) if blocks else msg


def _tool_name(tool: Any) -> str:
    return str(tool.get("name", "")) if isinstance(tool, dict) else str(getattr(tool, "name", type(tool).__name__))


def _ai(result: Any) -> AIMessage | None:
    if isinstance(result, AIMessage):
        return result
    response = getattr(result, "model_response", result)  # ExtendedModelResponse wraps a ModelResponse
    messages: list[BaseMessage] = getattr(response, "result", None) or []
    return next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)


def _bound_tools(model: Any) -> list[Any]:
    return list(getattr(model, "kwargs", {}).get("tools") or [])  # tools given to bind_tools()


def _record_call(
    stats: Stats,
    call_site: str,
    on_record: Callable[[dict[str, Any]], None] | None,
    model: Any,
    system: SystemMessage | None,
    tools: Sequence[Any],
    messages: Sequence[BaseMessage],
    result: Any,
) -> None:
    ai = _ai(result)
    if ai is None or not ai.usage_metadata:
        return
    u = usage(ai)
    stats.add(call_site, u)
    ai.response_metadata["cachemaxxing"] = u.attributes(call_site, prefix="")  # travels with the message into traces
    if on_record:
        sent = {
            "model": _provider(model)[1],
            "tools": [_tool_name(t) for t in tools],
            "system": jsonable(system.content) if system else "",
            "messages": [{k: v for k, v in jsonable(m).items() if k in _KEEP} for m in messages],
        }
        on_record(record(call_site, sent, ai))


def cache_fields(
    model: Any,
    system: SystemMessage | str | None = None,
    *,
    call_site: str = "graph",
    ttl: str | None = None,
    tools: Sequence[Any] = (),
) -> tuple[SystemMessage | None, dict[str, Any]]:
    """For a model call in your own LangGraph node: the system message with the right cache marker, and the
    extra keyword arguments for `invoke`. Same rules as CacheMiddleware.

        system, extra = cache_fields(llm, SYSTEM, call_site="graph.answer")
        ai = llm.bind_tools(tools).invoke([system, *state["messages"]], **extra)
    """
    msg = SystemMessage(content=system) if isinstance(system, str) else system
    provider, name = _provider(model)
    if provider == "anthropic":
        cc = _cc(_check_ttl("anthropic", ttl or "5m"))  # marker on the system prompt + automatic tail caching
        return _mark(msg, "cache_control", cc), {"cache_control": cc}
    if provider == "openai" and openai_explicit(name):
        options = {"mode": "implicit", "ttl": _check_ttl("openai", ttl or "30m")}
        return _mark(msg, "prompt_cache_breakpoint", {"mode": "explicit"}), {"prompt_cache_options": options}
    if provider == "openai":
        prefix = canonical_json([[_tool_name(t) for t in tools], jsonable(msg.content if msg else "")])
        return msg, {"prompt_cache_key": f"{call_site}:{hashlib.sha256(prefix.encode()).hexdigest()[:16]}"}
    return msg, {}  # Gemini caches implicitly; other providers are left alone


class CacheMiddleware(AgentMiddleware[Any, Any, Any]):
    """Add the right cache fields to every model call of a LangChain agent and measure what it saved."""

    def __init__(
        self,
        call_site: str = "agent",
        *,
        ttl: str | None = None,
        on_record: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """`call_site`: your name for this agent in Stats, logs and traces (any string, see `Prompt`).
        `ttl`: "5m"/"1h" for Anthropic, "30m"/"12h" for OpenAI (defaults: 5m, 30m).
        `on_record`: called with a `record()` dict per model call, e.g. to append it to a JSONL log."""
        super().__init__()
        self.call_site, self.ttl, self.on_record = call_site, ttl, on_record
        self.stats = Stats()

    def _prepare(self, request: ModelRequest[Any]) -> ModelRequest[Any]:
        tools = request.tools or []
        system, extra = cache_fields(
            request.model, request.system_message, call_site=self.call_site, ttl=self.ttl, tools=tools
        )
        if system is request.system_message and not extra:
            return request
        return request.override(system_message=system, model_settings={**extra, **(request.model_settings or {})})

    def _measure(self, request: ModelRequest[Any], result: Any) -> None:
        tools = request.tools or []
        _record_call(
            self.stats,
            self.call_site,
            self.on_record,
            request.model,
            request.system_message,
            tools,
            request.messages,
            result,
        )

    def wrap_model_call(
        self, request: ModelRequest[Any], handler: Callable[[ModelRequest[Any]], ModelResponse[Any]]
    ) -> Any:
        prepared = self._prepare(request)
        result = handler(prepared)
        self._measure(prepared, result)
        return result

    async def awrap_model_call(
        self, request: ModelRequest[Any], handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]]
    ) -> Any:
        prepared = self._prepare(request)
        result = await handler(prepared)
        self._measure(prepared, result)
        return result


class CachedModel(Runnable[Any, BaseMessage]):
    """Wrap a LangChain chat model (bind_tools() included) so every call gets the right cache fields and is
    measured, for hand-built LangGraph nodes and LCEL chains. (For create_agent, use CacheMiddleware.)

        llm = CachedModel(init_chat_model("openai:gpt-6-luna").bind_tools(tools), system=SYSTEM, call_site="graph")
        ai = llm.invoke(state["messages"])     # in a node; llm.stats has hit rate and $ per call site

    A leading SystemMessage in the input is used as is (and marked); otherwise `system` is prepended.
    `call_site` is your name for this model call in Stats, logs and traces (any string, see `Prompt`)."""

    def __init__(
        self,
        model: Runnable[Any, Any],
        *,
        system: SystemMessage | str | None = None,
        call_site: str = "graph",
        ttl: str | None = None,
        on_record: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.model, self.call_site, self.ttl, self.on_record = model, call_site, ttl, on_record
        self.system = SystemMessage(content=system) if isinstance(system, str) else system
        self.stats = Stats()
        self._tools = _bound_tools(model)
        _, extra = cache_fields(model, None, call_site=call_site, ttl=ttl, tools=self._tools)
        self._bound = model.bind(**extra) if extra else model

    def _messages(self, input: Any) -> list[BaseMessage]:
        raw = input.to_messages() if hasattr(input, "to_messages") else [input] if isinstance(input, str) else input
        msgs = convert_to_messages(raw)
        system, rest = (msgs[0], msgs[1:]) if msgs and isinstance(msgs[0], SystemMessage) else (self.system, msgs)
        marked, _ = cache_fields(self.model, system, call_site=self.call_site, ttl=self.ttl, tools=self._tools)
        return [marked, *rest] if marked is not None else list(rest)

    def invoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> BaseMessage:
        messages = self._messages(input)
        result = self._bound.invoke(messages, config, **kwargs)
        _record_call(self.stats, self.call_site, self.on_record, self.model, None, self._tools, messages, result)
        return result  # type: ignore[no-any-return]

    async def ainvoke(self, input: Any, config: RunnableConfig | None = None, **kwargs: Any) -> BaseMessage:
        messages = self._messages(input)
        result = await self._bound.ainvoke(messages, config, **kwargs)
        _record_call(self.stats, self.call_site, self.on_record, self.model, None, self._tools, messages, result)
        return result  # type: ignore[no-any-return]


__all__ = ["CacheMiddleware", "CachedModel", "cache_fields"]
