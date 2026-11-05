# Azure OpenAI

Azure OpenAI runs the same models as OpenAI with [the same request format](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching), cache breakpoints included. So cachemaxxing works with the code you'd write for OpenAI. The main difference is that `model` is the name of your **deployment**.

## Connect

```python
import os
from openai import OpenAI
from cachemaxxing import Prompt, usage

client = OpenAI(
    base_url="https://YOUR-RESOURCE.openai.azure.com/openai/v1/",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
)

chat = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": "How do I reset my router?"},
]
kw = Prompt("support.answer").messages(chat).openai_chat("gpt-6-luna")  # your deployment's name
resp = client.chat.completions.create(**kw)
print(f"{usage(resp).hit_rate:.0%} of input from cache")
```

The `AzureOpenAI` client works the same way, and so does `p.openai(...)` for the Responses API. To run a complete example, use `examples/chat.py azure`.

Two calls on a `gpt-6-luna` deployment, run live on 2026-11-04 and 2026-11-05 with a prompt of about 6,300 tokens that hadn't been cached before:

| API and client | Call 1 | Call 2 |
|---|---|---|
| Chat Completions, `OpenAI` client | 0 read, 6,302 written | 6,291 of 6,306 read |
| Responses, `OpenAI` client | 0 read, 6,306 written | 6,295 of 6,310 read |
| Chat Completions, `AzureOpenAI` client | 0 read, 6,303 written | 6,292 of 6,307 read |
| LangChain `AzureChatOpenAI` with `CachedModel` | 0 read, 6,301 written | 6,301 of 6,322 read |

## Deployment names

cachemaxxing chooses the cache fields from the model name. A deployment can have any name, so tell it when the name doesn't say which model runs there:

| Your deployment | Pass | What gets sent |
|---|---|---|
| Named after a GPT-5.6+ model, like `gpt-6-luna` | nothing | Cache breakpoints |
| GPT-5.6 or later under another name, like `prod-chat` | `explicit=True` | Cache breakpoints |
| Provisioned (PTU-M) | `explicit=False` | `prompt_cache_key` only |
| A model before GPT-5.6 | nothing, as long as the name doesn't look like GPT-5.6+ | `prompt_cache_key` only |

```python
kw = p.openai_chat("prod-chat", explicit=True)   # GPT-5.6 or later under another name
kw = p.openai_chat("gpt-6-luna", explicit=False)  # a provisioned deployment
```

According to Microsoft, provisioned deployments don't support breakpoints, and models before GPT-5.6 return a 400 error if you send them. Never pass `explicit=True` for those.

Without `explicit=True`, a deployment with another name still caches automatically. But breakpoints are what keep per-request context, such as retrieved chunks, out of the cached prefix.

## LangChain and LangGraph

`CacheMiddleware` and `CachedModel` work with `AzureChatOpenAI`:

```python
from langchain_openai import AzureChatOpenAI
from cachemaxxing.langchain import CachedModel

llm = AzureChatOpenAI(azure_deployment="gpt-6-luna", api_version="2025-04-01-preview")
cached = CachedModel(llm, call_site="support.answer")
```

If the deployment's name doesn't say it's GPT-5.6 or later, the wrappers add no cache fields, so Azure can't reject the call. Pass `explicit=True` to add them for such a deployment, or `explicit=False` to leave a provisioned one alone.

## Costs

`est_cost` and `saved` use OpenAI's list prices, not Azure's. Azure lists its prices per deployment type, so check yours on [Azure's pricing page](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/). If yours differ, [edit the price table at startup](production.md#costs).

With a custom deployment name, a response may report that name instead of the model. In that case `est_cost` is `None`. Name the model to get an estimate:

```python
u = usage(resp, model="gpt-6-luna")
```

## What has been tested

- **Live:** `gpt-6-luna` through Chat Completions, Responses (including the 12h TTL), both clients, `AzureChatOpenAI` and `explicit=False`, and a cache write on `gpt-6.1-sol`. A check on Azure runs every night, along with the other providers.
- **Offline only:** custom deployment names with `explicit=True`, against the real SDK with a mock server.
- **Not tested:** provisioned deployments, and models before GPT-5.6. That guidance comes from Microsoft's documentation.
- **LiteLLM:** the `azure/` route sends plain requests with no cache fields. Azure's automatic caching still applies.
