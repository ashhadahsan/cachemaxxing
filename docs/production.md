# Running in production

How to adopt cachemaxxing safely, what it does when something goes wrong, and what stays stable between releases.

## Roll it out in two steps

1. **Measure first.** Log calls with `record()` and run `cachemaxxing report` over the log, by hand, nightly or as a [CI gate](diagnosing.md#gate-it-in-ci). This changes nothing the model sees, so it can't change an answer. It tells you which call sites miss and why.
2. **Then fix one call site at a time.** Move the worst call site to `Prompt`, or wrap its LangChain model, and run your own evals on it before shipping. `Prompt` keeps the meaning of every message, but it does change the request:
    - It sorts tools by name.
    - It puts per-request context such as retrieved chunks after the conversation.
    - It tidies whitespace in the system prompt, context and examples.

    Then watch that call site's hit rate in the report or [in your traces](monitoring.md#traces).

## Pin the version

```
cachemaxxing~=0.10     # now
cachemaxxing~=1.0      # from 1.0: any 1.x release is a safe upgrade
```

## What happens when something goes wrong

The rule: **cachemaxxing never makes a model call fail that would have worked without it.** Mistakes in your configuration fail early, before anything is sent or billed. Everything else falls back and logs a warning.

| Situation | What happens |
|---|---|
| A TTL the provider doesn't offer (`Prompt` adapters, `CacheMiddleware`, `CachedModel`) | `ValueError` before the request is sent |
| `should_cache()` or `gemini_cache()` with a model that isn't in `facts.MODELS` | `ValueError` before anything is sent. [Add the model](#costs) or pass a known one |
| `CacheMiddleware` or `CachedModel` can't add cache fields | The request is sent without them; warning |
| `CacheMiddleware` or `CachedModel` can't measure the reply, or your `on_record` raises | The reply is returned as usual; warning |
| `gemini_cache()`: the Gemini caches API fails | Returns `None`, so the call uses implicit caching; warning |
| `gemini_cache()`: the token count fails | Falls back to an estimate of about 4 characters per token |
| `usage(response)` on a response it can't read | `ValueError`, and only `ValueError` |
| `record(..., redact=fn)` on a response it can't read | `ValueError`. Without `redact=`, `record()` doesn't read the response |
| `diff()` on something that isn't a request | `ValueError` |
| `cachemaxxing report` on unreadable lines | Skips them and prints a count to stderr. With `--strict`, exits 2 at the first one |
| A model that isn't in `facts.MODELS` (`usage`, adapters) | Works; `est_cost` and `saved` are `None` |

Warnings go to the standard `logging` logger named `cachemaxxing`, with the traceback. If you call `usage()` or `record()` in your own request path, wrap them the same way:

```python
try:
    log.write(json.dumps(record("support.answer", kwargs, resp, redact=hashed)) + "\n")
except Exception:
    logging.getLogger("cachemaxxing").warning("could not log a call", exc_info=True)
```

**CLI exit codes:** `0` is OK. `1` means `diff` found a divergence or `report` found a call site below `--min-hit-rate`. `2` means the input couldn't be read.

## Logs

- **Size.** A plain `record()` line holds the whole request and response, so it's roughly as big as both. A line written with `redact=` stores only the response's token counts, so it is smaller.
- **Personal data.** Use [`redact=`](diagnosing.md#logs-without-prompt-text) when prompts may hold personal data. The `report --html` page then shows only the redacted text.
- **Rotation.** Every line stands alone, so rotate the log however you like. `report` reads one file; to cover a longer period, concatenate the files first.
- **Sampling.** `report` finds drift by comparing consecutive calls from the same call site. To log only some traffic, sample whole conversations or time windows, never single calls, or nothing will line up.
- **Big logs.** `report` reads the log line by line. The dashboard draws the last 5,000 calls per call site, so the page stays small.

## Concurrency

- **Shared objects.** `Stats`, `CacheMiddleware` and `CachedModel` can be shared between threads and async tasks.
- **Cold starts.** Requests sent at the same moment before the first one has finished all find an empty cache, and each pays to write it. Send one request first, then fan out.
- **Gemini explicit caches.** Within one process, `gemini_cache()` creates at most one cache per prefix, even when many threads or tasks ask at once. Across processes, it finds an existing cache by name, but two processes that start at the same moment can each create one.

## Costs

`est_cost` and `saved` are estimates at list price, from the table in `cachemaxxing.facts`. They leave out batch and priority tiers, regional pricing and your own discounts. Gemini's hourly storage for explicit caches isn't included either.

- **Freshness.** The table is checked against the providers every month. Price changes ship in patch releases, and a changed estimate is not a breaking change.
- **Missing or different prices.** For a model that isn't listed, or a negotiated price, edit the table at startup:

```python
from cachemaxxing import facts

facts.MODELS["my-fine-tune"] = facts.Model("openai", input=0.30, output=1.20, cache_read=0.03, cache_write={"30m": 0.375})
```

## Stability

From 1.0 the project follows [Semantic Versioning](https://semver.org/):

- **Public API.** The names in `cachemaxxing`, `cachemaxxing.langchain`, `cachemaxxing.facts` and `cachemaxxing.count` are public, along with the CLI, its exit codes and the `record()` line format. [design/api.md](https://github.com/ashhadahsan/cachemaxxing/blob/main/design/api.md) has the full list. Anything starting with `_`, and other module paths, can change at any time.
- **Changes.** New names and optional parameters arrive in minor releases. A rename or removal keeps the old name working, with a `DeprecationWarning`, for at least one minor release. It is removed only in the next major release.
- **Python.** Every version from 3.11 is supported until its end of life. Dropping a version is a minor release.
- **SDKs.** The lowest versions allowed by the extras (`[anthropic]`, `[openai]`, `[gemini]`, `[langchain]`) are tested in CI. They are raised only in minor releases.
- **Provider drift.** A live check runs every night against Anthropic, OpenAI, Gemini and LangChain, so a provider or SDK change that breaks caching shows up within a day.

## Reporting problems

Report bugs at [GitHub issues](https://github.com/ashhadahsan/cachemaxxing/issues). Report security problems privately, as described in [SECURITY.md](https://github.com/ashhadahsan/cachemaxxing/blob/main/SECURITY.md).
