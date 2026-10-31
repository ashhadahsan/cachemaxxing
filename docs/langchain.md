# LangChain and LangGraph

Install: `pip install "cachemaxxing[langchain]"`, plus your provider's LangChain package (`langchain-openai`, `langchain-anthropic` or `langchain-google-genai`). `import cachemaxxing` on its own never imports LangChain.

| You use | Use this | What you write |
|---|---|---|
| LangChain agents: `create_agent`, which runs on LangGraph | `CacheMiddleware` | `middleware=[CacheMiddleware("support.agent")]` |
| A hand-built LangGraph `StateGraph` | `CachedModel` | `llm = CachedModel(model, system=SYSTEM)` then `llm.invoke(state["messages"])` |
| LangChain chains (LCEL) and direct calls | `CachedModel` | `prompt \| CachedModel(model)` |
| Full control in your own code | `cache_fields()` | `system, extra = cache_fields(model, SYSTEM)` |
| Measuring any LangChain response | `usage()` | `usage(ai_message)` |

All of them follow the same per-provider rules: an explicit breakpoint on the system prompt plus implicit mode on OpenAI GPT-5.6+, a `prompt_cache_key` on older OpenAI models, a system marker plus automatic tail caching on Anthropic, and nothing on Gemini, which caches implicitly.

## The simplest case: a list of messages

Wrap your chat model once with `CachedModel`, then call it with your `SystemMessage`, `HumanMessage` and `AIMessage` list, as you would call the model itself:

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from cachemaxxing.langchain import CachedModel

llm = CachedModel(init_chat_model("openai:gpt-6-luna"), call_site="chat")
messages = [SystemMessage(SYSTEM)]  # your long, fixed instructions

for question in ["How do I reset my router?", "And how do I update its firmware?"]:
    messages.append(HumanMessage(question))
    reply = llm.invoke(messages)  # an AIMessage
    messages.append(reply)

print(llm.stats.table())  # hit rate and $ for the "chat" call site
```

The system prompt gets the provider's cache marker, and the conversation is cached as it grows. Plain dicts work too: `llm.invoke([{"role": "user", "content": "..."}])`. To run it, use [`examples/langchain_chat.py`](https://github.com/ashhadahsan/cachemaxxing/blob/main/examples/langchain_chat.py):

```console
$ uv run --env-file .env python examples/langchain_chat.py anthropic
How do I reset my router?              9,999 input tokens,  9,995 from cache
And how do I update its firmware?     11,099 input tokens,  9,995 from cache
Thanks! Is that safe?                 11,515 input tokens, 11,095 from cache
```

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

In the agent benchmark (3 customers × 3 questions with a tool call, 2026-10-30), `CacheMiddleware` cached 89.9% of input on `claude-haiku-5-5`, the same as langchain-anthropic's `AnthropicPromptCachingMiddleware` (89.8%), against 0% with no middleware. On `gpt-6-luna` LangChain's default agent already caches well (90.4%), and `CacheMiddleware` matched it (90.1%). The middleware's value is one setup for every provider plus per-call-site measurement; it doesn't add savings over a provider's own good defaults.

!!! note
    On Anthropic, use `CacheMiddleware` *or* langchain-anthropic's `AnthropicPromptCachingMiddleware`, not both. Each adds its own breakpoints, and a request allows 4.

Some middleware rewrites the cached prefix on every call and will lower your hit rate:

- a `@dynamic_prompt` whose text changes per call
- tool-selection middleware that changes the tool list
- summarization or context-editing middleware that rewrites history

`cachemaxxing report` and `cachemaxxing diff` on the `on_record` log show where.

## Custom LangGraph graphs and chains: `CachedModel`

Middleware only runs inside `create_agent`. In your own graph, wrap the chat model once. Bound tools are fine. Every call then gets the system prompt, the right cache fields, and its usage recorded:

```python
from langchain.chat_models import init_chat_model
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from cachemaxxing.langchain import CachedModel

llm = CachedModel(init_chat_model("openai:gpt-6-luna").bind_tools(tools), system=SYSTEM, call_site="graph.support")

def model_node(state: MessagesState):
    return {"messages": [llm.invoke(state["messages"])]}

graph = StateGraph(MessagesState)
graph.add_node("model", model_node)
graph.add_node("tools", ToolNode(tools))
graph.add_edge(START, "model")
graph.add_conditional_edges("model", tools_condition)
graph.add_edge("tools", "model")
app = graph.compile()
# ... app.invoke(...) ...
print(llm.stats.table())
```

A leading `SystemMessage` in the input is used as it is, and marked; otherwise `system=` is prepended. `CachedModel` is a LangChain `Runnable`, so it also works in chains:

```python
chain = ChatPromptTemplate.from_messages([("system", SYSTEM), ("human", "{question}")]) | CachedModel(llm)
```

Live runs on 2026-10-30, 4 model calls each including a tool loop ([`examples/langgraph_custom.py`](https://github.com/ashhadahsan/cachemaxxing/blob/main/examples/langgraph_custom.py)):

- Starting from a cold cache, 74% of input was cached on `claude-haiku-5-5`.
- With the system prompt already warm from an earlier conversation, 98% was cached on both `gpt-6-luna` and `claude-haiku-5-5`.

`cache_fields(model, system)` is the lower-level piece both are built on. It returns the marked system message and the extra `invoke` kwargs, for code that assembles calls itself.

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
