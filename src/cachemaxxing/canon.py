"""Deterministic serialization helpers."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Same data, same bytes: sorted keys, fixed separators, non-ASCII kept."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def normalize_ws(text: str) -> str:
    """LF line endings, no trailing whitespace per line, no blank lines at either end."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def plain(obj: Any) -> Any:
    """An SDK (pydantic) object as a plain dict; anything else unchanged."""
    dump = getattr(obj, "model_dump", None)
    return dump(mode="json", exclude_none=True) if callable(dump) else obj


def jsonable(obj: Any) -> Any:
    """`plain`, applied recursively; tuples become lists."""
    obj = plain(obj)
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [jsonable(v) for v in obj]
    return obj


def tool_name(tool: Any) -> str:
    """Name of an Anthropic, OpenAI (Responses or Chat) or Gemini function tool; '' if none."""
    t = plain(tool)
    if not isinstance(t, dict):
        return ""
    fn = t.get("function")
    return str(fn.get("name", "") if isinstance(fn, dict) else t.get("name", ""))
