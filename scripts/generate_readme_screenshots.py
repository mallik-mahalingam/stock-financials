#!/usr/bin/env python3
"""Generate full-fidelity README screenshot(s) from SEC JSON.

Currently: PANW income statement only (all rows × 12 quarters + chart).
"""

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

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px; max-width: 1680px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #fff; color: #111;
}
h1 { font-size: 28px; font-weight: 650; margin: 0 0 6px; }
.sub { color: #5c6370; font-size: 14px; margin-bottom: 4px; }
.fiscal { color: #5c6370; font-size: 12px; margin-bottom: 18px; line-height: 1.45; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  padding: 8px 16px; border-radius: 999px; font-size: 13px; font-weight: 600;
  border: 1px solid #d8dde6; background: #fff; color: #444;
}
.tab.on { background: #2563eb; border-color: #2563eb; color: #fff; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 22px; }
.stat {
  border: 1px solid #e5e8ef; border-radius: 10px; padding: 14px 16px; background: #fff;
}
.stat b { display: block; font-size: 22px; font-weight: 650; margin-bottom: 4px; }
.stat span { font-size: 12px; color: #5c6370; line-height: 1.35; }
h2 { font-size: 18px; margin: 0 0 12px; font-weight: 650; }
.table-wrap {
  overflow: visible; border: 1px solid #e5e8ef; border-radius: 10px; background: #fff;
}
table.fin { border-collapse: collapse; min-width: 1320px; width: 100%; font-size: 12px; }
table.fin th, table.fin td {
  padding: 8px 10px; border-bottom: 1px solid #eef1f6; vertical-align: middle;
}
table.fin th { background: #f3f5f9; font-weight: 600; color: #444; text-align: right; }
table.fin th.line, table.fin td.line { text-align: left; min-width: 280px; max-width: 340px; }
table.fin td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.fin tr:nth-child(even) td { background: #fafbfc; }
table.fin tr.total td { font-weight: 600; }
table.fin tr.italic td { font-style: italic; color: #5c6370; }
.cb {
  display: inline-block; width: 14px; height: 14px; border: 1.5px solid #9aa3b2;
  border-radius: 3px; margin-right: 8px; vertical-align: -2px; position: relative;
}
.cb.on { background: #2563eb; border-color: #2563eb; }
.cb.on::after {
  content: ""; position: absolute; left: 3px; top: 1px; width: 5px; height: 8px;
  border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg);
}
.chart-section { margin-top: 24px; }
.chart-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.chart-head h2 { margin: 0; }
.pill {
  border: 1px solid #d8dde6; border-radius: 6px; padding: 4px 10px; font-size: 12px; background: #fff;
}
.hint { font-size: 12px; color: #5c6370; margin-left: auto; }
svg { width: 100%; max-width: 1180px; height: auto; display: block; }
.mini-wrap { margin-top: 16px; border: 1px solid #e5e8ef; border-radius: 10px; overflow: hidden; }
table.mini { width: 100%; border-collapse: collapse; font-size: 12px; }
table.mini th, table.mini td { padding: 8px 12px; border-bottom: 1px solid #eef1f6; }
table.mini th { background: #f3f5f9; text-align: left; }
table.mini td.num { text-align: right; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; }
"""


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def quarters(data: dict) -> list[str]:
    qs = data["quarters"]
    return [q["label"] for q in qs] if qs and isinstance(qs[0], dict) else list(qs)


def row_class(row: dict) -> str:
    if row.get("kind") == "total":
        return "total"
    if row.get("kind") == "italic":
        return "italic"
    return ""


def line_cell(row: dict, selected: set[str]) -> str:
    label = html.escape(row["label"])
    plottable = row.get("plottable", True)
    if not plottable:
        return f'<td class="line">{label}</td>'
    on = "on" if row["label"] in selected else ""
    return f'<td class="line"><span class="cb {on}"></span>{label}</td>'


def income_table(data: dict, qs: list[str], selected: set[str]) -> str:
    hdr = "".join(f"<th>{html.escape(q)}</th>" for q in qs)
    body = ""
    for row in data["rows"]:
        cells = "".join(f'<td class="num">{html.escape(v)}</td>' for v in row["values"])
        body += f'<tr class="{row_class(row)}">{line_cell(row, selected)}{cells}</tr>'
    return f"""<div class="table-wrap"><table class="fin">
<thead><tr><th class="line">Line item</th>{hdr}</tr></thead>
<tbody>{body}</tbody></table></div>"""


def parse_num(s: str) -> float | None:
    s = s.strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "").replace("%", "").replace("*", "").replace("+", "")
    if not s or s == "—":
        return None
    try:
        return -float(s) if neg else float(s)
    except ValueError:
        return None


def chart_block(data: dict, labels: list[str], qs: list[str]) -> str:
    colors = ["#2563eb", "#ea580c"]
    by = {r["label"]: r for r in data["rows"]}
    series = []
    for i, lab in enumerate(labels):
        row = by.get(lab)
        if not row:
            continue
        pts = [parse_num(v) for v in reversed(row["values"])]
        series.append((lab, pts, colors[i % 2], row))

    w, h = 1180, 420
    m = dict(l=72, r=28, t=24, b=44)
    iw, ih = w - m["l"] - m["r"], h - m["t"] - m["b"]
    vals = [v for _, pts, _, _ in series for v in pts if v is not None]
    lo, hi = (min(0, min(vals)), max(0, max(vals))) if vals else (0, 1)
    if lo == hi:
        hi += 1
    n = len(qs)

    def px(i: int) -> float:
        return m["l"] + (iw / n) * (i + 0.5)

    def py(v: float) -> float:
        return m["t"] + ih * (1 - (v - lo) / (hi - lo))

    grid = "".join(
        f'<line x1="{m["l"]}" y1="{m["t"] + ih * (1 - t / 4)}" x2="{w - m["r"]}" y2="{m["t"] + ih * (1 - t / 4)}" stroke="#e8ebf0"/>'
        for t in range(5)
    )
    cats = "".join(
        f'<text x="{px(i)}" y="{h - 10}" text-anchor="middle" font-size="11" fill="#6b7280">{html.escape(q)}</text>'
        for i, q in enumerate(reversed(qs))
    )
    lines = []
    mini = ""
    for lab, pts, col, row in series:
        coords = [f"{px(i)},{py(v)}" for i, v in enumerate(pts) if v is not None]
        if coords:
            lines.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{" ".join(coords)}"/>')
        nums = [v for v in pts if v is not None]
        chg = f"{((nums[-1] - nums[0]) / abs(nums[0])) * 100:+.1f}%" if len(nums) >= 2 and nums[0] else "—"
        mini += (
            f"<tr><td><span class='dot' style='background:{col}'></span>{html.escape(lab)}</td>"
            f"<td class='num'>{html.escape(row['values'][0])}</td>"
            f"<td class='num'>{chg}</td><td class='num'>—</td></tr>"
        )

    return f"""<div class="chart-section">
<div class="chart-head">
<h2>Chart</h2>
<span class="pill">Line ▾</span>
<span class="hint">Tick rows in the table to plot. Dollars left axis; second unit on right.</span>
</div>
<svg viewBox="0 0 {w} {h}">{grid}{cats}{''.join(lines)}</svg>
<div class="mini-wrap"><table class="mini">
<thead><tr><th>Selected metric</th><th>Latest</th><th>Total Change</th><th>CAGR (ann.)</th></tr></thead>
<tbody>{mini}</tbody></table></div>
</div>"""


def income_page(data: dict) -> str:
    qs = quarters(data)
    summary = data.get("summary") or {}
    selected = set(summary.get("defaultChartRows") or ["Total Revenues", "Operating Margin"])
    stats = "".join(
        f'<div class="stat"><b>{html.escape(s["value"])}</b><span>{html.escape(s["label"])}</span></div>'
        for s in summary.get("stats", [])[:4]
    )
    chart_labels = list(summary.get("defaultChartRows") or ["Total Revenues", "Operating Margin"])[:2]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>PANW — Financial Statements</h1>
<div class="sub">{html.escape(summary.get("subtitle", ""))}</div>
<div class="fiscal">{html.escape(summary.get("fiscalMapping", ""))}</div>
<div class="tabs">
<div class="tab on">Income</div>
<div class="tab">Balance Sheet</div>
<div class="tab">Cash Flow</div>
</div>
<div class="stats">{stats}</div>
<h2>Income Statement</h2>
{income_table(data, qs, selected)}
{chart_block(data, chart_labels, qs)}
</body></html>"""


def serve() -> ThreadingHTTPServer:
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

    data = load(JSON_DIR / "PANW-income.json")
    html_path = PREVIEW_DIR / "panw-income-full.html"
    html_path.write_text(income_page(data))
    png = OUT_DIR / "panw-income.png"

    srv = serve()
    try:
        url = f"http://127.0.0.1:8765/{html_path.relative_to(REPO).as_posix()}"
        subprocess.run(["playwright-cli", "open", url], check=True)
        subprocess.run(["playwright-cli", "resize", "1440", "900"], check=True)
        time.sleep(1)
        subprocess.run(["playwright-cli", "screenshot", f"--filename={png}", "--full-page"], check=True)
        subprocess.run(["playwright-cli", "close"], check=True)
        print(f"Wrote {png}")
    finally:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
