# Security policy

## Supported versions

Security fixes go into the latest minor release (for example 0.9.x, then 1.0.x). Upgrade to the latest patch release of that line to get them.

## Reporting a vulnerability

Please report privately through GitHub: [open a security advisory](https://github.com/ashhadahsan/cachemaxxing/security/advisories/new). Don't open a public issue.

Include the version, a minimal example and what an attacker could do with it. The fix ships as a patch release, with credit in the advisory unless you'd rather not be named.

## What to look at

cachemaxxing builds request arguments for your own SDK client and reads the replies. It has no runtime dependencies, and it never sends a request itself, except Gemini cache calls through the client you pass to `gemini_cache`. The most sensitive parts are:

- **The `report --html` page.** It embeds snippets of your prompts. It must not let prompt text run as script, and it must make no network requests.
- **`record()` logs.** With `redact=`, they must hold no prompt or output text, apart from model names, roles, block types and tool names.
- **The release pipeline.** Releases are built in GitHub Actions and published to PyPI with Trusted Publishing and attestations.
