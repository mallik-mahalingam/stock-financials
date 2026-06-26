"""Unified build router: domestic (10-Q/10-K XBRL) and FPI (6-K HTML) — all three statements."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sec_financials import is_fpi, json_path, lookup_cik, missing_data_columns, save_json

STATEMENTS = ("income", "balance-sheet", "cash-flow")


def build_all_documents(ticker: str) -> dict[str, dict[str, Any]]:
    """Build whatever statements are available for this filer (domestic or FPI)."""
    cik = lookup_cik(ticker)
    if is_fpi(cik):
        from fpi_html import build_all_html_documents

        return build_all_html_documents(ticker)

    from bs_xbrl import build_bs_document
    from cf_xbrl import build_cf_document
    from income_xbrl import build_income_document

    out: dict[str, dict[str, Any]] = {}
    for name, builder in (
        ("income", build_income_document),
        ("balance-sheet", build_bs_document),
        ("cash-flow", build_cf_document),
    ):
        doc = builder(ticker)
        if not missing_data_columns(doc):
            out[name] = doc
    if "income" not in out:
        raise SystemExit(f"Income build for {ticker} failed anchor coverage")
    return out


def write_all_json(ticker: str) -> dict[str, Path]:
    """Build and save all available statements. Income is required."""
    docs = build_all_documents(ticker)
    paths: dict[str, Path] = {}
    for stmt, doc in docs.items():
        path = json_path(ticker, stmt)
        save_json(path, doc)
        paths[stmt] = path
    return paths


def write_statement_json(ticker: str, statement: str) -> Path:
    """Build one statement; FPI reuses single-pass collector when possible."""
    t = ticker.strip().upper()
    cik = lookup_cik(t)
    if is_fpi(cik):
        from fpi_html import build_all_html_documents

        docs = build_all_html_documents(t)
        if statement not in docs:
            raise SystemExit(f"No {statement} data available for FPI filer {t}")
        path = json_path(t, statement)
        save_json(path, docs[statement])
        return path

    if statement == "income":
        from income_xbrl import build_income_document

        doc = build_income_document(t)
    elif statement == "balance-sheet":
        from bs_xbrl import build_bs_document

        doc = build_bs_document(t)
    elif statement == "cash-flow":
        from cf_xbrl import build_cf_document

        doc = build_cf_document(t)
    else:
        raise SystemExit(f"Unknown statement: {statement}")

    gaps = missing_data_columns(doc)
    if gaps:
        raise SystemExit(f"Built {statement} missing anchors: {', '.join(gaps[:3])}")
    path = json_path(t, statement)
    save_json(path, doc)
    return path
