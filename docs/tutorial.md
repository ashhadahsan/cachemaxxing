# Tutorial: find and fix a cache miss

In about ten minutes you'll take a small support bot that has the most common prompt-caching bug, let cachemaxxing find it, fix it, and keep it fixed. You need an OpenAI API key; the whole tutorial costs less than one cent. Every output below is from a real run on 2026-10-31.

## 1. Install

```console
$ pip install "cachemaxxing[openai]"
$ export OPENAI_API_KEY=sk-...
```

The bot is [`examples/tutorial.py`](https://github.com/ashhadahsan/cachemaxxing/blob/main/examples/tutorial.py) in the repository. Clone the repository to run it as is, or copy the snippets into your own code.

## 2. The app you have

The bot sends about 6,300 tokens of support policy and product docs as its system prompt, plus the conversation so far. Like many apps, it also puts the current time at the top of the system prompt:

```python
def before(chat):
    system = f"Current time: {datetime.now(UTC).isoformat()}\n\n{POLICY}\n\n{DOCS}"
    return {"model": "gpt-6-luna", "messages": [{"role": "system", "content": system}, *chat]}
```

Nothing looks wrong, and the answers are fine. The problem is on the bill, and you can't see it from the answers.

## 3. Measure it

Add two lines around each call:

```python
from cachemaxxing import Stats, usage

stats = Stats()                                         # once

kw = before(chat)
resp = client.chat.completions.create(**kw)
stats.add("support.answer", usage(resp), request=kw)    # after every call

print(stats.table())                                    # whenever you want the totals
```

- `usage(resp)` reads the provider's token counts: input, cache read, cache write and output, plus the estimated cost.
- `"support.answer"` is a **call site**, any name you choose for this place in your code. Use one name per prompt template.
- `request=kw` lets `Stats` compare each request with the previous one from the same call site. That comparison is the automatic diagnosis.

Run it:

```console
$ python examples/tutorial.py
How do I reset my router?             6,307 input tokens,      0 from cache (0%)
WARNING cachemaxxing: support.answer: the cached prefix broke: diverges at messages[0].content[0].text char 31 (timestamp), after ~11 matching tokens
  a: 'Current time: 2026-10-31T21:57:27.105469+00:00\n\n# Acme Router support p'
  b: 'Current time: 2026-10-31T21:57:32.635435+00:00\n\n# Acme Router support p'
  fix: A time changes on every call. Move it into .retrieved(), after the cached prefix.
And how do I update its firmware?     6,412 input tokens,      0 from cache (0%)
Thanks! Is that safe?                 6,503 input tokens,      0 from cache (0%)

call site       calls  hit rate  input   cache read  cache write  output  est $   saved $  top drift
support.answer  3      0.0%      19,222  0           19,213       608     0.0027  -0.0005  messages[].content[].text (timestamp) x2
```

Not one token came from cache. It's worse than that: `saved $` is negative. OpenAI wrote the prompt to its cache on every call, and on `gpt-6-luna` a cache write costs 1.25 times the input price. Then it never read the cache back. With this bug, caching costs more than having no caching at all.

## 4. Read the diagnosis

The warning tells you everything you need:

- **`diverges at messages[0].content[0].text char 31`**: the first place where this request differs from the previous one. Here that's character 31 of the system message (`messages[0]`). cachemaxxing reads a plain string content as one text block, so the path ends in `content[0].text`.
- **`(timestamp)`**: the text that changed looks like a time.
- **`after ~11 matching tokens`**: only the first 11 tokens matched. Providers cache a *prefix*, and a request reads from cache only up to the first byte that differs. A change near the top therefore throws away everything after it: here, all 6,300 tokens.
- **`a:` and `b:`**: the previous and the new request around that point. The seconds changed.
- **`fix:`**: what to do about it.

The warning is logged once per call site and cause, not on every call. `stats.table()` keeps counting: `messages[].content[].text (timestamp) x2` means both follow-up calls broke the same way. The warning goes through Python's standard `logging`, under the name `cachemaxxing`. If your app hasn't set up logging, Python prints it to stderr.

## 5. Fix it

The bot may need the time, so it stays in the prompt, just not at the top. Build the request with `Prompt`, which orders the parts from what never changes to what changes on every call:

```python
from cachemaxxing import Prompt

def fixed(chat):
    *history, question = chat
    p = Prompt("support.answer").system(POLICY).context(DOCS).history(history)
    p.retrieved(f"Current time: {datetime.now(UTC).isoformat()}").user(question["content"])
    return p.openai_chat("gpt-6-luna")
```

- **`.system()` and `.context()`**: the long, fixed text goes first.
- **`.history()`**: the conversation so far, sent unchanged.
- **`.retrieved()`**: anything that changes per request, such as the time, retrieved documents or a user profile. It goes after the conversation, so it can't break the cached prefix.
- **`.user()`**: the new question.
- **`.openai_chat(model)`**: returns the keyword arguments for `client.chat.completions.create`, with the cache breakpoints placed for you.

Run it again:

```console
$ python examples/tutorial.py --fixed
How do I reset my router?             6,305 input tokens,      0 from cache (0%)
And how do I update its firmware?     6,366 input tokens,  6,268 from cache (98%)
Thanks! Is that safe?                 6,472 input tokens,  6,279 from cache (97%)

call site       calls  hit rate  input   cache read  cache write  output  est $   saved $  top drift
support.answer  3      65.5%     19,143  12,547      6,340        818     0.0014  0.0010
```

The first call writes the cache. Every call after it reads about 98% of its input from cache, and there is no warning. The three calls cost about half as much as before ($0.0014 instead of $0.0027). The overall hit rate is 65.5% only because a first call always reads nothing; over a longer conversation it approaches 98%.

The same `Prompt` works for the other providers. `.anthropic("claude-haiku-5-5")` gives the arguments for `client.messages.create(max_tokens=1024, **kw)`, and `.gemini("gemini-3.8-flash")` gives them for `client.models.generate_content(**kw)`. The [quickstart](quickstart.md) shows where each provider's markers go.

## 6. Keep it fixed

`Stats` lives in memory. To watch production traffic, or to fail CI when the hit rate drops, log each call with `record()`:

```python
import json
from cachemaxxing import record

with open("calls.jsonl", "a") as log:
    log.write(json.dumps(record("support.answer", kw, resp)) + "\n")
```

`python examples/tutorial.py --log calls.jsonl` writes this log. Then run the report:

```console
$ cachemaxxing report calls.jsonl
call site       calls  hit rate  input   cache read  cache write  output  est $   saved $  top drift
support.answer  3      0.0%      19,222  0           19,213       608     0.0027  -0.0005  messages[].content[].text (timestamp) x2

support.answer: messages[].content[].text (timestamp) on 2 of 2 follow-up calls
  diverges at messages[0].content[0].text char 31 (timestamp), after ~11 matching tokens
  a: 'Current time: 2026-10-31T21:57:27.105469+00:00\n\n# Acme Router support p'
  b: 'Current time: 2026-10-31T21:57:32.635435+00:00\n\n# Acme Router support p'
  fix: A time changes on every call. Move it into .retrieved(), after the cached prefix.
```

From there:

- **Dashboard.** `--html report.html` writes the same report as a [dashboard page](monitoring.md#dashboard).
- **CI gate.** `--min-hit-rate 0.6` exits with code 1 when any call site is below 60%. Run it [in CI](diagnosing.md#gate-it-in-ci) so a change that breaks the cache can't ship unnoticed.
- **Personal data.** If your prompts contain it, log with [`redact=`](diagnosing.md#logs-without-prompt-text).

## 7. Compare two requests yourself

Sometimes all you have is two requests, say from a bug report or two lines of a log. Save each request's keyword arguments as JSON:

```python
json.dump(kw, open("request_1.json", "w"))   # an earlier call
json.dump(kw, open("request_2.json", "w"))   # a later one from the same call site
```

Then compare them:

```console
$ cachemaxxing diff request_1.json request_2.json
diverges at messages[0].content[0].text char 31 (timestamp), after ~11 matching tokens
  a: 'Current time: 2026-10-31T21:57:27.105469+00:00\n\n# Acme Router support p'
  b: 'Current time: 2026-10-31T21:57:32.635435+00:00\n\n# Acme Router support p'
  fix: A time changes on every call. Move it into .retrieved(), after the cached prefix.
```

It exits with code 1 when the requests diverge, and 0 when request 2 repeats all of request 1. `diff` also accepts lines written by `record()`.

## Where next

- **LangChain or LangGraph:** `CacheMiddleware` and `CachedModel` [do all of this automatically](langchain.md), warnings included.
- **Tools, RAG chunks and per-user data:** the [RAG chat example](rag.md), and how to [build the prompt from parts](quickstart.md#tools-rag-and-per-request-context-build-the-prompt-from-parts).
- **A prefix that matches but still isn't read from cache:** [Diagnosing](diagnosing.md#prefix-ok-still-no-cache-read).
- **Before you ship:** [Running in production](production.md).
