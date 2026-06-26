#!/usr/bin/env python3
"""Render balance-sheet or cash-flow canvas from JSON (unified-table pattern)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def ts_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def jsx_text(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def row_def(row: dict) -> str:
    parts = [f'label: "{ts_escape(row["label"])}"', f'vals: {json.dumps(row["values"])}']
    if row.get("kind"):
        parts.append(f'kind: "{row["kind"]}"')
    if row.get("unit"):
        parts.append(f'unit: "{row["unit"]}"')
    if row.get("plottable") is False:
        parts.append("plottable: false")
    return "{ " + ", ".join(parts) + " }"


def split_sections(rows: list[dict], section_titles: list[str]) -> list[tuple[str, list[dict]]]:
    sections: list[tuple[str, list[dict]]] = []
    current_title = section_titles[0] if section_titles else "Items"
    current_rows: list[dict] = []
    title_set = set(section_titles)

    for row in rows:
        if row["label"] in title_set and all(v == "" for v in row["values"]):
            if current_rows:
                sections.append((current_title, current_rows))
            current_title = row["label"]
            current_rows = []
        else:
            current_rows.append(row)
    if current_rows:
        sections.append((current_title, current_rows))
    return sections


BOILERPLATE = '''// GENERATED — do not edit by hand.
// Source: {src}
// Generated: {gen}
import {{
  Callout, Checkbox, Grid, H1, H2, H3, Row,
  Select, Stack, Stat, Table, Text, useCanvasState, useHostTheme,
}} from "cursor/canvas";

const QUARTERS = {quarters};
const CHART_CATEGORIES = [...QUARTERS].reverse();

type Kind = "normal" | "total";
type Unit = "$" | "%";
type RowDef = {{ label: string; vals: string[]; kind?: Kind; unit?: Unit; plottable?: boolean }};

{section_arrays}

const ALL_ROWS: RowDef[] = [{all_join}];

const UNIT_META: Record<Unit, {{ title: string }}> = {{
  "$": {{ title: "USD millions" }},
  "%": {{ title: "Percent" }},
}};
const unitOf = (r: RowDef): Unit => r.unit ?? "$";

const COL_ALIGN: Array<"left" | "right"> = ["left", ...QUARTERS.map(() => "right" as const)];

function toNum(v: string): number | null {{
  if (!v || v.trim() === "—") return null;
  const neg = /^\\(.*\\)$/.test(v.trim());
  const cleaned = v.replace(/[(),$%+\\s]/g, "");
  if (cleaned === "" || cleaned === "*") return null;
  const n = Number(cleaned.replace(/\\*$/, ""));
  return Number.isNaN(n) ? null : neg ? -n : n;
}}

const chartData = (r: RowDef) => [...r.vals].reverse().map((v) => toNum(v) ?? 0);
const fmtPct = (n: number | null) => (n === null ? "—" : `${{n >= 0 ? "+" : ""}}${{n.toFixed(1)}}%`);

function fmtVal(v: number, unit: Unit): string {{
  if (unit === "%") return `${{(Math.round(v * 10) / 10).toFixed(1)}}%`;
  if (unit === "eps") return v.toFixed(2);
  if (unit === "sh") {{
    const r = Math.round(v * 10) / 10;
    return Number.isInteger(r) ? String(r) : r.toFixed(1);
  }}
  const n = Math.round(v);
  const abs = Math.abs(n).toLocaleString("en-US");
  return n < 0 ? `(${{abs}})` : abs;
}}
function fmtAxis(v: number, unit: Unit): string {{
  if (unit === "%") return `${{(Math.round(v * 10) / 10).toFixed(1)}}%`;
  if (unit === "eps") return v.toFixed(2);
  if (unit === "sh") {{
    const r = Math.round(v * 10) / 10;
    return Number.isInteger(r) ? String(r) : r.toFixed(1);
  }}
  return Math.round(v).toLocaleString("en-US");
}}

function seriesStats(r: RowDef) {{
  const nums = [...r.vals].reverse().map(toNum).filter((n): n is number => n !== null);
  if (nums.length < 2) return {{ totalChange: null as number | null, cagr: null as number | null }};
  const first = nums[0], last = nums[nums.length - 1];
  const totalChange = first !== 0 ? ((last - first) / Math.abs(first)) * 100 : null;
  const years = (nums.length - 1) / 4;
  const cagr = first > 0 && last > 0 && years > 0 ? (Math.pow(last / first, 1 / years) - 1) * 100 : null;
  return {{ totalChange, cagr }};
}}

function domain(values: number[]): [number, number] {{
  const vals = values.filter((v) => Number.isFinite(v));
  if (!vals.length) return [0, 1];
  let min = Math.min(0, ...vals);
  let max = Math.max(0, ...vals);
  if (min === max) max = min + 1;
  if (max > 0) max *= 1.08;
  if (min < 0) min *= 1.08;
  return [min, max];
}}

function cell(v: string, kind?: Kind) {{
  if (kind === "total") return <Text as="span" weight="semibold">{{v}}</Text>;
  return <Text as="span">{{v}}</Text>;
}}

function labelCell(r: RowDef, selected: string[], onToggle: (label: string) => void) {{
  const text =
    r.kind === "total" ? (
      <Text as="span" weight="semibold" truncate style={{{{ minWidth: 0, flex: 1 }}}}>
        {{r.label}}
      </Text>
    ) : (
      <Text as="span" truncate style={{{{ minWidth: 0, flex: 1 }}}}>
        {{r.label}}
      </Text>
    );
  if (r.plottable === false) return text;
  return (
    <Row gap={{8}} align="center" style={{{{ minWidth: 0, maxWidth: 280 }}}}>
      <Checkbox checked={{selected.includes(r.label)}} onChange={{() => onToggle(r.label)}} />
      {{text}}
    </Row>
  );
}}

function FinTable({{ lead, defs, selected, onToggle }}: {{ lead: string; defs: RowDef[]; selected: string[]; onToggle: (label: string) => void }}) {{
  const rows = defs.map((r) => [labelCell(r, selected, onToggle), ...r.vals.map((v) => cell(v, r.kind))]);
  return (
    <Table
      headers={{[lead, ...QUARTERS]}}
      rows={{rows}}
      columnAlign={{COL_ALIGN}}
      framed
      striped
      style={{{{ minWidth: 1280, tableLayout: "fixed" }}}}
    />
  );
}}

type PlotSeries = {{ name: string; unit: Unit; color: string; data: number[] }};

function CombinedChart({{ plot, chartType }}: {{ plot: PlotSeries[]; chartType: string }}) {{
  const theme = useHostTheme();
  const cats = CHART_CATEGORIES;
  const N = cats.length;
  const leftUnit = plot[0].unit;
  const rightUnit = plot.find((p) => p.unit !== leftUnit)?.unit;
  const leftPlots = plot.filter((p) => p.unit === leftUnit);
  const rightPlots = plot.filter((p) => p.unit !== leftUnit);
  const hasRight = rightPlots.length > 0;
  const [lMin, lMax] = domain(leftPlots.flatMap((p) => p.data));
  const [rMin, rMax] = domain(rightPlots.flatMap((p) => p.data));
  const W = 1180, H = 420;
  const m = {{ top: 30, right: hasRight ? 72 : 28, bottom: 46, left: 80 }};
  const innerW = W - m.left - m.right;
  const innerH = H - m.top - m.bottom;
  const slotW = innerW / N;
  const xc = (i: number) => m.left + slotW * (i + 0.5);
  const scale = (v: number, min: number, max: number) => m.top + innerH * (1 - (v - min) / (max - min));
  const yFor = (p: PlotSeries, v: number) => (p.unit === leftUnit ? scale(v, lMin, lMax) : scale(v, rMin, rMax));
  const baseFor = (p: PlotSeries) => (p.unit === leftUnit ? scale(0, lMin, lMax) : scale(0, rMin, rMax));
  const showLabels = plot.length * N <= 36;
  const ticks = [0, 1, 2, 3, 4];
  const nb = plot.length;
  const groupW = slotW * 0.7;
  const barW = groupW / nb;
  return (
    <svg viewBox={{`0 0 ${{W}} ${{H}}`}} role="img" style={{{{ width: "100%", height: "auto" }}}}>
      {{ticks.map((t) => {{
        const y = m.top + innerH * (1 - t / 4);
        const lv = lMin + (lMax - lMin) * (t / 4);
        const rv = rMin + (rMax - rMin) * (t / 4);
        return (
          <g key={{t}}>
            <line x1={{m.left}} y1={{y}} x2={{m.left + innerW}} y2={{y}} stroke={{theme.stroke.tertiary}} strokeWidth={{1}} />
            <text x={{m.left - 8}} y={{y + 4}} textAnchor="end" fontSize={{11}} fill={{theme.text.tertiary}}>{{fmtAxis(lv, leftUnit)}}</text>
            {{hasRight && rightUnit && (
              <text x={{m.left + innerW + 8}} y={{y + 4}} textAnchor="start" fontSize={{11}} fill={{theme.text.tertiary}}>{{fmtAxis(rv, rightUnit)}}</text>
            )}}
          </g>
        );
      }})}}
      {{cats.map((c, i) => (
        <text key={{c}} x={{xc(i)}} y={{H - m.bottom + 18}} textAnchor="middle" fontSize={{11}} fill={{theme.text.secondary}}>{{c}}</text>
      ))}}
      {{chartType === "bar" &&
        plot.map((p, si) =>
          p.data.map((v, i) => {{
            const yv = yFor(p, v);
            const base = baseFor(p);
            const x = m.left + slotW * i + (slotW - groupW) / 2 + si * barW;
            return (
              <g key={{`${{p.name}}-${{i}}`}}>
                <rect x={{x}} y={{Math.min(base, yv)}} width={{barW * 0.86}} height={{Math.abs(base - yv)}} fill={{p.color}} rx={{1}} />
                {{showLabels && (
                  <text x={{x + barW * 0.43}} y={{Math.min(base, yv) - 3}} textAnchor="middle" fontSize={{9}} fill={{theme.text.secondary}}>{{fmtVal(v, p.unit)}}</text>
                )}}
              </g>
            );
          }}),
        )}}
      {{chartType === "line" &&
        plot.map((p) => (
          <g key={{p.name}}>
            <polyline points={{p.data.map((v, i) => `${{xc(i)}},${{yFor(p, v)}}`).join(" ")}} fill="none" stroke={{p.color}} strokeWidth={{2}} />
            {{p.data.map((v, i) => (
              <g key={{i}}>
                <circle cx={{xc(i)}} cy={{yFor(p, v)}} r={{3}} fill={{p.color}} />
                {{showLabels && (
                  <text x={{xc(i)}} y={{yFor(p, v) - 7}} textAnchor="middle" fontSize={{9}} fill={{theme.text.secondary}}>{{fmtVal(v, p.unit)}}</text>
                )}}
              </g>
            ))}}
          </g>
        ))}}
      <text x={{m.left}} y={{m.top - 12}} fontSize={{10}} fill={{theme.text.tertiary}}>{{UNIT_META[leftUnit].title}} (left)</text>
      {{hasRight && rightUnit && (
        <text x={{m.left + innerW}} y={{m.top - 12}} textAnchor="end" fontSize={{10}} fill={{theme.text.tertiary}}>{{UNIT_META[rightUnit].title}} (right)</text>
      )}}
    </svg>
  );
}}

function ChartArea({{ selected }}: {{ selected: string[] }}) {{
  const [chartType, setChartType] = useCanvasState<string>("chartType", "line");
  const theme = useHostTheme();
  const c = theme.category;
  const COLORS = [c.blue, c.orange, c.purple, c.green, c.pink, c.cyan, c.yellow, c.gray];
  const rows = ALL_ROWS.filter((r) => r.plottable !== false && selected.includes(r.label));
  const plot: PlotSeries[] = rows.map((r, i) => ({{ name: r.label, unit: unitOf(r), color: COLORS[i % COLORS.length], data: chartData(r) }}));
  const dot = (color: string) => (
    <span style={{{{ display: "inline-block", width: 9, height: 9, borderRadius: 9, background: color, marginRight: 8, verticalAlign: "middle" }}}} />
  );
  const statRows = rows.map((r, i) => {{
    const {{ totalChange, cagr }} = seriesStats(r);
    return [
      <Text as="span">{{dot(COLORS[i % COLORS.length])}}{{r.label}}</Text>,
      cell(r.vals[0]),
      cell(fmtPct(totalChange)),
      cell(fmtPct(cagr)),
    ];
  }});
  return (
    <Stack gap={{16}}>
      <Row gap={{12}} align="center">
        <H2>Chart</H2>
        <Select value={{chartType}} onChange={{setChartType}} options={{[{{ value: "line", label: "Line" }}, {{ value: "bar", label: "Bar" }}]}} style={{{{ width: 120 }}}} />
      </Row>
      {{plot.length === 0 ? (
        <Text tone="secondary">Select one or more rows in the table to chart them.</Text>
      ) : (
        <>
          <CombinedChart plot={{plot}} chartType={{chartType}} />
          <Table headers={{["Selected metric", "Latest", "Total Change", "CAGR (ann.)"]}} rows={{statRows}} columnAlign={{["left", "right", "right", "right"]}} framed />
        </>
      )}}
    </Stack>
  );
}}

export default function Statement() {{
  const [selected, setSelected] = useCanvasState<string[]>("chartRows", {default_chart});
  const toggle = (label: string) =>
    setSelected((prev) => (prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]));

  return (
    <Stack gap={{20}} style={{{{ padding: 24, maxWidth: 1680 }}}}>
      <Stack gap={{4}}>
        <H1>{title}</H1>
        <Text tone="secondary">{subtitle}</Text>
        <Text tone="secondary" size="small">{fiscal}</Text>
      </Stack>
      <Grid columns={{4}} gap={{16}}>
{stats}
      </Grid>
      <H2>{h2}</H2>
{section_tables}
      <ChartArea selected={{selected}} />
      <Callout tone="neutral" title="Notes & methodology">
        <Stack gap={{6}}>
{notes}
        </Stack>
      </Callout>
    </Stack>
  );
}}
'''


def render(data: dict, out_path: Path, *, src_json: Path) -> None:
    stype = data["statementType"]
    quarters = json.dumps([q["label"] for q in data["quarters"]])
    sections_cfg = data.get("sections", [])
    sections = split_sections(data["rows"], sections_cfg)

    section_arrays = []
    section_tables = []
    const_names = []
    for i, (title, rows) in enumerate(sections):
        name = ["ASSETS", "LIABS", "EQUITY", "OPERATING", "INVESTING", "FINANCING", "FCF"][i] if i < 7 else f"SEC{i}"
        const_names.append(name)
        body = ",\n".join("  " + row_def(r) for r in rows)
        section_arrays.append(f"const {name}: RowDef[] = [\n{body}\n];")
        section_tables.append(f'      <H3>{title}</H3>\n      <FinTable lead="{title}" defs={{{name}}} selected={{selected}} onToggle={{toggle}} />')

    summary = data.get("summary", {})
    stats = summary.get("stats", [])
    stat_lines = []
    for s in stats:
        tone = f' tone="{s["tone"]}"' if s.get("tone") else ""
        stat_lines.append(f'        <Stat value="{jsx_text(s["value"])}" label="{jsx_text(s["label"])}"{tone} />')

    notes = data.get("notes", [])
    note_lines = [f'          <Text size="small">{jsx_text(n)}</Text>' for n in notes]

    title_map = {
        "balance-sheet": f'{data["ticker"]} — Balance Sheet',
        "cash-flow": f'{data["ticker"]} — Cash Flow Statement',
    }
    h2_map = {"balance-sheet": "Balance Sheet", "cash-flow": "Cash Flow Statement"}

    body = BOILERPLATE.format(
        src=str(src_json),
        gen=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        quarters=quarters,
        section_arrays="\n\n".join(section_arrays),
        all_join=", ".join(f"...{n}" for n in const_names),
        default_chart=json.dumps(summary.get("defaultChartRows", [])),
        title=title_map.get(stype, data["ticker"]),
        subtitle=jsx_text(summary.get("subtitle", "")),
        fiscal=jsx_text(summary.get("fiscalMapping", "")),
        stats="\n".join(stat_lines),
        h2=h2_map.get(stype, "Statement"),
        section_tables="\n".join(section_tables),
        notes="\n".join(note_lines),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")


def main() -> None:
    from sec_financials import resolve_canvas_dir

    p = argparse.ArgumentParser()
    p.add_argument("json_file")
    p.add_argument("--canvas-dir", default=None, help="Default: ~/src/stock-financials/canvas/")
    args = p.parse_args()
    data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    stype = data["statementType"]
    name = {"balance-sheet": "balance-sheet", "cash-flow": "cashflow"}[stype]
    src = Path(args.json_file).expanduser().resolve()
    out = resolve_canvas_dir(args.canvas_dir) / f'{data["ticker"].lower()}-{name}.canvas.tsx'
    render(data, out, src_json=src)
    print(out)


if __name__ == "__main__":
    main()
