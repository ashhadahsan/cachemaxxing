# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-10-31

### Added

- `cachemaxxing report LOG --html PATH` writes a self-contained dashboard page. It shows the totals, the hit rate of every call, a sortable table of call sites, and each divergence in context with a fix. The page makes no network requests.
- A landing page at the docs root, and a demo dashboard built from a real log. The docs home moved to `overview/`.
- `Usage.saved`: USD saved compared with the same call without caching. It is negative when cache writes cost more than the reads saved. `Stats` and `report` show a `saved $` column.
- `Usage.attributes()`: a call's cache metrics as flat keys for Langfuse or LangSmith metadata and OpenTelemetry span attributes.
- `Prompt.messages(chat)` takes a chat kept as an OpenAI-style list of `{"role", "content"}` messages and renders it for any provider. Leading system messages become the cached system prompt. Gemini gets these turns converted to its own format.
- Simple examples: `examples/chat.py`, a plain message list, and `examples/langchain_chat.py`, with `SystemMessage`, `HumanMessage` and `AIMessage`. The quickstart now shows where each provider's cache markers go and the exact request that is sent.
- `call_site` is documented in the API reference and in the diagnosing guide.
- `CacheMiddleware` and `CachedModel` attach these metrics to every reply as `response_metadata["cachemaxxing"]`.

## [0.3.0] - 2026-10-31

### Added

- `diagnose=` on `anthropic()` and `openai()` requests the provider's own cache-miss verdict (Anthropic cache diagnostics, OpenAI prompt-cache diagnostics). `usage(...).miss_reason` carries it, and `Stats` and `report` show it per call site.
- `cachemaxxing.count.prefix_tokens()`: exact prefix token counts from the Anthropic, OpenAI or google-genai client.
- GitHub Action (`uses: ashhadahsan/cachemaxxing@v0.3.0`): fails the job when a call site's hit rate drops below `min-hit-rate`, and writes the report to the job summary.

### Changed

- Benchmarks v2:
  - a third arm, a clean prompt using only the provider's own automatic caching
  - RAG and LangChain-agent workloads
  - `claude-sonnet-5-5` and `gpt-6.1-sol`
  - every arm starts cold with its own prompt
  - costs compared on the input side, since output length varies with the answer and not with caching
- `gemini_cache()` counts the prefix exactly (once per prefix) instead of estimating at ~4 characters per token. On the benchmark prompt the estimate was 17% below Gemini's count (and 41% below Anthropic's).

## [0.2.0] - 2026-10-30

### Added

- Logo (`docs/assets/logo.svg`), used in the README and as the docs site's logo and favicon.
- `cachemaxxing.langchain.CacheMiddleware` for LangChain 1.x / LangGraph agents: per-provider cache fields on every model call (OpenAI GPT-5.6+ breakpoints, Anthropic markers and automatic caching), usage per call site, and an `on_record` hook for `cachemaxxing report`. New extra: `cachemaxxing[langchain]`.
- `cachemaxxing.langchain.CachedModel` (wrap a chat model for hand-built LangGraph graphs and LCEL chains) and `cache_fields()` (the low-level piece).
- `examples/langchain_agent.py` and `examples/langgraph_custom.py`.

### Fixed

- `usage()` on a LangChain `AIMessage` returned all zeros; it now reads `usage_metadata` for every provider integration.
- `diff` shows short values whole instead of a window cut mid-word.

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

[Unreleased]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ashhadahsan/cachemaxxing/releases/tag/v0.1.0
