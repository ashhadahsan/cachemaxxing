# Contributing

## Setup

```console
$ uv sync
```

That installs the package, the test tools and the provider SDKs, which the tests use offline. You need [uv](https://docs.astral.sh/uv/).

## Before you open a pull request

```console
$ uv run ruff check && uv run ruff format --check
$ uv run mypy
$ uv run coverage run -m pytest && uv run coverage report --fail-under=95
$ uv run --group docs zensical build --clean        # when you change docs
```

The tests never call a paid API. To check against the real providers, run `uv run --env-file .env python benchmarks/canary.py` with your own keys in `.env`. It costs about $0.02. The same check runs nightly on `main`.

- **Commits.** Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`. Keep pull requests small.
- **Changelog.** Add user-visible changes to `CHANGELOG.md` under `[Unreleased]`.
- **Public API.** If you change a public name or signature, `tests/test_api.py` fails. If the change is on purpose, run `UPDATE_API=1 uv run pytest tests/test_api.py` and commit `tests/api.txt`. Renames and removals need a deprecation first; see [design/api.md](design/api.md).
- **Dependencies.** Runtime dependencies stay at none. Provider SDKs are optional extras.

## Updating provider facts

Prices, minimum cacheable tokens and TTLs live in `src/cachemaxxing/facts.py`, and every row links to its source.

1. Edit the row.
2. Bump `VERIFIED`.
3. Regenerate the docs table with `uv run python -m cachemaxxing.facts > docs/_facts.md`.
4. Add a changelog entry.

A test fails if the docs table is out of date.
