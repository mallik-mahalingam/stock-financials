"""Display formatting for financial statement values.

Rules (standardized financials tables):
- USD millions ($): integer with thousands separators; negatives in parentheses
- EPS: always two decimal places
- Shares (millions): one decimal when fractional, otherwise integer (351.4 vs 813)
- Margins / effective tax rate: one decimal with trailing zero (47.0%)
- YoY % change: signed, one decimal (+10.4%, 0.0%)
"""

from __future__ import annotations


def fmt_dollar(v: int | float | None, derived: bool = False) -> str:
    if v is None:
        return "—"
    n = int(round(v))
    s = f"{abs(n):,}" if n >= 0 else f"({abs(n):,})"
    return f"{s}*" if derived else s


def fmt_eps(v: float | None) -> str:
    if v is None:
        return "—"
    s = f"{abs(v):.2f}"
    return f"({s})" if v < 0 else s


def fmt_sh(v: float | None) -> str:
    if v is None:
        return "—"
    r = round(v, 1)
    if abs(r - round(r)) < 1e-9:
        return str(int(round(r)))
    return f"{r:.1f}"


def fmt_margin(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{round(v, 1):.1f}%"


def fmt_pct_yoy(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%" if abs(v) >= 0.05 else "0.0%"
