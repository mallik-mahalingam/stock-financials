# Stock Financials

See **Income**, **Balance Sheet**, and **Cash Flow** for any US stock — last **12 quarters**, from official **SEC filings**, in a tabbed table inside **Cursor**.

No coding required.

---

## At a glance

| | One-time setup | Day-to-day use |
|---|----------------|----------------|
| **When** | Once, before your first stock | Every time you want financials |
| **What you do** | Download the folder → double-click **Setup.command** | Double-click **Get Financials.command** (or ask Cursor) |
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

> **macOS blocked the file?** Right-click **Setup.command** → **Open** → **Open** again (only needed the first time).

### Step 3 — Confirm setup worked

You should see **“Setup complete!”** in the window. Close it. You’re done with Part 1 — never repeat these steps on this Mac.

---

# Part 2 — Day-to-day use

Use this **whenever** you want financials for a stock. No setup steps — just pick a ticker.

### Option A — Double-click (simplest)

**Double-click:**

```
Get Financials.command
```

Type a ticker when prompted:

```
AAPL
PANW
MSFT
```

When it finishes, open the file it shows you in **Cursor** (under the `canvas` folder). Three tabs: **Income · Balance Sheet · Cash Flow**.

### Option B — Ask Cursor (no double-click)

In Cursor chat:

> Get financials for Apple  
> Show me PANW income, balance sheet, and cash flow  
> `/stock-financials MSFT`

Works after Part 1 setup is done once.

### Option C — Terminal (optional)

```bash
~/src/stock-financials/get-financials.sh AAPL
```

---

## Ongoing habits

| Situation | What to do |
|-----------|------------|
| New stock you’ve never looked up | **Get Financials.command** → enter ticker |
| Same stock, new quarter filed | **Get Financials.command** → same ticker again (only re-downloads if SEC has newer data) |
| Canvas looks wrong or stale | **Get Financials.command** again — don’t edit files by hand |
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

---

## Something wrong?

| Problem | Fix |
|---------|-----|
| “Setup is not done yet” | You skipped Part 1 — run **Setup.command** once |
| macOS won’t open `.command` file | Right-click → **Open** |
| “Python not installed” | Install from [python.org/downloads](https://www.python.org/downloads/), then run **Setup.command** again |
| Ticker not found | Use the US symbol (e.g. `BRK.B`) |

Saved data appears in `json-data/` and `canvas/` inside this folder (created automatically).

---

## About the data

Numbers come from **SEC EDGAR** (company 10-Q / 10-K filings). Some lines are calculated when filers don’t report them directly (marked with `*`).

Advanced CLI (`sync`, `check`, `build`) lives in `scripts/sec_financials.py`. Cursor agent details: `skills/SKILL.md`.
