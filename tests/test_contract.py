"""Real SDKs, mock HTTP: proves the adapters' kwargs are accepted and land in the request body as intended."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from cachemaxxing.prompt import Prompt
from cachemaxxing.usage import usage

FIX = Path(__file__).parent / "fixtures"


def transport(reply: str, seen: list[Any], lib: Any = httpx) -> Any:
    """A MockTransport from `lib` (httpx, or httpx2 for anthropic>=2) that records request bodies."""

    def handler(request: Any) -> Any:
        seen.append(json.loads(request.content))
        return lib.Response(200, json=json.loads((FIX / reply).read_text()))

    return lib.MockTransport(handler)


def prompt(history: list[Any] | None = None) -> Prompt:
    history = history or [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    return Prompt("contract").system("S" * 100).history(history).user("q")


def test_anthropic() -> None:
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")
    seen: list[Any] = []
    http = httpx2.Client(transport=transport("anthropic_message.json", seen, httpx2))
    client = anthropic.Anthropic(api_key="test", http_client=http)
    resp = client.messages.create(max_tokens=16, **prompt().anthropic("claude-haiku-5-5"))
    assert seen[0]["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert seen[0]["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert usage(resp).cache_read == 4000


@pytest.mark.parametrize("api", ["responses", "chat"])
def test_openai(api: str) -> None:
    openai = pytest.importorskip("openai")
    seen: list[Any] = []
    reply = "openai_response.json" if api == "responses" else "openai_chat.json"
    client = openai.OpenAI(api_key="test", http_client=httpx.Client(transport=transport(reply, seen)))
    p = prompt()
    if api == "responses":
        resp = client.responses.create(**p.openai("gpt-6-luna"))
    else:
        resp = client.chat.completions.create(**p.openai_chat("gpt-6-luna"))
    assert seen[0]["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert "prompt_cache_breakpoint" in json.dumps(seen[0])
    assert usage(resp).cache_read == 1024


def test_gemini() -> None:
    genai = pytest.importorskip("google.genai")
    seen: list[Any] = []
    http = httpx.Client(transport=transport("gemini_response.json", seen))
    client = genai.Client(api_key="test", http_options={"httpx_client": http})
    history = [{"role": "user", "parts": [{"text": "hi"}]}, {"role": "model", "parts": [{"text": "yo"}]}]
    resp = client.models.generate_content(**prompt(history).gemini("gemini-3.8-flash"))
    assert seen[0]["systemInstruction"]["parts"][0]["text"].startswith("S")
    assert usage(resp).cache_read == 4096
