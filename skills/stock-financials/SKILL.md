---
name: stock-financials
description: >-
  Build standardized 12-quarter GAAP financial statements (income, balance sheet,
  cash flow) from SEC filings. JSON cache in ~/src/stock-financials/json-data; refresh from
  EDGAR when stale; render Cursor canvases via ~/src/stock-financials CLI.
  Always sync canvases to workspace and show clickable links in chat (never wait for user to ask).
  Use for /stock-financials, SEC-Income, SEC-BalanceSheet, SEC-CashFlow,
  quarterly P&L, balance sheet, cash flow, FCF, or assets/liabilities/equity history.
---

# Stock Financials

**Related:** multi-ticker peer comparison table → `skills/stock-summary/` (`stock-summary` skill).

One workflow for **three statement types**. User gives **ticker only** — agent runs all three. JSON is the source of truth; one **tabbed canvas** is the deliverable.

## Default command (ticker only)

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER
```

This command:
1. **Checks** income, balance-sheet, and cash-flow JSON vs EDGAR
2. **Builds income** from SEC XBRL if stale or missing; **auto-builds balance sheet / cash flow** from XBRL if JSON missing
3. **Renders** `canvas/{ticker}-financials.canvas.tsx` — tabbed canvas (Income · Balance Sheet · Cash Flow) from whatever JSON exists

If `missingJson` includes balance-sheet or cash-flow, **build those JSON files** (per sections below), validate, then **re-run `sync TICKER`**.

Do **not** ask the user which statement unless they explicitly want only one.

## Paths

| Item | Path |
|------|------|
| Combined canvas | `~/src/stock-financials/canvas/{ticker}-financials.canvas.tsx` |
| Income JSON | `~/src/stock-financials/json-data/{TICKER}-income.json` |
| Balance sheet JSON | `~/src/stock-financials/json-data/{TICKER}-balance-sheet.json` |
| Cash flow JSON | `~/src/stock-financials/json-data/{TICKER}-cash-flow.json` |
| Income schema | `~/src/stock-financials/schema/income-v1.schema.json` |
| Row order (canonical) | `~/src/stock-financials/scripts/statement_templates.py` |

All under `~/src/stock-financials/`. See `~/src/stock-financials/README.md`.

Ticker **uppercase** in JSON filenames, **lowercase** in canvas filenames.

---

## Shared architecture

```
sync TICKER ──► build income if stale ──► build BS/CF JSON if missing ──► re-sync ──► tabbed canvas ──► validation pack
```

| Item | Path |
|------|------|
| JSON data | `~/src/stock-financials/json-data/{TICKER}-{statement}.json` |
| Schemas | `~/src/stock-financials/schema/` (with source — not in json-data) |
| CLI | `~/src/stock-financials/scripts/sec_financials.py` |
| Combined renderer | `~/src/stock-financials/scripts/render_financials_canvas.py` |
| Income XBRL builder | `~/src/stock-financials/scripts/income_xbrl.py` (generic — **never** add `build_{ticker}.py`) |
| Balance sheet XBRL builder | `~/src/stock-financials/scripts/bs_xbrl.py` |
| Cash flow XBRL builder | `~/src/stock-financials/scripts/cf_xbrl.py` |
| Stock snapshot (Yahoo) | `~/src/stock-financials/scripts/stock_snapshot.py` |
| Row templates / align | `scripts/statement_templates.py`, `scripts/statement_align.py` |
| Canvas templates | `~/src/stock-financials/templates/` |
| Generated canvases | `~/src/stock-financials/canvas/` |

Env: `STOCK_FINANCIALS_DIR` (JSON root), `STOCK_FINANCIALS_CANVAS_DIR` (canvas output), `SEC_USER_AGENT` (required by SEC EDGAR API).

### CLI

```bash
# Primary — ticker only (checks all 3, builds income, renders tabbed canvas)
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER

# Check all statements (omit statement arg)
python3 ~/src/stock-financials/scripts/sec_financials.py check TICKER

# Build any statement from SEC XBRL
python3 ~/src/stock-financials/scripts/sec_financials.py build TICKER [income|balance-sheet|cash-flow]

# Reorder rows to canonical template (after manual JSON edits)
python3 ~/src/stock-financials/scripts/sec_financials.py align TICKER [statement]

