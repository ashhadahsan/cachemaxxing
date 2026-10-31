import asyncio
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from cachemaxxing import gemini
from cachemaxxing.prompt import Prompt

BIG = Prompt("site").system("policy " * 8000)  # ~14k tokens estimated


class Caches:
    def __init__(self) -> None:
        self.items: list[Any] = []
        self.created: list[dict[str, Any]] = []

    def list(self) -> list[Any]:
        return list(self.items)

    def create(self, *, model: str, config: dict[str, Any]) -> Any:
        expire = datetime.now(UTC) + timedelta(seconds=int(config["ttl"][:-1]))
        c = SimpleNamespace(
            name=f"cachedContents/{len(self.created)}", display_name=config["display_name"], expire_time=expire
        )
        self.created.append(config)
        self.items.append(c)
        return c


class AsyncCaches:
    def __init__(self, inner: Caches) -> None:
        self.inner = inner

    async def list(self) -> AsyncIterator[Any]:
        async def gen() -> AsyncIterator[Any]:
            for c in self.inner.list():
                yield c

        return gen()

    async def create(self, **kw: Any) -> Any:
        return self.inner.create(**kw)


@pytest.fixture(autouse=True)
def fresh_memo() -> None:
    gemini._LIVE.clear()
    gemini._TOKENS.clear()


def client() -> Any:
    caches = Caches()
    return SimpleNamespace(caches=caches, aio=SimpleNamespace(caches=AsyncCaches(caches)))


def test_not_worth_it_returns_none_without_io() -> None:
    c = client()
    assert gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=0) is None
    assert gemini.gemini_cache(c, BIG, "gemini-4-argon", expected_reuses=50) is None
    assert c.caches.created == []


def test_creates_once_then_reuses_in_process_and_across_processes() -> None:
    c = client()
    name = gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20)
    assert name == "cachedContents/0" and c.caches.created[0]["system_instruction"]["parts"][0]["text"]
    assert gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20) == name
    gemini._LIVE.clear()  # simulate another process: found by display_name
    assert gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20) == name
    assert len(c.caches.created) == 1


def test_expired_cache_is_replaced() -> None:
    c = client()
    gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20)
    c.caches.items[0].expire_time = datetime.now(UTC)
    gemini._LIVE.clear()
    assert gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20) == "cachedContents/1"


def test_async_twin() -> None:
    c = client()
    name = asyncio.run(gemini.gemini_cache_async(c, BIG, "gemini-3.8-flash", expected_reuses=20))
    assert name == "cachedContents/0"


def test_function_tools_skip_explicit_cache() -> None:
    def get_weather(city: str) -> str:
        return city

    c = client()
    p = Prompt("site").tools([get_weather]).system("policy " * 8000)
    assert gemini.gemini_cache(c, p, "gemini-3.8-flash", expected_reuses=20) is None
    assert c.caches.created == []


def test_exact_count_decides_and_is_memoized() -> None:
    c = client()
    counted: list[str] = []

    def count_tokens(**kw: Any) -> Any:
        counted.append(kw["model"])
        return SimpleNamespace(total_tokens=5000)

    c.models = SimpleNamespace(count_tokens=count_tokens)
    small = Prompt("site").system("x " * 7000)  # estimated ~3.5k tokens: under the 4,096 minimum
    assert small.est_prefix_tokens() < 4096
    name = gemini.gemini_cache(c, small, "gemini-3.8-flash", expected_reuses=20)
    assert name == "cachedContents/0"  # the exact count (5,000) clears the minimum
    gemini.gemini_cache(c, small, "gemini-3.8-flash", expected_reuses=20)
    assert counted == ["gemini-3.8-flash"]


class SlowCaches(Caches):
    def create(self, *, model: str, config: dict[str, Any]) -> Any:
        time.sleep(0.05)  # a network round trip: other callers arrive while this one is creating
        return super().create(model=model, config=config)


def test_concurrent_callers_create_one_cache() -> None:
    caches = SlowCaches()
    c = SimpleNamespace(caches=caches, aio=SimpleNamespace(caches=AsyncCaches(caches)))
    with ThreadPoolExecutor(8) as pool:
        names = list(pool.map(lambda _: gemini.gemini_cache(c, BIG, "gemini-3.8-flash", expected_reuses=20), range(8)))
    assert len(caches.created) == 1 and set(names) == {"cachedContents/0"}


def test_concurrent_async_callers_create_one_cache() -> None:
    caches = Caches()

    class SlowAsync(AsyncCaches):
        async def create(self, **kw: Any) -> Any:
            await asyncio.sleep(0.05)
            return self.inner.create(**kw)

    c = SimpleNamespace(caches=caches, aio=SimpleNamespace(caches=SlowAsync(caches)))

    async def many() -> list[str | None]:
        call = gemini.gemini_cache_async(c, BIG, "gemini-3.8-flash", expected_reuses=20)
        return await asyncio.gather(
            *[gemini.gemini_cache_async(c, BIG, "gemini-3.8-flash", expected_reuses=20) for _ in range(7)], call
        )

    names = asyncio.run(many())
    assert len(caches.created) == 1 and set(names) == {"cachedContents/0"}
