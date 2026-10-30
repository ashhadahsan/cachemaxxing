from pathlib import Path

from cachemaxxing import facts


def test_every_model_is_sourced_and_sane() -> None:
    for name, m in facts.MODELS.items():
        assert m.provider in facts.PROVIDERS, name
        assert m.source.startswith("https://"), name
        assert 0 < m.cache_read < m.input, name
        assert all(price >= m.input for price in m.cache_write.values()), name


def test_find_strips_prefixes_and_snapshots() -> None:
    assert facts.find("anthropic/claude-haiku-5-5") is facts.MODELS["claude-haiku-5-5"]
    assert facts.find("models/gemini-3.8-flash-001") is facts.MODELS["gemini-3.8-flash"]
    assert facts.find("gpt-6.1-sol-2026-09-01") is facts.MODELS["gpt-6.1-sol"]
    assert facts.find("mystery") is None


def test_provider_of() -> None:
    assert facts.provider_of("bedrock/anthropic.claude-x") == "anthropic"
    assert facts.provider_of("gemini/gemini-9") == "gemini"
    assert facts.provider_of("gpt-7") == "openai"
    assert facts.provider_of("mistral/large") == "other"


def test_markdown_lists_every_model_and_the_date() -> None:
    md = facts.markdown()
    assert all(f"`{name}`" in md for name in facts.MODELS)
    assert facts.VERIFIED in md


def test_docs_facts_table_is_current() -> None:
    hint = "regenerate: uv run python -m cachemaxxing.facts > docs/_facts.md"
    assert Path("docs/_facts.md").read_text(encoding="utf-8") == facts.markdown(), hint
