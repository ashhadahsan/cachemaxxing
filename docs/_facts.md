| Provider | Max breakpoints | TTLs | Docs |
|---|---|---|---|
| anthropic | 4 | 5m, 1h | <https://platform.claude.com/docs/en/build-with-claude/prompt-caching> |
| openai | 4 | 30m, 12h | <https://developers.openai.com/api/docs/guides/prompt-caching> |
| gemini | implicit only | explicit caches take any TTL | <https://ai.google.dev/gemini-api/docs/caching> |

| Model | Input | Cache read | Cache write | Output | Min tokens | Storage/h | Source |
|---|--:|--:|---|--:|--:|--:|---|
| `claude-haiku-5-5` | 0.1 | 0.01 | 5m: 0.125, 1h: 0.2 | 0.5 | 512 | — | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-sonnet-5-5` | 2 | 0.1 | 5m: 2.5, 1h: 4 | 10 | 512 | — | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-opus-5-5` | 4 | 0.2 | 5m: 5, 1h: 8 | 20 | 512 | — | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `claude-fable-5-1` | 10 | 0.25 | 5m: 12.5, 1h: 20 | 50 | 512 | — | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| `gpt-6-luna` | 0.1 | 0.01 | 30m: 0.125, 12h: 0.25 | 0.5 | 1,024 | — | [pricing](https://developers.openai.com/api/docs/pricing) |
| `gpt-6.1-sol` | 2 | 0.1 | 30m: 2.5, 12h: 5 | 10 | 1,024 | — | [pricing](https://developers.openai.com/api/docs/pricing) |
| `gpt-6-astra` | 10 | 1 | 30m: 12.5, 12h: 25 | 50 | 1,024 | — | [pricing](https://developers.openai.com/api/docs/pricing) |
| `gemini-3.8-flash` | 0.75 | 0.075 | — | 3.75 | 4,096 | 0.5 | [pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| `gemini-3.1-flash-lite` | 0.25 | 0.025 | — | 1.5 | 4,096 | 1 | [pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| `gemini-4-argon` | 2 | 0.1 | — | 10 | 4,096 | — | [pricing](https://ai.google.dev/gemini-api/docs/pricing) |

USD per 1M tokens. Verified 2026-10-30.
