# cachemaxxing requirements

_Derived from the cachemaxxing v0.1 plan dated 2026-10-30._

## 4.1 Functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-1 | **Layout.** `Prompt(call_site)` takes up to seven segments: `tools`, `system`, `context`, `examples`, `history`, `retrieved`, `user`. The output order is always tools → system → context → examples → history → retrieved → user, however the methods are called. | Calling the methods in any order produces identical kwargs. |
| FR-2 | **Canonicalization.** `canonical_json` uses sorted keys, `(",", ":")` separators and `ensure_ascii=False`. Non-string parts are rendered as canonical JSON. Tools are sorted by name, including Gemini `function_declarations`; `sort=False` opts out. Whitespace is normalized (CRLF→LF, trailing spaces, blank edges) in system, context and examples only. | Inputs that are equal but differ in key order or line endings produce byte-identical kwargs. |
| FR-3 | **Never change meaning.** No reordering except tools and parts marked `reorderable=True`. History, retrieved and user text are passed through verbatim. History objects are never mutated: a marker goes only on a copy of one block, never on a thinking block. | Tests assert text equality and that the input lists are unchanged. |
| FR-4 | **Anthropic.** `p.anthropic(model, ttl="5m"\|"1h")` gives kwargs for `messages.create` with `cache_control` on: the last tool; the last static system block; and either the final user block (no retrieved segment) or the last markable history block (retrieved present). At most 3 markers, one TTL. | Shape tests. The SDK contract test accepts the kwargs and the body carries the markers. |
| FR-5 | **OpenAI.** `p.openai(model)` targets Responses and `p.openai_chat(model)` targets Chat Completions. GPT-5.6+ get `prompt_cache_options={"mode":"explicit","ttl":…}` and `prompt_cache_breakpoint` at the same boundaries, on text parts of input messages only. Legacy models get `prompt_cache_key = f"{call_site}:{prefix_hash}"`. `cache_key=` overrides it. 12h on Chat → `ValueError`. | Shape tests. The SDK contract tests (Responses and Chat) pass. |
| FR-6 | **Gemini.** `p.gemini(model, cached_content=None)` gives kwargs for `models.generate_content`: `system_instruction` parts, `tools`, `contents`. With `cached_content` set, `system_instruction`, `tools` and `tool_config` are omitted. | Shape tests. The google-genai contract or type-validation test passes. |
| FR-7 | **Gemini explicit cache.** `gemini_cache(client, p, model, expected_reuses=…, interval_s=60)` and `gemini_cache_async(...)` create or reuse a cache **only when `should_cache` says it pays**. Reuse is checked in-process first, then across processes by `display_name`. | Fake-client tests (sync and async): not worth it → `None`, no create; worth it → one create, then reuse; expired → new cache. |
| FR-8 | **LiteLLM.** `p.litellm(model, ttl=None, explicit=False)` gives kwargs, including `model`, for `litellm.completion` or the Proxy via the OpenAI SDK. Markers follow the underlying route: Claude gets `cache_control` on parts and in `tool.function`; `openai/` returns exactly `openai_chat()`; `gemini/` gets no markers unless `explicit=True`, which marks only the static system message; unknown routes get plain kwargs. `usage()` parses LiteLLM responses. No dependency on litellm. | Shape tests and usage tests. Live in D7. |
| FR-9 | **Economics.** `should_cache(prefix_tokens, expected_reuses, provider, model, *, interval_s=60)` returns `Decision(cache, ttl, saving, reason)` from `facts.MODELS`. | Break-even tests (§6 B8). |
| FR-10 | **Facts table.** `facts.MODELS` and `PROVIDERS` include `source` URLs and `VERIFIED`. `facts.markdown()` renders the docs table. | Every row has an https source. The docs file matches `markdown()`. |
| FR-11 | **Telemetry.** `usage(resp, model=None)` normalizes Anthropic, OpenAI Responses and Chat, Gemini (snake_case and camelCase) and LiteLLM responses, given as SDK objects or dicts, into `Usage(provider, model, input, cache_read, cache_write, output, est_cost)` plus `.hit_rate`. `Stats` aggregates per call site. `record()` builds a JSONL-ready dict. | Fixture tests per shape, including the providers' documented examples and long-context pricing. |
| FR-12 | **Drift diagnosis.** `diff(a, b)` returns the first `Divergence(path, offset, a, b, hint, prefix_chars)` or `None` when b repeats all of a. It ignores cache markers, treats string content as equal to a single text block, and ignores request params outside the prompt. Hints: `model`, `tool order`, `key order`, `removed`, `last turn`, `whitespace`, `uuid`, `timestamp`, `hex id`. | Table-driven tests (§6 B11). |
| FR-13 | **CLI.** `cachemaxxing diff A.json B.json` exits 1 on divergence. `cachemaxxing report LOG.jsonl [--min-hit-rate X]` prints, per call site: calls, hit rate, tokens, est $ and top drift (including "prefix ok, no cache read"). It exits 1 below the threshold. | `main([...])` tests with temporary files. |
| FR-14 | **Benchmarks.** One script per provider runs naive and cachemaxxing arms on the cheapest caching model (gemini-3.8-flash, gpt-6-luna, claude-haiku-5-5), 8 turns × 3 repetitions. Each reports cached % and est $, writes `benchmarks/results/<provider>.json`, and stays under a `--max-usd` guard. A chart is generated from the JSON. | Results committed. README numbers match the JSON. |
| FR-15 | **Docs site.** Pages: Home (measure-first, 10-line example, chart, install with pip and uv), Quickstart, How caching works (facts table with verified dates), Diagnosing a low hit rate, API reference (mkdocstrings), How it compares, Changelog. The README is the short Home with 4 badges. | `zensical build --clean` succeeds in CI. Site is live. |
| FR-16 | **Release.** `release.yml`: `workflow_dispatch` → TestPyPI; tag `v*` → PyPI. Uses OIDC Trusted Publishing, attestations, and environments with the owner as required reviewer. | TestPyPI dry run, then PyPI 0.1.0. |

