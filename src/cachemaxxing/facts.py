"""Provider prompt-caching facts. Prices are USD per 1M tokens; every row links to its source.

Checked on VERIFIED. Add or correct models by editing MODELS (it is a plain dict)."""

from __future__ import annotations

from dataclasses import dataclass, field

VERIFIED = "2026-10-30"


@dataclass(frozen=True)
class Provider:
    max_breakpoints: int | None  # explicit markers per request; None = none (implicit caching)
    ttls: tuple[str, ...]  # shortest first
    docs: str


@dataclass(frozen=True)
class Model:
    provider: str
    input: float
    output: float
    cache_read: float
    cache_write: dict[str, float] = field(default_factory=dict)  # TTL -> price, shortest first
    min_tokens: int = 1024
    storage_hour: float | None = None  # Gemini explicit caches, per 1M tokens per hour
    long_context: tuple[int, Model] | None = None  # (prompt tokens above which, these prices)
    source: str = ""


PROVIDERS = {
    "anthropic": Provider(4, ("5m", "1h"), "https://platform.claude.com/docs/en/build-with-claude/prompt-caching"),
    "openai": Provider(4, ("30m", "12h"), "https://developers.openai.com/api/docs/guides/prompt-caching"),
    "gemini": Provider(None, (), "https://ai.google.dev/gemini-api/docs/caching"),
}

_A = "https://platform.claude.com/docs/en/about-claude/pricing"
_O = "https://developers.openai.com/api/docs/pricing"
_G = "https://ai.google.dev/gemini-api/docs/pricing"

MODELS: dict[str, Model] = {
    "claude-haiku-5-5": Model(
        "anthropic",
        0.10,
        0.50,
        0.01,
        {"5m": 0.125, "1h": 0.20},
        512,
        source=_A,
        long_context=(100_000, Model("anthropic", 0.50, 2.50, 0.05, {"5m": 0.625, "1h": 1.00}, 512, source=_A)),
    ),
    "claude-sonnet-5-5": Model("anthropic", 2.00, 10.00, 0.10, {"5m": 2.50, "1h": 4.00}, 512, source=_A),
    "claude-opus-5-5": Model("anthropic", 4.00, 20.00, 0.20, {"5m": 5.00, "1h": 8.00}, 512, source=_A),
    "claude-fable-5-1": Model("anthropic", 10.00, 50.00, 0.25, {"5m": 12.50, "1h": 20.00}, 512, source=_A),
    "gpt-6-luna": Model("openai", 0.10, 0.50, 0.01, {"30m": 0.125, "12h": 0.25}, 1024, source=_O),
    "gpt-6.1-sol": Model("openai", 2.00, 10.00, 0.10, {"30m": 2.50, "12h": 5.00}, 1024, source=_O),
    "gpt-6-astra": Model("openai", 10.00, 50.00, 1.00, {"30m": 12.50, "12h": 25.00}, 1024, source=_O),
    # Gemini caches implicitly; storage_hour marks explicit-cache support.
    # gemini-3.8-flash prices double on 2027-01-01, gemini-4-argon's on 2026-12-01: patch releases then.
    "gemini-3.8-flash": Model("gemini", 0.75, 3.75, 0.075, min_tokens=4096, storage_hour=0.50, source=_G),
    "gemini-3.1-flash-lite": Model("gemini", 0.25, 1.50, 0.025, min_tokens=4096, storage_hour=1.00, source=_G),
    "gemini-4-argon": Model("gemini", 2.00, 10.00, 0.10, min_tokens=4096, source=_G),
}


def find(model: str) -> Model | None:
    """Longest-prefix match on the id, ignoring 'provider/' and 'models/' prefixes and dated suffixes."""
    name = model.rsplit("/", 1)[-1]
    best = max((k for k in MODELS if name.startswith(k)), key=len, default=None)
    return MODELS[best] if best else None


def provider_of(model: str) -> str:
    """'anthropic', 'openai', 'gemini' or 'other' for a model id, LiteLLM 'route/model' ids included."""
    if (m := find(model)) is not None:
        return m.provider
    prefix, _, rest = model.partition("/")
    if rest and prefix in PROVIDERS:
        return prefix
    name = rest or prefix
    if "claude" in name:
        return "anthropic"
    if name.startswith("gemini"):
        return "gemini"
    if not rest and name.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "other"


def markdown() -> str:
    """The facts as Markdown; docs/_facts.md is this output."""
    out = ["| Provider | Max breakpoints | TTLs | Docs |", "|---|---|---|---|"]
    for name, p in PROVIDERS.items():
        ttls = ", ".join(p.ttls) or "explicit caches take any TTL"
        out.append(f"| {name} | {p.max_breakpoints or 'implicit only'} | {ttls} | <{p.docs}> |")
    out += [
        "",
        "| Model | Input | Cache read | Cache write | Output | Min tokens | Storage/h | Source |",
        "|---|--:|--:|---|--:|--:|--:|---|",
    ]
    for name, m in MODELS.items():
        write = ", ".join(f"{ttl}: {price:g}" for ttl, price in m.cache_write.items()) or "—"
        storage = "—" if m.storage_hour is None else f"{m.storage_hour:g}"
        out.append(
            f"| `{name}` | {m.input:g} | {m.cache_read:g} | {write} | {m.output:g} "
            f"| {m.min_tokens:,} | {storage} | [pricing]({m.source}) |"
        )
    out += ["", f"USD per 1M tokens. Verified {VERIFIED}."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
