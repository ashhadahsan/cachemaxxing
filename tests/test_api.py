"""The public API, frozen. Changing a public name or signature means updating tests/api.txt on purpose:
UPDATE_API=1 uv run pytest tests/test_api.py. Removals and renames need a deprecation first (docs/production.md)."""

import inspect
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import cachemaxxing
from cachemaxxing import count, facts

SNAPSHOT = Path(__file__).parent / "api.txt"
FACTS = ["MODELS", "PROVIDERS", "VERIFIED", "Model", "Provider", "find", "provider_of"]
COUNT = ["prefix_tokens", "prefix_tokens_async"]


def describe(name: str, obj: Any) -> list[str]:
    if inspect.isclass(obj):
        lines = [f"class {name}{inspect.signature(obj)}"]
        for attr, member in sorted(vars(obj).items()):
            if attr.startswith("_"):
                continue
            if isinstance(member, property):
                lines.append(f"  {name}.{attr}: property")
            elif callable(member):
                lines.append(f"  {name}.{attr}{inspect.signature(member)}")
        return lines
    if callable(obj):
        return [f"{name}{inspect.signature(obj)}"]
    return [f"{name}: {type(obj).__name__}"]


def surface(langchain: ModuleType) -> list[str]:
    lines: list[str] = []
    for module, prefix, names in [
        (cachemaxxing, "", cachemaxxing.__all__),
        (langchain, "langchain.", langchain.__all__),
        (facts, "facts.", FACTS),
        (count, "count.", COUNT),
    ]:
        for name in sorted(names):
            lines += describe(prefix + name, getattr(module, name))
    return lines


def test_public_api_matches_the_snapshot() -> None:
    langchain = pytest.importorskip("cachemaxxing.langchain")
    got = "\n".join(surface(langchain)) + "\n"
    if os.environ.get("UPDATE_API"):
        SNAPSHOT.write_text(got)
    assert got == SNAPSHOT.read_text(), "public API changed; on purpose? UPDATE_API=1 uv run pytest tests/test_api.py"
