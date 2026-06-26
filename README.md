# Stock Financials

See **Income**, **Balance Sheet**, and **Cash Flow** for any US stock — last **12 quarters**, from official **SEC filings**, in a tabbed interactive table.

Works with **Cursor**, **Claude Code**, or on its own — no coding required.

---

## At a glance

| | One-time setup | Day-to-day use |
|---|----------------|----------------|
| **When** | Once, before your first stock | Every time you want financials |
| **What you do** | Download the folder → double-click **Setup.command** | **Ask your AI assistant** (or use a shortcut below) |
| **How long** | ~2 minutes | ~1 minute per ticker (first time); faster after that |
| **Run again?** | Only if you move to a new Mac or reinstall | Yes — any ticker, any time |

---

# Part 1 — One-time setup

Do this **once**. You should not need to run setup again unless you reinstall or switch computers.

### Step 1 — Get this folder on your Mac

**Option A — Download (easiest)**  
[github.com/mallik-mahalingam/stock-financials](https://github.com/mallik-mahalingam/stock-financials) → **Code** → **Download ZIP** → unzip.

**Option B — Git**

```bash
git clone https://github.com/mallik-mahalingam/stock-financials.git ~/src/stock-financials
```

### Step 2 — Run setup (one click)

In Finder, open the `stock-financials` folder and **double-click**:

```
Setup.command
```

Enter your **name** and **email** when asked. The SEC requires this for automated downloads. Setup saves your answers to `~/.stock-financials.env` — you won’t be asked again.

When prompted, say **yes** to link the AI skill (for Cursor). For **Claude Code**, add this repo’s `skills/` folder to your Claude skills path so the assistant knows how to run sync.

> **macOS blocked the file?** Right-click **Setup.command** → **Open** → **Open** again (only needed the first time).

### Step 3 — Confirm setup worked

You should see **“Setup complete!”** in the window. Close it. You’re done with Part 1 — never repeat these steps on this Mac.

---

# Part 2 — Day-to-day use

Use this **whenever** you want financials for a stock. No setup steps — just ask.

### Ask your AI assistant

In **Cursor**, **Claude Code**, or any AI tool with this skill installed, type something like:

> Get financials for Apple  
> Show me PANW income, balance sheet, and cash flow  
> `/stock-financials MSFT`

The assistant runs the sync, builds the table, and points you to the canvas file. Works after Part 1 is done once.

<small>

**Other ways**

· **Double-click** `Get Financials.command` → enter ticker (e.g. `AAPL`) → open the file it shows you under `canvas/`

· **Terminal:** `~/src/stock-financials/get-financials.sh AAPL`

</small>

---

## What the canvas looks like

After sync, you get **one file** with **three tabs** — **Income · Balance Sheet · Cash Flow**. Open it in **Cursor** for the interactive view: summary stats at the top, **12 quarters** in the table, and charts you can customize by ticking rows.

Real example — **PANW** (Palo Alto Networks), from SEC filings:

### Income tab

![PANW income statement canvas — 12 quarters, revenue, margins, EPS, and chart](docs/screenshots/panw-income.png)

### Balance sheet tab

![PANW balance sheet canvas — assets, liabilities, equity across 12 quarters](docs/screenshots/panw-balance-sheet.png)

### Cash flow tab

![PANW cash flow canvas — operating, investing, financing, and free cash flow](docs/screenshots/panw-cash-flow.png)

<small>

Scroll horizontally in the canvas to see all 12 quarters. Tick checkboxes beside row names to add them to the chart. Values marked `*` are calculated when the filing doesn’t report that line directly.

</small>

---

## Ongoing habits

| Situation | What to do |
|-----------|------------|
| New stock you’ve never looked up | Ask your AI: *“Get financials for TICKER”* |
| Same stock, new quarter filed | Ask again with the same ticker (only re-downloads if SEC has newer data) |
| Canvas looks wrong or stale | Ask again — don’t edit files by hand |
| New Mac or fresh install | Repeat **Part 1** only |

---

## Reading the table

| You see | Meaning |
|---------|---------|
| `$2,257` | Dollars in **millions** |
| `(183)` | Loss / negative |
| `0.76` | Earnings per share |
| `47.0%` | Margin or year-over-year change |
| `*` | Estimated when the filing doesn’t report that line directly |

Open the `.canvas.tsx` file in **Cursor** for the interactive view (tabs + charts). The underlying data is also saved as JSON in `json-data/`.

---

## Something wrong?

| Problem | Fix |
|---------|-----|
| “Setup is not done yet” | You skipped Part 1 — run **Setup.command** once |
| AI doesn’t know what to do | Install the skill: Cursor via Setup, or add `skills/` for Claude |
| macOS won’t open `.command` file | Right-click → **Open** |
| “Python not installed” | Install from [python.org/downloads](https://www.python.org/downloads/), then run **Setup.command** again |
| Ticker not found | Use the US symbol (e.g. `BRK.B`) |

<small>

Saved data appears in `json-data/` and `canvas/` inside this folder (created automatically). Advanced CLI (`sync`, `check`, `build`) lives in `scripts/sec_financials.py`. Agent workflow details: `skills/SKILL.md`.

</small>

---

## About the data

Numbers come from **SEC EDGAR** (company 10-Q / 10-K filings). Some lines are calculated when filers don’t report them directly (marked with `*`).
