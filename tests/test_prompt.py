import pytest

from cachemaxxing.prompt import Prompt, openai_explicit

TOOLS = [
    {"name": "search", "description": "s", "input_schema": {"type": "object"}},
    {"name": "calc", "description": "c", "input_schema": {"type": "object"}},
]


def test_tools_sorted_by_name_unless_opted_out() -> None:
    assert [t["name"] for t in Prompt().tools(TOOLS)._tools] == ["calc", "search"]
    assert [t["name"] for t in Prompt().tools(TOOLS, sort=False)._tools] == ["search", "calc"]


def test_gemini_declarations_sorted_inside_each_tool() -> None:
    p = Prompt().tools([{"function_declarations": [{"name": "z"}, {"name": "a"}]}])
    assert [d["name"] for d in p._tools[0]["function_declarations"]] == ["a", "z"]


def test_static_text_normalized_data_canonical_and_reorderable() -> None:
    p = Prompt().system("A  \r\nB\n").context([{"b": 1, "a": 2}, "doc"]).examples(["y", "x"], reorderable=True)
    assert p.static == ["A\nB", '{"a":2,"b":1}', "doc", "x", "y"]


def test_volatile_segments_are_verbatim() -> None:
    p = Prompt().retrieved("  chunk  \r\n").user(" q ")
    assert p._retrieved == ["  chunk  \r\n"] and p._user == [" q "]


def test_prefix_hash_tracks_only_tools_and_static_text() -> None:
    base = Prompt().tools(TOOLS).system("S")
    assert base.prefix_hash() == Prompt().tools(TOOLS[::-1]).system("S").user("x").prefix_hash()
    assert base.prefix_hash() != Prompt().tools(TOOLS).system("S2").prefix_hash()
    assert len(base.prefix_hash()) == 16 and base.est_prefix_tokens() > 0


CC = {"type": "ephemeral"}
HIST = [
    {"role": "user", "content": "hi"},
    {
        "role": "assistant",
        "content": [{"type": "thinking", "thinking": "", "signature": "s"}, {"type": "text", "text": "yo"}],
    },
]


def full(order: list[str]) -> Prompt:
    p = Prompt("t")
    steps = {
        "tools": lambda: p.tools(TOOLS),
        "system": lambda: p.system("S"),
        "context": lambda: p.context(["d1", "d2"]),
        "history": lambda: p.history(HIST),
        "retrieved": lambda: p.retrieved("chunk"),
        "user": lambda: p.user("q"),
    }
    for name in order:
        steps[name]()
    return p


def test_call_order_does_not_matter() -> None:
    order = ["tools", "system", "context", "history", "retrieved", "user"]
    assert full(order).anthropic("m") == full(order[::-1]).anthropic("m")


def test_anthropic_layout_and_markers() -> None:
    kw = Prompt().tools(TOOLS).system("S").context("D").history(HIST).user("q").anthropic("claude-haiku-5-5")
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["tools"][-1]["cache_control"] == CC and "cache_control" not in kw["tools"][0]
    assert kw["system"] == [{"type": "text", "text": "S"}, {"type": "text", "text": "D", "cache_control": CC}]
    assert kw["messages"][:2] == HIST
    assert kw["messages"][-1] == {"role": "user", "content": [{"type": "text", "text": "q", "cache_control": CC}]}


def test_retrieved_moves_marker_to_history_end_skipping_thinking() -> None:
    kw = Prompt().system("S").history(HIST).retrieved("chunk").user("q").anthropic("m", ttl="1h")
    blocks = kw["messages"][1]["content"]
    assert "cache_control" not in blocks[0]
    assert blocks[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert all("cache_control" not in b for b in kw["messages"][-1]["content"])


def test_history_never_mutated_and_at_most_three_markers() -> None:
    hist = [dict(m) for m in HIST]
    kw = Prompt().tools(TOOLS).system("S").history(hist).retrieved("c").user("q").anthropic("m")
    assert hist == HIST
    assert str(kw).count("cache_control") <= 3


def test_question_already_in_history_gets_the_marker() -> None:
    kw = Prompt().system("S").history([*HIST, {"role": "user", "content": "q"}]).anthropic("m")
    assert kw["messages"][-1]["content"] == [{"type": "text", "text": "q", "cache_control": CC}]


BP = {"mode": "explicit"}
OAI_HIST = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]


