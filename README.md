# Stock Financials

Pull the last **12 quarters** of official GAAP financials — **Income Statement**, **Balance Sheet**, and **Cash Flow** — straight from SEC filings, and view them in a clean, tabbed table inside **Cursor**.

You do **not** need to be a software engineer. After a one-time setup, getting financials for a stock is usually **one command** (or one sentence in Cursor chat).

---

## What you get

For any US-listed ticker (e.g. `AAPL`, `PANW`, `INTU`):

| Output | What it is |
|--------|------------|
| **Interactive canvas** | A tabbed spreadsheet-style view in Cursor — Income · Balance Sheet · Cash Flow — with charts on key rows |
| **Data files** | Saved under `json-data/` so you can re-open them without re-downloading from the SEC |

Numbers come from **SEC EDGAR** (the company’s own filings), not from a third-party data vendor.

---

## One-time setup

Do these steps once after cloning the repo.

### Step 1 — Clone the repo

Open **Terminal** (on Mac: Spotlight → type “Terminal” → Enter), then paste:

```bash
git clone https://github.com/mallik-mahalingam/stock-financials.git ~/src/stock-financials
cd ~/src/stock-financials
```

> **Already have the folder?** Just `cd ~/src/stock-financials` instead.

### Step 2 — Check Python

This tool uses Python, which is already installed on most Macs. Check with:

```bash
python3 --version
```

You should see **3.10 or higher**. No extra packages to install.

### Step 3 — Tell the SEC who you are (required)

The SEC requires every automated request to include a **name and email**. Replace the example below with yours:

```bash
export SEC_USER_AGENT="Jane Doe stock-financials research jane@example.com"
```

To avoid typing this every time, add the same line to your shell profile:

```bash
echo 'export SEC_USER_AGENT="Jane Doe stock-financials research jane@example.com"' >> ~/.zshrc
source ~/.zshrc
```

### Step 4 — Optional: enable Cursor AI help

If you use **Cursor**, link the built-in skill so the AI knows how to run this for you:

```bash
ln -sf ~/src/stock-financials/skills ~/.cursor/skills/stock-financials
```

After this, you can type in chat: *“Get financials for PANW”* or `/stock-financials AAPL`.

---

## How to use it (main workflow)

Replace `TICKER` with a stock symbol (always uppercase in commands).

### Get all three statements + canvas

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER
```

**Examples:**

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync PANW
python3 ~/src/stock-financials/scripts/sec_financials.py sync AAPL
python3 ~/src/stock-financials/scripts/sec_financials.py sync INTU
```

The first run for a ticker takes **30–90 seconds** (downloads from the SEC). Later runs are fast unless a new quarterly filing appeared.

When it finishes, you’ll see a path like:

```
canvas/panw-financials.canvas.tsx
```

### Open the canvas in Cursor

1. In Cursor’s **file explorer**, go to `~/src/stock-financials/canvas/`
2. Open `{ticker}-financials.canvas.tsx` (ticker is lowercase, e.g. `panw-financials.canvas.tsx`)
3. Cursor shows the interactive table beside your chat

**Tip — show canvas next to chat automatically:** copy the file into your project’s canvases folder:

```bash
cp ~/src/stock-financials/canvas/panw-financials.canvas.tsx \
   ~/.cursor/projects/<your-project>/canvases/
```

Replace `<your-project>` with your Cursor workspace folder name under `~/.cursor/projects/`.

---

## Easiest path: ask Cursor

If you completed **Step 4** above, skip the terminal and just ask in Cursor chat:

> “Sync financials for Microsoft”  
> “Show me AAPL income, balance sheet, and cash flow for the last 12 quarters”  
> `/stock-financials DDOG`

The agent runs `sync`, opens the canvas, and links it in chat.

---

## When a new quarter is filed

