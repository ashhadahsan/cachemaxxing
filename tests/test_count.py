from types import SimpleNamespace
from typing import Any

import pytest

from cachemaxxing.count import prefix_tokens
from cachemaxxing.prompt import Prompt

TOOLS = [{"name": "lookup", "description": "d", "input_schema": {"type": "object"}}]


def recorder(result: Any) -> tuple[list[dict[str, Any]], Any]:
    calls: list[dict[str, Any]] = []

    def fn(**kw: Any) -> Any:
        calls.append(kw)
        return result

    return calls, fn


def test_anthropic_counts_tools_and_static_text() -> None:
    calls, fn = recorder(SimpleNamespace(input_tokens=5012))
    client = SimpleNamespace(messages=SimpleNamespace(count_tokens=fn))
    p = Prompt().tools(TOOLS).system("S").context("D").history([{"role": "user", "content": "old"}]).user("q")
    assert prefix_tokens(client, p, "claude-haiku-5-5") == 5012
    sent = calls[0]
    assert sent["model"] == "claude-haiku-5-5" and sent["tools"][0]["name"] == "lookup"
    assert [b["text"] for b in sent["system"]] == ["S", "D"] and "old" not in str(sent["messages"])


def test_openai_and_gemini() -> None:
    calls, fn = recorder(SimpleNamespace(input_tokens=4100))
    openai_client = SimpleNamespace(responses=SimpleNamespace(input_tokens=SimpleNamespace(count=fn)))
    assert prefix_tokens(openai_client, Prompt().system("S"), "gpt-6-luna") == 4100
    assert "prompt_cache_options" not in calls[0] and calls[0]["model"] == "gpt-6-luna"
    calls, fn = recorder(SimpleNamespace(total_tokens=5321))
    gemini_client = SimpleNamespace(models=SimpleNamespace(count_tokens=fn))
    assert prefix_tokens(gemini_client, Prompt().system("S").context("D"), "gemini-3.8-flash") == 5321
    assert calls[0]["contents"][0]["parts"] == [{"text": "S"}, {"text": "D"}]


def test_unknown_client_raises() -> None:
    with pytest.raises(TypeError):
        prefix_tokens(object(), Prompt().system("S"), "m")
