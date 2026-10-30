# LangChain and LangGraph

Install: `pip install "cachemaxxing[langchain]"`, plus your provider's LangChain package (`langchain-openai`, `langchain-anthropic` or `langchain-google-genai`). `import cachemaxxing` on its own never imports LangChain.

## Cache an agent: `CacheMiddleware`

For agents built with LangChain 1.x `create_agent`, which run on LangGraph:

```python
import json
from langchain.agents import create_agent
from cachemaxxing.langchain import CacheMiddleware

log = open("agent_calls.jsonl", "a")
cache = CacheMiddleware("support.agent", on_record=lambda r: log.write(json.dumps(r) + "\n"))
agent = create_agent("openai:gpt-6-luna", tools=[check_warranty], system_prompt=SYSTEM, middleware=[cache])

agent.invoke({"messages": [{"role": "user", "content": "Is my router under warranty?"}]})
print(cache.stats.table())        # hit rate and $ per call site, in process
# later: cachemaxxing report agent_calls.jsonl
```

On every model call, tool loops included, it changes only that call and never the agent's state:

| Model | What it adds |
|---|---|
| OpenAI GPT-5.6+ (`ChatOpenAI`) | An explicit breakpoint on the system prompt, plus `prompt_cache_options={"mode": "implicit"}`, so the shared prefix is cached and the conversation keeps OpenAI's moving breakpoint |
| OpenAI before 5.6 | `prompt_cache_key` from the call site and the system prompt + tools |
| Anthropic (`ChatAnthropic`) | `cache_control` on the system prompt, plus automatic caching for the conversation tail |
| Gemini, others | Nothing; Gemini caches implicitly |

Your own `model_settings` always win. `ttl=` takes `"5m"`/`"1h"` (Anthropic) or `"30m"`/`"12h"` (OpenAI).

A live run of [`examples/langchain_agent.py`](https://github.com/ashhadahsan/cachemaxxing/blob/main/examples/langchain_agent.py) (3 questions, one tool call, 4 model calls, 2026-10-30) gave 74.4% cached input on `gpt-6-luna` and 74.3% on `claude-haiku-5-5`. Only the first, cold call paid to write the cache.

!!! note
    On Anthropic, use `CacheMiddleware` *or* langchain-anthropic's `AnthropicPromptCachingMiddleware`, not both. Each adds its own breakpoints, and a request allows 4.

Some middleware rewrites the cached prefix on every call and will lower your hit rate:

- a `@dynamic_prompt` whose text changes per call
- tool-selection middleware that changes the tool list
- summarization or context-editing middleware that rewrites history

`cachemaxxing report` and `cachemaxxing diff` on the `on_record` log show where.

## Measure any LangChain call

`usage()` reads a LangChain `AIMessage` for every provider integration:

```python
from cachemaxxing import Stats, usage

ai = llm.invoke(messages)
u = usage(ai)                      # input, cache_read, cache_write, output, est_cost, hit_rate
stats = Stats(); stats.add("chain.answer", u)
```

## Calling a chat model directly

The adapters' output works as LangChain input, cache markers included:

```python
from langchain_openai import ChatOpenAI
kw = Prompt("direct").system(SYSTEM).user(question).openai_chat("gpt-6-luna")
ai = ChatOpenAI(model=kw.pop("model")).invoke(kw.pop("messages"), **kw)  # prompt_cache_options passes through

from langchain_anthropic import ChatAnthropic
kw = Prompt("direct").system(SYSTEM).user(question).anthropic("claude-haiku-5-5")
ai = ChatAnthropic(model=kw["model"]).invoke([{"role": "system", "content": kw["system"]}, *kw["messages"]])
```

Both were checked live with langchain 1.4.7: the second identical call read 6,272 of 6,283 input tokens on OpenAI and 9,993 of 10,005 on Anthropic. For tools, pass `kw["tools"]` to `bind_tools()`. Anthropic tool dicts need a `description`, or LangChain drops the marker.
