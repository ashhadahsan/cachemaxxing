from typing import Any

from cachemaxxing.canon import canonical_json, jsonable, normalize_ws, tool_name


def test_canonical_json_ignores_key_order_and_keeps_unicode() -> None:
    assert canonical_json({"b": 1, "a": [1, {"d": 2, "c": "é"}]}) == '{"a":[1,{"c":"é","d":2}],"b":1}'


def test_normalize_ws_keeps_indentation_and_inner_spacing() -> None:
    assert normalize_ws("\r\n  def f():  \r\n    return  1\t\n\n") == "  def f():\n    return  1"


def test_tool_name_for_every_format() -> None:
    assert tool_name({"name": "a", "input_schema": {}}) == "a"
    assert tool_name({"type": "function", "name": "b"}) == "b"
    assert tool_name({"type": "function", "function": {"name": "c"}}) == "c"
    assert tool_name({"function_declarations": []}) == ""


def test_jsonable_converts_sdk_objects_recursively() -> None:
    class Obj:
        def model_dump(self, **kw: Any) -> dict[str, int]:
            return {"x": 1}

    assert jsonable({"a": [Obj(), (1, 2)]}) == {"a": [{"x": 1}, [1, 2]]}
