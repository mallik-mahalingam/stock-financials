# stock-financials

12-quarter GAAP financial statements (income, balance sheet, cash flow) from SEC XBRL. JSON cache + tabbed Cursor canvases.

**JSON is the source of truth.** Canvases are generated — never hand-edit `.tsx`; re-run `sync`.

---

## Install

### 1. Clone / copy the repo

```bash
git clone <your-remote> ~/src/stock-financials
cd ~/src/stock-financials
```

Or use an existing checkout at `~/src/stock-financials`.

### 2. Requirements

- **Python 3.10+** (stdlib only for the main XBRL pipeline — no `pip install` required)
- Network access to [SEC EDGAR](https://www.sec.gov/edgar/search/)

### 3. SEC User-Agent (required)

EDGAR blocks generic clients. Set your name and email:

```bash
export SEC_USER_AGENT="YourName stock-financials research you@example.com"
```

Add to `~/.zshrc` or `~/.bashrc` to persist.

### 4. Cursor skill (optional)

```bash
ln -sf ~/src/stock-financials/skills ~/.cursor/skills/stock-financials
```

Skill file: `skills/SKILL.md`. Triggers: `/stock-financials`, `SEC-Income`, `SEC-BalanceSheet`, `SEC-CashFlow`.

### 5. Generated output directories

`json-data/` and `canvas/` are gitignored (see `.gitignore`). They are created on first `sync`:

```
json-data/{TICKER}-income.json
json-data/{TICKER}-balance-sheet.json
json-data/{TICKER}-cash-flow.json
canvas/{ticker}-financials.canvas.tsx
```

---

## Quick start

Build all three statements and render the tabbed canvas for Palo Alto Networks:

```bash
export SEC_USER_AGENT="YourName stock-financials research you@example.com"

python3 ~/src/stock-financials/scripts/sec_financials.py sync PANW
```

Output (abbreviated):

```json
{
  "ticker": "PANW",
  "canvasPath": "/Users/you/src/stock-financials/canvas/panw-financials.canvas.tsx",
  "available": ["income", "balance-sheet", "cash-flow"],
  "missingJson": [],
  "checks": { "...": "JSON is current" }
}
```

Open in Cursor — copy the canvas into your workspace if Glass should show it beside chat:

```bash
cp ~/src/stock-financials/canvas/panw-financials.canvas.tsx \
   ~/.cursor/projects/<workspace>/canvases/
```

---

## Examples

Set a shell alias to shorten commands:

```bash
alias sf='python3 ~/src/stock-financials/scripts/sec_financials.py'
export SEC_USER_AGENT="YourName stock-financials research you@example.com"
```

### Sync (primary — do this first)

Checks EDGAR staleness, rebuilds income if needed, auto-builds missing BS/CF from XBRL, renders tabbed canvas.

```bash
sf sync INTU
sf sync AAPL
sf sync DDOG
```

Custom canvas output directory:

```bash
sf sync PANW --canvas-dir ~/.cursor/projects/Users-you-src-analysis/canvases
```

### Check without rebuilding

See whether JSON is current vs latest 10-Q on EDGAR:

```bash
sf check PANW              # all three statements
sf check PANW income       # income only
```

### Build individual statements

Force rebuild from SEC XBRL company facts:

```bash
sf build PANW                    # all three
sf build PANW income
sf build PANW balance-sheet
sf build PANW cash-flow
```

### Validate JSON

```bash
sf validate ~/src/stock-financials/json-data/PANW-income.json
sf validate ~/src/stock-financials/json-data/PANW-balance-sheet.json
sf validate ~/src/stock-financials/json-data/PANW-cash-flow.json
```

Prints `OK` or lists anchor-row / row-order errors.

### Re-render canvas (JSON unchanged)

```bash
sf render PANW
sf render PANW --canvas-dir ./canvas
```

### Align row order after manual JSON edits

```bash
sf align PANW
sf align PANW income
```

### Paths and EDGAR links

```bash
sf path PANW                 # all JSON paths
sf path PANW income

sf edgar PANW                 # recent 10-Q / 10-K filing URLs
sf edgar PANW --limit 12
```

### Legacy single-tab income canvas

```bash
sf sync MSFT income
sf render MSFT income --canvas-dir ./canvas
```

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SEC_USER_AGENT` | *(required)* | EDGAR API identity string |
| `STOCK_FINANCIALS_DIR` | `{repo}/json-data` | JSON output root |
| `STOCK_FINANCIALS_CANVAS_DIR` | `{repo}/canvas` | Canvas output root |

Example — store JSON outside the repo:

```bash
export STOCK_FINANCIALS_DIR=~/stock-financials-cache
export STOCK_FINANCIALS_CANVAS_DIR=~/.cursor/projects/my-workspace/canvases
sf sync PANW
```

---

## Directory layout

```
~/src/stock-financials/
  README.md
  .gitignore                      # ignores json-data/* and canvas/*
  scripts/
    sec_financials.py             # CLI entry point
    income_xbrl.py                # income from XBRL
    bs_xbrl.py                      # balance sheet (instant tags)
    cf_xbrl.py                      # cash flow (YTD → quarterly)
    statement_templates.py          # canonical row order
    statement_align.py
    number_format.py                # display formatting rules
    render_financials_canvas.py     # tabbed canvas renderer
    render_unified_canvas.py        # legacy single-statement render
  schema/
    income-v1.schema.json
    balance-sheet-v1.schema.json
    cash-flow-v1.schema.json
  templates/
    financials_canvas.template.tsx
    income_canvas.template.tsx
  json-data/                      # gitignored — generated JSON
  canvas/                         # gitignored — generated canvases
  skills/
    SKILL.md                        # Cursor agent skill
```

---

## Display formatting

Display rules in `scripts/number_format.py`:

| Type | Format |
|------|--------|
| USD millions | Integer + commas: `2,257`, `(183)` |
| EPS | Always 2 decimals: `0.76` |
| Shares (millions) | 1 decimal when fractional: `351.4`; else integer: `813` |
| Margins / YoY % | 1 decimal: `47.0%`, `+10.4%` |

Derived values marked with `*` in JSON display strings.

---

## Validation

`validate` checks schema, 12-quarter column alignment, anchor-row coverage, and row order vs `statement_templates.py`.

| Statement | Anchor rows (must be populated in all 12 columns) |
|-----------|---------------------------------------------------|
| income | Total Revenues, Consolidated Net Income |
| balance-sheet | Total Assets, Total Liabilities, Total Shareholders' Equity |
| cash-flow | Cash from Operating Activities, Net Change in Cash |

`sync` reports `missingColumns` when anchors have gaps. Section divider rows (`Assets`, `Operating Activities`, …) are intentionally blank.

---

## Workflows

| Goal | Command |
|------|---------|
| Fresh ticker, all statements | `sf sync TICKER` |
| EDGAR filed new 10-Q | `sf sync TICKER` (rebuilds if stale) |
| Fix one statement only | `sf build TICKER balance-sheet` then `sf sync TICKER` |
| Manual JSON edit | edit `json-data/` → `sf align TICKER` → `sf validate …` → `sf sync TICKER` |
| Canvas only refresh | `sf render TICKER` |

---

## Known limitations (SEC XBRL)

**Source of truth is SEC EDGAR.** Row order follows the canonical templates in `statement_templates.py`; values come from XBRL tags and derivations.

| Area | Notes |
|------|-------|
| Income Q4 | FY 10-K − 9M YTD when no standalone quarterly tag |
| COGS* | Derived when `CostOfRevenue` missing (e.g. INTU) |
| Cash flow WC lines | Section totals tie; individual WC lines may differ |
| FCF memo lines | NOPAT / Levered / Unlevered use 21% tax — illustrative only |
| Optional rows | Omitted when blank in all 12 quarters |

See `skills/SKILL.md` for validation packs and agent workflow details.

---

## Rules

- Never add ticker-specific build scripts — use `build TICKER [statement]`.
- Edit JSON, not `.tsx`; re-run `sync TICKER` to refresh the canvas.
- Row labels/order: `scripts/statement_templates.py`; run `align TICKER` after manual edits.
