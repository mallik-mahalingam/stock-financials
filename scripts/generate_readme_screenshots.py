#!/usr/bin/env python3
"""Generate README preview PNGs: canvas-style table + chart in one short wide image."""

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

PREVIEW_ROWS: dict[str, list[str]] = {
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
        "Cash and Cash Equivalents",
        "Total Current Assets",
        "Total Assets",
        "Total Liabilities",
        "Total Shareholders' Equity",
    ],
    "cash-flow": [
        "Cash from Operating Activities",
        "Capital Expenditure",
        "Free Cash Flow",
        "Cash from Investing Activities",
        "Cash from Financing Activities",
        "Net Change in Cash",
    ],
}

QUARTERS_SHOWN = 6
VIEWPORT = (1280, 480)

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 18px 22px 16px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f4f6fa; color: #111;
}
.top { margin-bottom: 14px; }
h1 { font-size: 22px; margin: 0 0 4px; font-weight: 650; }
.sub { font-size: 12px; color: #5c6370; }
.tabs { display: flex; gap: 8px; margin: 12px 0; }
.tab {
  padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 600;
  border: 1px solid #d8dde6; background: #fff; color: #444;
}
.tab.on { background: #2563eb; color: #fff; border-color: #2563eb; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
.stat { background: #fff; border: 1px solid #e5e8ef; border-radius: 8px; padding: 8px 10px; }
.stat b { display: block; font-size: 17px; margin-bottom: 2px; }
.stat span { font-size: 10px; color: #5c6370; line-height: 1.3; }
.grid { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 14px; align-items: start; }
.panel { background: #fff; border: 1px solid #e5e8ef; border-radius: 10px; padding: 12px; }
.panel h2 { font-size: 14px; margin: 0 0 8px; }
.hint { font-size: 10px; color: #6b7280; margin: 0 0 8px; font-style: italic; }
table { border-collapse: collapse; width: 100%; font-size: 11px; }
th, td { padding: 5px 7px; border-bottom: 1px solid #eef1f6; white-space: nowrap; }
th { background: #f3f5f9; text-align: right; font-weight: 600; color: #444; }
th:first-child, td:first-child { text-align: left; min-width: 150px; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
tr:nth-child(even) td { background: #fafbfc; }
tr.tot td { font-weight: 600; }
tr.it td { font-style: italic; color: #5c6370; }
.chart-title { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
.legend { font-size: 11px; color: #5c6370; margin-bottom: 8px; }
svg { width: 100%; height: auto; display: block; }
.mini { margin-top: 10px; font-size: 10px; }
.mini td, .mini th { padding: 4px 6px; }
"""


def load_json(name: str) -> dict:
    return json.loads((JSON_DIR / name).read_text())


def quarter_labels(data: dict, n: int | None = None) -> list[str]:
    qs = data["quarters"]
    labels = [q["label"] for q in qs] if qs and isinstance(qs[0], dict) else list(qs)
    return labels[:n] if n else labels


def all_rows(data: dict) -> list[dict]:
    if data.get("sections"):
        rows: list[dict] = []
        for sec in data["sections"]:
            rows.extend(sec["rows"])
        return rows
    return data["rows"]


def pick_rows(data: dict, active: str) -> list[dict]:
    by = {r["label"]: r for r in all_rows(data)}
    out: list[dict] = []
    for lab in PREVIEW_ROWS[active]:
        row = by.get(lab)
        if not row and lab == "Free Cash Flow":
            row = next((r for r in all_rows(data) if r["label"] == lab and r.get("plottable") is not False), None)
        if row:
            out.append(row)
    return out


def row_cls(row: dict) -> str:
    if row.get("kind") == "total":
        return "tot"
    if row.get("kind") == "italic":
        return "it"
    return ""


def table_block(data: dict, active: str, title: str) -> str:
    qs = quarter_labels(data, QUARTERS_SHOWN)
    hdr = "".join(f"<th>{html.escape(q)}</th>" for q in qs)
    body = ""
    for row in pick_rows(data, active):
        cells = "".join(f'<td class="n">{html.escape(v)}</td>' for v in row["values"][:QUARTERS_SHOWN])
        body += f'<tr class="{row_cls(row)}"><td>{html.escape(row["label"])}</td>{cells}</tr>'
    return f"""<div class="panel">
<h2>{html.escape(title)}</h2>
<p class="hint">Preview — live canvas has every line item × 12 quarters</p>
<table><thead><tr><th>Line item</th>{hdr}</tr></thead><tbody>{body}</tbody></table>
</div>"""


def parse_num(raw: str) -> float | None:
    s = raw.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("%", "").replace("*", "").replace("+", "")
    if not s or s == "—":
        return None
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def chart_series(data: dict, labels: list[str]) -> list[tuple[str, list[float | None], str]]:
    colors = ["#2563eb", "#ea580c"]
    seen: set[str] = set()
    out: list[tuple[str, list[float | None], str]] = []
    for i, lab in enumerate(labels):
        for row in all_rows(data):
            if row["label"] == lab and lab not in seen and row.get("plottable") is not False:
                seen.add(lab)
                pts = [parse_num(v) for v in reversed(row["values"])]
                out.append((lab, pts, colors[i % 2]))
                break
    return out


def chart_block(data: dict) -> str:
    labels = (data.get("summary") or {}).get("defaultChartRows") or ["Total Revenues"]
    labels = labels[:2]
    series = chart_series(data, labels)
    quarters = quarter_labels(data)
    w, h = 520, 190
    m = dict(l=44, r=12, t=16, b=28)
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    vals = [v for _, pts, _ in series for v in pts if v is not None]
    if not vals:
        return '<div class="panel"><p>No chart</p></div>'
    lo, hi = min(0, min(vals)), max(0, max(vals))
    if lo == hi:
        hi += 1
    n = len(quarters)

    def px(i: int) -> float:
        return m["l"] + (iw / n) * (i + 0.5)

    def py(v: float) -> float:
        return m["t"] + ih * (1 - (v - lo) / (hi - lo))

    grid = "".join(
        f'<line x1="{m["l"]}" y1="{m["t"] + ih * (1 - t / 4)}" x2="{w - m["r"]}" y2="{m["t"] + ih * (1 - t / 4)}" stroke="#e8ebf0"/>'
        for t in range(5)
    )
    cats = "".join(
        f'<text x="{px(i)}" y="{h - 6}" text-anchor="middle" font-size="8" fill="#6b7280">{html.escape(q)}</text>'
        for i, q in enumerate(reversed(quarters))
    )
    lines = []
    leg = []
    mini = ""
    for lab, pts, col in series:
        coords = [f"{px(i)},{py(v)}" for i, v in enumerate(pts) if v is not None]
        if coords:
            lines.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{" ".join(coords)}"/>')
        leg.append(f'<span style="color:{col};font-weight:600">{html.escape(lab)}</span>')
        nums = [v for v in pts if v is not None]
        chg = f"{((nums[-1] - nums[0]) / abs(nums[0])) * 100:+.1f}%" if len(nums) >= 2 and nums[0] else "—"
        row = all_rows(data)
        latest = next((r["values"][0] for r in row if r["label"] == lab and r.get("plottable") is not False), "—")
        mini += f"<tr><td style='color:{col}'>● {html.escape(lab)}</td><td class='n'>{html.escape(latest)}</td><td class='n'>{chg}</td></tr>"

    return f"""<div class="panel">
<div class="chart-title">Chart</div>
<div class="legend">{' · '.join(leg)}</div>
<svg viewBox="0 0 {w} {h}">{grid}{cats}{''.join(lines)}</svg>
<table class="mini"><thead><tr><th>Metric</th><th>Latest</th><th>Change</th></tr></thead><tbody>{mini}</tbody></table>
</div>"""


def page(active: str, data: dict, title: str) -> str:
    stats = (data.get("summary") or {}).get("stats") or []
    stats_html = "".join(
        f'<div class="stat"><b>{html.escape(s["value"])}</b><span>{html.escape(s["label"])}</span></div>'
        for s in stats[:4]
    )
    tabs = "".join(
        f'<div class="tab{" on" if k == active else ""}">{html.escape(lbl)}</div>' for k, lbl, _, _ in TABS
    )
    sub = (data.get("summary") or {}).get("subtitle") or ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="top">
<h1>PANW — Financial Statements</h1>
<div class="sub">{html.escape(sub)}</div>
<div class="tabs">{tabs}</div>
<div class="stats">{stats_html}</div>
</div>
<div class="grid">
{table_block(data, active, title)}
{chart_block(data)}
</div>
</body></html>"""


def start_server() -> ThreadingHTTPServer:
    handler = lambda *a, **k: SimpleHTTPRequestHandler(*a, directory=str(REPO), **k)  # noqa: E731
    srv = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    Thread(target=srv.serve_forever, daemon=True).start()
    for _ in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:8765/", timeout=1)
            return srv
        except Exception:
            time.sleep(0.1)
    return srv


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    srv = start_server()
    w, h = VIEWPORT
    try:
        for key, _, json_name, title in TABS:
            data = load_json(json_name)
            html_path = PREVIEW_DIR / f"panw-{key}.html"
            html_path.write_text(page(key, data, title))
            png = OUT_DIR / f"panw-{key}.png"
            url = f"http://127.0.0.1:8765/{html_path.relative_to(REPO).as_posix()}"
            subprocess.run(["playwright-cli", "open", url], check=True)
            subprocess.run(["playwright-cli", "resize", str(w), str(h)], check=True)
            time.sleep(0.6)
            subprocess.run(["playwright-cli", "screenshot", f"--filename={png}"], check=True)
            subprocess.run(["playwright-cli", "close"], check=True)
            print(f"Wrote {png}")
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
