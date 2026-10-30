import pytest

from cachemaxxing.economics import should_cache


def test_anthropic_5m_pays_after_one_reuse() -> None:
    d = should_cache(10_000, 1, "anthropic", "claude-haiku-5-5")
    assert d.cache and d.ttl == "5m"
    assert d.saving == pytest.approx(2 * 0.01 * 0.10 - (0.01 * 0.125 + 0.01 * 0.01))


def test_no_reuse_loses_money() -> None:
    d = should_cache(10_000, 0, "anthropic", "claude-haiku-5-5")
    assert not d.cache and d.saving < 0


def test_twenty_minute_gaps_need_1h_and_two_reuses() -> None:
    assert should_cache(10_000, 2, "anthropic", "claude-haiku-5-5", interval_s=1200).ttl == "1h"
    assert not should_cache(10_000, 1, "anthropic", "claude-haiku-5-5", interval_s=1200).cache


def test_minimum_and_gap_limits() -> None:
    assert "minimum" in should_cache(400, 9, "anthropic", "claude-haiku-5-5").reason
    assert not should_cache(10_000, 9, "anthropic", "claude-haiku-5-5", interval_s=7200).cache


def test_openai_picks_30m_then_12h() -> None:
    assert should_cache(5_000, 3, "openai", "gpt-6-luna", interval_s=600).ttl == "30m"
    assert should_cache(5_000, 3, "openai", "gpt-6-luna", interval_s=3600).ttl == "12h"


def test_gemini_explicit_includes_storage() -> None:
    d = should_cache(100_000, 10, "gemini", "gemini-3.8-flash")
    cost = 0.1 * 0.75 + 10 * 0.1 * 0.075 + 0.1 * 0.50 * 600 / 3600
    assert d.cache and d.ttl == "600s" and d.saving == pytest.approx(11 * 0.1 * 0.75 - cost)
    assert not should_cache(100_000, 10, "gemini", "gemini-4-argon").cache


def test_unknown_or_mismatched_model_raises() -> None:
    with pytest.raises(ValueError):
        should_cache(5_000, 1, "openai", "claude-haiku-5-5")
