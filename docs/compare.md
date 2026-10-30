# How it compares

cachemaxxing is a small library that works on the request you are about to send and the response you got back. It is not a proxy, and it never sends requests itself (except Gemini cache creation, through your own client).

| Project | What it is | Where it is ahead | What it doesn't do |
|---|---|---|---|
| Provider features (Anthropic automatic caching and cache diagnostics, OpenAI implicit mode and diagnostics) | Server-side caching and online diagnosis | Zero code; always current | Not cross-provider; automatic placement pays write premiums on per-request tails; no cost accounting per call site |
| [LiteLLM](https://docs.litellm.ai/docs/completion/prompt_caching) | Unified SDK and proxy | `cache_control_injection_points` inside a proxy; huge provider coverage | No layout, economics or diff; a heavy dependency. cachemaxxing works *with* it via `p.litellm(model)`. |
| [PrefixForge](https://github.com/abidedavana/prefixforge) | Prompt compiler with a replay CI gate | An offline cache simulator that models TTLs and the lookback window | Single unpublished commit, Anthropic-only, no economics or request diff, stale provider data |
| [prefixcash](https://pypi.org/project/prefixcash/) | CLI/TUI and LiteLLM callback | Labels why a prefix broke; heat-map TUI | Measurement only; word-level diff of flattened text; prices cache writes at the base rate |
| pydantic-ai | Agent framework | Caching settings and cache-bust warnings built in | Only inside the framework |
| Helicone, Portkey, LangWatch | Gateways | Pass caching through and report it in a dashboard | A proxy in your request path |
| vLLM, SGLang, llm-d | Self-hosted engines | Prefix caching and cache-aware routing in the server | Not for hosted APIs |
| GPTCache | Semantic response cache | Skips the call entirely on similar questions | A different problem; unmaintained since 2024 |

## Compared with the providers' own automatic caching

Measured on 2026-10-30 with the same content laid out cleanly. See the [benchmark](index.md#benchmark).

- **Anthropic automatic caching** (top-level `cache_control`) paid write premiums on every call and read nothing back whenever the last message carried per-turn context. It cost more than not caching at all. cachemaxxing's breakpoints were 82–89% cheaper.
- **Gemini implicit caching** reached 39–56% of input. cachemaxxing's explicit cache, used only when it pays, reached 88–97% and was 62–67% cheaper.
- **OpenAI implicit caching** already did well with a stable prefix. cachemaxxing was 6–19% cheaper.
- **LangChain's `AnthropicPromptCachingMiddleware`** tied `CacheMiddleware` on agents (89.8% vs 89.9% cached).

**Use cachemaxxing when** you call more than one provider, want hit rate and dollars per call site, need to know which byte broke the cache, or send prompts with a per-request tail (RAG chunks, timestamps) that automatic placement would cache wastefully.

**You may not need it when** you use one provider, your system prompt is frozen, and the provider's automatic caching already shows high `cache_read` numbers.
