#!/usr/bin/env python3
"""Fetch peer-comparison stock summary metrics from Yahoo Finance (yfinance).

Any null fields are reported in `gaps` so the agent can warn the user or
backfill price/history from Schwab MCP when available.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

try:
    import pandas as pd
    import yfinance as yf
except ImportError as e:
    raise SystemExit(
        "Install dependencies: pip install yfinance pandas"
    ) from e

SOURCE = "Yahoo Finance (yfinance)"


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def clean_hist(hist: pd.DataFrame) -> pd.DataFrame:
    return hist.dropna(subset=["Close"]).copy()


def ret_from_hist(h: pd.DataFrame, days: int) -> float | None:
    if len(h) < 2:
        return None
    idx = max(0, len(h) - 1 - days)
    return (h["Close"].iloc[-1] / h["Close"].iloc[idx] - 1) * 100


def ytd_ret(h: pd.DataFrame) -> float | None:
    if len(h) < 2:
        return None
    year = h.index[-1].year
    y = h[h.index.year == year]
    if len(y) < 2:
        return None
    return (y["Close"].iloc[-1] / y["Close"].iloc[0] - 1) * 100


def compute_roic(ticker: yf.Ticker) -> float | None:
    """ROIC ≈ NOPAT / (Equity + Debt − Cash) from latest financial statements."""
    try:
        inc = ticker.income_stmt
        bs = ticker.balance_sheet
        if inc is None or bs is None or inc.empty or bs.empty:
            return None
        op_inc = inc.loc["Operating Income"].iloc[0] if "Operating Income" in inc.index else None
        tax = inc.loc["Tax Provision"].iloc[0] if "Tax Provision" in inc.index else None
        pretax = inc.loc["Pretax Income"].iloc[0] if "Pretax Income" in inc.index else None
        if op_inc is None:
            return None
        etr = (tax / pretax) if tax and pretax and pretax != 0 else 0.21
        nopat = op_inc * (1 - etr)
        equity = bs.loc["Stockholders Equity"].iloc[0] if "Stockholders Equity" in bs.index else None
        debt = bs.loc["Total Debt"].iloc[0] if "Total Debt" in bs.index else None
        cash = bs.loc["Cash And Cash Equivalents"].iloc[0] if "Cash And Cash Equivalents" in bs.index else 0
        if equity is None:
            return None
        invested = equity + (debt or 0) - (cash or 0)
        if invested <= 0:
            return None
        return float(nopat / invested)
    except Exception:
        return None


def rnd(v: Any, n: int = 1) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return round(float(v), n)


def clean_name(raw: str | None, symbol: str) -> str:
    if not raw:
        return symbol
    name = raw.replace(" - New York Re", "").replace(", Inc.", "").replace(" Inc.", "")
    name = name.replace(", N.V.", "").replace(" N.V.", "")
    return name.strip()


def fetch_row(symbol: str) -> dict[str, Any]:
    t = yf.Ticker(yahoo_symbol(symbol))
    info = t.info or {}
    h = clean_hist(t.history(period="1y", auto_adjust=True))

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None and len(h):
        price = float(h["Close"].iloc[-1])

    ath = info.get("allTimeHigh")
    high52 = info.get("fiftyTwoWeekHigh")
    low52 = info.get("fiftyTwoWeekLow")

    short_now = info.get("shortPercentOfFloat")
    short_prior_shares = info.get("sharesShortPriorMonth")
    float_shares = info.get("floatShares")
    short_3m_bps = None
    if short_now is not None and short_prior_shares and float_shares:
        prior_pct = short_prior_shares / float_shares
        short_3m_bps = (short_now - prior_pct) * 10000

    eps_g_26 = eps_g_27 = fwd_pe_26 = fwd_pe_27 = None
    try:
        ee = t.earnings_estimate
        if ee is not None and not ee.empty:
            if "0y" in ee.index:
                if pd.notna(ee.loc["0y", "growth"]):
                    eps_g_26 = float(ee.loc["0y", "growth"]) * 100
                if price and pd.notna(ee.loc["0y", "avg"]) and ee.loc["0y", "avg"]:
                    fwd_pe_26 = float(price / ee.loc["0y", "avg"])
            if "+1y" in ee.index:
                if pd.notna(ee.loc["+1y", "growth"]):
                    eps_g_27 = float(ee.loc["+1y", "growth"]) * 100
                if price and pd.notna(ee.loc["+1y", "avg"]) and ee.loc["+1y", "avg"]:
                    fwd_pe_27 = float(price / ee.loc["+1y", "avg"])
    except Exception:
        pass

    roe = info.get("returnOnEquity")
    roic = compute_roic(t)
    sym = symbol.strip().upper()
    mkt_cap = info.get("marketCap") or info.get("totalAssets") or 0

    return {
        "symbol": sym,
        "name": clean_name(info.get("shortName") or info.get("longName"), sym),
        "price": rnd(price, 2),
        "mktCapMM": rnd(mkt_cap / 1e6, 0),
        "retYTD": rnd(ytd_ret(h)),
        "ret1M": rnd(ret_from_hist(h, 21)),
        "ret3M": rnd(ret_from_hist(h, 63)),
        "ret6M": rnd(ret_from_hist(h, 126)),
        "ret12M": rnd(ret_from_hist(h, min(252, len(h) - 1))),
        "pctFromATH": rnd((price / ath - 1) * 100 if price and ath else None),
        "pctFrom52Low": rnd((price / low52 - 1) * 100 if price and low52 else None),
        "pctTo52High": rnd((high52 / price - 1) * 100 if price and high52 else None),
        "shortNow": rnd(short_now * 100 if short_now else None, 2),
        "short3mBps": rnd(short_3m_bps, 0),
        "epsGrowth2026": rnd(eps_g_26),
        "epsGrowth2027": rnd(eps_g_27),
        "fwdPE2026": rnd(fwd_pe_26 or info.get("forwardPE")),
        "fwdPE2027": rnd(fwd_pe_27),
        "roe": rnd(roe * 100 if roe else None),
        "roic": rnd(roic * 100 if roic else None),
    }


def fetch_summary(symbols: list[str]) -> dict[str, Any]:
    rows = [fetch_row(s) for s in symbols]
    gaps: dict[str, list[str]] = {}
    skip = {"name", "symbol", "price"}
    for row in rows:
        for k, v in row.items():
            if v is None and k not in skip:
                gaps.setdefault(k, []).append(row["symbol"])

    return {
        "asOf": datetime.now(timezone.utc).strftime("%b %d, %Y"),
        "source": SOURCE,
        "symbols": [s.strip().upper() for s in symbols],
        "rows": rows,
        "gaps": gaps,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch stock summary table metrics from Yahoo Finance")
    p.add_argument("symbols", nargs="+", help="Ticker symbols")
    p.add_argument("-o", "--output", help="Write JSON to file")
    args = p.parse_args()

    payload = fetch_summary(args.symbols)
    text = json.dumps(payload, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        print(text)

    if payload["gaps"]:
        print("\nMissing fields (ask user or try Schwab fallback):", file=sys.stderr)
        print(json.dumps(payload["gaps"], indent=2), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