# List JSON paths for all statements
python3 ~/src/stock-financials/scripts/sec_financials.py path TICKER

# Validate a JSON file (structure + 12-quarter anchor-row coverage)
python3 ~/src/stock-financials/scripts/sec_financials.py validate ~/src/stock-financials/json-data/TICKER-income.json

# Re-render tabbed canvas without rebuilding
python3 ~/src/stock-financials/scripts/sec_financials.py render TICKER

# Recent EDGAR filings
python3 ~/src/stock-financials/scripts/sec_financials.py edgar TICKER

# Current stock snapshot (Yahoo Finance) — also included in sync JSON output
python3 ~/src/stock-financials/scripts/sec_financials.py snapshot TICKER
python3 ~/src/stock-financials/scripts/sec_financials.py snapshot TICKER --markdown
```

Requires **`yfinance`** (`pip install yfinance`). One-time setup installs it if missing.

Legacy single-statement canvas (optional): append `income` to `sync` or `render`.

**Hard rule:** income refresh via `build` / `sync` only — never `build_{ticker}.py`. **Edit JSON, not `.tsx`**, then re-run `sync TICKER`.

### JSON document shape (all types)

Every file shares this skeleton; `statementType` discriminates:

```json
{
  "schemaVersion": 1,
  "statementType": "income | balance-sheet | cash-flow",
  "ticker": "MSFT",
  "companyName": "...",
  "currency": "USD",
  "unit": "millions",
  "fiscalYearEndMonth": 6,
  "updatedAt": "ISO-8601",
  "edgar": {
    "cik": "0000789019",
    "latestQuarterlyFilingDate": "2026-04-29",
    "latestQuarterlyForm": "10-Q",
    "latestQuarterlyAccession": "...",
    "latestQuarterlyUrl": "https://www.sec.gov/..."
  },
  "quarters": [
    { "label": "Mar '26", "periodEnd": "2026-03-31", "fiscalLabel": "Q3 FY26", "source": { "form": "10-Q", "filingDate": "...", "url": "..." } }
  ],
  "rows": [
    { "label": "...", "values": ["..."], "kind": "normal|italic|total", "unit": "$|%|eps|sh", "plottable": true, "derived": false }
  ],
  "summary": { "subtitle": "...", "fiscalMapping": "...", "stats": [], "defaultChartRows": [] },
  "notes": ["..."],
  "verification": { }
}
```

`rows[].values.length` must equal `quarters.length` (always **12**). Display strings: `"8,558"`, `"47.0%"`, `"—"`, trailing `*` for derived.

### Coverage validation (mandatory)

After building or editing JSON, run `validate` on each file. The CLI checks **anchor rows** — not section divider rows (e.g. `Assets`, `Operating Activities`), which are intentionally blank.

| Statement | Anchor rows (every column must have data) |
|-----------|---------------------------------------------|
| income | Total Revenues, Consolidated Net Income |
| balance-sheet | Total Assets, Total Liabilities, Total Shareholders' Equity |
| cash-flow | Cash from Operating Activities, Net Change in Cash |

`sync TICKER` reports `missingColumns` when anchor gaps remain. For income, `check`/`sync` auto-rebuilds from XBRL when gaps or staleness are detected.

---

## Shared canvas rules

All three statements use the canvas skill conventions:

1. **12 quarter columns**, most recent first in the table; chart time axis **oldest → newest** (reverse column order).
2. **One unified `Table` per statement** — section titles (Assets, Operating Activities, etc.) are **bold divider rows inside the table**, not separate tables (separate tables misalign columns).
3. Shared header: `["Line item", ...QUARTERS]`, `tableLayout: "fixed"`, label column **360px**, `framed` + `striped`.
4. **Key metrics row** (below tab pills, above statement body) — two equal-width framed tables side by side:
   - **Left:** `{Income|Balance Sheet|Cash Flow} highlights` — 2-column table (`Metric | Value`) from JSON `summary.stats`; colored values; updates with active tab.
   - **Right:** **Stock snapshot** (Yahoo Finance via `yfinance`, embedded at render) — **3-column table** `Metric | (middle) | Value`:
     - **Price row:** `Price` · middle: `+15.7% from 52W low (+$23.31) · -44.8% from 52W high (-$139.14)` (green/red) · Value: **$372.97** (accent, right-aligned).
     - Other rows: 52-week low/high, market cap, P/E — empty middle cell; value right-aligned.
   - **`sync TICKER` always re-renders** the canvas from `templates/financials_canvas.template.tsx` (never hand-edit `canvas/*.canvas.tsx`). After template or renderer changes, re-run `sync TICKER` and **copy** to workspace `canvases/` (see below). `STOCK_SNAPSHOT = null` → install `yfinance` and sync again.
5. **Interactive chart** below: custom inline-SVG **`CombinedChart`** (not SDK `BarChart`/`LineChart`):
   - One converged plot, dual axes ($ left, % or second unit right)
   - Line / Bar `Select`, value labels with **full numbers (no `k`)**
   - Stats table: Latest, Total Change %, CAGR (`years = (points−1)/4`)
   - `useCanvasState` for selection + chart type
6. **Checkbox** on each plottable row label for chart selection.

Templates: `~/src/stock-financials/templates/financials_canvas.template.tsx` (combined tabbed canvas). Legacy single income: `income_canvas.template.tsx`.

---

## Always show canvases (mandatory)

**Every run must end with clickable canvas links in chat.** The user must never need to ask "show the canvases."

After render, **always**:

1. **Sync** generated files from `~/src/stock-financials/canvas/` to the **active workspace canvases folder** (Cursor only opens canvases from here):

```bash
# Resolve slug from Workspace Path (e.g. /Users/mallik70/src/analysis → Users-mallik70-src-analysis)
SLUG=$(python3 -c "import os; p=os.environ.get('WORKSPACE_PATH','').lstrip('/'); print(p.replace('/', '-'))")
DEST=~/.cursor/projects/"$SLUG"/canvases
mkdir -p "$DEST"
# Combined tabbed canvas (lowercase ticker)
cp ~/src/stock-financials/canvas/TICKER-financials.canvas.tsx "$DEST/"
```

Replace `TICKER` with the lowercase ticker (e.g. `msft`).

If `WORKSPACE_PATH` is unavailable, derive slug from the workspace path in user_info the same way (strip leading `/`, replace `/` with `-`).

2. **Show the Yahoo Finance snapshot table in chat** (see **Stock snapshot** below) — then **Canvas** links (canvas shows the same data in paired Key metrics tables):

| Canvas | Link |
|--------|------|
| Financials (Income · Balance Sheet · Cash Flow tabs) | `[{ticker}-financials.canvas.tsx](file:///…/canvases/{ticker}-financials.canvas.tsx)` |

Use the full absolute path. Tabs appear only for JSON that exists.

3. **Then** append the validation pack (sources, spot-check, verification flags). Do not bury canvas links below the validation pack.

4. If render failed or JSON is missing, say so — do not omit the canvases section silently; explain which files are unavailable.

**Never** finish a stock-financials run with only JSON paths or "canvases are at …" without clickable links.

---

## Stock snapshot (mandatory)

After `sync TICKER`:

**Canvas** — the paired **Key metrics row** (see Shared canvas rules §4) always includes **Stock snapshot** on the right when Yahoo data loads. The price row uses **three columns** (label · 52W deltas in the middle · price in Value). Highlights on the left update with the active tab. **`sync TICKER` regenerates the canvas** — then copy to workspace `canvases/` and link `{ticker}-financials.canvas.tsx` beside chat (Cursor only opens canvases from that folder).

**Chat** — paste `markdownTable` from sync JSON (or `snapshot TICKER --markdown`) before canvas links:

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py snapshot TICKER --markdown
```

If `snapshotError` appears, run `pip install yfinance` and retry.

| Metric | Value |
|--------|-------|
| Current price | +15.7% from 52W low (+$23.31) · -44.8% from 52W high (-$139.14) · **$372.97** |
| 52-week low | $349.20 |
| 52-week high | $555.45 |
| Market cap | $2.77T |
| P/E (trailing) | 22.2x |

Include the table header line with company name, ticker, source, and as-of timestamp from `markdownTable`.

**Never** finish a stock-financials run without this snapshot when Yahoo data is available, and **always** link the canvas so the user sees the same metrics rendered in the paired tables.

---

# Income statement

## Source

`build income` uses SEC **XBRL company facts** (10-Q/10-K). Three-month flow tags; Q4 derived as **FY minus 9M YTD** when no standalone quarterly tag exists:

| Fiscal year-end | Q4 period-end | YTD9 window |
|-----------------|---------------|-------------|
| December | Dec 31 | Jan 1 – Sep 30 |
| January | Jan 31 | Feb 1 – Oct 31 (prior year) |
| July | Jul 31 | Aug 1 – Apr 30 |
| September / October | last Sat in Sep (10-K) | auto: FY 10-K − 9M 10-Q same fiscal start |

Quarters auto-discovered from EDGAR submissions (12 period-ends, most recent first). **July FY filers** (e.g. PANW, INTU) previously showed blank Jul columns until Q4 derivation was applied — re-run `build TICKER` or `sync TICKER` after any income_xbrl fix.

**COGS / gross profit gaps:** Some filers (e.g. INTU) report cost of revenue in the 10-Q but do not tag `CostOfRevenue` in XBRL. Builder derives cost of sales* as `CostsAndExpenses − operating expense components` and marks derived cells with `*`.

**Revenue scope (fintech filers):** Some filers (e.g. MELI) tag `Revenues` as *net revenues and financial income* while `CostOfGoodsAndServicesSold` is *cost of net revenues and financial expenses*. The builder **must** pair revenue + COGS to the SEC **`GrossProfit` XBRL tag** — never use contract-only revenue (`RevenueFromContractWithCustomerExcludingAssessedTax`) with broad COGS. Build/validate **fail** when computed gross profit diverges from tagged `GrossProfit` by >$1M.

## Verification

- Gross Profit = Revenue − Cost of Sales
- **Gross Profit matches SEC `GrossProfit` XBRL tag** (`grossProfitMatchesXbrlTag`) — mandatory when tag exists
- Operating Profit ties to reported income from operations
- Pretax − Tax = Net Income

Set in JSON `verification`: `grossProfitTies`, `grossProfitMatchesXbrlTag`, `operatingProfitTies`, `pretaxMinusTaxTiesNetIncome`.

## Row mapping (order)

Canonical row order is **`scripts/statement_templates.py`** (`INCOME_ROWS`) — union of AAPL / PANW / INTU reference layouts. Optional rows omitted when blank in all 12 quarters.

| Row | Maps from |
|-----|-----------|
| Total Revenues | Total net revenue |
| Total Revenues %Chg (YoY) | YoY % vs same quarter prior year (column *i* vs *i*+4) |
| Total Revenues %Chg (QoQ) | QoQ % vs prior quarter (column *i* vs *i*+1; newest column has no prior quarter) |
| Cost of Sales | Total cost of revenue (or derived*) |
| Gross Profit / Gross Profit Margin | derived |
| SG&A, **D&A Expenses**, R&D, Other Operating Expenses | reported buckets |
| Operating Profit / Operating Margin | income from operations / derived |
| **Interest and Investment Income**, **Interest Expense**, Non-Operating Income | reported |
| Pretax, Tax, Net Income, **Discontinued Ops** | reported |
| Basic/Diluted EPS, WASO, **Shares Outstanding** | per-share / shares |
| **EBITDA** | Operating Profit + D&A (memo line) |
| Effective Tax Rate | Tax ÷ Pretax |

Units: `"$"`, `"%"`, `"eps"`, `"sh"`. Mark derived cells with `*` in display values.

## Render

Included in `sync TICKER`. Tabs appear only for JSON that exists.

## Validation pack (income)

1. Sources — URL per quarter (note prior-year column backfills)
2. Fiscal mapping
3. Spot-check — latest + mid-window: revenue, operating income, net income, diluted EPS
4. Subtotal verification (step above)
5. **`grossProfitMatchesXbrlTag`** — if false, rebuild income; do not analyze margins from stale JSON
6. All `*` / derived cells
7. Copy-paste prompt:

```
You are auditing a GAAP income statement built from SEC XBRL company facts (10-Q/10-K).
Compare reported quarterly figures to canvas values. Flag mismatch > $0.1M or > $0.01 EPS.
Flag derived rows not marked derived.
Sources: [URLs]  Spot-check: [table]  Mapping: [notes]
```

---

# Balance sheet

## Source

`build balance-sheet` uses SEC **XBRL instant tags** (10-Q/10-K). Splits A/R vs Other Receivables when tagged; derives Total Cash*, Total Trade Receivables*, Total LT Liabilities* when needed.

Manual Exhibit 99.1 still valid when XBRL gaps remain.

## Verification

- Total Assets = Total Liabilities + Total Shareholders' Equity (each quarter)
- Subtotals tie to components

JSON `verification`: `assetsEqualsLiabilitiesPlusEquity`, `exceptions[]`.

## Row mapping

See **`BALANCE_SHEET_ROWS`** in `scripts/statement_templates.py` — Assets (Cash, ST investments, A/R, Other receivables, Inventories, …), Liabilities (A/P, Accrued, ST debt, Unearned revenue, Leases, …), Equity (Treasury stock, APIC, AOCI, Retained earnings, …).

## Canvas

Sectioned tables embedded in the tabbed `{ticker}-financials.canvas.tsx`. Write JSON, validate, re-run `sync TICKER`.

## Validation pack (balance sheet)

Spot-check: Total Assets, Total Liabilities, Total Equity, Cash — latest + mid-window quarter-**end**. Confirm accounting equation each quarter. Prompt mentions period-end columns, not "Three Months Ended."

---

# Cash flow statement

## Source

`build cash-flow` uses SEC **XBRL flow tags**. Standalone quarters derived from **fiscal YTD** (current YTD − prior-quarter YTD, same fiscal start). Q4 from 10-K when needed.

Manual Exhibit 99.1 still valid when XBRL gaps remain.

## Verification

- Section totals match filing
- Operating + Investing + Financing (+ FX if disclosed) ≈ Net Change in Cash
- Free Cash Flow* = Operating CF − |CapEx|

## Row mapping

See **`CASH_FLOW_ROWS`** in `scripts/statement_templates.py` — Operating (Net income, D&A, SBC, WC changes including **Accrued expenses** and **Unearned revenue**), Investing, Financing (ST/LT debt nets, share issuance/repurchase, dividends), Free Cash Flow section.

Preserve filing sign convention (outflows negative). Map filer-specific lines before `Other *` catch-alls.

## Canvas

Sectioned tables embedded in the tabbed `{ticker}-financials.canvas.tsx`. Write JSON, validate, re-run `sync TICKER`.

## Validation pack (cash flow)

Spot-check: Operating, Investing, Financing, Net Change in Cash, CapEx. Standalone quarterly columns only. Note all FCF-section rows as derived.

---

# End-to-end checklist

```
- [ ] sync TICKER
- [ ] show Yahoo Finance snapshot table in chat (from sync JSON or snapshot --markdown)
- [ ] validate each JSON (anchor rows filled, 12 quarters; income `grossProfitMatchesXbrlTag` must be true)
- [ ] if missingJson: build balance-sheet and/or cash-flow JSON → validate → sync TICKER again
- [ ] if missingColumns in sync output: fix gaps → validate → sync again
- [ ] sync TICKER (re-renders canvas from template + embeds Yahoo snapshot)
- [ ] copy `canvas/{ticker}-financials.canvas.tsx` → workspace `canvases/` and link in chat (Key metrics row + 3-col stock snapshot visible)
- [ ] append validation pack (all three statements that have JSON)
```

Do not claim "verified" without running the arithmetic checks for each statement type present.

---

# Known limitations (SEC XBRL)

**SEC EDGAR is source of truth.** Row order follows `scripts/statement_templates.py`; values are XBRL-derived.

- **Revenue scope mismatch**: fintech filers may tag `Revenues` broader than contract revenue; builder pairs to `GrossProfit` XBRL tag (see income section).
- **WC line items** (cash flow): quarterly = fiscal YTD − prior YTD; individual lines may differ from vendor displays while **Operating / Investing / Financing totals** tie to SEC.
- **COGS / gross profit***: derived when filer omits `CostOfRevenue` (INTU); cells marked `*`.
- **Other receivables / APIC**: filer-specific XBRL tag fallbacks; subtotals still tie.
- **FCF section**: FCF* = Op CF + CapEx; NOPAT* / Levered* / Unlevered* use 21% tax — illustrative only.
- **CF verification**: O+I+F ≈ ΔCash may fail when FX or restricted-cash effects exist — check `verification.exceptions` (e.g. INTU).
- **Operating profit bridge**: ±$75M tolerance when components don’t fully reconcile in XBRL.
- **Optional rows**: omitted when all-blank across 12 quarters.
- **Audit**: flag mismatches vs **SEC filing** when tag mapping differs.

