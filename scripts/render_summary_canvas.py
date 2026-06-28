#!/usr/bin/env python3
"""Render a Cursor canvas peer-comparison summary table from fetch_summary.py JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def js_obj(rows: list[dict]) -> str:
    lines = ["const ROWS = ["]
    for r in rows:
        parts = [f'  {{ symbol: "{r["symbol"]}", name: "{r["name"]}", mktCapMM: {r["mktCapMM"]}' ]
        keys = [
            "retYTD", "ret1M", "ret3M", "ret6M", "ret12M",
            "pctFromATH", "pctFrom52Low", "pctTo52High",
            "shortNow", "short3mBps",
            "epsGrowth2026", "epsGrowth2027",
            "fwdPE2026", "fwdPE2027",
            "roe", "roic",
        ]
        for k in keys:
            v = r.get(k)
            if v is None:
                parts.append(f", {k}: 0")
            elif isinstance(v, float) and v == int(v):
                parts.append(f", {k}: {int(v)}")
            else:
                parts.append(f", {k}: {v}")
        parts.append(" },")
        lines.append("".join(parts))
    lines.append("] as const;")
    return "\n".join(lines)


CANVAS_TEMPLATE = '''import {{ useCanvasState }} from "cursor/canvas";

const AS_OF = "{as_of}";
const TITLE = "{title}";
const SOURCE = "{source}";

{rows_const}

type Row = (typeof ROWS)[number];
type MetricKey = {metric_keys};
type SortKey = "name" | "symbol" | "mktCapMM" | MetricKey;
type SortDir = "asc" | "desc";
type SortState = {{ key: SortKey; dir: SortDir }};

type MetricCol = {{
  key: MetricKey;
  label: string;
  group: string;
  heatmap: boolean;
  fmt: (v: number) => string;
  higherIsBetter: boolean;
}};

const METRIC_COLS: MetricCol[] = [
  {{ key: "retYTD", label: "YTD", group: "Stock Return", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "ret1M", label: "1M", group: "Stock Return", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "ret3M", label: "3M", group: "Stock Return", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "ret6M", label: "6M", group: "Stock Return", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "ret12M", label: "12M", group: "Stock Return", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "pctFromATH", label: "From ATH", group: "Price vs Range", heatmap: true, fmt: fmtHeatPct, higherIsBetter: true }},
  {{ key: "pctFrom52Low", label: "52W Low", group: "Price vs Range", heatmap: true, fmt: fmtHeatPctSigned, higherIsBetter: true }},
  {{ key: "pctTo52High", label: "To 52W High", group: "Price vs Range", heatmap: true, fmt: fmtHeatPctSigned, higherIsBetter: false }},
  {{ key: "shortNow", label: "Now", group: "Short Interest", heatmap: true, fmt: (v) => `${{v.toFixed(2)}}%`, higherIsBetter: false }},
  {{ key: "short3mBps", label: "3M Δ", group: "Short Interest", heatmap: true, fmt: fmtHeatBps, higherIsBetter: false }},
  {{ key: "epsGrowth2026", label: "2026", group: "EPS Growth", heatmap: false, fmt: fmtPlainPct, higherIsBetter: true }},
  {{ key: "epsGrowth2027", label: "2027", group: "EPS Growth", heatmap: false, fmt: fmtPlainPct, higherIsBetter: true }},
  {{ key: "fwdPE2026", label: "2026", group: "P/E Ratio", heatmap: false, fmt: fmtPlainX, higherIsBetter: false }},
  {{ key: "fwdPE2027", label: "2027", group: "P/E Ratio", heatmap: false, fmt: fmtPlainX, higherIsBetter: false }},
  {{ key: "roe", label: "ROE", group: "Returns", heatmap: false, fmt: fmtPlainPct, higherIsBetter: true }},
  {{ key: "roic", label: "ROIC", group: "Returns", heatmap: false, fmt: fmtPlainPct, higherIsBetter: true }},
];

const HEAT_COUNT = METRIC_COLS.filter((c) => c.heatmap).length;
const PLAIN_COUNT = METRIC_COLS.length - HEAT_COUNT;
const GRID_COLS = `minmax(108px,1.15fr) 46px 68px repeat(${{HEAT_COUNT}}, minmax(40px,0.42fr)) repeat(${{PLAIN_COUNT}}, minmax(40px,0.42fr))`;

const cellBase = {{
  padding: "2px 5px",
  fontSize: 10,
  lineHeight: "13px",
  fontVariantNumeric: "tabular-nums",
  whiteSpace: "nowrap",
  borderRight: "1px solid #1a1a1a",
  borderBottom: "1px solid #1a1a1a",
}};

function fmtHeatPct(v: number): string {{
  const n = Math.round(v);
  if (n < 0) return `(${{Math.abs(n)}}%)`;
  return `${{n}}%`;
}}

function fmtHeatPctSigned(v: number): string {{
  const n = Math.round(v);
  if (n < 0) return `(${{Math.abs(n)}}%)`;
  return `${{n}}%`;
}}

function fmtHeatBps(v: number): string {{
  const n = Math.round(v);
  if (n < 0) return `(${{Math.abs(n)}})`;
  return `${{n}}`;
}}

function fmtPlainPct(v: number): string {{
  return `${{Math.round(v)}}%`;
}}

function fmtPlainX(v: number): string {{
  return `${{v.toFixed(1)}}x`;
}}

function fmtMktCap(mm: number): string {{
  return `$${{Math.round(mm).toLocaleString("en-US")}}`;
}}

type Rgb = [number, number, number];

// Worst → best: dark red → light red → yellow → light green → dark green
const HEAT_STOPS: Rgb[] = [
  [156, 0, 6],       // #9C0006 dark red
  [248, 105, 107],   // #F8696B red
  [255, 199, 206],   // #FFC7CE light red
  [255, 235, 132],   // #FFEB84 yellow
  [198, 239, 206],   // #C6EFCE light green
  [99, 190, 123],    // #63BE7B green
  [0, 97, 0],        // #006100 dark green
];

function rgbStr([r, g, b]: Rgb): string {{
  return `rgb(${{r}}, ${{g}}, ${{b}})`;
}}

function luminance([r, g, b]: Rgb): number {{
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
}}

function heatTextColor(bg: Rgb): string {{
  return luminance(bg) < 0.52 ? "#FFFFFF" : "#141414";
}}

function rankIndex(values: number[], value: number, higherIsBetter: boolean): number {{
  const sorted = [...values].sort((a, b) => a - b);
  const idx = sorted.indexOf(value);
  return higherIsBetter ? idx : sorted.length - 1 - idx;
}}

function heatStyle(rankIdx: number, count: number): {{ background: string; color: string }} {{
  if (count <= 1) {{
    const bg = HEAT_STOPS[3];
    return {{ background: rgbStr(bg), color: heatTextColor(bg) }};
  }}
  const t = rankIdx / (count - 1);
  const stopIdx = Math.round(t * (HEAT_STOPS.length - 1));
  const bg = HEAT_STOPS[stopIdx];
  return {{ background: rgbStr(bg), color: heatTextColor(bg) }};
}}

const ROW_SELECTED_OUTLINE = "2px solid #2563eb";
const ROW_SELECTED_PLAIN_BG = "#dbeafe";

function HeatCell({{ value, col, selected, onClick }}: {{ value: number; col: MetricCol; selected: boolean; onClick: () => void }}) {{
  const values = ROWS.map((r) => r[col.key]);
  const idx = rankIndex(values, value, col.higherIsBetter);
  const {{ background, color }} = heatStyle(idx, values.length);
  return (
    <div
      onClick={{onClick}}
      style={{{{
      ...cellBase,
      textAlign: "center",
      fontWeight: 700,
      background,
      color,
      cursor: "pointer",
      outline: selected ? ROW_SELECTED_OUTLINE : undefined,
      outlineOffset: selected ? -2 : undefined,
    }}}}>
      {{col.fmt(value)}}
    </div>
  );
}}

function PlainCell({{ value, col, selected, onClick }}: {{ value: number; col: MetricCol; selected: boolean; onClick: () => void }}) {{
  return (
    <div
      onClick={{onClick}}
      style={{{{
      ...cellBase,
      textAlign: "center",
      fontWeight: 500,
      background: selected ? ROW_SELECTED_PLAIN_BG : "#ffffff",
      color: "#141414",
      cursor: "pointer",
      outline: selected ? ROW_SELECTED_OUTLINE : undefined,
      outlineOffset: selected ? -2 : undefined,
    }}}}>
      {{col.fmt(value)}}
    </div>
  );
}}

function sortValue(row: Row, key: SortKey): string | number {{
  if (key === "name") return row.name;
  if (key === "symbol") return row.symbol;
  if (key === "mktCapMM") return row.mktCapMM;
  return row[key];
}}

function compareRows(a: Row, b: Row, sort: SortState): number {{
  const av = sortValue(a, sort.key);
  const bv = sortValue(b, sort.key);
  const cmp = typeof av === "number" && typeof bv === "number"
    ? av - bv
    : String(av).localeCompare(String(bv));
  return sort.dir === "asc" ? cmp : -cmp;
}}

function SortHeader({{
  label,
  sortKey,
  sort,
  onSort,
  align = "center",
}}: {{
  label: string;
  sortKey: SortKey;
  sort: SortState;
  onSort: (key: SortKey) => void;
  align?: "left" | "center" | "right";
}}) {{
  const active = sort.key === sortKey;
  const arrow = sort.dir === "asc" ? "▲" : "▼";
  return (
    <div
      role="button"
      tabIndex={{0}}
      onClick={{() => onSort(sortKey)}}
      onKeyDown={{(e) => {{
        if (e.key === "Enter" || e.key === " ") {{
          e.preventDefault();
          onSort(sortKey);
        }}
      }}}}
      style={{{{
        ...cellBase,
        background: active ? "#333333" : "#000000",
        color: "#ffffff",
        fontWeight: 700,
        textAlign: align,
        fontSize: 10,
        padding: "3px 5px",
        cursor: "pointer",
        userSelect: "none",
      }}}}
    >
      {{label}}{{active ? ` ${{arrow}}` : ""}}
    </div>
  );
}}

export default function StockHeatmap() {{
  const [sort, setSort] = useCanvasState<SortState>("sort", {{ key: "mktCapMM", dir: "desc" }});
  const [selectedSymbol, setSelectedSymbol] = useCanvasState<string | null>("selectedSymbol", null);
  const sortedRows = [...ROWS].sort((a, b) => compareRows(a, b, sort));

  const onSort = (key: SortKey) => {{
    setSort((prev) => (
      prev.key === key
        ? {{ key, dir: prev.dir === "asc" ? "desc" : "asc" }}
        : {{ key, dir: "desc" }}
    ));
  }};

  const onRowClick = (symbol: string) => {{
    setSelectedSymbol((prev) => (prev === symbol ? null : symbol));
  }};

  const groups: {{ label: string; span: number }}[] = [];
  let last = "";
  for (const col of METRIC_COLS) {{
    if (col.group !== last) {{
      groups.push({{ label: col.group, span: METRIC_COLS.filter((c) => c.group === col.group).length }});
      last = col.group;
    }}
  }}

  const headerCell = {{
    ...cellBase,
    background: "#000000",
    color: "#ffffff",
    fontWeight: 700,
    textAlign: "center",
    fontSize: 10,
    padding: "3px 5px",
  }};

  return (
    <div style={{{{ padding: 8, background: "#f3f3f3", minWidth: 0 }}}}>
      <div style={{{{ border: "1px solid #1a1a1a", overflow: "auto", background: "#ffffff" }}}}>
        <div style={{{{ display: "grid", gridTemplateColumns: GRID_COLS, minWidth: 1280 }}}}>
          <div style={{{{ ...headerCell, textAlign: "left" }}}}>{{TITLE}}</div>
          <div style={{{{ ...headerCell }}}} />
          <div style={{{{ ...headerCell }}}} />
          {{groups.map((g) => (
            <div key={{g.label}} style={{{{ ...headerCell, gridColumn: `span ${{g.span}}` }}}}>
              {{g.label}}
            </div>
          ))}}

          <SortHeader label="Company" sortKey="name" sort={{sort}} onSort={{onSort}} align="left" />
          <SortHeader label="Ticker" sortKey="symbol" sort={{sort}} onSort={{onSort}} />
          <SortHeader label="Mkt. Cap." sortKey="mktCapMM" sort={{sort}} onSort={{onSort}} align="right" />
          {{METRIC_COLS.map((col) => (
            <SortHeader key={{col.key}} label={{col.label}} sortKey={{col.key}} sort={{sort}} onSort={{onSort}} />
          ))}}

          {{sortedRows.map((row) => {{
            const selected = selectedSymbol === row.symbol;
            const selectRow = () => onRowClick(row.symbol);
            return (
            <div key={{row.symbol}} style={{{{ display: "contents" }}}}>
              <div
                onClick={{selectRow}}
                style={{{{
                  ...cellBase,
                  textAlign: "left",
                  fontWeight: 700,
                  background: selected ? ROW_SELECTED_PLAIN_BG : "#ffffff",
                  color: "#141414",
                  cursor: "pointer",
                  outline: selected ? ROW_SELECTED_OUTLINE : undefined,
                  outlineOffset: selected ? -2 : undefined,
                }}}}
              >
                {{row.name}}
              </div>
              <div
                onClick={{selectRow}}
                style={{{{
                  ...cellBase,
                  textAlign: "center",
                  fontWeight: 700,
                  background: selected ? ROW_SELECTED_PLAIN_BG : "#ffffff",
                  color: "#141414",
                  cursor: "pointer",
                  outline: selected ? ROW_SELECTED_OUTLINE : undefined,
                  outlineOffset: selected ? -2 : undefined,
                }}}}
              >
                {{row.symbol}}
              </div>
              <div
                onClick={{selectRow}}
                style={{{{
                  ...cellBase,
                  textAlign: "right",
                  fontWeight: 500,
                  background: selected ? ROW_SELECTED_PLAIN_BG : "#ffffff",
                  color: "#141414",
                  cursor: "pointer",
                  outline: selected ? ROW_SELECTED_OUTLINE : undefined,
                  outlineOffset: selected ? -2 : undefined,
                }}}}
              >
                {{fmtMktCap(row.mktCapMM)}}
              </div>
              {{METRIC_COLS.map((col) => (
                col.heatmap
                  ? <HeatCell key={{col.key}} value={{row[col.key]}} col={{col}} selected={{selected}} onClick={{selectRow}} />
                  : <PlainCell key={{col.key}} value={{row[col.key]}} col={{col}} selected={{selected}} onClick={{selectRow}} />
              ))}}
            </div>
            );
          }})}}
        </div>
      </div>

      <div style={{{{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: "#666666", gap: 12, flexWrap: "wrap" }}}}>
        <span>Source: {{SOURCE}} · Click headers to sort · Click a row to highlight</span>
        <span>*Values in $MM, pricing as of {{AS_OF}}</span>
      </div>
    </div>
  );
}}
'''


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("json_path", help="Summary JSON from fetch_summary.py")
    p.add_argument("-o", "--output", required=True, help="Output .canvas.tsx path")
    p.add_argument("--title", default="Stock Comparison Heatmap")
    p.add_argument("--subtitle", default="")
    args = p.parse_args()

    data = json.loads(Path(args.json_path).read_text())

    content = CANVAS_TEMPLATE.format(
        as_of=data.get("asOf", ""),
        title=args.title.replace('"', '\\"'),
        rows_const=js_obj(data["rows"]),
        metric_keys='"' + '" | "'.join([
            "retYTD", "ret1M", "ret3M", "ret6M", "ret12M",
            "pctFromATH", "pctFrom52Low", "pctTo52High",
            "shortNow", "short3mBps",
            "epsGrowth2026", "epsGrowth2027",
            "fwdPE2026", "fwdPE2027",
            "roe", "roic",
        ]) + '"',
        source=data.get("source", "Yahoo Finance"),
    )

    Path(args.output).write_text(content)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
