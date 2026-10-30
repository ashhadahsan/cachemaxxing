"""results/*.json -> docs/assets/benchmark.svg: cached-token % per provider, naive vs cachemaxxing (stdlib only)."""

import json
from pathlib import Path

ROOT = Path(__file__).parent
ORDER = ["anthropic", "openai", "gemini"]
NAMES = {"anthropic": "Anthropic", "openai": "OpenAI", "gemini": "Gemini"}
ARMS = [("naive", "--series-1"), ("cachemaxxing", "--series-2")]
W, H, LEFT, RIGHT, TOP, BOTTOM = 720, 400, 56, 24, 92, 76
STYLE = """
  .viz { --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
         --series-1:#2a78d6; --series-2:#eb6834; font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
  @media (prefers-color-scheme: dark) {
    .viz { --surface:#1a1a19; --ink:#f0efec; --ink-2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
           --series-1:#3987e5; --series-2:#d95926; }
  }
  .t { fill:var(--ink); } .t2 { fill:var(--ink-2); } .m { fill:var(--muted); } .n { font-variant-numeric:tabular-nums; }
"""


def bar(x: float, y: float, w: float, base: float, color: str, tip: str) -> str:
    r = min(4.0, (base - y) / 2, w / 2)  # rounded data-end, flat on the baseline
    d = f"M{x:.1f},{base:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}H{x + w - r:.1f}"
    d += f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{base:.1f}Z"
    return f'<path d="{d}" style="fill:var({color})"><title>{tip}</title></path>'


def main() -> Path:
    results = {
        p: json.loads((ROOT / "results" / f"{p}.json").read_text())
        for p in ORDER
        if (ROOT / "results" / f"{p}.json").exists()
    }
    plot_w, plot_h, base = W - LEFT - RIGHT, H - TOP - BOTTOM, H - BOTTOM
    group_w = plot_w / max(1, len(results))
    bar_w = min(64.0, group_w * 0.3)
    date = max((r["date"] for r in results.values()), default="")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="viz" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-labelledby="title desc">',
        f"<style>{STYLE}</style>",
        f'<rect width="{W}" height="{H}" rx="8" style="fill:var(--surface)"/>',
        '<title id="title">Cached input tokens per 8-turn chat: naive vs cachemaxxing</title>',
    ]
    desc = "; ".join(
        f"{NAMES[p]} {r['model']}: naive {r['arms']['naive']['cached_pct']['mean']}%, "
        f"cachemaxxing {r['arms']['cachemaxxing']['cached_pct']['mean']}%"
        for p, r in results.items()
    )
    out.append(f'<desc id="desc">{desc}</desc>')
    out.append(
        f'<text x="{LEFT}" y="30" class="t" font-size="16" font-weight="600">Cached input tokens per 8-turn chat</text>'
    )
    out.append(
        f'<text x="{LEFT}" y="50" class="t2" font-size="12">mean of 3 runs · cheapest caching model per provider '
        f"· est. $ at list price · {date}</text>"
    )
    for i, (arm, color) in enumerate(ARMS):  # legend: always present for 2 series
        lx = LEFT + i * 130
        out.append(f'<rect x="{lx}" y="64" width="10" height="10" rx="2" style="fill:var({color})"/>')
        out.append(f'<text x="{lx + 16}" y="73" class="t2" font-size="12">{arm}</text>')
    for pct in (0, 25, 50, 75, 100):  # recessive grid
        y = base - plot_h * pct / 100
        stroke = "--axis" if pct == 0 else "--grid"
        out.append(
            f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:var({stroke})" stroke-width="1"/>'
        )
        out.append(f'<text x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" class="m n" font-size="11">{pct}%</text>')
    for g, (p, r) in enumerate(results.items()):
        cx = LEFT + group_w * (g + 0.5)
        for j, (arm, color) in enumerate(ARMS):
            a = r["arms"][arm]
            pct, usd = a["cached_pct"]["mean"], a["est_usd"]["mean"]
            x = cx - bar_w - 1 + j * (bar_w + 2)  # 2px gap between adjacent bars
            y = base - plot_h * pct / 100
            tip = f"{NAMES[p]} · {arm}: {pct}% cached (runs {a['cached_pct']['min']}–{a['cached_pct']['max']}%), ~${usd:.4f}/run"
            out.append(bar(x, min(y, base - 1), bar_w, base, color, tip))
            out.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" class="t n" font-size="12">{pct:g}%</text>'
            )
        naive, cmx = r["arms"]["naive"]["est_usd"]["mean"], r["arms"]["cachemaxxing"]["est_usd"]["mean"]
        out.append(
            f'<text x="{cx:.1f}" y="{base + 22}" text-anchor="middle" class="t" font-size="13" font-weight="600">{NAMES[p]}</text>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{base + 39}" text-anchor="middle" class="t2" font-size="11">{r["model"]}</text>'
        )
        out.append(
            f'<text x="{cx:.1f}" y="{base + 56}" text-anchor="middle" class="t2 n" font-size="11">'
            f"${naive:.4f} → ${cmx:.4f} per run</text>"
        )
    out.append("</svg>")
    dest = ROOT.parent / "docs" / "assets" / "benchmark.svg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    return dest


if __name__ == "__main__":
    print(main())
