import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cachemaxxing.usage import Stats, Usage, record, usage


def test_anthropic_input_excludes_cache_tokens_so_we_add_them() -> None:
    r = {
        "type": "message",
        "model": "claude-haiku-5-5",
        "usage": {
            "input_tokens": 100,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 9000,
            "output_tokens": 50,
            "cache_creation": {"ephemeral_5m_input_tokens": 1000, "ephemeral_1h_input_tokens": 0},
        },
    }
    u = usage(r)
    assert (u.provider, u.input, u.cache_read, u.cache_write, u.output) == ("anthropic", 10100, 9000, 1000, 50)
    assert u.hit_rate == pytest.approx(9000 / 10100)
    assert u.est_cost == pytest.approx((100 * 0.10 + 9000 * 0.01 + 1000 * 0.125 + 50 * 0.50) / 1e6)


def test_openai_responses_docs_example_with_both_ttls() -> None:
    r = {
        "object": "response",
        "model": "gpt-6-luna",
        "usage": {
            "input_tokens": 12000,
            "output_tokens": 10,
            "input_tokens_details": {
                "cached_tokens": 4000,
                "cache_write_tokens": 7000,
                "cache_write_tokens_details": {"ttl_30m_tokens": 3000, "ttl_12h_tokens": 4000},
            },
        },
    }
    u = usage(r)
    assert (u.input, u.cache_read, u.cache_write) == (12000, 4000, 7000)
    assert u.est_cost == pytest.approx((1000 * 0.10 + 4000 * 0.01 + 3000 * 0.125 + 4000 * 0.25 + 10 * 0.50) / 1e6)


def test_openai_chat() -> None:
    r = {
        "object": "chat.completion",
        "model": "gpt-6-luna",
        "usage": {"prompt_tokens": 2000, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 1024}},
    }
    assert (usage(r).input, usage(r).cache_read, usage(r).provider) == (2000, 1024, "openai")


def test_gemini_snake_and_camel_case_agree_and_thoughts_count_as_output() -> None:
    snake = {
        "model_version": "gemini-3.8-flash",
        "candidates": [],
        "usage_metadata": {
            "prompt_token_count": 5000,
            "cached_content_token_count": 4096,
            "candidates_token_count": 20,
            "thoughts_token_count": 30,
        },
    }
    camel = {
        "modelVersion": "gemini-3.8-flash",
        "usageMetadata": {
            "promptTokenCount": 5000,
            "cachedContentTokenCount": 4096,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 30,
        },
    }
    assert usage(snake) == usage(camel)
    assert (usage(snake).output, usage(snake).cache_read) == (50, 4096)


def test_litellm_claude_response() -> None:
    r = {
        "object": "chat.completion",
        "model": "claude-haiku-5-5",
        "usage": {
            "prompt_tokens": 10100,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 9000, "cache_creation_tokens": 1000},
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 9000,
        },
    }
    u = usage(r)
    assert (u.provider, u.input, u.cache_read, u.cache_write) == ("anthropic", 10100, 9000, 1000)


def test_long_context_tier_prices_the_whole_request() -> None:
    r = {"type": "message", "model": "claude-haiku-5-5", "usage": {"input_tokens": 150_000, "output_tokens": 0}}
    assert usage(r).est_cost == pytest.approx(150_000 * 0.50 / 1e6)


def test_unknown_model_has_no_cost_and_unknown_shape_raises() -> None:
    assert usage({"type": "message", "model": "x", "usage": {"input_tokens": 1}}).est_cost is None
    with pytest.raises(ValueError):
        usage({"foo": 1})


def test_sdk_objects_and_model_override() -> None:
    class Resp:
        def model_dump(self, **kw: Any) -> dict[str, Any]:
            return {"type": "message", "model": "x", "usage": {"input_tokens": 10, "output_tokens": 0}}

    assert usage(Resp(), model="claude-haiku-5-5").est_cost == pytest.approx(10 * 0.10 / 1e6)


