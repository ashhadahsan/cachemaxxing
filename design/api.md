# Public API (frozen for 1.0)

Reviewed 2026-10-31, before 0.9.0. `tests/api.txt` holds the exact names and signatures, and `tests/test_api.py` fails CI when they change. The stability rules are in `docs/production.md#stability`.

## What is public

| Import path | Names |
|---|---|
| `cachemaxxing` | everything in `__all__`: `Prompt`, `usage`, `Usage`, `Stats`, `record`, `diff`, `Divergence`, `should_cache`, `Decision`, `gemini_cache`, `gemini_cache_async`, `canonical_json` |
| `cachemaxxing.langchain` | `CacheMiddleware`, `CachedModel`, `cache_fields` |
| `cachemaxxing.facts` | `MODELS`, `PROVIDERS`, `VERIFIED`, `Model`, `Provider`, `find`, `provider_of` |
| `cachemaxxing.count` | `prefix_tokens`, `prefix_tokens_async` |
| CLI | `cachemaxxing diff A B` and `cachemaxxing report LOG [--min-hit-rate X] [--html PATH] [--strict]`; exit codes 0 (ok), 1 (divergence or gate failed), 2 (unreadable input) |
| Formats | the `record()` line (`call_site`, `request`, `response`, or `response.cachemaxxing_usage` when redacted), and the `Usage.attributes()` keys |

`Stats.calls`, `Stats.totals` and `Stats.misses` are public to read. Everything else is internal and may change in any release: underscore names, the `canon`, `diff`, `economics`, `prompt`, `usage`, `gemini`, `dashboard` and `cli` module paths (import from `cachemaxxing` instead), `facts.markdown()`, the dashboard's embedded JSON, and the request kwargs beyond what each provider documents.

## Decisions

Every public name was kept; none is renamed or removed before 1.0, so no deprecation aliases are needed.

| Name | Decision | Why |
|---|---|---|
| `Prompt` and its adapters | keep | Used in every example; adapters return each SDK's own kwargs, so their shape follows the providers, not us |
| `Prompt.static`, `prefix_hash`, `est_prefix_tokens`, `gemini_prefix` | keep | Used by `gemini_cache`, `count` and callers that build their own explicit caches |
| `diagnose: bool \| str` | keep | `True` turns on Anthropic's cache diagnostics. A string is the previous response's id, which Anthropic and OpenAI compare the request with |
| `Usage.input` | keep | Includes cache reads and writes on every provider. This is the one comparable total, and `hit_rate` divides by it. Documented on the field |
| `canonical_json` | keep | Callers use it to serialize their own tools and context the same way `Prompt` does |
| `facts.MODELS` as a plain dict | keep | Documented way to add or correct a model without waiting for a release |
| `count.prefix_tokens` | keep at its submodule path | Documented there; adding a top-level export later is not breaking |
| `gemini_cache` returning `None` | keep, widened | `None` already meant "stay on implicit caching"; since 0.9.0 it also means "the caches API failed" (with a warning), so a cache outage never fails the call |

## How a change is made after 1.0

- **Additions** (new names, new keyword-only parameters with defaults): any minor release. Update `tests/api.txt`.
- **Renames and removals**: the old name keeps working for at least one minor release and emits `DeprecationWarning` (`stacklevel=2`) naming the replacement; removal only in the next major release.
- **Behaviour**: a change that makes a call fail where it used to succeed is breaking. Cost estimates changing because prices changed is not.
