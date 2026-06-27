__HEADER__
import {
  Callout, Checkbox, Grid, H1, H2, H3, Pill, Row,
  Select, Stack, Table, Text, useCanvasState, useHostTheme,
  type TableProps,
} from "cursor/canvas";

type Kind = "normal" | "italic" | "total";
type Unit = "$" | "%" | "eps" | "sh";
type RowDef = { label: string; vals: string[]; kind?: Kind; unit?: Unit; plottable?: boolean };
type SectionBlock = { title: string; rows: RowDef[] };
type StatementData = {
  quarters: string[];
  rows: RowDef[];
  sections: SectionBlock[] | null;
  statementType: "income" | "balance-sheet" | "cash-flow";
  summary: {
    subtitle?: string;
    fiscalMapping?: string;
    stats?: Array<{ value: string; label: string; tone?: string }>;
    defaultChartRows?: string[];
  };
  notes: string[];
};

type StockSnapshot = {
  source: string;
  asOf: string;
  price: string;
  fromLowPct: string;
  fromHighPct: string;
  fromLowAbs: string;
  fromHighAbs: string;
  fiftyTwoWeekLow: string;
  fiftyTwoWeekHigh: string;
  marketCap: string;
  trailingPE: string;
};

__STOCK_SNAPSHOT__

__DATA_BLOCKS__

__TAB_DATA__

const TAB_LABELS: Record<string, string> = {
  income: "Income",
  "balance-sheet": "Balance Sheet",
  "cash-flow": "Cash Flow",
};

type SummaryStat = { value: string; label: string; tone?: string };
type MetricCell = TableProps["rows"][number][number];
type MetricRow = { label: MetricCell; value: MetricCell; rowTone?: "success" | "info" };
type ValueTone = "default" | "accent" | "success" | "danger" | "info";

function useMetricColors() {
  const theme = useHostTheme();
  return {
    accent: theme.accent.primary,
    success: theme.diff.stripAdded,
    danger: theme.diff.stripRemoved,
    info: theme.accent.primary,
    default: theme.text.primary,
  };
}

function MetricValue({ text, tone = "default", size = "body" }: { text: string; tone?: ValueTone; size?: "body" | "small" }) {
  const colors = useMetricColors();
  return <Text weight="semibold" size={size} style={{ color: colors[tone] }}>{text}</Text>;
}

function PriceRangeMiddle({ snap }: { snap: StockSnapshot }) {
  return (
    <Row gap={6} wrap align="center" justify="center">
      <MetricValue
        text={`${snap.fromLowPct} from 52W low (${snap.fromLowAbs})`}
        tone="success"
        size="small"
      />
      <Text tone="secondary" size="small">·</Text>
      <MetricValue
        text={`${snap.fromHighPct} from 52W high (${snap.fromHighAbs})`}
        tone="danger"
        size="small"
      />
    </Row>
  );
}

function StockSnapshotTable({ snap }: { snap: StockSnapshot }) {
  return (
    <Stack gap={6} style={{ height: "100%", minWidth: 0 }}>
      <Stack gap={2}>
        <H2>Stock snapshot</H2>
        <Text tone="secondary" size="small">{snap.source} · {snap.asOf}</Text>
      </Stack>
      <Table
        headers={["Metric", "", "Value"]}
        rows={[
          ["Price", <PriceRangeMiddle snap={snap} />, <MetricValue text={snap.price} tone="accent" />],
          ["52-week low", "", <MetricValue text={snap.fiftyTwoWeekLow} />],
          ["52-week high", "", <MetricValue text={snap.fiftyTwoWeekHigh} />],
          ["Market cap", "", <MetricValue text={snap.marketCap} tone="info" />],
          ["P/E (trailing)", "", <MetricValue text={snap.trailingPE} />],
        ]}
        columnAlign={["left", "center", "right"]}
        framed
        style={{ width: "100%" }}
      />
    </Stack>
  );
}

