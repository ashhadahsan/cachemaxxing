# cachemaxxing

[![PyPI](https://img.shields.io/pypi/v/cachemaxxing)](https://pypi.org/project/cachemaxxing/)
[![Python](https://img.shields.io/pypi/pyversions/cachemaxxing)](https://pypi.org/project/cachemaxxing/)
[![CI](https://github.com/ashhadahsan/cachemaxxing/actions/workflows/ci.yml/badge.svg)](https://github.com/ashhadahsan/cachemaxxing/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/ashhadahsan/cachemaxxing/blob/main/LICENSE)

**Stop paying full price for the same tokens.**

Anthropic, OpenAI and Gemini bill a repeated prompt prefix at a fraction of the input price, but only when the bytes really repeat. cachemaxxing finds where they don't, tells you what it costs, and lays your prompts out so they do.

- **Measure.** `usage()` normalizes every provider's usage, and `cachemaxxing report` gives hit rate and $ per call site.
- **Diagnose.** `cachemaxxing diff` shows the first byte where two requests diverge, and why.
- **Fix.** `Prompt` orders segments from most to least stable and places each provider's cache markers.

```python
from cachemaxxing import Prompt, usage

p = Prompt(call_site="support.answer")
p.tools(TOOLS).system(SYSTEM).context(DOCS).history(messages).user(question)

resp = client.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))

u = usage(resp)
print(f"{u.hit_rate:.0%} of input from cache, ~${u.est_cost or 0:.4f}")
```

A full multi-turn RAG chat lives in [`examples/rag_chat.py`](examples/rag_chat.py).
The API works the same with `p.openai(...)`, `p.openai_chat(...)`, `p.gemini(...)` and `p.litellm(...)`. It is a thin library, not a proxy, and has zero runtime dependencies.

## Benchmark

![Cached input tokens per 8-turn chat, naive vs cachemaxxing](https://raw.githubusercontent.com/ashhadahsan/cachemaxxing/main/docs/assets/benchmark.svg)

| Provider | Model | Cached input | $ per conversation | Saving |
|---|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | 0.0% → **94.8%** | $0.0092 → $0.0017 | **82%** |
| OpenAI | `gpt-6-luna` | 0.0% → **93.1%** | $0.0070 → $0.0012 | **83%** |
| Gemini | `gemini-3.8-flash` | 0.0% → **97.5%** | $0.0484 → $0.0094 | **80%** |

The same 8-turn conversation, 3 customers per arm, starting from a cold cache, with costs estimated at list price. The naive arm has four common habits: a timestamp at the top of the prompt, tool order that varies, JSON key order that varies, and history re-rendered every turn. The Gemini row uses an explicit cache, creation and storage cost included; with implicit caching alone it reached 40.0%. Data: [`benchmarks/results/`](benchmarks/results/), 2026-10-30.

## Install

```console
pip install cachemaxxing        # or: uv add cachemaxxing
pip install "cachemaxxing[anthropic]"   # extras: anthropic, openai, gemini, litellm
```

**Docs:** https://ashhadahsan.github.io/cachemaxxing/ covers the quickstart, how caching works per provider, diagnosing a low hit rate, the API reference, and how it compares.

MIT licensed.
