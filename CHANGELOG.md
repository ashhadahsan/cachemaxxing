# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Automatic diagnosis: `stats.add(call_site, usage(resp), request=kw)`. `Stats` compares each request with the previous one from the same call site. The first time something breaks the cached prefix, it logs a warning on the `cachemaxxing` logger with where the requests diverge, the text before and after, and how to fix it. It then counts each cause in `stats.drift`, and `stats.table()` shows the top cause per call site. `Stats(warn=False)` keeps the diagnosis without the warnings. `add()` returns the `Divergence` when a call broke the prefix. `CacheMiddleware` and `CachedModel` diagnose automatically.
- `Divergence.fix`: what to change for each kind of divergence. Log warnings, `cachemaxxing report`, `cachemaxxing diff` and the dashboard all show the same advice.
- A tutorial that takes a support bot with a timestamp at the top of its prompt from 0% to 98% cached input, with real output, plus `examples/tutorial.py`.

### Changed

- `cachemaxxing report` prints, under its table, the most frequent cause for each call site that missed, with the first example and the fix.
- `cachemaxxing diff` adds a `fix:` line.
- The "prefix matched but nothing was read" drift is now labelled `prefix ok, no cache read`. The explanation moved to the diagnosis below the table.

## [0.9.0] - 2026-10-31

This is the release candidate for 1.0. The public API is now frozen.

### Added

- A "Running in production" guide covering rollout, what happens when something fails, logs, concurrency, costs and the stability policy.
- The public API is listed in `design/api.md`, and `tests/api.txt` freezes every public name and signature. From 1.0, renames and removals go through a deprecation first.
- `SECURITY.md` with private vulnerability reporting, `CONTRIBUTING.md`, and issue templates for bugs and wrong prices.

### Changed

- The development status is now Beta.

### Fixed

- `gemini_cache` and `gemini_cache_async` no longer make your call fail when the Gemini caches API fails. They return `None`, so the call uses implicit caching, and log a warning on the `cachemaxxing` logger.

## [0.5.0] - 2026-10-31

### Added

- `record(..., redact=fn)` writes a log line without prompt or output text. Every string in the request goes through `fn`, except model names, roles, block types and tool names. The response is reduced to its token counts and cost. `report` gives the same hit rates, costs and drifting fields as on a plain log. `CacheMiddleware` and `CachedModel` take the same `redact=` for their `on_record` lines.

### Changed

- The `report --html` dashboard draws at most the last 5,000 calls of each call site, and says so when there are more, so the page stays small for any log size. The totals and the table still count every call.
- The dashboard page has a Content-Security-Policy, so the browser itself blocks any network request.

### Fixed

- `Stats` is safe to share between threads. Before, concurrent `add()` calls could lose counts.
- Concurrent `gemini_cache` and `gemini_cache_async` calls for the same prefix now create one explicit cache. Before, each caller could create its own, and each was billed for storage.

## [0.4.1] - 2026-10-31

### Fixed

- `CacheMiddleware` and `CachedModel` no longer make a model call fail when adding cache fields or measuring the reply fails, including when your `on_record` raises. The call goes through, and a warning goes to the `cachemaxxing` logger. A wrong setting, such as a TTL the provider doesn't offer, still raises before anything is sent. `CacheMiddleware` now also checks the TTL when it is created.
- `usage()` now raises only `ValueError` for responses it can't read. Before, some unexpected field types raised `AttributeError` or `TypeError`.

### Changed

- `cachemaxxing report` reads the log line by line instead of loading it whole. It skips lines it can't read and counts them on stderr; before, the first one stopped the report. Add `--strict` to stop at the first unreadable line, with exit code 2.

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

[Unreleased]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.5.0...v0.9.0
[0.5.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ashhadahsan/cachemaxxing/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ashhadahsan/cachemaxxing/releases/tag/v0.1.0
