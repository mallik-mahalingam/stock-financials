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


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%"


def _fmt_price_delta(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.2f}"


def _range_metrics(price: float | None, low52: float | None, high52: float | None) -> dict[str, float | None]:
    from_low_pct = from_high_pct = from_low_abs = from_high_abs = None
    if price is not None and low52 not in (None, 0):
        from_low_abs = price - low52
        from_low_pct = from_low_abs / low52 * 100
    if price is not None and high52 not in (None, 0):
        from_high_abs = price - high52
        from_high_pct = from_high_abs / high52 * 100
    return {
        "fromLowPct": from_low_pct,
        "fromHighPct": from_high_pct,
        "fromLowAbs": from_low_abs,
        "fromHighAbs": from_high_abs,
    }


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
    range_m = _range_metrics(price, low52, high52)

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
        **range_m,
        "display": {
            "price": _fmt_price(price),
            "fiftyTwoWeekLow": _fmt_price(low52),
            "fiftyTwoWeekHigh": _fmt_price(high52),
            "marketCap": _fmt_mcap(mcap),
            "trailingPE": _fmt_pe(pe),
            "fromLowPct": _fmt_pct(range_m["fromLowPct"]),
            "fromHighPct": _fmt_pct(range_m["fromHighPct"]),
            "fromLowAbs": _fmt_price_delta(range_m["fromLowAbs"]),
            "fromHighAbs": _fmt_price_delta(range_m["fromHighAbs"]),
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
        f"| Current price | {d['fromLowPct']} from 52W low ({d['fromLowAbs']}) · {d['fromHighPct']} from 52W high ({d['fromHighAbs']}) · **{d['price']}** |",
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
