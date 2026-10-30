"""results/*/*.json -> a Markdown table for the README and docs. Every number comes from the results files."""

import json
from pathlib import Path

from cachemaxxing.facts import MODELS

ROOT = Path(__file__).parent / "results"
ROWS = [
    ("chat", "claude-haiku-5-5"),
    ("chat", "gpt-6-luna"),
    ("chat", "gemini-3.8-flash"),
    ("chat", "claude-sonnet-5-5"),
    ("chat", "gpt-6.1-sol"),
    ("rag", "claude-haiku-5-5"),
    ("rag", "gpt-6-luna"),
    ("rag", "gemini-3.8-flash"),
    ("agent", "claude-haiku-5-5"),
    ("agent", "gpt-6-luna"),
]


def input_usd(arm: dict, model: str) -> float:
    """Estimated $ per conversation minus output tokens: the part caching changes. Output length varies with
    how long the model answers, not with caching, so leaving it in would hide or invent differences."""
    output = sum(r["output"] for r in arm["runs"]) / len(arm["runs"])
    return float(arm["est_usd"]["mean"]) - output * MODELS[model].output / 1e6


def cell(arm: dict | None, model: str) -> str:
    return "—" if arm is None else f"{arm['cached_pct']['mean']:g}% · ${input_usd(arm, model):.4f}"


def vs(base: dict | None, cmx: dict, model: str) -> str:
    if base is None or not input_usd(base, model):
        return "—"
    change = 1 - input_usd(cmx, model) / input_usd(base, model)
    return f"{change:.0%} cheaper" if change >= 0.005 else ("same" if change > -0.005 else f"{-change:.0%} dearer")


def main() -> str:
    lines = [
        "| Workload | Model | naive | clean + provider auto-caching | cachemaxxing | vs naive | vs clean |",
        "|---|---|---|---|---|---|---|",
    ]
    for workload, model in ROWS:
        path = ROOT / workload / f"{model}.json"
        if not path.exists():
            continue
        arms = json.loads(path.read_text())["arms"]
        n, c, x = arms.get("naive"), arms.get("clean"), arms["cachemaxxing"]
        lines.append(
            f"| {workload} | `{model}` | {cell(n, model)} | {cell(c, model)} | {cell(x, model)} "
            f"| {vs(n, x, model)} | {vs(c, x, model)} |"
        )
    note = (
        "Cells: cached share of input tokens · estimated input cost per conversation at list price "
        "(cache writes and explicit-cache storage included; output excluded, since answer length varies "
        "between runs regardless of caching)."
    )
    return "\n".join(lines) + "\n\n" + note + "\n"


if __name__ == "__main__":
    print(main(), end="")
