"""Prompt: segments ordered from most to least stable, rendered as request kwargs per provider."""

from __future__ import annotations

import hashlib
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