## 4.2 Non-functional requirements

| ID | Requirement | Verified by |
|---|---|---|
| NFR-1 | **Pure core:** `dependencies = []`; importing `cachemaxxing` imports no SDK, `httpx` or `requests`; no file or network I/O outside `gemini.py`, which uses the caller's client | `tests/test_packaging.py` |
| NFR-2 | Python 3.11–3.15 | CI matrix |
| NFR-3 | `mypy --strict` on `src/`; ships `py.typed` | CI |
| NFR-4 | ruff lint and format | CI |
| NFR-5 | Tests run offline; CI has no keys; SDKs are dev-only with mock HTTP transports | CI |
| NFR-6 | No `requests` anywhere | CI grep step and the packaging test |
| NFR-7 | Supply chain: `uv.lock` committed with `uv sync --locked`; actions pinned by SHA; Dependabot; Trusted Publishing; attestations | Workflows |
| NFR-8 | Honesty: homepage and README numbers come only from committed benchmark JSON; "How it compares" says where others are ahead | Review at G6 |
| NFR-9 | Facts freshness: each row has a source; the docs show `VERIFIED` | `test_facts.py` |
| NFR-10 | Secrets: `.env` is never tracked | `git check-ignore .env` in Task A1 and before every push |

## 4.3 Out of scope for v0.1

These are left out as the handoff says:
- semantic or response caching
- proxies and servers
- routing for self-hosted engines
- framework integrations other than LiteLLM
- the npm package (phase 2)
- token counting with real tokenizers (`est_prefix_tokens` uses ~4 chars per token; callers can pass exact counts)
- surfacing provider-side cache diagnostics in code (documented in "Diagnosing" instead)
- a LiteLLM logging callback (the owner chose adapter plus parsing)

## 4.4 Traceability

| Req | Code | Tests |
|---|---|---|
| FR-1, FR-2, FR-3 | `src/cachemaxxing/canon.py`, `prompt.py` | `tests/test_canon.py`, `tests/test_prompt.py` |
| FR-4, FR-5, FR-6, FR-8 | `prompt.py` | `tests/test_prompt.py`, `tests/test_contract.py` |
| FR-7 | `gemini.py` | `tests/test_gemini.py` |
| FR-9 | `economics.py` | `tests/test_economics.py` |
| FR-10 | `facts.py`, `docs/_facts.md` | `tests/test_facts.py` |
| FR-11 | `usage.py` | `tests/test_usage.py`, `tests/test_contract.py` |
| FR-12 | `diff.py` | `tests/test_diff.py` |
| FR-13 | `cli.py` | `tests/test_cli.py` |
| FR-14 | `benchmarks/` | `benchmarks/results/*.json` (Phase 5 evidence) |
| FR-15 | `docs/`, `mkdocs.yml`, `.github/workflows/docs.yml` | Docs build in CI |
| FR-16 | `.github/workflows/release.yml` | TestPyPI dry run |
| NFR-1, NFR-6 | — | `tests/test_packaging.py` |