function statValueTone(tone?: string): ValueTone {
  if (tone === "success") return "success";
  if (tone === "info") return "info";
  return "default";
}

function CompactMetricTable({
  title,
  caption,
  rows,
}: {
  title: string;
  caption?: string;
  rows: MetricRow[];
}) {
  return (
    <Stack gap={6} style={{ height: "100%", minWidth: 0 }}>
      <Stack gap={2}>
        <H2>{title}</H2>
        {caption ? <Text tone="secondary" size="small">{caption}</Text> : null}
      </Stack>
      <Table
        headers={["Metric", "Value"]}
        rows={rows.map((r) => [r.label, r.value])}
        columnAlign={["left", "right"]}
        rowTone={rows.map((r) => r.rowTone)}
        framed
        style={{ width: "100%" }}
      />
    </Stack>
  );
}

function KeyMetricsRow({
  snap,
  stats,
  highlightsTitle,
}: {
  snap: StockSnapshot | null;
  stats: SummaryStat[];
  highlightsTitle: string;
}) {
  const finRows: MetricRow[] = stats.map((s) => ({
    label: s.label,
    value: <MetricValue text={s.value} tone={statValueTone(s.tone)} />,
    rowTone: s.tone === "success" || s.tone === "info" ? (s.tone as "success" | "info") : undefined,
  }));

  if (!snap && stats.length === 0) return null;

  const showPair = snap && stats.length > 0;

  return (
    <Grid
      columns={showPair ? "minmax(0, 1fr) minmax(0, 1fr)" : 1}
      gap={16}
      align="stretch"
      style={{ width: "100%", maxWidth: 960 }}
    >
      {stats.length > 0 ? (
        <CompactMetricTable title={highlightsTitle} rows={finRows} />
      ) : null}
      {snap ? <StockSnapshotTable snap={snap} /> : null}
    </Grid>
  );
}

const UNIT_META: Record<Unit, { title: string }> = {
  "$": { title: "USD millions" },
  "%": { title: "Percent" },
  eps: { title: "Per share (USD)" },
  sh: { title: "Shares (millions)" },
};

function unitOf(r: RowDef): Unit {
  if (r.unit) return r.unit as Unit;
  if (/EPS/i.test(r.label)) return "eps";
  if (/Shares/i.test(r.label)) return "sh";
  if (r.vals.some((v) => v.includes("%"))) return "%";
  return "$";
}

function colAlign(quarters: string[]): Array<"left" | "right"> {
  return ["left", ...quarters.map(() => "right" as const)];
}

function toNum(v: string): number | null {
  if (!v || v.trim() === "—") return null;
  const neg = /^\(.*\)$/.test(v.trim());
  const cleaned = v.replace(/[(),$%+\s]/g, "");
  if (cleaned === "" || cleaned === "*") return null;
  const n = Number(cleaned.replace(/\*$/, ""));
  return Number.isNaN(n) ? null : neg ? -n : n;
}

function chartData(r: RowDef, quarters: string[]) {
  return [...r.vals].reverse().map((v) => toNum(v) ?? 0);
}

function chartCategories(quarters: string[]) {
  return [...quarters].reverse();
}

