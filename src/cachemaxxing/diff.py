"""Find where request b stops repeating request a's cacheable prefix."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .canon import jsonable

_ORDER = ("model", "tools", "system", "instructions", "config", "messages", "input", "contents")
_GEMINI_PREFIX = ("cached_content", "system_instruction", "tools", "tool_config")
_LISTS = ("messages", "input", "contents")
_MARKERS = {"cache_control", "prompt_cache_breakpoint"}
_TEXT_TYPES = {"text", "input_text", "output_text"}
_TOOL_NAME = re.compile(r"(?:config\.)?tools\[\d+\](?:\.function|\.function_declarations\[\d+\])?\.name")
_HINTS = (
    ("uuid", re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")),
    ("timestamp", re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d|\b\d{1,2}:\d\d:\d\d\b|\b1\d{9}(?:\d{3})?\b")),
    ("hex id", re.compile(r"\b[0-9a-f]{16,}\b")),
)

FIXES = {  # what to do about each hint: shown by warnings, `report`, `cachemaxxing diff` and the dashboard
    "timestamp": "A time changes on every call. Move it into .retrieved(), after the cached prefix.",
    "uuid": "An id changes on every call. Drop it from the prompt, or move it into .retrieved().",
    "hex id": "An id changes on every call. Drop it from the prompt, or move it into .retrieved().",
    "tool order": "The same tools arrive in a different order. Pass them through Prompt.tools(), which sorts them.",
    "key order": "The same JSON is serialized with another key order. Pass dicts to Prompt, or use canonical_json().",
    "whitespace": "Only whitespace differs. Prompt normalizes whitespace in system, context and examples.",
    "model": "The model changed. Different models never share a cache.",
    "removed": "This call dropped part of the previous one, such as trimmed history. Trim less often, in bigger steps.",
    "last turn": "Only the newest turn differs: that is how a conversation grows, not a miss.",
}
GENERIC_FIX = "Anything that changes per request belongs after the cached prefix: in .retrieved() or .user()."
NO_READ = "prefix ok, no cache read"
NO_READ_WHY = (
    "The request repeated the previous one, but nothing was read from cache: the cache expired (the TTL counts "
    "from the previous request), the prefix is below the provider's minimum, or the request reached another server."
)


@dataclass(frozen=True)
class Divergence:
    path: str  # where the two requests differ, e.g. "system[0].text"
    offset: int  # characters into that value
    a: str  # text around the divergence in request a
    b: str  # ... and in request b
    hint: str | None  # model, tool order, key order, removed, last turn, whitespace, uuid, timestamp, hex id
    prefix_chars: int  # identical characters before it (about 4 per token)

    def __str__(self) -> str:
        why = f" ({self.hint})" if self.hint else ""
        return (
            f"diverges at {self.path} char {self.offset}{why}, after ~{self.prefix_chars // 4:,} matching tokens\n"
            f"  a: {self.a!r}\n  b: {self.b!r}\n  fix: {self.fix}"
        )

    @property
    def fix(self) -> str:
        """What to change so the next request repeats this one's prefix."""
        return FIXES.get(self.hint or "", GENERIC_FIX)


def _leaves(x: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(x, dict):
        if isinstance(x.get("content"), str):  # "hi" renders like [{"type": "text", "text": "hi"}]
            x = {**x, "content": [{"type": "text", "text": x["content"]}]}
        for k, v in x.items():
            if k not in _MARKERS and not (k == "type" and v in _TEXT_TYPES):
                yield from _leaves(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, x if isinstance(x, str) else json.dumps(x)


def _snake(key: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", key).lower()


def _request(r: Any) -> dict[str, Any]:
    r = jsonable(r)
    if not isinstance(r, dict):
        raise ValueError("expected a request object (a JSON dict) or a record() line")
    inner = r.get("request")
    return inner if isinstance(inner, dict) else r


def _flat(req: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k in _ORDER:
        if k in req:
            v = req[k]
            if k == "config" and isinstance(v, dict):  # google-genai accepts camelCase keys too
                snake = {_snake(key): x for key, x in v.items()}
                v = {c: snake[c] for c in _GEMINI_PREFIX if c in snake}
                if isinstance(v.get("system_instruction"), str):
                    v["system_instruction"] = {"parts": [{"text": v["system_instruction"]}]}
            elif k == "system" and isinstance(v, str):  # "S" renders like [{"type": "text", "text": "S"}]
                v = [{"type": "text", "text": v}]
            out += _leaves(v, k)
    return out


def diff(a: Any, b: Any) -> Divergence | None:
    """First point where b stops repeating a's prompt; None when b repeats all of a.
    Accepts request kwargs, SDK objects, or record() lines."""
    ra, rb = _request(a), _request(b)
    fa, fb = _flat(ra), _flat(rb)
    seen = 0
    for i, (pa, va) in enumerate(fa):
        if i == len(fb):
            return Divergence(pa, 0, va[:60], "", "removed", seen)
        pb, vb = fb[i]
        if pa != pb:
            parent = pa.rsplit(".", 1)[0]
            same = pb.rsplit(".", 1)[0] == parent and {x for x in fa if x[0].startswith(parent)} == {
                x for x in fb if x[0].startswith(parent)
            }
            return Divergence(f"{pa} / {pb}", 0, va[:60], vb[:60], "key order" if same else None, seen)
        if va != vb:
            off = len(os.path.commonprefix([va, vb]))
            hint = _hint(pa, va, vb, off, fa, fb, ra)
            return Divergence(pa, off, _ctx(va, off), _ctx(vb, off), hint, seen + off)
        seen += len(va)
    return None


def _ctx(value: str, off: int) -> str:
    """The whole value when it's short, otherwise 40 characters either side of the divergence."""
    return value if len(value) <= 100 else value[max(0, off - 40) : off + 40]


def _hint(
    path: str, va: str, vb: str, off: int, fa: list[tuple[str, str]], fb: list[tuple[str, str]], ra: dict[str, Any]
) -> str | None:
    if path == "model":
        return "model"
    names_a = [v for p, v in fa if _TOOL_NAME.fullmatch(p)]
    names_b = [v for p, v in fb if _TOOL_NAME.fullmatch(p)]
    if "tools" in path.split("[")[0] and names_a != names_b and sorted(names_a) == sorted(names_b):
        return "tool order"
    for k in _LISTS:
        items = ra.get(k)
        if isinstance(items, list) and items and path.startswith(f"{k}[{len(items) - 1}]"):
            return "last turn"
    if va.split() == vb.split():
        return "whitespace"
    wa, wb = va[max(0, off - 40) : off + 40], vb[max(0, off - 40) : off + 40]
    return next((name for name, rx in _HINTS if rx.search(wa) and rx.search(wb)), None)
