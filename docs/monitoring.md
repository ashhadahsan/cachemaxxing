# Monitoring: traces and dashboard

Two ways to watch hit rate and savings over time:

- in the tracing tool you already use (Langfuse, LangSmith or anything OpenTelemetry)
- in a dashboard built from your `record()` log

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