def test_responses_explicit_mode_on_gpt_5_6_plus() -> None:
    kw = Prompt("support").system("S").history(OAI_HIST).user("q").openai("gpt-6-luna")
    assert kw["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert "prompt_cache_key" not in kw
    assert kw["input"][0] == {
        "role": "developer",
        "content": [{"type": "input_text", "text": "S", "prompt_cache_breakpoint": BP}],
    }
    assert kw["input"][-1] == {
        "role": "user",
        "content": [{"type": "input_text", "text": "q", "prompt_cache_breakpoint": BP}],
    }


def test_retrieved_marks_last_user_message_never_assistant() -> None:
    kw = Prompt().system("S").history(OAI_HIST).retrieved("c").user("q").openai("gpt-6.1-sol")
    assert kw["input"][1]["content"] == [{"type": "input_text", "text": "hi", "prompt_cache_breakpoint": BP}]
    assert kw["input"][2] == {"role": "assistant", "content": "yo"}


def test_legacy_models_get_prompt_cache_key_only() -> None:
    p = Prompt("support").system("S").user("q")
    kw = p.openai("gpt-5.5")
    assert kw["prompt_cache_key"] == f"support:{p.prefix_hash()}"
    assert "prompt_cache_options" not in kw and "prompt_cache_breakpoint" not in str(kw)


def test_cache_key_override_and_chat_shape() -> None:
    kw = Prompt().system("S").user("q").openai_chat("gpt-6-luna", cache_key="tenant-42")
    assert kw["prompt_cache_key"] == "tenant-42"
    assert kw["messages"][0] == {
        "role": "system",
        "content": [{"type": "text", "text": "S", "prompt_cache_breakpoint": BP}],
    }
    with pytest.raises(ValueError, match="Responses-only"):
        Prompt().user("q").openai_chat("gpt-6-luna", ttl="12h")


def test_openai_explicit_detection() -> None:
    assert all(map(openai_explicit, ["gpt-5.6", "openai/gpt-6.1-sol", "gpt-6-luna-2026-09-01", "gpt-7"]))
    assert not any(map(openai_explicit, ["gpt-5.5", "gpt-5", "gpt-4.1", "o3", "claude-x"]))


GTOOLS = [{"function_declarations": [{"name": "f", "description": "d"}]}]


def test_gemini_implicit_layout() -> None:
    kw = (
        Prompt()
        .tools(GTOOLS)
        .system("S")
        .context("D")
        .history([{"role": "user", "parts": [{"text": "hi"}]}])
        .retrieved("c")
        .user("q")
        .gemini("gemini-3.8-flash")
    )
    assert kw["model"] == "gemini-3.8-flash"
    assert kw["config"] == {"system_instruction": {"parts": [{"text": "S"}, {"text": "D"}]}, "tools": GTOOLS}
    assert kw["contents"][-1] == {"role": "user", "parts": [{"text": "c"}, {"text": "q"}]}
    assert "cache_control" not in str(kw)


def test_gemini_cached_content_omits_what_the_cache_holds() -> None:
    kw = Prompt().tools(GTOOLS).system("S").user("q").gemini("gemini-3.8-flash", cached_content="cachedContents/1")
    assert kw["config"] == {"cached_content": "cachedContents/1"}


CHAT_TOOLS = [
    {"type": "function", "function": {"name": "b", "parameters": {}}},
    {"type": "function", "function": {"name": "a", "parameters": {}}},
]


def test_litellm_claude_markers_in_openai_format() -> None:
    kw = Prompt().tools(CHAT_TOOLS).system("S").user("q").litellm("anthropic/claude-haiku-5-5")
    assert kw["model"] == "anthropic/claude-haiku-5-5"
    assert [t["function"]["name"] for t in kw["tools"]] == ["a", "b"]
    assert kw["tools"][-1]["function"]["cache_control"] == CC
    assert kw["messages"][0] == {"role": "system", "content": [{"type": "text", "text": "S", "cache_control": CC}]}
    assert kw["messages"][-1]["content"][-1]["cache_control"] == CC


def test_litellm_openai_route_equals_openai_chat() -> None:
    p = Prompt("x").system("S").user("q")
    assert p.litellm("openai/gpt-6-luna") == p.openai_chat("openai/gpt-6-luna")


def test_litellm_gemini_implicit_unless_explicit_then_static_only() -> None:
    p = Prompt().system("S").history([{"role": "user", "content": "hi"}]).user("q")
    assert "cache_control" not in str(p.litellm("gemini/gemini-3.8-flash"))
    kw = p.litellm("gemini/gemini-3.8-flash", explicit=True)
    assert kw["messages"][0]["content"][-1]["cache_control"] == CC
    assert "cache_control" not in str(kw["messages"][1:])


def test_litellm_unknown_route_is_plain() -> None:
    kw = Prompt().system("S").user("q").litellm("mistral/mistral-large")
    assert "cache" not in str(kw) and kw["model"] == "mistral/mistral-large"
