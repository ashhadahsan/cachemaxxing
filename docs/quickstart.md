# Quickstart

```console
pip install "cachemaxxing[anthropic]"   # or [openai], [gemini], [litellm]
uv add cachemaxxing                      # zero runtime dependencies; extras just pull in a provider SDK
```

## Your chat, as you already keep it

Keep your conversation as the usual OpenAI-style list of `{"role": ..., "content": ...}` messages. Pass it to `Prompt().messages(...)`, then render it for your provider:

```python
from openai import OpenAI
from cachemaxxing import Prompt, usage

client = OpenAI()
chat = [{"role": "system", "content": SYSTEM}]  # your long, fixed instructions

chat.append({"role": "user", "content": "How do I reset my router?"})
p = Prompt("support").messages(chat)
response = client.chat.completions.create(**p.openai_chat("gpt-6-luna"))
chat.append({"role": "assistant", "content": response.choices[0].message.content})

print(f"{usage(response).hit_rate:.0%} of the input came from cache")
```

The same `p` renders for every provider: `p.openai(...)` for the Responses API, `p.anthropic(...)` and `p.gemini(...)`. Your list is never changed; markers go only on copies. Anthropic and Gemini don't take a system message inside the conversation, so `messages()` moves it to where each provider expects it.

[`examples/chat.py`](https://github.com/ashhadahsan/cachemaxxing/blob/main/examples/chat.py) runs three turns on any provider. Real output, OpenAI:

```console
$ uv run --env-file .env python examples/chat.py openai
How do I reset my router?             6,283 input tokens,      0 from cache (0%)
And how do I update its firmware?     6,347 input tokens,  6,280 from cache (99%)
Thanks! Is that safe?                 6,433 input tokens,  6,344 from cache (99%)
```

### Where the caching happens

| Part of the request | Cached? | Anthropic | OpenAI GPT-5.6+ | Gemini |
|---|---|---|---|---|
| Tools | Yes: rarely change | `cache_control` on the last tool | covered by the system prompt's breakpoint (tools come first) | implicit |
| System prompt | Yes: the biggest saving | `cache_control` on its last block | `prompt_cache_breakpoint` on its last part | implicit |
| Conversation so far | Yes: the next turn reads it back | `cache_control` on the latest user message | a breakpoint on the latest user message and on the one before | implicit |
| Per-request context (`.retrieved()`: RAG chunks, current time) | No: it changes on every call | placed after the markers | placed after the markers | placed last |

Gemini caches repeated prefixes on its own, so nothing is marked. An explicit cache is used only when [`gemini_cache()`](caching.md) finds that it pays.

### What gets sent

For a short chat, with a system prompt, a question, an answer and a follow-up:

=== "OpenAI (Chat Completions)"

    ```json
    {"model": "gpt-6-luna",
     "messages": [
       {"role": "system", "content": [{"type": "text", "text": "You are Acme's support bot. ...",
                                       "prompt_cache_breakpoint": {"mode": "explicit"}}]},
       {"role": "user", "content": [{"type": "text", "text": "How do I reset my router?",
                                     "prompt_cache_breakpoint": {"mode": "explicit"}}]},
       {"role": "assistant", "content": "Hold the reset button for 10 seconds."},
       {"role": "user", "content": [{"type": "text", "text": "And the firmware?",
                                     "prompt_cache_breakpoint": {"mode": "explicit"}}]}],
     "prompt_cache_options": {"mode": "explicit", "ttl": "30m"}}
    ```

=== "Anthropic"

    ```json
    {"model": "claude-haiku-5-5",
     "system": [{"type": "text", "text": "You are Acme's support bot. ...", "cache_control": {"type": "ephemeral"}}],
     "messages": [
       {"role": "user", "content": "How do I reset my router?"},
       {"role": "assistant", "content": "Hold the reset button for 10 seconds."},
       {"role": "user", "content": [{"type": "text", "text": "And the firmware?",
                                     "cache_control": {"type": "ephemeral"}}]}]}
    ```

=== "Gemini"

    ```json
    {"model": "gemini-3.8-flash",
     "contents": [
       {"role": "user", "parts": [{"text": "How do I reset my router?"}]},
       {"role": "model", "parts": [{"text": "Hold the reset button for 10 seconds."}]},
       {"role": "user", "parts": [{"text": "And the firmware?"}]}],
     "config": {"system_instruction": {"parts": [{"text": "You are Acme's support bot. ..."}]}}}
    ```

Using LangChain's `SystemMessage`, `HumanMessage` and `AIMessage`? See [LangChain and LangGraph](langchain.md#the-simplest-case-a-list-of-messages).

## Tools, RAG and per-request context: build the prompt from parts

When a request has more than a system prompt and a chat, set each part on its own. Segments go from most to least stable, whatever order you call them in: tools, system, context, examples, history, retrieved, user.

```python
from cachemaxxing import Prompt

p = Prompt(call_site="support.answer")
p.tools(TOOLS)                 # sorted by name; your provider's tool format
p.system(SYSTEM)               # frozen instructions
p.context(DOCS)                # static reference material (dicts become canonical JSON)
p.history(messages)            # earlier turns, append-only, never modified
p.retrieved([chunks, f"Time: {now}"])  # per-request context: after the history
p.user(question)
```

### Render it for your provider

=== "Anthropic"

    ```python
    resp = client.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))
    ```

=== "OpenAI"

    ```python
    resp = client.responses.create(**p.openai("gpt-6-luna"))
    # or: client.chat.completions.create(**p.openai_chat("gpt-6-luna"))
    ```

=== "Gemini"

    ```python
    resp = client.models.generate_content(**p.gemini("gemini-3.8-flash"))
    ```

=== "LiteLLM"

    ```python
    resp = litellm.completion(max_tokens=1024, **p.litellm("anthropic/claude-haiku-5-5"))
    ```

Each adapter returns the full kwargs, `model` included, with the provider's cache markers at the stability boundaries.

### Measure

```python
from cachemaxxing import usage

u = usage(resp)
print(u.input, u.cache_read, u.cache_write, u.output, f"{u.hit_rate:.0%}", u.est_cost)
```

`usage()` accepts the SDK response object or its JSON, for every provider and LiteLLM.

## Runnable example

```console
uv run --env-file .env python examples/quickstart.py anthropic   # or openai, gemini, litellm
```

```python
--8<-- "examples/quickstart.py"
```

Next: [log your calls and find the misses](diagnosing.md).
