from typing import Any

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


def test_stale_markers_in_history_do_not_pile_up() -> None:
    hist: list[Any] = [{"role": "user", "content": "q0"}]
    for i in range(4):
        kw = Prompt().tools(TOOLS).system("S").history(hist).user(f"q{i + 1}").anthropic("claude-haiku-5-5")
        assert str(kw).count("cache_control") <= 3
        hist = [*kw["messages"], {"role": "assistant", "content": f"a{i}"}]
    hist = []
    for i in range(4):  # OpenAI: stale breakpoints stripped; the previous turn's position is re-marked instead
        kw = Prompt().system("S").history(hist).user(f"q{i}").openai("gpt-6-luna")
        assert str(kw).count("prompt_cache_breakpoint") == min(i + 2, 3)
        hist = [*kw["input"][1:], {"role": "assistant", "content": f"a{i}"}]
    assert "prompt_cache_breakpoint" not in str(Prompt().history(hist).user("q").openai("gpt-5.5"))
    claude_marked = [{"role": "user", "content": [{"type": "text", "text": "hi", "cache_control": CC}]}]
    assert "cache_control" not in str(
        Prompt().system("S").history(claude_marked).user("q").litellm("gemini/gemini-3.8-flash")
    )


def test_empty_parts_are_dropped() -> None:
    kw = Prompt().system("S").context("").retrieved(["", "  "]).user("q").anthropic("m")
    assert kw["system"] == [{"type": "text", "text": "S", "cache_control": CC}]
    assert kw["messages"] == [{"role": "user", "content": [{"type": "text", "text": "q", "cache_control": CC}]}]
    assert Prompt().user("  ")._user == []


def test_ttls_are_validated_per_provider() -> None:
    with pytest.raises(ValueError):
        Prompt().user("q").anthropic("m", ttl="30m")
    with pytest.raises(ValueError):
        Prompt().user("q").openai("gpt-6-luna", ttl="1h")
    with pytest.raises(ValueError):
        Prompt().user("q").litellm("openai/gpt-6-luna", ttl="1h")
    with pytest.raises(ValueError, match="explicit"):
        Prompt().system("S").user("q").litellm("gemini/gemini-4-argon", explicit=True)


def test_gemini_tool_objects_and_camel_case_are_sorted() -> None:
    class Tool:
        def model_dump(self, **kw: Any) -> dict[str, Any]:
            return {"function_declarations": [{"name": "z"}, {"name": "a"}]}

    assert [d["name"] for d in Prompt().tools([Tool()])._tools[0]["function_declarations"]] == ["a", "z"]
    camel = Prompt().tools([{"functionDeclarations": [{"name": "z"}, {"name": "a"}]}])
    assert [d["name"] for d in camel._tools[0]["functionDeclarations"]] == ["a", "z"]


def test_python_function_tools_hash_stably() -> None:
    def get_weather(city: str) -> str:
        return city

    a, b = Prompt().tools([get_weather]).system("S"), Prompt().tools([get_weather]).system("S")
    assert a.prefix_hash() == b.prefix_hash() and a.est_prefix_tokens() > 0


def test_litellm_stale_tool_markers_are_replaced() -> None:
    stale = [{"type": "function", "function": {"name": "z", "parameters": {}, "cache_control": CC}}, *CHAT_TOOLS]
    kw = Prompt().tools(stale).system("S").user("q").litellm("anthropic/claude-haiku-5-5")
    assert str(kw["tools"]).count("cache_control") == 1 and "cache_control" in kw["tools"][-1]["function"]


def test_marker_skips_empty_text_blocks() -> None:
    hist = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": ""}]
    kw = Prompt().system("S").history(hist).retrieved("chunk").user("q").anthropic("m")
    assert kw["messages"][0]["content"] == [{"type": "text", "text": "hi", "cache_control": CC}]
    assert kw["messages"][1] == {"role": "assistant", "content": ""}
    blocks = [{"role": "assistant", "content": [{"type": "text", "text": "yo"}, {"type": "text", "text": " "}]}]
    kw = Prompt().history(blocks).retrieved("c").user("q").anthropic("m")
    assert (
        kw["messages"][0]["content"][0]["cache_control"] == CC
        and "cache_control" not in kw["messages"][0]["content"][1]
    )


def test_openai_re_marks_the_previous_turns_position() -> None:
    hist = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    marked = lambda kw: [i for i, m in enumerate(kw["input"]) if "prompt_cache_breakpoint" in str(m)]  # noqa: E731
    chat = Prompt().system("S").history(hist).user("q3").openai("gpt-6-luna")
    assert marked(chat) == [0, 3, 5]  # static, previous final (q2), this final (q3)
    rag = Prompt().system("S").history(hist).retrieved("chunk").user("q3").openai("gpt-6-luna")
    assert marked(rag) == [0, 1, 3]  # static, previous history end (q1), this history end (q2)
    anthropic = Prompt().system("S").history(hist).user("q3").anthropic("m")
    assert str(anthropic["messages"]).count("cache_control") == 1  # Anthropic's lookback finds earlier entries


def test_diagnose_requests_the_providers_own_miss_reasons() -> None:
    p = Prompt().system("S").user("q")
    assert p.anthropic("m", diagnose=True)["diagnostics"] == {"previous_message_id": None}
    assert p.anthropic("m", diagnose="msg_1")["diagnostics"] == {"previous_message_id": "msg_1"}
    assert "diagnostics" not in p.anthropic("m")
    opts = p.openai("gpt-6-luna", diagnose="resp_1")["prompt_cache_options"]
    assert opts == {"mode": "explicit", "ttl": "30m", "comparison_response_id": "resp_1"}
    assert "comparison_response_id" not in str(p.openai("gpt-6-luna", diagnose=True))
    with pytest.raises(ValueError, match="Responses"):
        p.openai_chat("gpt-6-luna", diagnose="resp_1")
    with pytest.raises(ValueError, match="GPT-5.6"):
        p.openai("gpt-5.5", diagnose="resp_1")
