# cachemaxxing

**Stop paying full price for the same tokens.**

Anthropic, OpenAI and Gemini bill a repeated prompt prefix at a fraction of the input price, but only when the bytes really repeat. cachemaxxing finds where they don't, tells you what it costs, and lays your prompts out so they do.

1. **Measure.** `usage()` turns every provider's response into the same numbers: input, cache read, cache write, output, estimated $ and hit rate. `cachemaxxing report` totals them per call site.
2. **Diagnose.** `cachemaxxing diff` shows the first byte where two consecutive requests diverge, and why: a timestamp, a UUID, tool order, JSON key order.
3. **Fix.** `Prompt` orders your prompt from most to least stable and places each provider's cache markers for you.

```python
from cachemaxxing import Prompt, usage

p = Prompt(call_site="support.answer")
p.tools(TOOLS).system(SYSTEM).context(DOCS).history(messages).user(question)

resp = client.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))

u = usage(resp)
print(f"{u.hit_rate:.0%} of input from cache, ~${u.est_cost or 0:.4f}")
```

The same `Prompt` renders for `p.openai(...)`, `p.openai_chat(...)`, `p.gemini(...)` and `p.litellm(...)`. It is a thin library, not a proxy: you keep your own SDK client.

## Benchmark

![Cached input tokens per 8-turn chat, naive vs cachemaxxing](assets/benchmark.svg)

The same 8-turn support conversation, with a ~6k-token system prompt, product docs and 6 tools, was sent twice: once with the four common habits and once through cachemaxxing. Each arm ran 3 conversations, one customer each, starting from a cold cache. Costs are estimates at list price.

| Provider | Model | Cached input | $ per conversation | Saving |
|---|---|---|---|---|
| Anthropic | `claude-haiku-5-5` | 0.0% → **94.8%** | $0.0092 → $0.0017 | **82%** |
| OpenAI | `gpt-6-luna` | 0.0% → **93.1%** | $0.0070 → $0.0012 | **83%** |
| Gemini | `gemini-3.8-flash` | 0.0% → **97.5%** | $0.0484 → $0.0094 | **80%** |

The naive arm has four habits: a timestamp and request id at the top of the system prompt, tools in a different order on each call, JSON with varying key order, and history re-rendered every turn. On Gemini, the cachemaxxing arm used an explicit cache via `gemini_cache()`, because `should_cache()` said it pays; the cache's creation and storage cost is included. With implicit caching alone, the same layout reached 40.0% ($0.0315 per conversation).

Source: `benchmarks/results/*.json`, run 2026-10-30. Re-run any of it with `uv run --env-file .env python benchmarks/bench_<provider>.py`.

## Install

```console
pip install cachemaxxing
uv add cachemaxxing
```

There are no runtime dependencies. Extras pull in a provider SDK: `cachemaxxing[anthropic]`, `[openai]`, `[gemini]`, `[litellm]`.

Next: the [quickstart](quickstart.md).
