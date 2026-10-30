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
from cachemaxxing import Prompt, usage

p = Prompt(call_site="support.answer")
p.tools(TOOLS).system(SYSTEM).context(DOCS).history(messages).retrieved(chunks).user(question)

resp = client.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))

u = usage(resp)
print(f"{u.hit_rate:.0%} of input from cache, ~${u.est_cost or 0:.4f}")
```

## Works with

| | How |
|---|---|
| **Anthropic** | `client.messages.create(**p.anthropic(model))` |
| **OpenAI** | `client.responses.create(**p.openai(model))` or `client.chat.completions.create(**p.openai_chat(model))` |
| **Gemini** | `client.models.generate_content(**p.gemini(model))`, with an explicit cache via `gemini_cache()` when `should_cache()` says it pays |
| **LiteLLM** | `litellm.completion(**p.litellm("anthropic/claude-haiku-5-5"))` |
| **LangChain agents** | `create_agent(..., middleware=[CacheMiddleware("support.agent")])` |
| **LangGraph graphs, LCEL chains** | `llm = CachedModel(chat_model, system=SYSTEM)`, then `llm.invoke(state["messages"])` |

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

## Benchmark

![Cached input tokens per 8-turn chat, naive vs cachemaxxing](https://raw.githubusercontent.com/ashhadahsan/cachemaxxing/main/docs/assets/benchmark.svg)

| Provider | Model | Cached input | $ per conversation | Saving |
|---|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | 0.0% → **94.8%** | $0.0092 → $0.0017 | **82%** |
| OpenAI | `gpt-6-luna` | 0.0% → **93.1%** | $0.0070 → $0.0012 | **83%** |
| Gemini | `gemini-3.8-flash` | 0.0% → **97.5%** | $0.0484 → $0.0094 | **80%** |

The same 8-turn conversation was run for 3 customers per arm, each starting from a cold cache. Costs are estimates at list price. The naive arm has four common habits: a timestamp at the top of the prompt, tool order that varies, JSON key order that varies, and history re-rendered every turn. The Gemini row uses an explicit cache, with its creation and storage cost included; with implicit caching alone it reached 40.0%. Data: [`benchmarks/results/`](benchmarks/results/), 2026-10-30.

## Examples

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
