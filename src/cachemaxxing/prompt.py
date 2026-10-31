"""Prompt: segments ordered from most to least stable, rendered as request kwargs per provider."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Self

from . import facts
from .canon import canonical_json, normalize_ws, plain, tool_name

Json = dict[str, Any]
Parts = str | Mapping[str, Any] | Sequence[str | Mapping[str, Any]]


def _parts(x: Parts) -> list[str]:
    """Text parts: strings verbatim, anything else as canonical JSON."""
    items: Sequence[Any] = [x] if isinstance(x, str | Mapping) else x
    return [p if isinstance(p, str) else canonical_json(p) for p in items]


def _texts(content: Any) -> list[str] | None:
    """Text of a chat message's content (a string or a list of text parts); None if it holds anything else."""
    if isinstance(content, str):
        return [content]
    if isinstance(content, list) and all(isinstance(b, dict) and "text" in b for b in content):
        return [str(b["text"]) for b in content]
    return None


def _gemini_turn(msg: Any) -> Any:
    """A {"role", "content"} text turn as Gemini content; Gemini-format and tool-call turns pass through."""
    m = plain(msg)
    texts = _texts(m.get("content")) if isinstance(m, dict) and "parts" not in m else None
    if texts is None:
        return msg
    return {"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": t} for t in texts]}


def _sort_tool(t: Any) -> Any:
    t = plain(t)
    if isinstance(t, dict):
        for key in ("function_declarations", "functionDeclarations"):
            if isinstance(t.get(key), list):
                return {**t, key: sorted(t[key], key=tool_name)}
    return t


_NOT_MARKABLE = {"thinking", "redacted_thinking"}
_LITELLM_ROUTES = {  # LiteLLM route prefixes that honour each provider's cache fields
    "anthropic": {"", "anthropic", "bedrock", "vertex_ai"},
    "openai": {"", "openai"},
    "gemini": {"", "gemini", "vertex_ai"},
}


def _cc(ttl: str) -> Json:
    return {"type": "ephemeral"} if ttl == "5m" else {"type": "ephemeral", "ttl": ttl}


def _drop(t: Any, key: str) -> Any:
    d = plain(t)
    return {k: v for k, v in d.items() if k != key} if isinstance(d, dict) and key in d else t


def _drop_fn(t: Any) -> Any:
    """A LiteLLM tool without a stale cache_control inside its function object."""
    d = plain(t)
    if isinstance(d, dict) and isinstance(d.get("function"), dict) and "cache_control" in d["function"]:
        return {**d, "function": _drop(d["function"], "cache_control")}
    return t


def _check_ttl(provider: str, ttl: str) -> str:
    if ttl not in facts.PROVIDERS[provider].ttls:
        raise ValueError(f"{provider} cache TTL must be one of {facts.PROVIDERS[provider].ttls}, not {ttl!r}")
    return ttl


def _unmark(msg: Any, key: str) -> Any:
    """Copy of msg without `key` markers on its blocks. Markers aren't content; stale ones would pile up."""
    m = plain(msg)
    if not (isinstance(m, dict) and isinstance(m.get("content"), list)):
        return msg
    blocks = [plain(b) for b in m["content"]]
    if not any(isinstance(b, dict) and key in b for b in blocks):
        return msg
    return {**m, "content": [{k: v for k, v in b.items() if k != key} if isinstance(b, dict) else b for b in blocks]}


def openai_explicit(model: str) -> bool:
    """GPT-5.6 and later take explicit cache breakpoints; older models cache implicitly."""
    m = re.search(r"gpt-(\d+)(?:\.(\d+))?", model)
    return m is not None and (int(m[1]), int(m[2] or 0)) >= (5, 6)


