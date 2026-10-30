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
