"""Prompt: segments ordered from most to least stable, rendered as request kwargs per provider."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, Self

from .canon import canonical_json, normalize_ws, plain, tool_name

Json = dict[str, Any]
Parts = str | Mapping[str, Any] | Sequence[str | Mapping[str, Any]]


def _parts(x: Parts) -> list[str]:
    """Text parts: strings verbatim, anything else as canonical JSON."""
    items: Sequence[Any] = [x] if isinstance(x, str | Mapping) else x
    return [p if isinstance(p, str) else canonical_json(p) for p in items]


def _sort_tool(t: Any) -> Any:
    if isinstance(t, dict) and isinstance(t.get("function_declarations"), list):
        return {**t, "function_declarations": sorted(t["function_declarations"], key=tool_name)}
    return t


_NOT_MARKABLE = {"thinking", "redacted_thinking"}


def _cc(ttl: str) -> Json:
    return {"type": "ephemeral"} if ttl == "5m" else {"type": "ephemeral", "ttl": ttl}


def openai_explicit(model: str) -> bool:
    """GPT-5.6 and later take explicit cache breakpoints; older models cache implicitly."""
    m = re.search(r"gpt-(\d+)(?:\.(\d+))?", model)
    return m is not None and (int(m[1]), int(m[2] or 0)) >= (5, 6)


def _mark(msg: Any, key: str, marker: Json, text_type: str, only_text: bool) -> Any:
    """Copy of msg with `marker` on its last markable block, or None if it has none. Text never changes."""
    m = dict(plain(msg))
    content = m.get("content")
    if isinstance(content, str):
        m["content"] = [{"type": text_type, "text": content, key: marker}]
        return m
    if isinstance(content, list):
        blocks = [plain(b) for b in content]
        for i in range(len(blocks) - 1, -1, -1):
            kind = blocks[i].get("type") if isinstance(blocks[i], dict) else None
            ok = kind == text_type if only_text else kind is not None and kind not in _NOT_MARKABLE
            if ok:
                blocks[i] = {**blocks[i], key: marker}
                m["content"] = blocks
                return m
    return None


class Prompt:
    """Collect segments in any order; render with an adapter. Output order is fixed:
    tools, system, context, examples, history, retrieved, user."""

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
        self._system = [normalize_ws(t) for t in _parts(text)]
        return self

    def context(self, docs: Parts, *, reorderable: bool = False) -> Self:
        """Static reference material. reorderable=True sorts the parts so their order can't drift."""
        parts = [normalize_ws(t) for t in _parts(docs)]
        self._context = sorted(parts) if reorderable else parts
        return self

    def examples(self, examples: Parts, *, reorderable: bool = False) -> Self:
        parts = [normalize_ws(t) for t in _parts(examples)]
        self._examples = sorted(parts) if reorderable else parts
        return self

    def history(self, messages: Sequence[Any]) -> Self:
        """Earlier turns in your provider's message format. Append-only; never modified."""
        self._history = list(messages)
        return self

    def retrieved(self, chunks: Parts) -> Self:
        """Per-request context (RAG chunks, time, user profile). Placed after history, verbatim."""
        self._retrieved = _parts(chunks)
        return self

    def user(self, text: str) -> Self:
        self._user = [text]
        return self

    @property
    def static(self) -> list[str]:
        return self._system + self._context + self._examples

    def _prefix_blob(self) -> str:
        return canonical_json([[plain(t) for t in self._tools], self.static])

    def prefix_hash(self) -> str:
        """16 hex chars that change exactly when the tools or the static text change."""
        return hashlib.sha256(self._prefix_blob().encode()).hexdigest()[:16]

    def est_prefix_tokens(self) -> int:
        # ponytail: ~4 chars/token estimate; pass exact counts to should_cache() when you have them
        return len(self._prefix_blob()) // 4

    def _tail(
        self, marker: Json | None, key: str, text_type: str, roles: tuple[str, ...], *, only_text: bool
    ) -> list[Any]:
        """History, then the final user turn, with one marker at the end of what the next request repeats:
        the final user block, or the end of history when a per-request retrieved block follows."""
        msgs = list(self._history)
        final: list[Json] = [{"type": text_type, "text": t} for t in self._retrieved + self._user]
        if marker is not None:
            if final and not self._retrieved:
                final[-1][key] = marker
            else:
                for i in range(len(msgs) - 1, -1, -1):
                    m = plain(msgs[i])
                    if isinstance(m, dict) and m.get("role") in roles:
                        marked = _mark(m, key, marker, text_type, only_text)
                        if marked is not None:
                            msgs[i] = marked
                            break
        if final:
            msgs.append({"role": "user", "content": final})
        return msgs

    def anthropic(self, model: str, *, ttl: str = "5m") -> Json:
        """kwargs for anthropic `client.messages.create(max_tokens=..., **kwargs)`."""
        cc = _cc(ttl)
        kw: Json = {"model": model}
        if self._tools:
            kw["tools"] = [*self._tools[:-1], {**plain(self._tools[-1]), "cache_control": cc}]
        if self.static:
            kw["system"] = [{"type": "text", "text": t} for t in self.static]
            kw["system"][-1]["cache_control"] = cc
        kw["messages"] = self._tail(cc, "cache_control", "text", ("user", "assistant"), only_text=False)
        return kw

    def openai(self, model: str, *, ttl: str = "30m", cache_key: str | None = None) -> Json:
        """kwargs for openai `client.responses.create(**kwargs)`."""
        return self._openai(model, ttl, cache_key, field="input", role="developer", text_type="input_text")

    def openai_chat(self, model: str, *, ttl: str = "30m", cache_key: str | None = None) -> Json:
        """kwargs for openai `client.chat.completions.create(**kwargs)` and OpenAI-compatible servers."""
        if ttl == "12h":
            raise ValueError("the 12h cache TTL is Responses-only; use Prompt.openai()")
        return self._openai(model, ttl, cache_key, field="messages", role="system", text_type="text")

    def _openai(self, model: str, ttl: str, cache_key: str | None, *, field: str, role: str, text_type: str) -> Json:
        explicit = openai_explicit(model)
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
        msgs += self._tail(bp, "prompt_cache_breakpoint", text_type, ("user", "developer", "system"), only_text=True)
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
        contents = list(self._history)
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
