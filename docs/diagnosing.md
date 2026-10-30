# Diagnosing a low hit rate

A cache miss never raises an error. Requests keep succeeding; the bill is just higher. The only ground truth is the usage the provider returns, so start there.

## 1. Log every call

```python
import json
from cachemaxxing import record, usage

kwargs = p.anthropic("claude-haiku-5-5")
resp = client.messages.create(max_tokens=1024, **kwargs)
with open("calls.jsonl", "a") as log:
    log.write(json.dumps(record("support.answer", kwargs, resp)) + "\n")
```

The library never writes files itself; `record()` just builds a JSON-serializable line with the call site, the request and the response.

## 2. Find the call sites that miss

```console
$ cachemaxxing report calls.jsonl
call site       calls  hit rate  input    cache read  cache write  output  est $   top drift
support.answer  120    3.1%      912,410  28,104      0            6,012   0.0927  system[].text (timestamp) x119
search.rerank   48     91.4%     402,551  367,902     12,880       1,920   0.0061
```

`top drift` is the most common place where consecutive requests from the same call site diverge. `prefix ok, no cache read` means the requests matched but nothing was read; see the causes below.

## 3. See the exact byte

```console
$ cachemaxxing diff request_41.json request_42.json
diverges at system[0].text char 41 (timestamp), after ~10 matching tokens
  a: 'You are helpful. Today is 2026-10-30T10:00:00Z.'
  b: 'You are helpful. Today is 2026-10-30T10:05:00Z.'
```

`diff` accepts request kwargs or `record()` lines. It ignores cache markers (they move every turn by design), treats `"text"` the same as a single text block, and ignores request parameters that are not part of the prompt.

| Hint | What it means | Fix |
|---|---|---|
| `timestamp`, `uuid`, `hex id` | A per-request value sits inside the prefix | Move it to `p.retrieved(...)` or `p.user(...)`, after the history |
| `tool order` | Same tools, different order | `p.tools(tools)` sorts them by name |
| `key order` | Same JSON object, keys in a different order | Pass the data to `p.context(...)`: it is serialized canonically |
| `whitespace` | Same words, different spacing or line endings | `p.system` / `context` / `examples` normalize it |
| `model` | The model changed; caches are per model | Keep one model per call site |
| `removed` | History got shorter (truncated or summarized) | Append-only history; summarize rarely and at stable points |
| `last turn` | Only the previous request's final turn differs | Usually expected: the retrieved context isn't kept in history |

## Prefix OK, still no cache read

- **The TTL expired.** Anthropic's 5-minute and OpenAI's 30-minute TTLs are measured from the start of the request that wrote or last read the entry. Use `should_cache(..., interval_s=...)` to pick a longer TTL when calls are minutes apart.
- **The prefix is below the minimum** for the model (`cachemaxxing.facts.MODELS[...].min_tokens`).
- **Concurrent requests.** An Anthropic entry becomes readable only after the first response starts streaming. Send one request, wait for its first token, then fan out.
- **Workspace isolation.** Anthropic caches are per workspace; traffic split across workspaces writes separate entries.
- **Routing.** On OpenAI GPT-5.5 and older, more than about 15 requests per minute per `prompt_cache_key` overflow to other machines.
- **Best effort.** Gemini implicit caching needs a few seconds to warm up and is not guaranteed; use `gemini_cache()` when the economics say an explicit cache pays.
- **The 20-block lookback.** An Anthropic breakpoint looks back at most 20 content blocks for an earlier entry. A single turn that appends more than that needs an extra breakpoint.

## Gate it in CI

Replay recorded traffic and fail the build when a call site regresses:

```console
$ cachemaxxing report calls.jsonl --min-hit-rate 0.6
```

It exits 1 and names each call site below the threshold.

## Provider-side diagnostics

- **Anthropic**: the cache-diagnostics beta (`cache-diagnosis-2026-04-07`, Claude API only) reports which part of a request changed against the previous one.
- **OpenAI**: GPT-5.6+ prompt-cache diagnostics on the Responses API.

They work at the request level, online. `cachemaxxing diff` is offline, byte-level and the same for every provider, and works on logs you already have.