def test_stats_aggregates_per_call_site_and_formats() -> None:
    s = Stats()
    u = Usage("anthropic", "m", input=100, cache_read=50, est_cost=0.5)
    s.add("a", u)
    s.add("a", u)
    s.add("b", Usage("openai", "x", input=10))
    assert s.calls == {"a": 2, "b": 1}
    assert s.totals["a"].input == 200 and s.totals["a"].est_cost == 1.0
    table = s.table({"a": "system[].text (timestamp) x3"})
    assert "50.0%" in table and "n/a" in table and "timestamp" in table


def test_record_is_json_serializable() -> None:
    class Obj:
        def model_dump(self, **kw: Any) -> dict[str, str]:
            return {"type": "message"}

    line = record("a", {"messages": [Obj()]}, Obj())
    assert json.loads(json.dumps(line)) == {
        "call_site": "a",
        "request": {"messages": [{"type": "message"}]},
        "response": {"type": "message"},
    }


def test_recorded_live_gemini_response() -> None:
    live = json.loads((Path(__file__).parent / "fixtures" / "gemini_live.json").read_text())
    u = usage(live)
    assert (u.provider, u.model) == ("gemini", live["model_version"])
    assert (u.input, u.cache_read) == (7144, 5099) and u.est_cost is not None


def ai_message(provider: str, model: str, usage_metadata: dict[str, Any]) -> Any:
    messages = pytest.importorskip("langchain_core.messages")
    meta = {"model_provider": provider, "model_name": model}
    return messages.AIMessage(content="ok", usage_metadata=usage_metadata, response_metadata=meta)


def test_langchain_ai_message_anthropic_ttl_split() -> None:
    m = ai_message(
        "anthropic",
        "claude-haiku-5-5",
        {
            "input_tokens": 10100,
            "output_tokens": 50,
            "total_tokens": 10150,
            "input_token_details": {"cache_read": 9000, "cache_creation": 0, "ephemeral_5m_input_tokens": 1000},
        },
    )
    u = usage(m)
    assert (u.provider, u.model, u.input, u.cache_read, u.cache_write, u.output) == (
        "anthropic",
        "claude-haiku-5-5",
        10100,
        9000,
        1000,
        50,
    )
    assert u.est_cost == pytest.approx((100 * 0.10 + 9000 * 0.01 + 1000 * 0.125 + 50 * 0.50) / 1e6)


def test_langchain_ai_message_openai_gemini_and_priority_tier() -> None:
    details = {"cache_read": 4000, "cache_creation": 7000}
    o = usage(
        ai_message(
            "openai",
            "gpt-6-luna",
            {"input_tokens": 12000, "output_tokens": 10, "total_tokens": 12010, "input_token_details": details},
        )
    )
    assert (o.provider, o.cache_read, o.cache_write) == ("openai", 4000, 7000)
    g = usage(
        ai_message(
            "google_genai",
            "gemini-3.8-flash",
            {
                "input_tokens": 5000,
                "output_tokens": 50,
                "total_tokens": 5050,
                "input_token_details": {"cache_read": 4096},
            },
        )
    )
    assert (g.provider, g.input, g.cache_read, g.output) == ("gemini", 5000, 4096, 50)
    p = usage(
        ai_message(
            "openai",
            "gpt-6-luna",
            {
                "input_tokens": 100,
                "output_tokens": 1,
                "total_tokens": 101,
                "input_token_details": {"priority_cache_read": 80},
            },
        )
    )
    assert p.cache_read == 80


def test_provider_miss_reasons_are_captured() -> None:
    a = {
        "type": "message",
        "model": "claude-haiku-5-5",
        "usage": {"input_tokens": 10, "cache_creation_input_tokens": 41850, "output_tokens": 1},
        "diagnostics": {"cache_miss_reason": {"type": "system_changed", "cache_missed_input_tokens": 41850}},
    }
    assert usage(a).miss_reason == "system_changed"
    pending = {**a, "diagnostics": {"cache_miss_reason": None}}
    assert usage(pending).miss_reason is None and usage({**a, "diagnostics": None}).miss_reason is None
    o = {
        "object": "response",
        "model": "gpt-6-luna",
        "usage": {"input_tokens": 100, "output_tokens": 1},
        "prompt_cache_diagnostics": {"type": "cache_miss", "reason": "tools_changed", "cache_missed_tokens": 90},
    }
    assert usage(o).miss_reason == "tools_changed"
    hit = {**o, "prompt_cache_diagnostics": {"type": "cache_hit"}}
    gone = {**o, "prompt_cache_diagnostics": {"type": "comparison_response_not_found"}}
    assert usage(hit).miss_reason is None and usage(gone).miss_reason == "comparison_response_not_found"