def _mark(msg: Any, key: str, marker: Json, text_type: str, only_text: bool) -> Any:
    """Copy of msg with `marker` on its last markable block, or None if it has none. Text never changes."""
    m = dict(plain(msg))
    content = m.get("content")
    if isinstance(content, str):
        if not content.strip():  # providers reject markers on empty text
            return None
        m["content"] = [{"type": text_type, "text": content, key: marker}]
        return m
    if isinstance(content, list):
        blocks = [plain(b) for b in content]
        for i in range(len(blocks) - 1, -1, -1):
            kind = blocks[i].get("type") if isinstance(blocks[i], dict) else None
            ok = kind == text_type if only_text else kind is not None and kind not in _NOT_MARKABLE
            if ok and not (kind in ("text", "input_text") and not str(blocks[i].get("text", "")).strip()):
                blocks[i] = {**blocks[i], key: marker}
                m["content"] = blocks
                return m
    return None


class Prompt:
    """Collect segments in any order; render with an adapter. Output order is fixed:
    tools, system, context, examples, history, retrieved, user.

    `call_site` is any name you choose for the place in your code that makes this call, such as
    "support.answer" or "rag.answer". There is no fixed list. Use one per prompt template, not one per user
    or per request. It groups usage per call site in `Stats`, `record()` and `cachemaxxing report`, and the
    report finds drift by comparing consecutive requests of the same call site. It also names Gemini
    explicit caches, and it is part of `prompt_cache_key` on OpenAI models before GPT-5.6."""

    def __init__(self, call_site: str = "default") -> None:
        self.call_site = call_site
        self._tools: list[Any] = []
        self._system: list[str] = []
        self._context: list[str] = []
        self._examples: list[str] = []
        self._history: list[Any] = []
        self._retrieved: list[str] = []
        self._user: list[str] = []

    def tools(self, tools: Sequence[Any], *, sort: bool = True) -> Self:
        """Tool definitions in your provider's format; sorted by name unless sort=False."""
        self._tools = sorted(map(_sort_tool, tools), key=tool_name) if sort else list(tools)
        return self

    def system(self, text: Parts) -> Self:
        self._system = [t for t in map(normalize_ws, _parts(text)) if t]
        return self

    def context(self, docs: Parts, *, reorderable: bool = False) -> Self:
        """Static reference material. reorderable=True sorts the parts so their order can't drift."""
        parts = [t for t in map(normalize_ws, _parts(docs)) if t]
        self._context = sorted(parts) if reorderable else parts
        return self

    def examples(self, examples: Parts, *, reorderable: bool = False) -> Self:
        parts = [t for t in map(normalize_ws, _parts(examples)) if t]
        self._examples = sorted(parts) if reorderable else parts
        return self

    def messages(self, messages: Sequence[Any]) -> Self:
        """Your whole chat as an OpenAI-style list of {"role": ..., "content": ...} dicts, for any provider.
        Leading system/developer messages become the system prompt; the rest, latest user message included,
        is the conversation. Same as .system(...).history(...)."""
        msgs = list(messages)
        n = 0
        while n < len(msgs) and isinstance(m := plain(msgs[n]), dict) and m.get("role") in ("system", "developer"):
            n += 1
        system = [t for m in msgs[:n] for t in _texts(plain(m).get("content")) or []]
        if system:
            self.system(system)
        return self.history(msgs[n:])

    def history(self, messages: Sequence[Any]) -> Self:
        """Earlier turns, append-only, never modified: your provider's message format, or {"role", "content"}
        text turns (converted for Gemini)."""
        self._history = list(messages)
        return self

    def retrieved(self, chunks: Parts) -> Self:
        """Per-request context (RAG chunks, time, user profile). Placed after history, verbatim."""
        self._retrieved = [t for t in _parts(chunks) if t.strip()]
        return self

    def user(self, text: str) -> Self:
        self._user = [text] if text.strip() else []
        return self

    @property
    def static(self) -> list[str]:
        return self._system + self._context + self._examples

    def _prefix_blob(self) -> str:
        tools = [t.__qualname__ if callable(t) else plain(t) for t in self._tools]  # python-function tools: by name
        return canonical_json([tools, self.static])

    def prefix_hash(self) -> str:
        """16 hex chars that change exactly when the tools or the static text change."""
        return hashlib.sha256(self._prefix_blob().encode()).hexdigest()[:16]

    def est_prefix_tokens(self) -> int:
        # ponytail: ~4 chars/token estimate; pass exact counts to should_cache() when you have them
        return len(self._prefix_blob()) // 4

    def _tail(
        self,
        marker: Json | None,
        key: str,
        text_type: str,
        roles: tuple[str, ...],
        *,
        only_text: bool,
        count: int = 1,
    ) -> list[Any]:
        """History, then the final user turn, with `count` markers on the last markable positions: the final
        user block (unless a per-request retrieved block follows it), then eligible history messages.
        Stale markers in history are stripped first so they never pile up. Anthropic needs one tail marker
        (its 20-block lookback finds earlier entries); OpenAI only looks up at breakpoints present in the
        request, so count=2 also re-marks the position the previous request wrote."""
        msgs = [_unmark(m, key) for m in self._history]
        final: list[Json] = [{"type": text_type, "text": t} for t in self._retrieved + self._user]
        left = count if marker is not None else 0
        if left and final and not self._retrieved:
            final[-1][key] = marker
            left -= 1
        for i in range(len(msgs) - 1, -1, -1):
            if not left:
                break
            m = plain(msgs[i])
            if isinstance(m, dict) and m.get("role") in roles and marker is not None:
                marked = _mark(m, key, marker, text_type, only_text)
                if marked is not None:
                    msgs[i] = marked
                    left -= 1
        if final:
            msgs.append({"role": "user", "content": final})
        return msgs

    def anthropic(self, model: str, *, ttl: str = "5m", diagnose: bool | str = False) -> Json:
        """kwargs for anthropic `client.messages.create(max_tokens=..., **kwargs)`.
        diagnose=True opts in to Anthropic's cache diagnostics; pass the previous response's id on later turns
        and usage(response).miss_reason says what changed (system_changed, tools_changed, ...)."""
        cc = _cc(_check_ttl("anthropic", ttl))
        kw: Json = {"model": model}
        if self._tools:
            tools = [_drop(t, "cache_control") for t in self._tools]
            kw["tools"] = [*tools[:-1], {**plain(tools[-1]), "cache_control": cc}]
        if self.static:
            kw["system"] = [{"type": "text", "text": t} for t in self.static]
            kw["system"][-1]["cache_control"] = cc
        kw["messages"] = self._tail(cc, "cache_control", "text", ("user", "assistant"), only_text=False)
        if diagnose:
            kw["diagnostics"] = {"previous_message_id": diagnose if isinstance(diagnose, str) else None}
        return kw

    def openai(
        self, model: str, *, ttl: str = "30m", cache_key: str | None = None, diagnose: bool | str = False
    ) -> Json:
        """kwargs for openai `client.responses.create(**kwargs)`. diagnose=<previous response id> asks OpenAI
        (GPT-5.6+) to compare with that response; usage(response).miss_reason then says why a cache missed."""
        kw = self._openai(model, ttl, cache_key, field="input", role="developer", text_type="input_text")
        if isinstance(diagnose, str):
            if "prompt_cache_options" not in kw:
                raise ValueError("prompt cache diagnostics need GPT-5.6 or later")
            kw["prompt_cache_options"]["comparison_response_id"] = diagnose
        return kw

    def openai_chat(
        self, model: str, *, ttl: str = "30m", cache_key: str | None = None, diagnose: bool | str = False
    ) -> Json:
        """kwargs for openai `client.chat.completions.create(**kwargs)` and OpenAI-compatible servers."""
        if ttl == "12h":
            raise ValueError("the 12h cache TTL is Responses-only; use Prompt.openai()")
        if isinstance(diagnose, str):
            raise ValueError("prompt cache diagnostics are Responses-only; use Prompt.openai()")
        return self._openai(model, ttl, cache_key, field="messages", role="system", text_type="text")

    def _openai(self, model: str, ttl: str, cache_key: str | None, *, field: str, role: str, text_type: str) -> Json:
        explicit = openai_explicit(model)
        if explicit:
            _check_ttl("openai", ttl)
        bp: Json | None = {"mode": "explicit"} if explicit else None
        kw: Json = {"model": model}
        if self._tools:
            kw["tools"] = list(self._tools)
        msgs: list[Any] = []
        if self.static:
            parts: list[Json] = [{"type": text_type, "text": t} for t in self.static]
            if bp is not None:
                parts[-1]["prompt_cache_breakpoint"] = bp
            msgs.append({"role": role, "content": parts})
        roles = ("user", "developer", "system")
        msgs += self._tail(bp, "prompt_cache_breakpoint", text_type, roles, only_text=True, count=2)
        kw[field] = msgs
        if explicit:
            kw["prompt_cache_options"] = {"mode": "explicit", "ttl": ttl}
        if cache_key or not explicit:
            kw["prompt_cache_key"] = cache_key or f"{self.call_site}:{self.prefix_hash()}"
        return kw

    def gemini(self, model: str, *, cached_content: str | None = None) -> Json:
        """kwargs for google-genai `client.models.generate_content(**kwargs)`. Implicit caching unless
        cached_content (from gemini_cache) is given; then the cached fields are left out."""
        config: Json = {"cached_content": cached_content} if cached_content else self.gemini_prefix()
        contents = [_gemini_turn(m) for m in self._history]
        final = [{"text": t} for t in self._retrieved + self._user]
        if final:
            contents.append({"role": "user", "parts": final})
        return {"model": model, "contents": contents, "config": config}

    def gemini_prefix(self) -> Json:
        """The cacheable part of a Gemini request: what an explicit cache holds."""
        prefix: Json = {}
        if self.static:
            prefix["system_instruction"] = {"parts": [{"text": t} for t in self.static]}
        if self._tools:
            prefix["tools"] = list(self._tools)
        return prefix

    def litellm(self, model: str, *, ttl: str | None = None, explicit: bool = False) -> Json:
        """kwargs for `litellm.completion(**kwargs)` (or the LiteLLM Proxy via the OpenAI SDK), model included.
        Cache fields follow the route: Claude gets cache_control, openai/ gets openai_chat(), gemini/ stays
        implicit unless explicit=True (LiteLLM then creates an explicit cache for the static prefix)."""
        route = model.split("/", 1)[0] if "/" in model else ""
        provider = facts.provider_of(model)
        if route not in _LITELLM_ROUTES.get(provider, set()):
            provider = "other"
        if provider == "openai":
            return self.openai_chat(model, ttl=ttl or "30m")
        if provider == "gemini" and explicit and (fm := facts.find(model)) is not None and fm.storage_hour is None:
            raise ValueError(f"{model} has no explicit caching; drop explicit=True")
        mark = provider == "anthropic" or (provider == "gemini" and explicit)
        marker = _cc(_check_ttl("anthropic", ttl or "5m")) if mark else None
        kw: Json = {"model": model}
        if self._tools:
            tools = [_drop_fn(t) for t in self._tools]
            last = plain(tools[-1])
            if provider == "anthropic" and isinstance(last, dict) and isinstance(last.get("function"), dict):
                tools[-1] = {**last, "function": {**last["function"], "cache_control": marker}}
            kw["tools"] = tools
        msgs: list[Any] = []
        if self.static:
            parts: list[Json] = [{"type": "text", "text": t} for t in self.static]
            if marker is not None:
                parts[-1]["cache_control"] = marker
            msgs.append({"role": "system", "content": parts})
        # Gemini explicit caches cover the static prefix only; a history marker would create a cache per turn.
        tail_marker = marker if provider == "anthropic" else None
        msgs += self._tail(tail_marker, "cache_control", "text", ("user", "assistant"), only_text=True)
        kw["messages"] = msgs
        return kw
