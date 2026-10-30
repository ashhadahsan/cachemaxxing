# Quickstart

```console
pip install "cachemaxxing[anthropic]"   # or [openai], [gemini], [litellm]
uv add cachemaxxing                      # zero runtime dependencies; extras just pull in a provider SDK
```

## 1. Build the prompt once, in a fixed order

Segments go from most to least stable, whatever order you call them in: tools, system, context, examples, history, retrieved, user.

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

## 2. Render it for your provider

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

## 3. Measure

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