def test_stats_counts_miss_reasons_per_call_site() -> None:
    s = Stats()
    s.add("a", Usage("anthropic", "m", input=10, miss_reason="system_changed"))
    s.add("a", Usage("anthropic", "m", input=10, miss_reason="system_changed"))
    s.add("a", Usage("anthropic", "m", input=10))
    assert s.misses == {"a": {"system_changed": 2}}
    assert "provider: system_changed x2" in s.table()


def test_saved_is_the_uncached_price_minus_the_actual_one() -> None:
    r = {
        "type": "message",
        "model": "claude-haiku-5-5",
        "usage": {
            "input_tokens": 100,
            "cache_read_input_tokens": 9000,
            "cache_creation_input_tokens": 1000,
            "output_tokens": 50,
        },
    }
    u = usage(r)
    uncached = (10100 * 0.10 + 50 * 0.50) / 1e6
    assert u.saved == pytest.approx(uncached - (u.est_cost or 0))
    writes_only = {**r, "usage": {"input_tokens": 0, "cache_creation_input_tokens": 1000, "output_tokens": 0}}
    assert usage(writes_only).saved == pytest.approx(-(1000 * 0.025) / 1e6)  # paid the 1.25x write premium
    assert usage({"type": "message", "model": "x", "usage": {"input_tokens": 1}}).saved is None


def test_stats_sums_saved_and_shows_it() -> None:
    s = Stats()
    s.add("a", Usage("anthropic", "m", input=100, cache_read=90, est_cost=0.1, saved=0.4))
    s.add("a", Usage("anthropic", "m", input=100, cache_read=90, est_cost=0.1, saved=0.4))
    assert s.totals["a"].saved == pytest.approx(0.8)
    assert "saved $" in s.table() and "0.8000" in s.table()


def test_attributes_for_traces() -> None:
    u = Usage(
        "anthropic",
        "claude-haiku-5-5",
        input=10100,
        cache_read=9000,
        cache_write=1000,
        output=50,
        est_cost=0.0005,
        saved=0.0006,
        miss_reason="system_changed",
    )
    a = u.attributes("support.answer")
    assert a["cachemaxxing.call_site"] == "support.answer" and a["cachemaxxing.hit_rate"] == pytest.approx(
        0.8911, abs=1e-4
    )
    assert a["cachemaxxing.saved_usd"] == 0.0006 and a["cachemaxxing.miss_reason"] == "system_changed"
    assert all(isinstance(v, str | int | float) for v in a.values())  # valid OpenTelemetry attribute values
    bare = Usage("x", "y", input=1).attributes(prefix="")
    assert "est_cost_usd" not in bare and "miss_reason" not in bare and bare["input_tokens"] == 1  # None omitted


KEYS = [
    "type", "model", "object", "usage", "usage_metadata", "usageMetadata", "candidates", "input_tokens",
    "output_tokens", "prompt_tokens", "completion_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
    "cache_creation", "prompt_tokens_details", "input_tokens_details", "cached_tokens", "prompt_token_count",
    "response_metadata", "input_token_details", "model_provider", "diagnostics", "prompt_cache_diagnostics",
]  # fmt: skip
LEAVES = (
    st.none()
    | st.booleans()
    | st.integers(-10, 10**9)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.sampled_from(["message", "response", "chat.completion", "claude-haiku-5-5", "openai"])
    | st.text(max_size=4)
)
JSONISH = st.recursive(
    LEAVES, lambda c: st.lists(c, max_size=3) | st.dictionaries(st.sampled_from(KEYS), c, max_size=4), max_leaves=25
)


@settings(max_examples=500)
@given(st.dictionaries(st.sampled_from(KEYS), JSONISH, max_size=6))
def test_usage_raises_only_value_error(d: dict[str, Any]) -> None:
    try:
        usage(d)
    except ValueError:
        pass