const fmtPct = (n: number | null) => (n === null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`);

function fmtVal(v: number, unit: Unit): string {
  if (unit === "%") return `${(Math.round(v * 10) / 10).toFixed(1)}%`;
  if (unit === "eps") return v.toFixed(2);
  if (unit === "sh") {
    const r = Math.round(v * 10) / 10;
    return Number.isInteger(r) ? String(r) : r.toFixed(1);
  }
  const n = Math.round(v);
  const abs = Math.abs(n).toLocaleString("en-US");
  return n < 0 ? `(${abs})` : abs;
}

function fmtAxis(v: number, unit: Unit): string {
  if (unit === "%") return `${(Math.round(v * 10) / 10).toFixed(1)}%`;
  if (unit === "eps") return v.toFixed(2);
  if (unit === "sh") {
    const r = Math.round(v * 10) / 10;
    return Number.isInteger(r) ? String(r) : r.toFixed(1);
  }
  return Math.round(v).toLocaleString("en-US");
}

function seriesStats(r: RowDef) {
  const nums = [...r.vals].reverse().map(toNum).filter((n): n is number => n !== null);
  if (nums.length < 2) return { totalChange: null as number | null, cagr: null as number | null };
  const first = nums[0], last = nums[nums.length - 1];
  const totalChange = first !== 0 ? ((last - first) / Math.abs(first)) * 100 : null;
  const years = (nums.length - 1) / 4;
  const cagr = first > 0 && last > 0 && years > 0 ? (Math.pow(last / first, 1 / years) - 1) * 100 : null;
  return { totalChange, cagr };
}

function domain(values: number[]): [number, number] {
  const vals = values.filter((v) => Number.isFinite(v));
  if (!vals.length) return [0, 1];
  let min = Math.min(0, ...vals);
  let max = Math.max(0, ...vals);
  if (min === max) max = min + 1;
  if (max > 0) max *= 1.08;
  if (min < 0) min *= 1.08;
  return [min, max];
}

function cell(v: string, kind?: Kind) {
  if (kind === "italic") return <Text as="span" italic tone="secondary" size="small">{v}</Text>;
  if (kind === "total") return <Text as="span" weight="semibold">{v}</Text>;
  return <Text as="span">{v}</Text>;
}

function labelCell(r: RowDef, selected: string[], onToggle: (label: string) => void) {
  const text =
    r.kind === "total" ? (
      <Text as="span" weight="semibold" truncate style={{ minWidth: 0, flex: 1 }}>{r.label}</Text>
    ) : r.kind === "italic" ? (
      <Text as="span" italic tone="secondary" size="small" truncate style={{ minWidth: 0, flex: 1 }}>{r.label}</Text>
    ) : (
      <Text as="span" truncate style={{ minWidth: 0, flex: 1 }}>{r.label}</Text>
    );
  if (r.plottable === false) return text;
  return (
    <Row gap={8} align="center" style={{ minWidth: 0, maxWidth: 360 }}>
      <Checkbox checked={selected.includes(r.label)} onChange={() => onToggle(r.label)} />
      {text}
    </Row>
  );
}

function FinTable({
  lead, defs, quarters, selected, onToggle,
}: {
  lead: string; defs: RowDef[]; quarters: string[]; selected: string[]; onToggle: (label: string) => void;
}) {
  const rows = defs.map((r) => [labelCell(r, selected, onToggle), ...r.vals.map((v) => cell(v, r.kind as Kind))]);
  return (
    <Table
      headers={["Line item", ...quarters]}
      rows={rows}
      columnAlign={colAlign(quarters)}
      framed
      striped
      style={{ minWidth: 1280, tableLayout: "fixed" }}
    />
  );
}

type PlotSeries = { name: string; unit: Unit; color: string; data: number[] };

function CombinedChart({ plot, chartType, categories }: { plot: PlotSeries[]; chartType: string; categories: string[] }) {
  const theme = useHostTheme();
  const cats = categories;
  const N = cats.length;
  if (!plot.length) return null;

  const leftUnit = plot[0].unit;
  const rightUnit = plot.find((p) => p.unit !== leftUnit)?.unit;
  const leftPlots = plot.filter((p) => p.unit === leftUnit);
  const rightPlots = plot.filter((p) => p.unit !== leftUnit);
  const hasRight = rightPlots.length > 0;
  const [lMin, lMax] = domain(leftPlots.flatMap((p) => p.data));
  const [rMin, rMax] = domain(rightPlots.flatMap((p) => p.data));

  const W = 1180, H = 420;
  const m = { top: 30, right: hasRight ? 72 : 28, bottom: 46, left: 72 };
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
    <svg viewBox={`0 0 ${W} ${H}`} role="img" style={{ width: "100%", height: "auto" }}>
      {ticks.map((t) => {
        const y = m.top + innerH * (1 - t / 4);
        const lv = lMin + (lMax - lMin) * (t / 4);
        const rv = rMin + (rMax - rMin) * (t / 4);
        return (
          <g key={t}>
            <line x1={m.left} y1={y} x2={m.left + innerW} y2={y} stroke={theme.stroke.tertiary} strokeWidth={1} />
            <text x={m.left - 8} y={y + 4} textAnchor="end" fontSize={11} fill={theme.text.tertiary}>{fmtAxis(lv, leftUnit)}</text>
            {hasRight && rightUnit && (
              <text x={m.left + innerW + 8} y={y + 4} textAnchor="start" fontSize={11} fill={theme.text.tertiary}>{fmtAxis(rv, rightUnit)}</text>
            )}
          </g>
        );
      })}
      {cats.map((c, i) => (
        <text key={c} x={xc(i)} y={H - m.bottom + 18} textAnchor="middle" fontSize={11} fill={theme.text.secondary}>{c}</text>
      ))}
      {chartType === "bar" &&
        plot.map((p, si) =>
          p.data.map((v, i) => {
            const yv = yFor(p, v);
            const base = baseFor(p);
            const x = m.left + slotW * i + (slotW - groupW) / 2 + si * barW;
            return (
              <g key={`${p.name}-${i}`}>
                <rect x={x} y={Math.min(base, yv)} width={barW * 0.86} height={Math.abs(base - yv)} fill={p.color} rx={1} />
                {showLabels && (
                  <text x={x + barW * 0.43} y={Math.min(base, yv) - 3} textAnchor="middle" fontSize={9} fill={theme.text.secondary}>{fmtVal(v, p.unit)}</text>
                )}
              </g>
            );
          }),
        )}
      {chartType === "line" &&
        plot.map((p) => (
          <g key={p.name}>
            <polyline points={p.data.map((v, i) => `${xc(i)},${yFor(p, v)}`).join(" ")} fill="none" stroke={p.color} strokeWidth={2} />
            {p.data.map((v, i) => (
              <g key={i}>
                <circle cx={xc(i)} cy={yFor(p, v)} r={3} fill={p.color} />
                {showLabels && (
                  <text x={xc(i)} y={yFor(p, v) - 7} textAnchor="middle" fontSize={9} fill={theme.text.secondary}>{fmtVal(v, p.unit)}</text>
                )}
              </g>
            ))}
          </g>
        ))}
      <text x={m.left} y={m.top - 12} fontSize={10} fill={theme.text.tertiary}>{UNIT_META[leftUnit].title} (left)</text>
      {hasRight && rightUnit && (
        <text x={m.left + innerW} y={m.top - 12} textAnchor="end" fontSize={10} fill={theme.text.tertiary}>{UNIT_META[rightUnit].title} (right)</text>
      )}
    </svg>
  );
}

function ChartArea({
  tabKey, rows, quarters, selected,
}: {
  tabKey: string; rows: RowDef[]; quarters: string[]; selected: string[];
}) {
  const [chartType, setChartType] = useCanvasState<string>(`${tabKey}.chartType`, "line");
  const theme = useHostTheme();
  const c = theme.category;
  const COLORS = [c.blue, c.orange, c.purple, c.green, c.pink, c.cyan, c.yellow, c.gray];
  const cats = chartCategories(quarters);
  const plotRows = rows.filter((r) => r.plottable !== false && selected.includes(r.label));
  const plot: PlotSeries[] = plotRows.map((r, i) => ({
    name: r.label,
    unit: unitOf(r),
    color: COLORS[i % COLORS.length],
    data: chartData(r, quarters),
  }));

  const dot = (color: string) => (
    <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 9, background: color, marginRight: 8, verticalAlign: "middle" }} />
  );
  const statRows = plotRows.map((r, i) => {
    const { totalChange, cagr } = seriesStats(r);
    return [
      <Text as="span">{dot(COLORS[i % COLORS.length])}{r.label}</Text>,
      cell(r.vals[0], r.kind as Kind),
      cell(fmtPct(totalChange)),
      cell(fmtPct(cagr)),
    ];
  });

  return (
    <Stack gap={16}>
      <Row gap={12} align="center">
        <H2>Chart</H2>
        <Select
          value={chartType}
          onChange={setChartType}
          options={[{ value: "line", label: "Line" }, { value: "bar", label: "Bar" }]}
          style={{ width: 120 }}
        />
        <Text tone="secondary" size="small">Tick rows in the table to plot. Dollars left axis; second unit on right.</Text>
      </Row>
      {plot.length === 0 ? (
        <Text tone="secondary">Select one or more rows in the table to chart them.</Text>
      ) : (
        <>
          <CombinedChart plot={plot} chartType={chartType} categories={cats} />
          <Table headers={["Selected metric", "Latest", "Total Change", "CAGR (ann.)"]} rows={statRows} columnAlign={["left", "right", "right", "right"]} framed />
        </>
      )}
    </Stack>
  );
}

function SectionTable({
  sec,
  quarters,
  selected,
  onToggle,
}: {
  sec: SectionBlock;
  quarters: string[];
  selected: string[];
  onToggle: (label: string) => void;
}) {
  return (
    <Stack gap={8}>
      <H3>{sec.title}</H3>
      <FinTable lead={sec.title} defs={sec.rows} quarters={quarters} selected={selected} onToggle={onToggle} />
    </Stack>
  );
}

function NoteLine({ text }: { text: string }) {
  return <Text size="small">{text}</Text>;
}

function StatementPanel({ tabKey, data, title }: { tabKey: string; data: StatementData; title: string }) {
  const defaultChart = data.summary.defaultChartRows?.length
    ? data.summary.defaultChartRows
    : data.statementType === "income"
      ? ["Total Revenues"]
      : [data.rows.find((r) => r.plottable !== false)?.label ?? data.rows[0]?.label].filter(Boolean);
  const [selected, setSelected] = useCanvasState<string[]>(`${tabKey}.chartRows`, defaultChart);
  const toggle = (label: string) =>
    setSelected((prev) => (prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]));
  const fiscal = data.summary.fiscalMapping ?? "";
  const subtitle = data.summary.subtitle ?? "";

  return (
    <Stack gap={20}>
      {subtitle ? <Text tone="secondary">{subtitle}</Text> : null}
      {fiscal ? <Text tone="secondary" size="small">{fiscal}</Text> : null}
      <H2>{title}</H2>
      {data.sections ? (
        data.sections.map((sec) => (
          <SectionTable
            sec={sec}
            quarters={data.quarters}
            selected={selected}
            onToggle={toggle}
          />
        ))
      ) : (
        <FinTable lead="Income Statement" defs={data.rows} quarters={data.quarters} selected={selected} onToggle={toggle} />
      )}
      <ChartArea tabKey={tabKey} rows={data.rows} quarters={data.quarters} selected={selected} />
      {data.notes.length > 0 ? (
        <Callout tone="neutral" title="Notes & methodology">
          <Stack gap={6}>
            {data.notes.map((n) => (
              <NoteLine text={n} />
            ))}
          </Stack>
        </Callout>
      ) : null}
    </Stack>
  );
}

export default function Financials() {
  const [tab, setTab] = useCanvasState<string>("activeTab", "__DEFAULT_TAB__");
  const active = TAB_DATA[tab];
  const stats = active?.summary.stats ?? [];

  return (
    <Stack gap={20} style={{ padding: 24, maxWidth: 1680 }}>
      <Stack gap={4}>
        <H1>__TICKER__ — Financial Statements</H1>
        <Text tone="secondary">__SUBTITLE__</Text>
      </Stack>
      <Row gap={8}>
__PILLS__
      </Row>
      <KeyMetricsRow
        snap={STOCK_SNAPSHOT}
        stats={stats}
        highlightsTitle={`${TAB_LABELS[tab] ?? tab} highlights`}
      />
__PANELS__
    </Stack>
  );
}