Run the same command again:

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py sync TICKER
```

The tool checks whether SEC has a newer 10-Q than your saved data. If yes, it rebuilds automatically.

To **check without rebuilding** (see if you’re up to date):

```bash
python3 ~/src/stock-financials/scripts/sec_financials.py check TICKER
```

---

## Shorter commands (optional)

Paste once per Terminal session (or add to `~/.zshrc`):

```bash
alias sf='python3 ~/src/stock-financials/scripts/sec_financials.py'
```

Then use:

```bash
sf sync PANW
sf check AAPL
```

---

## Reading the tables

| Symbol / style | Meaning |
|----------------|---------|
| `$2,257` | Dollars in **millions** |
| `(183)` | Negative number |
| `0.76` | Earnings per share (2 decimal places) |
| `47.0%` | Margin or year-over-year change |
| `*` on a value | Calculated by this tool when the filing doesn’t report that line directly |

**Section headers** (e.g. “Operating Activities”, “Assets”) are labels only — the numbers are in the rows below them.

---

## Where files are saved

After `sync TICKER`, look here:

```
~/src/stock-financials/
  json-data/
    PANW-income.json
    PANW-balance-sheet.json
    PANW-cash-flow.json
  canvas/
    panw-financials.canvas.tsx    ← open this in Cursor
```

These folders are created automatically. They are **not** checked into git — they live on your machine.

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| `SEC_USER_AGENT` / blocked by SEC | Set Step 3 again in this Terminal window, or add it to `~/.zshrc` |
| `python3: command not found` | Install Python 3 from [python.org](https://www.python.org/downloads/) or `brew install python` |
| Ticker not found | Use the US exchange symbol (e.g. `BRK.B` not `BRK-B`). Some foreign-only listings may not work. |
| Canvas looks old | Run `sync TICKER` again — don’t edit the `.tsx` file by hand |
| Slow first run | Normal — SEC download + parsing. Retry if your network dropped |

**View recent SEC filings for a ticker** (opens URLs you can click in the terminal output):

```bash
sf edgar PANW
```

---

## Other commands (reference)

Most people only need `sync`. These are here if you need more control:

| What you want | Command |
|---------------|---------|
| Everything (usual choice) | `sf sync TICKER` |
| Check if data is stale | `sf check TICKER` |
| Force re-download from SEC | `sf build TICKER` |
| Rebuild one statement only | `sf build TICKER income` (or `balance-sheet`, `cash-flow`) |
| Refresh canvas only | `sf render TICKER` |
| See saved file paths | `sf path TICKER` |

Advanced environment variables (optional):

| Variable | Purpose |
|----------|---------|
| `SEC_USER_AGENT` | **Required** — your name + email for SEC |
| `STOCK_FINANCIALS_DIR` | Custom folder for JSON data |
| `STOCK_FINANCIALS_CANVAS_DIR` | Custom folder for canvas output |

---

## What to know about the data

- **Source:** SEC EDGAR XBRL tags from 10-Q / 10-K filings.
- **Q4 columns:** Sometimes computed as full-year minus first nine months when the filer doesn’t publish a standalone Q4 tag.
- **Cash flow detail:** Operating / Investing / Financing **totals** tie to the filing; individual working-capital lines can differ slightly from vendor sites.
- **Free cash flow extras** (NOPAT, Levered FCF, etc.): Derived memo lines using a simplified 21% tax assumption — useful for comparison, not official GAAP subtotals.
- **Blank rows:** Omitted when empty across all 12 quarters.

For agent validation rules and row definitions, see `skills/SKILL.md`.

---

## Project layout (for reference)

```
~/src/stock-financials/
  scripts/sec_financials.py   ← main command you run
  json-data/                  ← generated data (your machine)
  canvas/                     ← generated views (your machine)
  skills/SKILL.md             ← Cursor agent instructions
  schema/                     ← data format definitions
  templates/                  ← canvas layout templates
```

**Do not** hand-edit `.tsx` canvas files. Always run `sync TICKER` to refresh after data changes.
