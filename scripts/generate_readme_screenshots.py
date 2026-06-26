#!/usr/bin/env python3
"""Generate chart PNG screenshots for README (tables stay as markdown)."""

from __future__ import annotations

import html
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

REPO = Path(__file__).resolve().parent.parent
JSON_DIR = REPO / "json-data"
OUT_DIR = REPO / "docs" / "screenshots"
PREVIEW_DIR = REPO / "docs" / "preview"

TABS = [
    ("income", "Income", "PANW-income.json"),
    ("balance-sheet", "Balance Sheet", "PANW-balance-sheet.json"),
    ("cash-flow", "Cash Flow", "PANW-cash-flow.json"),
]

README_CHART_VIEWPORT = (1200, 360)

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 16px 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8f9fb; color: #1a1a1a;
}
.tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.tab {
  padding: 8px 16px; border-radius: 999px; font-size: 13px; font-weight: 500;
  border: 1px solid #d8dde6; background: #fff; color: #444;
}
.tab.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.chart-box {
  background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 14px 16px;
}
.chart-title { font-size: 16px; font-weight: 600; margin-bottom: 10px; }
.legend { font-size: 12px; color: #5c6370; margin-bottom: 10px; }
.wrap { overflow-x: auto; border: 1px solid #eef1f6; border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { padding: 7px 10px; border-bottom: 1px solid #eef1f6; }
th { background: #f3f5f9; text-align: left; font-weight: 600; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.chart-stats { margin-top: 14px; }
svg { width: 100%; height: auto; display: block; }
"""


def load_json(name: str) -> dict:
    return json.loads((JSON_DIR / name).read_text())


def quarter_labels(data: dict) -> list[str]:
    qs = data["quarters"]
    if qs and isinstance(qs[0], dict):
        return [q["label"] for q in qs]
    return list(qs)


def iter_rows(data: dict) -> list[dict]:
    if data.get("sections"):
        out: list[dict] = []
        for sec in data["sections"]:
            out.extend(sec["rows"])
        return out
    return data["rows"]


def parse_value(raw: str) -> float | None:
    s = raw.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("%", "").replace("*", "").replace("+", "")
    if not s or s == "—":
        return None
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def chart_rows(data: dict, labels: list[str]) -> list[tuple[str, list[str]]]:
    seen: set[str] = set()
    picked: list[tuple[str, list[str]]] = []
    for row in iter_rows(data):
        lab = row["label"]
        if lab in labels and lab not in seen and row.get("plottable") is not False:
            seen.add(lab)
            picked.append((lab, row["values"]))
    for lab in labels:
        if lab not in seen:
            for row in iter_rows(data):
                if row["label"] == lab and row.get("plottable") is not False:
                    picked.append((lab, row["values"]))
                    break
    return picked


def chart_html(data: dict, labels: list[str]) -> str:
    quarters = quarter_labels(data)
    series = []
    colors = ["#2563eb", "#ea580c", "#7c3aed", "#16a34a"]
    for i, (lab, vals) in enumerate(chart_rows(data, labels)):
        parsed = [parse_value(v) for v in reversed(vals)]
        series.append((lab, parsed, colors[i % len(colors)]))

    w, h = 1180, 220
    m = dict(l=72, r=28, t=20, b=36)
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    allv = [v for _, pts, _ in series for v in pts if v is not None]
    if not allv:
        return "<p>No chart data</p>"
    vmin, vmax = min(0, min(allv)), max(0, max(allv))
    if vmin == vmax:
        vmax += 1
    n = len(quarters)

    def x(i):
        return m["l"] + (iw / n) * (i + 0.5)

    def y(v):
        return m["t"] + ih * (1 - (v - vmin) / (vmax - vmin))

    grid = "".join(
        f'<line x1="{m["l"]}" y1="{m["t"] + ih * (1 - t / 4)}" x2="{w-m["r"]}" y2="{m["t"] + ih * (1 - t / 4)}" stroke="#e5e8ef"/>'
        for t in range(5)
    )
    cats = "".join(
        f'<text x="{x(i)}" y="{h-6}" text-anchor="middle" font-size="10" fill="#5c6370">{html.escape(q)}</text>'
        for i, q in enumerate(reversed(quarters))
    )
    paths = []
    legend = []
    for lab, pts, col in series:
        coords = [f"{x(i)},{y(v)}" for i, v in enumerate(pts) if v is not None]
        if coords:
            paths.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.5" points="{" ".join(coords)}"/>')
        legend.append(f'<span style="color:{col};font-weight:600">{html.escape(lab)}</span>')

    stats_rows = ""
    for (lab, vals), (_, pts, col) in zip(chart_rows(data, labels), series, strict=False):
        nums = [v for v in pts if v is not None]
        latest = html.escape(vals[0] if vals else "—")
        chg_s = f"{((nums[-1] - nums[0]) / abs(nums[0])) * 100:+.1f}%" if len(nums) >= 2 and nums[0] != 0 else "—"
        stats_rows += (
            f"<tr><td><span style='color:{col}'>●</span> {html.escape(lab)}</td>"
            f"<td class='num'>{latest}</td><td class='num'>{chg_s}</td></tr>"
        )

    return f"""<div class="chart-box">
<div class="chart-title">Chart</div>
<div class="legend">{' · '.join(legend)}</div>
<svg viewBox="0 0 {w} {h}">{grid}{cats}{''.join(paths)}</svg>
<div class="chart-stats"><div class="wrap"><table>
<thead><tr><th>Selected metric</th><th>Latest</th><th>Total Change</th></tr></thead>
<tbody>{stats_rows}</tbody></table></div></div></div>"""


def tabs_html(active: str) -> str:
    return "".join(
        f'<div class="{"tab active" if key == active else "tab"}">{html.escape(label)}</div>'
        for key, label, _ in TABS
    )


def page_html(active: str, data: dict) -> str:
    default = data.get("summary", {}).get("defaultChartRows") or ["Total Revenues"]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
<div class="tabs">{tabs_html(active)}</div>
{chart_html(data, default[:2])}
</body></html>"""


def start_server(port: int = 8765) -> ThreadingHTTPServer:
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(REPO), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    return server


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    server = start_server()
    port = server.server_address[1]
    w, h = README_CHART_VIEWPORT
    try:
        for key, _, json_name in TABS:
            data = load_json(json_name)
            html_path = PREVIEW_DIR / f"panw-{key}-chart.html"
            html_path.write_text(page_html(key, data))
            png = OUT_DIR / f"panw-{key}-chart.png"
            url = f"http://127.0.0.1:{port}/{html_path.relative_to(REPO).as_posix()}"
            subprocess.run(["playwright-cli", "open", url], check=True)
            subprocess.run(["playwright-cli", "resize", str(w), str(h)], check=True)
            time.sleep(0.75)
            subprocess.run(["playwright-cli", "screenshot", f"--filename={png}"], check=True)
            subprocess.run(["playwright-cli", "close"], check=True)
            print(f"Wrote {png}")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
