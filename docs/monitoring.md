# Monitoring: traces and dashboard

Two ways to watch hit rate and savings:

- in a dashboard page built from your `record()` log
- in the tracing tool you already use (Langfuse, LangSmith or anything OpenTelemetry)

## Dashboard

```console
$ cachemaxxing report calls.jsonl --min-hit-rate 0.6 --html report.html
```

This writes one self-contained HTML page next to the usual table. Open it in any browser. The page shows:

- the totals: calls, hit rate, spend, and the money caching saved
- a gate banner, when you pass `--min-hit-rate`
- the hit rate of every call, per call site
- a sortable table of call sites
- for each call site that missed, the exact characters that changed between consecutive requests, and how to fix it
- the provider's own verdict, when you used `diagnose=`

[See a demo built from a real log of 20 calls](demo.html). One of its call sites has the classic bug: the current time at the top of the system prompt.

The page makes no network requests. The data is embedded and drawn by inline JavaScript, and a Content-Security-Policy in the page makes the browser block any request too. It does contain short snippets of your prompts around each divergence, so share it as you would share the log. With a log written using `record(..., redact=)`, the snippets show your redacted text instead.

The page stays small for any log size. For each call site, the chart draws the most recent 5,000 calls and says so when there are more. The totals and the table always count every call. A log of 7,000 calls gives a page of about 180 KB. `--html` doesn't change the exit code: the gate still fails below `--min-hit-rate`. That makes the page a good CI artifact:

```yaml
- run: cachemaxxing report calls.jsonl --min-hit-rate 0.6 --html report.html
- uses: actions/upload-artifact@v5
  if: always()
  with: {name: cache-report, path: report.html}
```

## Traces

`Usage.attributes()` returns a call's cache metrics as a flat dict. Every value is a string or a number, so the dict works as Langfuse or LangSmith metadata and as OpenTelemetry span attributes.

```python
from cachemaxxing import usage

u = usage(response)
u.attributes("support.answer")
# {"cachemaxxing.call_site": "support.answer", "cachemaxxing.provider": "anthropic",
#  "cachemaxxing.model": "claude-haiku-5-5", "cachemaxxing.hit_rate": 0.891...,
#  "cachemaxxing.input_tokens": 10100, "cachemaxxing.cache_read_tokens": 9000,
#  "cachemaxxing.cache_write_tokens": 1000, "cachemaxxing.output_tokens": 50,
#  "cachemaxxing.est_cost_usd": 0.00025, "cachemaxxing.saved_usd": 0.000785}
```

- `saved_usd` is what the call would have cost with no caching, minus what it cost. It is negative when cache writes cost more than the reads saved.
- `miss_reason` appears only when you asked the provider for diagnostics (`diagnose=`, see [Diagnosing](diagnosing.md#ask-the-provider)).
- Values the library doesn't know are left out. For example, cost is unknown for a model that isn't in the facts table.
- Use `prefix=""` for bare keys.

!!! note
    The recipes below follow the Langfuse and LangSmith Python SDK docs. They have not yet been run against live Langfuse or LangSmith projects.

### LangChain and LangGraph: automatic

`CacheMiddleware` and `CachedModel` attach the metrics to every model reply as `response_metadata["cachemaxxing"]`. You don't need any extra code. The reply carries them into the agent's outputs, so they show up wherever LangSmith or Langfuse display those outputs.

```python
ai = result["messages"][-1]
ai.response_metadata["cachemaxxing"]  # {"call_site": "support.agent", "hit_rate": 0.9, "saved_usd": ...}
```

### Langfuse

Put the metrics in the current observation's metadata. To chart the hit rate over time, also record it as a numeric score:

```python
from langfuse import get_client, observe

langfuse = get_client()


@observe()
def answer(question: str) -> str:
    response = client.messages.create(max_tokens=1024, **p.anthropic("claude-haiku-5-5"))
    u = usage(response)
    langfuse.update_current_span(metadata=u.attributes("support.answer"))
    langfuse.score_current_trace(name="cache_hit_rate", value=u.hit_rate, data_type="NUMERIC")
    return response.content[0].text
```

### LangSmith

Add the metrics to the current run's metadata:

```python
import langsmith as ls


@ls.traceable
def answer(question: str) -> str:
    response = client.responses.create(**p.openai("gpt-6-luna"))
    ls.get_current_run_tree().metadata.update(usage(response).attributes("support.answer"))
    return response.output_text
```

### OpenTelemetry

```python
from opentelemetry import trace

with trace.get_tracer("app").start_as_current_span("support.answer") as span:
    response = client.models.generate_content(**p.gemini("gemini-3.8-flash"))
    span.set_attributes(usage(response).attributes("support.answer"))
```
