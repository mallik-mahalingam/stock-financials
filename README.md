# Stock Financials

See **Income**, **Balance Sheet**, and **Cash Flow** for any US stock — last **12 quarters**, pulled from official **SEC filings**, shown in a tabbed table inside **Cursor**.

No coding required.

---

## Install (one time)

### 1. Get this folder on your Mac

**Option A — Download (easiest)**  
Go to [github.com/mallik-mahalingam/stock-financials](https://github.com/mallik-mahalingam/stock-financials) → green **Code** → **Download ZIP** → unzip.

**Option B — Git**  
Open Terminal and paste:

```bash
git clone https://github.com/mallik-mahalingam/stock-financials.git ~/src/stock-financials
```

### 2. Run setup (one click)

In Finder, open the `stock-financials` folder and **double-click**:

```
Setup.command
```

It will ask for your **name** and **email** (the SEC requires this). That’s it — setup saves your answers so you never type them again.

> **First time on Mac?** If macOS blocks the file: right-click **Setup.command** → **Open** → **Open** again.

---

## Get financials (one click)

**Double-click:**

```
Get Financials.command
```

Type a ticker when asked, for example:

```
AAPL
PANW
MSFT
```

Wait about a minute the first time. When it finishes, it shows you a file to open in **Cursor** (and may highlight it in Finder).

**In Cursor:** open the file it mentions — something like `panw-financials.canvas.tsx` under the `canvas` folder. You’ll see three tabs: Income · Balance Sheet · Cash Flow.

---

## Even easier: ask Cursor

After running **Setup.command** once, you can skip the double-click step and just type in Cursor chat:

> Get financials for Apple  
> Show me PANW income, balance sheet, and cash flow  
> `/stock-financials MSFT`

---

## When numbers update

After a company files a new quarterly report, run **Get Financials.command** again with the same ticker. It only re-downloads if SEC has something newer.

---

## Reading the table

| You see | Meaning |
|---------|---------|
| `$2,257` | Dollars in **millions** |
| `(183)` | Loss / negative |
| `0.76` | Earnings per share |
| `47.0%` | Margin or year-over-year change |
| `*` | Estimated by this tool when the filing doesn’t spell out that line |

---

## Something wrong?

| Problem | Fix |
|---------|-----|
| “Setup is not done yet” | Double-click **Setup.command** first |
| macOS won’t open `.command` file | Right-click → **Open** |
| “Python not installed” | Install from [python.org/downloads](https://www.python.org/downloads/), then run Setup again |
| Wrong or old numbers | Run **Get Financials.command** again — don’t edit files by hand |
| Ticker not found | Use the US symbol (e.g. `BRK.B`) |

Your saved data lives in the `json-data` and `canvas` folders inside this project. Those folders are created automatically on first use.

---

## Optional: Terminal one-liners

If you prefer Terminal after setup:

```bash
~/src/stock-financials/get-financials.sh AAPL
```

Advanced commands live in `scripts/sec_financials.py` (`sync`, `check`, `build`). See `skills/SKILL.md` for Cursor agent details.

---

## About the data

Numbers come from **SEC EDGAR** (the company’s own 10-Q / 10-K filings), not from a paid data feed. Some lines are calculated when filers don’t report them directly (marked with `*`).
