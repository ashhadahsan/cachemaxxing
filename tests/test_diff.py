from typing import Any

from cachemaxxing.diff import Divergence, diff

SYS = "You are helpful. Today is 2026-10-30T10:00:00Z."
BASE: dict[str, Any] = {
    "model": "m",
    "tools": [{"name": "a"}, {"name": "b"}],
    "system": [{"type": "text", "text": SYS}],
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 5,
}


def w(**kw: Any) -> dict[str, Any]:
    return {**BASE, **kw}


def hint(a: Any, b: Any) -> str | None:
    d = diff(a, b)
    assert isinstance(d, Divergence)
    return d.hint


def test_identical_and_appended_requests_do_not_diverge() -> None:
    assert diff(BASE, BASE) is None
    assert diff(BASE, w(messages=[*BASE["messages"], {"role": "assistant", "content": "yo"}])) is None


def test_timestamp() -> None:
    d = diff(BASE, w(system=[{"type": "text", "text": SYS.replace("10:00", "10:05")}]))
    assert d is not None and d.path == "system[0].text" and d.hint == "timestamp"
    assert d.offset == len("You are helpful. Today is 2026-10-30T10:0")


def test_uuid_and_hex_ids() -> None:
    a = w(system="req 3f2b8c1e-9a4d-4e5f-8b6a-1c2d3e4f5a6b")
    assert hint(a, w(system="req 7d1e2f3a-4b5c-4d6e-9f80-a1b2c3d4e5f6")) == "uuid"
    assert hint(w(system="id 0123456789abcdef01"), w(system="id fedcba9876543210ff")) == "hex id"


def test_tool_order_and_key_order() -> None:
    assert hint(BASE, w(tools=[{"name": "b"}, {"name": "a"}])) == "tool order"
    a, b = w(tools=[{"name": "a", "description": "x"}]), w(tools=[{"description": "x", "name": "a"}])
    assert hint(a, b) == "key order"


def test_markers_string_content_and_outside_params_are_ignored() -> None:
    block = {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}
    assert diff(w(messages=[{"role": "user", "content": [block]}]), BASE) is None
    assert diff({"call_site": "x", "request": BASE}, w(max_tokens=99, temperature=1)) is None


def test_model_whitespace_removed_and_last_turn() -> None:
    assert hint(BASE, w(model="m2")) == "model"
    assert hint(w(system="You are  helpful"), w(system="You are helpful")) == "whitespace"
    two = w(messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}])
    assert hint(two, BASE) == "removed"
    rag = w(messages=[{"role": "user", "content": "chunk\nhi"}])
    assert hint(rag, two) == "last turn"


def test_gemini_config_counts_only_prefix_fields() -> None:
    a = {"model": "g", "contents": [], "config": {"system_instruction": "S", "temperature": 0}}
    assert diff(a, {**a, "config": {"system_instruction": "S", "temperature": 1}}) is None
    d = diff(a, {**a, "config": {"system_instruction": "S2"}})
    assert d is not None and d.path == "config.system_instruction"


def test_str_is_readable() -> None:
    d = diff(BASE, w(system=[{"type": "text", "text": SYS.replace("10:00", "10:05")}]))
    assert "system[0].text" in str(d) and "(timestamp)" in str(d)
