import subprocess
import sys
import tomllib
from pathlib import Path


def test_public_api() -> None:
    from cachemaxxing import (  # noqa: F401
        Decision,
        Divergence,
        Prompt,
        Stats,
        Usage,
        canonical_json,
        diff,
        gemini_cache,
        gemini_cache_async,
        record,
        should_cache,
        usage,
    )


def test_zero_runtime_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
    assert project.get("dependencies", []) == []


def test_import_pulls_in_no_sdk_http_or_requests() -> None:
    banned = "{'anthropic','openai','google','litellm','httpx','httpx2','requests'}"
    code = f"import sys, cachemaxxing; print(sorted({{m.split('.')[0] for m in sys.modules}} & {banned}))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_no_requests_in_the_tree() -> None:
    needle = "import " + "requests"  # split so this file doesn't match itself
    for path in Path(".").glob("[sbet]*/**/*.py"):
        assert needle not in path.read_text(encoding="utf-8"), path
