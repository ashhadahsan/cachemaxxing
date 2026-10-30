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
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from .canon import canonical_json, jsonable
from .prompt import _cc, _check_ttl, openai_explicit
from .usage import Stats, record, usage

_KEEP = ("type", "content", "tool_calls", "tool_call_id", "name")  # what a provider sees; LangChain ids are not


def _provider(model: Any) -> tuple[str, str]:
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


class CacheMiddleware(AgentMiddleware[Any, Any, Any]):
    """Add the right cache fields to every model call of a LangChain agent and measure what it saved."""

    def __init__(
        self,
        call_site: str = "agent",
        *,
        ttl: str | None = None,
        on_record: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """`ttl`: "5m"/"1h" for Anthropic, "30m"/"12h" for OpenAI (defaults: 5m, 30m).
        `on_record`: called with a `record()` dict per model call, e.g. to append it to a JSONL log."""
        super().__init__()
        self.call_site, self.ttl, self.on_record = call_site, ttl, on_record
        self.stats = Stats()

    def _prepare(self, request: ModelRequest[Any]) -> ModelRequest[Any]:
        provider, name = _provider(request.model)
        settings = dict(request.model_settings or {})
        if provider == "anthropic":
            cc = _cc(_check_ttl("anthropic", self.ttl or "5m"))
            settings.setdefault("cache_control", cc)  # automatic breakpoint: follows the growing conversation
            return request.override(
                system_message=_mark(request.system_message, "cache_control", cc), model_settings=settings
            )
        if provider == "openai" and openai_explicit(name):
            options = {"mode": "implicit", "ttl": _check_ttl("openai", self.ttl or "30m")}
            settings.setdefault("prompt_cache_options", options)
            marked = _mark(request.system_message, "prompt_cache_breakpoint", {"mode": "explicit"})
            return request.override(system_message=marked, model_settings=settings)
        if provider == "openai":
            system = request.system_message.content if request.system_message else ""
            prefix = canonical_json([[_tool_name(t) for t in request.tools or []], jsonable(system)])
            settings.setdefault(
                "prompt_cache_key", f"{self.call_site}:{hashlib.sha256(prefix.encode()).hexdigest()[:16]}"
            )
            return request.override(model_settings=settings)
        return request

    def _measure(self, request: ModelRequest[Any], result: Any) -> None:
        ai = _ai(result)
        if ai is None or not ai.usage_metadata:
            return
        self.stats.add(self.call_site, usage(ai))
        if self.on_record:
            sent = {
                "model": _provider(request.model)[1],
                "tools": [_tool_name(t) for t in request.tools or []],
                "system": jsonable(request.system_message.content) if request.system_message else "",
                "messages": [{k: v for k, v in jsonable(m).items() if k in _KEEP} for m in request.messages],
            }
            self.on_record(record(self.call_site, sent, ai))

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


__all__ = ["CacheMiddleware"]
