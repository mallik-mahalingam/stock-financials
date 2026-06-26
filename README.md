# stock-financials

CLI and builders for SEC-sourced GAAP financial statements. Used by the Cursor skill at `skills/SKILL.md` (symlinked from `~/.cursor/skills/stock-financials/SKILL.md`).

**JSON is the source of truth.** Canvases are generated artifacts — edit JSON and re-run `sync`, never hand-edit canvas data.

## Primary command (ticker only)

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER
```

Checks all three statements, builds income from XBRL if stale, renders **`canvas/{ticker}-financials.canvas.tsx`** — a tabbed canvas (Income · Balance Sheet · Cash Flow). Tabs appear only for JSON that exists.

If balance-sheet or cash-flow JSON is missing, `sync` auto-builds from XBRL (`scripts/bs_xbrl.py` / `scripts/cf_xbrl.py`).

## Directory layout

```
~/src/stock-financials/
  README.md
  scripts/
    sec_financials.py               # CLI entry point
    income_xbrl.py                  # income from XBRL
    bs_xbrl.py                      # balance sheet (instant tags)
    cf_xbrl.py                      # cash flow (YTD → quarterly)
    statement_templates.py          # canonical Koyfin row order
    statement_align.py              # reorder legacy JSON to template
    number_format.py                # Koyfin-aligned display formatting
    render_financials_canvas.py     # combined tabbed canvas
    render_unified_canvas.py        # legacy single-statement render
  schema/
    income-v1.schema.json
    balance-sheet-v1.schema.json
    cash-flow-v1.schema.json
  templates/
    financials_canvas.template.tsx
    income_canvas.template.tsx
  json-data/
    {TICKER}-income.json
    {TICKER}-balance-sheet.json
    {TICKER}-cash-flow.json
  canvas/
    {ticker}-financials.canvas.tsx
  skills/
    SKILL.md
```

Cursor discovers the skill via symlink:

```bash
ln -s ~/src/stock-financials/skills ~/.cursor/skills/stock-financials
```

## CLI

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER      # primary
python3 ~/src/stock-financials/scripts/sec_financials.py check TICKER    # all statements
python3 ~/src/stock-financials/scripts/sec_financials.py build TICKER [income|balance-sheet|cash-flow]
python3 ~/src/stock-financials/scripts/sec_financials.py align TICKER [statement]
python3 ~/src/stock-financials/scripts/sec_financials.py render TICKER
python3 ~/src/stock-financials/scripts/sec_financials.py path TICKER
python3 ~/src/stock-financials/scripts/sec_financials.py edgar TICKER
python3 ~/src/stock-financials/scripts/sec_financials.py validate ~/src/stock-financials/json-data/TICKER-income.json
```

Legacy single income canvas: append `income` to `sync` or `render`.

Env: `SEC_USER_AGENT`, `STOCK_FINANCIALS_DIR`, `STOCK_FINANCIALS_CANVAS_DIR`.

## Schema

JSON schemas live under `schema/` (not in `json-data/`):

- `schema/income-v1.schema.json`
- `schema/balance-sheet-v1.schema.json`
- `schema/cash-flow-v1.schema.json`

Row order: `scripts/statement_templates.py` (union of AAPL / PANW / INTU Koyfin layouts). `validate` checks anchor-row coverage and relative row order.

**Display formatting** (`scripts/number_format.py`, Koyfin-aligned): USD millions as integers with commas; EPS always two decimals; shares one decimal when fractional (351.4) otherwise integer (813); margins and YoY % always one decimal (47.0%, +10.4%).

## Coverage validation

`validate FILE.json` checks structure plus **anchor rows** (must have data in all 12 columns):

| Statement | Anchor rows |
|-----------|-------------|
| income | Total Revenues, Consolidated Net Income |
| balance-sheet | Total Assets, Total Liabilities, Total Shareholders' Equity |
| cash-flow | Cash from Operating Activities, Net Change in Cash |

Section divider rows (`Assets`, `Operating Activities`, etc.) are intentionally blank. All-blank data rows are hidden in the canvas at render time. `sync TICKER` reports `missingColumns` when anchor gaps remain. Income auto-rebuilds from XBRL when gaps or staleness are detected.

Income Q4 derivation (when XBRL has no standalone quarterly tag): FY minus 9M YTD — Dec FY (Jan–Sep), Jan FY (Feb–Oct), Jul FY (Aug–Apr), **Sep/Oct FY** (auto-detected from 10-K + 9M 10-Q). Some filers (e.g. INTU) omit `CostOfRevenue` in XBRL — COGS* is derived from `CostsAndExpenses` minus operating expense components.

Cash flow quarterly columns: fiscal YTD flow minus prior-quarter YTD (same fiscal start). CapEx/outflows shown negative (Koyfin convention).

## Known limitations (SEC XBRL vs Koyfin)

**Source of truth is SEC EDGAR**, not Koyfin. Row order follows Koyfin’s standardized layout (`scripts/statement_templates.py`) for cross-ticker comparison; **values** come from XBRL tags and derivations below.

| Area | Behavior | vs Koyfin |
|------|----------|-----------|
| Income Q4 | FY 10-K − 9M YTD when no standalone quarterly tag (Dec / Jan / Jul / Sep-Oct FY) | Usually aligns; filer rounding may differ |
| COGS* | Derived when `CostOfRevenue` missing (e.g. INTU) | Aligns when derivation matches filing bridge |
| Operating profit check | Component bridge tolerates ±$75M (filers embed D&A differently) | Koyfin may show exact filing lines |
| Balance sheet — Other Receivables | Fallback tags (e.g. `NotesAndLoansReceivableNetCurrent`) | May differ slightly (e.g. PANW 591 vs 571) |
| Balance sheet — APIC | May use `CommonStocksIncludingAdditionalPaidInCapital` when APIC untagged | Common Stock row often blank |
| Cash flow — WC lines | YTD-difference on standard XBRL tags | **Section totals tie**; individual WC lines may differ |
| Cash flow — O+I+F vs ΔCash | Verified when FX/restricted-cash tags absent | Some filers fail on FX — see `verification.exceptions` |
| FCF section | FCF = Op CF + CapEx; NOPAT/Levered/Unlevered use **21% tax memo** | Koyfin uses proprietary models |
| Optional rows | Omitted when blank in all 12 quarters | Koyfin shows full template with dashes |

When `verification.exceptions` is non-empty, note it in the validation pack — do not claim full tie without checking.

## Workflows

**Income / balance sheet / cash flow** — automatic via XBRL: `build TICKER [statement]` or `sync TICKER` (auto-builds missing BS/CF).

**Legacy manual JSON** — if XBRL gaps remain, edit JSON per skill → `align TICKER` → `validate` → `sync TICKER`.

**Canvas in Cursor** — after `sync`, copy `canvas/{ticker}-financials.canvas.tsx` into the workspace `canvases/` folder (see `skills/SKILL.md`).

## Rules

- Never add ticker-specific build scripts — use `build TICKER [statement]`.
- Edit JSON, not `.tsx`; re-run `sync TICKER` to refresh the canvas.
- Row labels/order: see `scripts/statement_templates.py`; run `align TICKER` after manual edits.
