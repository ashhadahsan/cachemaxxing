# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-30

### Added

- `Prompt`: segments ordered from most to least stable (tools, system, context, examples, history, retrieved, user), with deterministic serialization.
- Adapters: `anthropic()` (cache_control at stability boundaries), `openai()` / `openai_chat()` (explicit breakpoints on GPT-5.6+, `prompt_cache_key` on older models), `gemini()` (implicit by default), `litellm()` (route-aware markers).
- `usage()`: one normalized shape for Anthropic, OpenAI Responses and Chat, Gemini and LiteLLM responses, with list-price cost estimates; `Stats` per call site; `record()` for JSONL logs.
- `diff()`: the first point where two requests diverge, with hints (timestamp, uuid, tool order, key order, ...).
- `should_cache()`: whether explicit caching pays, per provider and model.
- `gemini_cache()` / `gemini_cache_async()`: create or reuse Gemini explicit caches only when they pay.
- CLI: `cachemaxxing diff A B` and `cachemaxxing report LOG --min-hit-rate X`.
- Provider facts table with sources, verified 2026-10-30.
- Benchmarks: naive vs cachemaxxing on claude-haiku-5-5, gpt-6-luna and gemini-3.8-flash (8-turn conversations, cold start, one customer per conversation), with results JSON and a chart.
- `examples/quickstart.py` for Anthropic, OpenAI, Gemini and LiteLLM.
- `examples/rag_chat.py`: a multi-turn RAG chat with per-turn retrieval, append-only history, `diff` between turns, JSONL logging and a `Stats` table.

[Unreleased]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ashhadahsan/cachemaxxing/releases/tag/v0.1.0
