"""October 2026 calendar strip of the shape-measurement production run.

Reads the production page's tile_history.json (processed_at per tile, 0.25 deg² per tile)
and writes images/run_calendar.svg: one column per October day, a bar for the area whose
shapes finished that day, day numbers underneath. Text is drawn in the deck's font so the
SVG matches the slides.

    python3 figures/run_calendar.py [tile_history.json]
"""
import collections
import json
import pathlib
import sys
import urllib.request

SRC = "https://unions-wl.github.io/production/tile_history.json"
OUT = pathlib.Path(__file__).resolve().parent.parent / "images" / "run_calendar.svg"
TILE_DEG2 = 0.25
W, H = 560, 150
X0, X1 = 6, W - 6
BASE, TOP = 92, 6            # bar baseline and top (px)
BAR = "#c0582b"              # theme accent
INK, SOFT, RULE = "#1a1a1a", "#6b6b6b", "#d9d4cc"

rows = json.load(open(sys.argv[1]) if len(sys.argv) > 1 else urllib.request.urlopen(SRC))["rows"]
per_day = collections.Counter(int(r[3][8:10]) for r in rows if r[3] and r[3].startswith("2026-10"))
deg2 = {d: n * TILE_DEG2 for d, n in per_day.items()}
first, last, peak = min(deg2), max(deg2), max(deg2.values())
cw = (X1 - X0) / 31

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
       f'font-family="EB Garamond, Garamond, serif">']
svg.append(f'<line x1="{X0}" y1="{BASE}" x2="{X1}" y2="{BASE}" stroke="{RULE}" stroke-width="1.5"/>')
for d in range(1, 32):
    x = X0 + (d - 1) * cw
    if d in deg2:
        h = (BASE - TOP) * deg2[d] / peak
        svg.append(f'<rect x="{x + 1.5:.1f}" y="{BASE - h:.1f}" width="{cw - 3:.1f}" height="{h:.1f}" fill="{BAR}" rx="1.5"/>')
    run = first <= d <= last
    weight = ' font-weight="600"' if d in (first, last) else ""
    svg.append(f'<text x="{x + cw / 2:.1f}" y="{BASE + 20}" text-anchor="middle" font-size="15" '
               f'fill="{INK if run else SOFT}"{weight}>{d}</text>')
xa, xb = X0 + (first - 1) * cw + 2, X0 + last * cw - 2
svg.append(f'<path d="M{xa:.1f} {BASE + 28} v6 H{xb:.1f} v-6" fill="none" stroke="{INK}" stroke-width="1.2"/>')
svg.append(f'<text x="{(xa + xb) / 2:.1f}" y="{H - 4}" text-anchor="middle" font-size="17" fill="{INK}">'
           f'{last - first + 1} days in October 2026</text>')
svg.append("</svg>")
OUT.write_text("\n".join(svg))
print(OUT, {d: deg2[d] for d in sorted(deg2)}, "total", sum(deg2.values()))
