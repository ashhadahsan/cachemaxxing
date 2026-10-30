"""results/{chat,rag}/*.json -> docs/assets/benchmark.svg: cached-token % per arm, provider and workload (stdlib only)."""

import json
from pathlib import Path

ROOT = Path(__file__).parent
MODELS = [("Anthropic", "claude-haiku-5-5"), ("OpenAI", "gpt-6-luna"), ("Gemini", "gemini-3.8-flash")]
PANELS = [("chat", "Chat: 8 turns"), ("rag", "RAG: 8 turns, fresh chunks every turn")]
ARMS = [
    ("naive", "s1", "naive"),
    ("clean", "s3", "clean + provider auto-caching"),
    ("cachemaxxing", "s2", "cachemaxxing"),
]
W, LEFT, RIGHT, TOP, PANEL_H, GAP = 760, 56, 24, 96, 210, 70
STYLE = """
  .viz { font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
  .bg { fill:#fcfcfb; } .t { fill:#0b0b0b; } .t2 { fill:#52514e; } .m { fill:#898781; }
  .grid { stroke:#e1e0d9; } .axis { stroke:#c3c2b7; }
  .s1 { fill:#2a78d6; } .s2 { fill:#eb6834; } .s3 { fill:#1baf7a; }
  .n { font-variant-numeric:tabular-nums; }
  @media (prefers-color-scheme: dark) {
    .bg { fill:#1a1a19; } .t { fill:#f0efec; } .t2 { fill:#c3c2b7; }
    .grid { stroke:#2c2c2a; } .axis { stroke:#383835; }
    .s1 { fill:#3987e5; } .s2 { fill:#d95926; } .s3 { fill:#199e70; }
  }
"""


def bar(x: float, y: float, w: float, base: float, cls: str, tip: str) -> str:
    r = min(4.0, (base - y) / 2, w / 2)  # rounded data-end, flat on the baseline
    d = f"M{x:.1f},{base:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}H{x + w - r:.1f}"
    d += f"Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{base:.1f}Z"
    return f'<path d="{d}" class="{cls}"><title>{tip}</title></path>'


def main() -> Path:
    height = TOP + len(PANELS) * (PANEL_H + GAP) - GAP + 36
    plot_w = W - LEFT - RIGHT
    group_w = plot_w / len(MODELS)
    bar_w = min(44.0, group_w * 0.22)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="viz" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" aria-labelledby="title desc">',
        f"<style>{STYLE}</style>",
        f'<rect width="{W}" height="{height}" rx="8" class="bg"/>',
        '<title id="title">Cached input tokens: naive vs clean prompt with provider auto-caching vs cachemaxxing</title>',
    ]
    desc, dates = [], set()
    out.append(
        f'<text x="{LEFT}" y="30" class="t" font-size="16" font-weight="600">Cached input tokens per conversation</text>'
    )
    sub = "mean of 3 conversations per arm, each benchmark starting cold · cheapest caching model per provider"
    out.append(f'<text x="{LEFT}" y="50" class="t2" font-size="12">{sub}</text>')
    for i, (_, cls, label) in enumerate(ARMS):  # legend: always present for several series
        lx = LEFT + [0, 90, 310][i]
        out.append(f'<rect x="{lx}" y="64" width="10" height="10" rx="2" class="{cls}"/>')
        out.append(f'<text x="{lx + 16}" y="73" class="t2" font-size="12">{label}</text>')
    for pi, (workload, title) in enumerate(PANELS):
        top = TOP + pi * (PANEL_H + GAP) + 26
        base = top + PANEL_H - 40
        plot_h = base - top
        out.append(f'<text x="{LEFT}" y="{top - 10}" class="t" font-size="13" font-weight="600">{title}</text>')
        for pct in (0, 50, 100):
            y = base - plot_h * pct / 100
            cls = "axis" if pct == 0 else "grid"
            out.append(f'<line x1="{LEFT}" x2="{W - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" class="{cls}" stroke-width="1"/>')
            out.append(
                f'<text x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" class="m n" font-size="11">{pct}%</text>'
            )
        for g, (name, model) in enumerate(MODELS):
            path = ROOT / "results" / workload / f"{model}.json"
            if not path.exists():
                continue
            r = json.loads(path.read_text())
            dates.add(r["date"])
            cx = LEFT + group_w * (g + 0.5)
            for j, (arm, cls, label) in enumerate(ARMS):
                a = r["arms"].get(arm)
                if a is None:
                    continue
                pct, usd = a["cached_pct"]["mean"], a["est_usd"]["mean"]
                x = cx - 1.5 * bar_w - 2 + j * (bar_w + 2)  # 2px gap between adjacent bars
                y = base - plot_h * pct / 100
                tip = f"{name} · {workload} · {label}: {pct}% cached, ~${usd:.4f} per conversation"
                out.append(bar(x, min(y, base - 1), bar_w, base, cls, tip))
                out.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" class="t n" font-size="11">{pct:g}%</text>'
                )
                desc.append(f"{workload} {name} {label} {pct}%")
            out.append(
                f'<text x="{cx:.1f}" y="{base + 18}" text-anchor="middle" class="t" font-size="12" font-weight="600">{name}</text>'
            )
            out.append(
                f'<text x="{cx:.1f}" y="{base + 33}" text-anchor="middle" class="t2" font-size="11">{model}</text>'
            )
    out.insert(4, f'<desc id="desc">{"; ".join(desc)}. Run {", ".join(sorted(dates))}.</desc>')
    out.append("</svg>")
    dest = ROOT.parent / "docs" / "assets" / "benchmark.svg"
    dest.write_text("\n".join(out) + "\n")
    return dest


if __name__ == "__main__":
    print(main())
