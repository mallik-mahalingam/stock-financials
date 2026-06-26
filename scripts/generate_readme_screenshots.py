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

COMPACT_ROWS: dict[str, list[str]] = {
    "income": [
        "Total Revenues",
        "Total Revenues %Chg",
        "Gross Profit",
        "Gross Profit Margin",
        "Operating Profit",
        "Operating Margin",
        "Consolidated Net Income",
        "Diluted EPS",
    ],
    "balance-sheet": [
        "Assets",
        "Cash and Cash Equivalents",
        "Total Current Assets",
        "Total Assets",
        "Liabilities",
        "Total Liabilities",
        "Total Shareholders' Equity",
    ],
    "cash-flow": [
        "Operating Activities",
        "Cash from Operating Activities",
        "Investing Activities",
        "Cash from Investing Activities",
        "Financing Activities",
        "Cash from Financing Activities",
        "Free Cash Flow",
        "Net Change in Cash",
    ],
}

README_QUARTERS = 6
README_VIEWPORT = (1440, 1020)

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8f9fb; color: #1a1a1a; max-width: 1680px;
}
body.readme { padding: 20px 24px 24px; }
h1 { font-size: 28px; margin: 0 0 4px; font-weight: 650; }
body.readme h1 { font-size: 24px; }
.sub { color: #5c6370; font-size: 14px; margin-bottom: 8px; }
body.readme .sub { font-size: 13px; margin-bottom: 6px; }
.fiscal { color: #5c6370; font-size: 12px; margin-bottom: 20px; }
body.readme .fiscal { display: none; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
body.readme .tabs { margin-bottom: 14px; }
.tab {
  padding: 8px 16px; border-radius: 999px; font-size: 13px; font-weight: 500;
  border: 1px solid #d8dde6; background: #fff; color: #444;
}
.tab.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
body.readme .stats { gap: 12px; margin-bottom: 16px; }
.stat {
  background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 14px 16px;
}
body.readme .stat { padding: 10px 12px; }
.stat .val { font-size: 22px; font-weight: 650; margin-bottom: 4px; }
body.readme .stat .val { font-size: 18px; }
.stat .lbl { font-size: 12px; color: #5c6370; line-height: 1.35; }
h2 { font-size: 18px; margin: 0 0 12px; }
body.readme h2 { font-size: 16px; margin-bottom: 8px; }
.hint { color: #5c6370; font-size: 12px; margin: -4px 0 10px; font-style: italic; }
.wrap { overflow-x: auto; border: 1px solid #e5e8ef; border-radius: 10px; background: #fff; }
table { border-collapse: collapse; min-width: 1280px; width: 100%; font-size: 12px; }
body.readme table { min-width: 900px; font-size: 11px; }
th, td { padding: 8px 10px; border-bottom: 1px solid #eef1f6; white-space: nowrap; }
body.readme th, body.readme td { padding: 6px 8px; }
th { background: #f3f5f9; text-align: right; font-weight: 600; color: #444; }
th:first-child, td:first-child { text-align: left; min-width: 260px; max-width: 320px; }
body.readme th:first-child, body.readme td:first-child { min-width: 220px; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:nth-child(even) td { background: #fafbfc; }
tr.total td { font-weight: 600; }
tr.section td { font-weight: 600; background: #f0f3f8; color: #333; }
tr.italic td { font-style: italic; color: #5c6370; }
.chart-box {
  margin-top: 24px; background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 16px;
}
body.readme .chart-box { margin-top: 16px; padding: 14px; }
.chart-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.legend { font-size: 12px; color: #5c6370; margin-bottom: 12px; }
.chart-stats { margin-top: 16px; font-size: 12px; }
.chart-stats table { min-width: 720px; }
body.readme svg { min-height: 260px; max-height: 300px; }
svg { width: 100%; height: auto; display: block; }
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


def quarter_labels(data: dict, limit: int | None = None) -> list[str]:
    qs = data["quarters"]
    if qs and isinstance(qs[0], dict):
        labels = [q["label"] for q in qs]
    else:
        labels = list(qs)
    return labels[:limit] if limit else labels


def iter_rows(data: dict) -> list[dict]:
    if data.get("sections"):
        out: list[dict] = []
        for sec in data["sections"]:
            out.extend(sec["rows"])
        return out
    return data["rows"]


def compact_rows(data: dict, active: str) -> list[dict]:
    wanted = COMPACT_ROWS[active]
    by_label = {r["label"]: r for r in iter_rows(data)}
    picked: list[dict] = []
    for lab in wanted:
        row = by_label.get(lab)
        if not row:
            continue
        if lab == "Free Cash Flow" and row.get("plottable") is False:
            for r in iter_rows(data):
                if r["label"] == lab and r.get("plottable") is not False:
                    row = r
                    break
        picked.append(row)
    return picked


def table_html(data: dict, active: str, *, readme: bool) -> str:
    limit = README_QUARTERS if readme else None
    quarters = quarter_labels(data, limit)
    rows = compact_rows(data, active) if readme else iter_rows(data)
    body = "\n".join(render_row(row, quarters) for row in rows)
    headers = "".join(f"<th>{html.escape(q)}</th>" for q in quarters)
    hint = (
        '<p class="hint">Sample rows — last 6 quarters shown. Live canvas has all line items × 12 quarters.</p>'
        if readme
        else ""
    )
    return f"""{hint}<div class="wrap"><table>
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


def simple_chart_svg(data: dict, labels: list[str], *, readme: bool) -> str:
    quarters = quarter_labels(data)
    series = []
    colors = ["#2563eb", "#ea580c", "#7c3aed", "#16a34a"]
    for i, (lab, vals) in enumerate(chart_rows(data, labels)):
        parsed = [parse_value(v) for v in reversed(vals)]
        series.append((lab, parsed, colors[i % len(colors)]))

    w, h = (1180, 300) if readme else (1180, 420)
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


def page_html(active: str, tab_label: str, data: dict, section_title: str, *, readme: bool) -> str:
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
    chart = simple_chart_svg(data, default[:2], readme=readme)

    subtitle = data.get("summary", {}).get("subtitle", "")
    fiscal = data.get("summary", {}).get("fiscalMapping", "")
    body_cls = "readme" if readme else ""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{body_cls}">
<h1>PANW — Financial Statements</h1>
<div class="sub">{html.escape(subtitle)}</div>
<div class="fiscal">{html.escape(fiscal[:120] + ("…" if len(fiscal) > 120 else ""))}</div>
<div class="tabs">{tabs_html}</div>
<div class="stats">{stats_html}</div>
<h2>{html.escape(section_title)}</h2>
{table_html(data, active, readme=readme)}
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
        content = page_html(key, tab_label, data, section_title, readme=True)
        path = PREVIEW_DIR / f"panw-{key}-readme.html"
        path.write_text(content)
        html_paths.append((key, path))

    w, h = README_VIEWPORT
    server = start_server()
    port = server.server_address[1]
    try:
        for key, path in html_paths:
            png = OUT_DIR / f"panw-{key}.png"
            rel = path.relative_to(REPO).as_posix()
            url = f"http://127.0.0.1:{port}/{rel}"
            subprocess.run(["playwright-cli", "open", url], check=True)
            subprocess.run(["playwright-cli", "resize", str(w), str(h)], check=True)
            time.sleep(0.75)
            subprocess.run(["playwright-cli", "screenshot", f"--filename={png}"], check=True)
            subprocess.run(["playwright-cli", "close"], check=True)
            print(f"Wrote {png} ({w}x{h} viewport)")
    finally:
        server.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
