---
name: stock-summary
description: >-
  Build an interactive peer-comparison stock summary table (returns, price vs
  range, short interest, EPS growth, forward P/E, ROE, ROIC) as a Cursor canvas
  for any user-supplied ticker list. Sortable columns and row highlight included.
  Use for stock summary, peer heatmap, ecosystem comparison, stock map, or
  comparative snapshot across N symbols.
---

# Stock Summary

Build a compact, ConsensusGurus-style **peer comparison table** as a Cursor canvas for **any ticker list** the user provides.

## Prerequisites

```bash
pip install yfinance pandas
```

Same dependency as `~/src/stock-financials/requirements.txt` (`yfinance`).

Read the canvas skill first: `~/.cursor/skills-cursor/canvas/SKILL.md`

## Inputs (from user)

| Input | Required | Notes |
|-------|----------|-------|
| Ticker list | Yes | Any count; uppercase symbols; skip ETFs if fundamentals are needed |
| Title | Yes | Shown in table header (e.g. sector or theme label) |
| Output slug | No | Kebab-case basename; default = slugified title |

Do **not** hard-code tickers in the skill or scripts. Always use the symbols the user requests.

**Layout:** `skills/` holds agent instructions (`SKILL.md`) only. Runnable code lives in `~/src/stock-financials/scripts/` alongside `sec_financials.py`.

## Paths

| Item | Path |
|------|------|
| CLI scripts | `~/src/stock-financials/scripts/` (`build_summary.py`, `fetch_summary.py`, `render_summary_canvas.py`) |
| Skill doc only | `~/src/stock-financials/skills/stock-summary/SKILL.md` |
| Cached JSON | `~/src/stock-financials/summary-data/{slug}.json` |
| Generated canvas | `~/src/stock-financials/canvas/{slug}.canvas.tsx` |
| Workspace canvas (IDE) | `~/.cursor/projects/<workspace-slug>/canvases/{slug}.canvas.tsx` |

## One-command build (preferred)

```bash
python3 ~/src/stock-financials/scripts/build_summary.py \
  SYMBOL1 SYMBOL2 SYMBOL3 \
  --title "Your Comparison Title"
```

Optional flags:

- `--slug custom-name` — override output basename
- `--allow-gaps` — render when some symbols lack fundamentals (ETFs, ADRs with sparse Yahoo data)

Exit code `2` + `gaps` JSON on stderr when fields are missing. Report gaps to the user; offer to drop symbols or use `--allow-gaps`.

## Step-by-step (when debugging)

**1. Fetch metrics (Yahoo Finance via yfinance)**

```bash
python3 ~/src/stock-financials/scripts/fetch_summary.py \
  SYMBOL1 SYMBOL2 ... \
  -o ~/src/stock-financials/summary-data/{slug}.json
```

**2. Render canvas**

```bash
python3 ~/src/stock-financials/scripts/render_summary_canvas.py \
  ~/src/stock-financials/summary-data/{slug}.json \
  -o ~/src/stock-financials/canvas/{slug}.canvas.tsx \
  --title "Your Comparison Title"
```

**3. Sync to workspace** (Cursor only opens canvases from the project `canvases/` folder)

```bash
SLUG=$(python3 -c "import os; p=os.environ.get('WORKSPACE_PATH','').lstrip('/'); print(p.replace('/', '-'))")
mkdir -p ~/.cursor/projects/"$SLUG"/canvases
cp ~/src/stock-financials/canvas/{slug}.canvas.tsx ~/.cursor/projects/"$SLUG"/canvases/
```

If `WORKSPACE_PATH` is unavailable, derive the slug from the active workspace path the same way (strip leading `/`, replace `/` with `-`).

**4. Link in chat** — full absolute path to the workspace `.canvas.tsx` file.

## Data source policy

1. **Primary:** Yahoo Finance (`yfinance`).
2. **Never fabricate** missing metrics.
3. If `gaps` is non-empty, tell the user which symbols/fields are missing before rendering (unless user accepts `--allow-gaps`).
4. **Schwab MCP fallback** (price/history only): `schwab_get_quotes` + `schwab_get_price_history` when Yahoo history fails. Schwab does **not** provide short interest, ROE, ROIC, or forward estimates.

ETFs and funds often lack short interest, EPS estimates, ROE, and ROIC on Yahoo — exclude them or use `--allow-gaps` and leave those cells at zero.

## Table columns

| Group | Metrics |
|-------|---------|
| Identity | Company, Ticker, Mkt Cap ($MM) |
| Stock Return | YTD, 1M, 3M, 6M, 12M |
| Price vs Range | % from ATH, % from 52W low, % upside to 52W high |
| Short Interest | Now (% float), 3M Δ (bps) |
| EPS Growth | Current FY, Next FY (Yahoo `earnings_estimate`) |
| P/E Ratio | Current FY, Next FY (price ÷ consensus EPS) |
| Returns | ROE, ROIC |

### Metric definitions

- **% from ATH** — `(price / allTimeHigh − 1) × 100`
- **% from 52W low** — `(price / fiftyTwoWeekLow − 1) × 100`
- **% to 52W high** — `(fiftyTwoWeekHigh / price − 1) × 100` (lower = closer to high)
- **Short 3M Δ** — change in short % of float vs prior month, basis points
- **ROIC** — NOPAT ÷ (Equity + Debt − Cash) from latest Yahoo statements
- **Returns** — drop NaN rows from 1Y history before computing returns

## Visual layout

- **Compact** — 10px font, 2–3px padding, tight columns
- **Black header** — two rows (group labels + column labels), white bold text
- **Dark borders** — `1px solid #1a1a1a`
- **White body** for identity, EPS, P/E, and Returns columns
- **Negatives** — parentheses: `(25%)` not `-25%`
- **Mkt Cap** — `$248,563` (raw $MM with commas)
- **Footer** — source + as-of date

## Heat coloring

**Colored:** Stock Return, Price vs Range, Short Interest  
**Plain white:** EPS Growth, P/E Ratio, Returns (ROE/ROIC)

Peer-rank **7-stop palette** per column (do **not** use `useHostTheme` for heat fills):

Worst → best: `#9C0006` → `#F8696B` → `#FFC7CE` → `#FFEB84` → `#C6EFCE` → `#63BE7B` → `#006100`

- Map each peer rank to the nearest stop (best = dark green, worst = dark red)
- White text on dark red/green; dark text on yellow/light cells
- `% to 52W high` and short interest: **lower is better**

Heat colors are computed across the **full peer set** — sorting does not change rank colors.

## Interactivity (built into canvas)

- **Sort** — click column header; toggle asc/desc; active column shows ▲/▼
- **Row highlight** — click any cell in a row; click again to clear
- State persists via `useCanvasState` (sort + selection)

## End-to-end checklist

```
- [ ] Collect ticker list + title from user
- [ ] Run build_summary.py (or fetch + render)
- [ ] If gaps: report missing fields; drop symbols or --allow-gaps
- [ ] Copy canvas to workspace canvases/
- [ ] Link canvas in chat (absolute path)
- [ ] Mention: click headers to sort, click row to highlight
```

## Trigger phrases

- `/stock-summary` with a ticker list
- "build a stock summary for these symbols"
- "peer comparison heatmap / map / table"
- "ecosystem snapshot for N stocks"
