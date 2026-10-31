<img src="https://raw.githubusercontent.com/ashhadahsan/cachemaxxing/main/docs/assets/logo.svg" width="88" alt="cachemaxxing logo" align="right">

# cachemaxxing

[![PyPI](https://img.shields.io/pypi/v/cachemaxxing?cacheSeconds=3600)](https://pypi.org/project/cachemaxxing/)
[![Python](https://img.shields.io/pypi/pyversions/cachemaxxing?cacheSeconds=3600)](https://pypi.org/project/cachemaxxing/)
[![CI](https://github.com/ashhadahsan/cachemaxxing/actions/workflows/ci.yml/badge.svg)](https://github.com/ashhadahsan/cachemaxxing/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/ashhadahsan/cachemaxxing/blob/main/LICENSE)

**Stop paying full price for the same tokens.**

Anthropic, OpenAI and Gemini bill a repeated prompt prefix at a fraction of the input price, but only when the bytes really repeat. cachemaxxing finds where they don't, tells you what it costs, and lays your prompts out so they do. It is a thin library, not a proxy: zero runtime dependencies, and you keep your own SDK client.

- **Measure.** `usage()` turns any provider's response into the same numbers: input, cache read, cache write, output, estimated $ and hit rate. `cachemaxxing report` totals them per call site.
- **Diagnose.** `cachemaxxing diff` shows the first byte where two consecutive requests diverge, and why.
- **Fix.** `Prompt` orders your prompt from most to least stable and places each provider's cache markers for you.

```python
from openai import OpenAI
from cachemaxxing import Prompt, usage

chat = [
    {"role": "system", "content": SYSTEM},  # your long, fixed instructions: cached
    {"role": "user", "content": "How do I reset my router?"},
]
p = Prompt(call_site="support.answer").messages(chat)  # call_site: any name for this call, used in reports

resp = OpenAI().chat.completions.create(**p.openai_chat("gpt-6-luna"))
# same p: anthropic.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))
#         genai_client.models.generate_content(**p.gemini("gemini-3.8-flash"))

u = usage(resp)
print(f"{u.hit_rate:.0%} of input from cache, ~${u.est_cost or 0:.4f}")
```

The system prompt and the conversation so far get the provider's cache markers, so each turn reads everything before the new question from cache. For tools, RAG chunks or a timestamp, build the prompt from parts: `p.tools(TOOLS).system(SYSTEM).history(chat).retrieved(chunks).user(question)`. The quickstart shows [where the markers go, and the exact request](https://ashhadahsan.github.io/cachemaxxing/quickstart/).

## Works with

| | How |
|---|---|
| **Anthropic** | `client.messages.create(**p.anthropic(model))` |
| **OpenAI** | `client.responses.create(**p.openai(model))` or `client.chat.completions.create(**p.openai_chat(model))` |
| **Gemini** | `client.models.generate_content(**p.gemini(model))`, with an explicit cache via `gemini_cache()` when `should_cache()` says it pays |
| **LiteLLM** | `litellm.completion(**p.litellm("anthropic/claude-haiku-5-5"))` |
| **LangChain agents** | `create_agent(..., middleware=[CacheMiddleware("support.agent")])` |
| **LangChain messages, LangGraph graphs, LCEL** | `llm = CachedModel(chat_model)`, then `llm.invoke([SystemMessage(...), HumanMessage(...)])` |

On OpenAI GPT-5.6+ it places explicit cache breakpoints. On Anthropic it places `cache_control` markers, at most 4. Gemini stays on implicit caching unless an explicit cache pays.

## Find the misses

```console
$ cachemaxxing report calls.jsonl --min-hit-rate 0.6     # from record() logs; exits 1 below the threshold
call site   calls  hit rate  input   cache read  cache write  output  est $   top drift
rag.answer  4      88.8%     31,574  28,024      714          2,601   0.0020

$ cachemaxxing diff request_1.json request_2.json
diverges at system[0].text char 41 (timestamp), after ~14 matching tokens
  a: 'You are helpful. Today is 2026-10-30T10:00:00Z.'
  b: 'You are helpful. Today is 2026-10-30T10:05:00Z.'
```

Add `--html report.html` for the same report as a self-contained dashboard page. [See the demo](https://ashhadahsan.github.io/cachemaxxing/demo.html), built from a real log. For the provider's own verdict, add `diagnose=` to an adapter; `usage(resp).miss_reason` then says `system_changed`, `tools_changed`, and so on. To gate CI on hit rate, use the bundled GitHub Action: `uses: ashhadahsan/cachemaxxing@v0.5.0` with `log:` and `min-hit-rate:`.

Before you put it in a production request path, read [Running in production](https://ashhadahsan.github.io/cachemaxxing/production/). It covers rollout, what happens when something fails (cachemaxxing never fails a call that would have worked without it), logs without prompt text, concurrency and the stability policy.

## Benchmark

![Cached input tokens per conversation: naive vs clean prompt with provider auto-caching vs cachemaxxing](https://raw.githubusercontent.com/ashhadahsan/cachemaxxing/main/docs/assets/benchmark.svg)

- **Against a sloppy app** (the naive arm, chat and RAG): input cost is 76–88% lower on every model.
- **Against a clean prompt using the provider's own one-line caching**, it depends on the provider:
  - *Anthropic:* automatic caching puts its single cache entry after the per-turn context (time, request id, retrieved chunks). That entry changes every turn, so the app pays the 1.25× write premium on every call and reads nothing back. That is 0% cached, and dearer than not caching at all. A breakpoint after the static prompt, which cachemaxxing places, fixes it: 82–89% cheaper.
  - *Gemini:* implicit caching is best-effort and reached 39–56%. The explicit cache cachemaxxing creates when `should_cache()` says it pays reached 88–97%, 62–67% cheaper, with creation and storage included.
  - *OpenAI:* implicit caching already finds a stable prefix, and cachemaxxing is only 6–19% cheaper. On OpenAI the win is fixing the habits, plus the measuring tools.
  - *LangChain agents:* `CacheMiddleware` ties LangChain's `AnthropicPromptCachingMiddleware` on Anthropic and the default agent on OpenAI. It adds one setup for every provider and per-call-site measurement, not extra savings.

| Workload | Model | naive | clean + provider auto-caching | cachemaxxing | vs naive | vs clean |
|---|---|---|---|---|---|---|
| chat | `claude-haiku-5-5` | 0% · $0.0090 | 0% · $0.0112 | 94.4% · $0.0014 | 84% cheaper | 87% cheaper |
| chat | `gpt-6-luna` | 0% · $0.0068 | 92.8% · $0.0009 | 94% · $0.0009 | 87% cheaper | 6% cheaper |
| chat | `gemini-3.8-flash` | 0% · $0.0468 | 55.6% · $0.0236 | 97.3% · $0.0077 | 83% cheaper | 67% cheaper |
| chat | `claude-sonnet-5-5` | 0% · $0.1791 | 0% · $0.2232 | 92.4% · $0.0247 | 86% cheaper | 89% cheaper |
| chat | `gpt-6.1-sol` | 0% · $0.1389 | 88.4% · $0.0209 | 91% · $0.0168 | 88% cheaper | 19% cheaper |
| rag | `claude-haiku-5-5` | 0% · $0.0069 | 0% · $0.0086 | 87.4% · $0.0015 | 78% cheaper | 82% cheaper |
| rag | `gpt-6-luna` | 0% · $0.0049 | 84.1% · $0.0011 | 85.6% · $0.0010 | 80% cheaper | 15% cheaper |
| rag | `gemini-3.8-flash` | 0% · $0.0352 | 39.1% · $0.0226 | 88.2% · $0.0086 | 76% cheaper | 62% cheaper |
| agent | `claude-haiku-5-5` | 0% · $0.0044 | 89.8% · $0.0010 | 89.9% · $0.0009 | 78% cheaper | 1% cheaper |
| agent | `gpt-6-luna` | 90.4% · $0.0006 | — | 90.1% · $0.0006 | 2% dearer | — |

Cells: cached share of input tokens · estimated input cost per conversation at list price (cache writes and explicit-cache storage included; output excluded, since answer length varies between runs regardless of caching).

Setup: 8-turn conversations (agents: 3 questions with a tool call), 3 customers per arm. Every arm starts from a cold cache with its own prompt, so no arm reads another's entries. The naive arm has the four habits: a timestamp and request id at the top of the system prompt, tool order that varies, JSON key order that varies, and history re-rendered every turn; in RAG, chunks also go in the system prompt. The clean arm has the same content laid out well, with Anthropic's top-level `cache_control` or OpenAI's and Gemini's default implicit caching. Data: [`benchmarks/results/`](https://github.com/ashhadahsan/cachemaxxing/tree/main/benchmarks/results), run 2026-10-30. Rerun with `uv run --env-file .env python benchmarks/bench_<provider>.py --workload chat|rag` and `benchmarks/bench_agent.py`; the table comes from `benchmarks/summary.py`.

## Examples

- [`examples/chat.py`](examples/chat.py): start here. A chat kept as a plain list of messages, cached on every turn, on any provider
- [`examples/langchain_chat.py`](examples/langchain_chat.py): the same with LangChain `SystemMessage` / `HumanMessage` / `AIMessage`
- [`examples/quickstart.py`](examples/quickstart.py): one prompt, every provider and LiteLLM
- [`examples/rag_chat.py`](examples/rag_chat.py): a multi-turn RAG chat with per-turn retrieval, logging and a report
- [`examples/langchain_agent.py`](examples/langchain_agent.py): a LangChain `create_agent` agent with `CacheMiddleware`
- [`examples/langgraph_custom.py`](examples/langgraph_custom.py): a hand-built LangGraph graph with `CachedModel`

## Install

```console
pip install cachemaxxing                  # or: uv add cachemaxxing
pip install "cachemaxxing[anthropic]"     # extras: anthropic, openai, gemini, litellm, langchain
```

**Docs:** https://ashhadahsan.github.io/cachemaxxing/ covers the quickstart, how caching works per provider, diagnosing a low hit rate, LangChain and LangGraph, the API reference, and how it compares.

MIT licensed.
