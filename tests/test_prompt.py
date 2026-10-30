from cachemaxxing.prompt import Prompt

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
