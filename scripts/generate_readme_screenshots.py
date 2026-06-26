#!/usr/bin/env python3
"""Generate canvas-style HTML previews and PNG screenshots for README."""

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
    ("income", "Income", "PANW-income.json", "Income Statement"),
    ("balance-sheet", "Balance Sheet", "PANW-balance-sheet.json", "Balance Sheet"),
    ("cash-flow", "Cash Flow", "PANW-cash-flow.json", "Cash Flow Statement"),
]

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8f9fb; color: #1a1a1a; max-width: 1680px;
}
h1 { font-size: 28px; margin: 0 0 4px; font-weight: 650; }
.sub { color: #5c6370; font-size: 14px; margin-bottom: 8px; }
.fiscal { color: #5c6370; font-size: 12px; margin-bottom: 20px; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  padding: 8px 16px; border-radius: 999px; font-size: 13px; font-weight: 500;
  border: 1px solid #d8dde6; background: #fff; color: #444;
}
.tab.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat {
  background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 14px 16px;
}
.stat .val { font-size: 22px; font-weight: 650; margin-bottom: 4px; }
.stat .lbl { font-size: 12px; color: #5c6370; line-height: 1.35; }
h2 { font-size: 18px; margin: 0 0 12px; }
.wrap { overflow-x: auto; border: 1px solid #e5e8ef; border-radius: 10px; background: #fff; }
table { border-collapse: collapse; min-width: 1280px; width: 100%; font-size: 12px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #eef1f6; white-space: nowrap; }
th { background: #f3f5f9; text-align: right; font-weight: 600; color: #444; position: sticky; top: 0; }
th:first-child, td:first-child { text-align: left; min-width: 260px; max-width: 320px; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:nth-child(even) td { background: #fafbfc; }
tr.total td { font-weight: 600; }
tr.section td { font-weight: 600; background: #f0f3f8; color: #333; }
tr.italic td { font-style: italic; color: #5c6370; }
.chart-box {
  margin-top: 24px; background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 16px;
  page-break-inside: avoid;
}
.chart-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.legend { font-size: 12px; color: #5c6370; margin-bottom: 12px; }
.chart-stats { margin-top: 16px; font-size: 12px; }
.chart-stats table { min-width: 720px; }
svg { width: 100%; height: auto; display: block; min-height: 320px; }
"""


def load_json(name: str) -> dict:
    return json.loads((JSON_DIR / name).read_text())


def row_class(row: dict) -> str:
    if row.get("plottable") is False and row.get("kind") == "total":
        return "section"
    if row.get("kind") == "total":
        return "total"
    if row.get("kind") == "italic":
        return "italic"
    return ""


def quarter_labels(data: dict) -> list[str]:
    qs = data["quarters"]
    if qs and isinstance(qs[0], dict):
        return [q["label"] for q in qs]
    return list(qs)


def table_html(data: dict) -> str:
    quarters = quarter_labels(data)
    rows = data.get("sections")
    if rows:
        body_parts = []
        for sec in data["sections"]:
            for row in sec["rows"]:
                body_parts.append(render_row(row, quarters))
        body = "\n".join(body_parts)
    else:
        body = "\n".join(render_row(r, quarters) for r in data["rows"])
    headers = "".join(f"<th>{html.escape(q)}</th>" for q in quarters)
    return f"""<div class="wrap"><table>
<thead><tr><th>Line item</th>{headers}</tr></thead>
<tbody>{body}</tbody></table></div>"""


def render_row(row: dict, quarters: list[str]) -> str:
    cls = row_class(row)
    cells = "".join(f'<td class="num">{html.escape(v or "—")}</td>' for v in row["values"][: len(quarters)])
    return f'<tr class="{cls}"><td>{html.escape(row["label"])}</td>{cells}</tr>'


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
    for row in data["rows"]:
        lab = row["label"]
        if lab in labels and lab not in seen and row.get("plottable") is not False:
            seen.add(lab)
            picked.append((lab, row["values"]))
    for lab in labels:
        if lab not in seen:
            for row in data["rows"]:
                if row["label"] == lab and row.get("plottable") is not False:
                    picked.append((lab, row["values"]))
                    break
    return picked


def simple_chart_svg(data: dict, labels: list[str]) -> str:
    quarters = quarter_labels(data)
    series = []
    colors = ["#2563eb", "#ea580c", "#7c3aed", "#16a34a"]
    for i, (lab, vals) in enumerate(chart_rows(data, labels)):
        parsed = [parse_value(v) for v in reversed(vals)]
        series.append((lab, parsed, colors[i % len(colors)]))

    w, h = 1180, 420
    m = dict(l=72, r=28, t=24, b=40)
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    allv = [v for _, pts, _ in series for v in pts if v is not None]
    if not allv:
        return "<p class='legend'>Chart preview</p>"
    vmin, vmax = min(0, min(allv)), max(0, max(allv))
    if vmin == vmax:
        vmax += 1
    n = len(quarters)

    def x(i):
        return m["l"] + (iw / n) * (i + 0.5)

    def y(v):
        return m["t"] + ih * (1 - (v - vmin) / (vmax - vmin))

    lines = []
    for t in range(5):
        yy = m["t"] + ih * (1 - t / 4)
        lines.append(f'<line x1="{m["l"]}" y1="{yy}" x2="{w-m["r"]}" y2="{yy}" stroke="#e5e8ef"/>')

    cats = "".join(
        f'<text x="{x(i)}" y="{h-8}" text-anchor="middle" font-size="11" fill="#5c6370">{html.escape(q)}</text>'
        for i, q in enumerate(reversed(quarters))
    )
    paths = []
    legend = []
    for lab, pts, col in series:
        coords = []
        for i, v in enumerate(pts):
            if v is None:
                continue
            coords.append(f"{x(i)},{y(v)}")
        if coords:
            paths.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{" ".join(coords)}"/>')
        legend.append(f'<span style="color:{col};font-weight:600">{html.escape(lab)}</span>')

    stats_rows = ""
    for (lab, vals), (_, pts, col) in zip(chart_rows(data, labels), series, strict=False):
        nums = [v for v in pts if v is not None]
        latest = html.escape(vals[0] if vals else "—")
        if len(nums) >= 2 and nums[0] != 0:
            chg_s = f"{((nums[-1] - nums[0]) / abs(nums[0])) * 100:+.1f}%"
        else:
            chg_s = "—"
        stats_rows += (
            f"<tr><td><span style='color:{col}'>●</span> {html.escape(lab)}</td>"
            f"<td class='num'>{latest}</td><td class='num'>{chg_s}</td></tr>"
        )

    return f"""<div class="chart-box"><div class="chart-title">Chart</div>
<div class="legend">{' · '.join(legend)}</div>
<svg viewBox="0 0 {w} {h}">{''.join(lines)}{cats}{''.join(paths)}</svg>
<div class="chart-stats"><div class="wrap"><table>
<thead><tr><th>Selected metric</th><th>Latest</th><th>Total Change</th></tr></thead>
<tbody>{stats_rows}</tbody></table></div></div></div>"""


def page_html(active: str, tab_label: str, data: dict, section_title: str) -> str:
    stats = data.get("summary", {}).get("stats", [])
    stats_html = "".join(
        f'<div class="stat"><div class="val">{html.escape(s["value"])}</div>'
        f'<div class="lbl">{html.escape(s["label"])}</div></div>'
        for s in stats[:4]
    )
    tabs_html = ""
    for key, label, _, _ in TABS:
        cls = "tab active" if key == active else "tab"
        tabs_html += f'<div class="{cls}">{html.escape(label)}</div>'

    default = data.get("summary", {}).get("defaultChartRows") or ["Total Revenues"]
    chart = simple_chart_svg(data, default[:2])

    subtitle = data.get("summary", {}).get("subtitle", "")
    fiscal = data.get("summary", {}).get("fiscalMapping", "")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>PANW — Financial Statements</h1>
<div class="sub">{html.escape(subtitle)}</div>
<div class="fiscal">{html.escape(fiscal[:120] + ("…" if len(fiscal) > 120 else ""))}</div>
<div class="tabs">{tabs_html}</div>
<div class="stats">{stats_html}</div>
<h2>{html.escape(section_title)}</h2>
{table_html(data)}
{chart}
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

    html_paths = []
    for key, tab_label, json_name, section_title in TABS:
        data = load_json(json_name)
        content = page_html(key, tab_label, data, section_title)
        path = PREVIEW_DIR / f"panw-{key}.html"
        path.write_text(content)
        html_paths.append((key, path))

    server = start_server()
    port = server.server_address[1]
    try:
        for key, path in html_paths:
            png = OUT_DIR / f"panw-{key}.png"
            rel = path.relative_to(REPO).as_posix()
            url = f"http://127.0.0.1:{port}/{rel}"
            subprocess.run(["playwright-cli", "open", url], check=True)
            subprocess.run(["playwright-cli", "resize", "1440", "900"], check=True)
            time.sleep(0.75)
            subprocess.run(
                ["playwright-cli", "screenshot", f"--filename={png}", "--full-page"],
                check=True,
            )
            subprocess.run(["playwright-cli", "close"], check=True)
            print(f"Wrote {png}")
    finally:
        server.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
