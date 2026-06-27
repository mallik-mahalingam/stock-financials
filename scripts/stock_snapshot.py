"""Fetch current stock snapshot from Yahoo Finance (via yfinance)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

SOURCE = "Yahoo Finance"


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v:,.2f}"


def _fmt_mcap(v: float | None) -> str:
    if v is None:
        return "—"
    n = float(v)
    if n >= 1e12:
        return f"${n / 1e12:.2f}T"
    if n >= 1e9:
        return f"${n / 1e9:.2f}B"
    if n >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.0f}"


def _fmt_pe(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}x"


def fetch_snapshot(ticker: str) -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "yfinance is required for stock snapshots. Install with: pip install yfinance"
        ) from e

    sym = yahoo_symbol(ticker)
    info = yf.Ticker(sym).info or {}

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    low52 = info.get("fiftyTwoWeekLow")
    high52 = info.get("fiftyTwoWeekHigh")
    mcap = info.get("marketCap")
    pe = info.get("trailingPE") or info.get("forwardPE")

    return {
        "ticker": ticker.strip().upper(),
        "yahooSymbol": sym,
        "companyName": info.get("shortName") or info.get("longName") or ticker.strip().upper(),
        "asOf": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": SOURCE,
        "price": price,
        "fiftyTwoWeekLow": low52,
        "fiftyTwoWeekHigh": high52,
        "marketCap": mcap,
        "trailingPE": pe,
        "display": {
            "price": _fmt_price(price),
            "fiftyTwoWeekLow": _fmt_price(low52),
            "fiftyTwoWeekHigh": _fmt_price(high52),
            "marketCap": _fmt_mcap(mcap),
            "trailingPE": _fmt_pe(pe),
        },
    }


def markdown_table(snapshot: dict[str, Any]) -> str:
    d = snapshot["display"]
    title = snapshot.get("companyName") or snapshot["ticker"]
    lines = [
        f"**{title} ({snapshot['ticker']})** — {snapshot['source']} · {snapshot['asOf']}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Current price | {d['price']} |",
        f"| 52-week low | {d['fiftyTwoWeekLow']} |",
        f"| 52-week high | {d['fiftyTwoWeekHigh']} |",
        f"| Market cap | {d['marketCap']} |",
        f"| P/E (trailing) | {d['trailingPE']} |",
    ]
    return "\n".join(lines)


def snapshot_payload(ticker: str) -> dict[str, Any]:
    snap = fetch_snapshot(ticker)
    return {"snapshot": snap, "markdownTable": markdown_table(snap)}


def print_snapshot(ticker: str, *, as_json: bool = True) -> None:
    payload = snapshot_payload(ticker)
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload["markdownTable"])
