#!/usr/bin/env python3
"""Render combined tabbed financials canvas (income + balance sheet + cash flow)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from render_unified_canvas import split_sections
from sec_financials import STATEMENT_SUFFIX, TEMPLATES_DIR, jsx_text, json_path, normalize_ticker

TAB_ORDER = [
    ("income", "Income"),
    ("balance-sheet", "Balance Sheet"),
    ("cash-flow", "Cash Flow"),
]


BLANK_VALUES = frozenset({"—", "-", "", " "})


def row_has_data(row: dict[str, Any]) -> bool:
    """Keep totals and any row with at least one populated quarter."""
    if row.get("kind") == "total":
        return True
    return any(v not in BLANK_VALUES for v in row.get("values") or [])


def filter_empty_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if row_has_data(r)]


def _row_embed(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "label": row["label"],
        "vals": row["values"],
        "kind": row.get("kind", "normal"),
        "unit": row.get("unit", "$"),
        "plottable": row.get("plottable", True),
    }
    return out


def prepare_statement_embed(data: dict[str, Any]) -> dict[str, Any]:
    stype = data["statementType"]
    rows = [_row_embed(r) for r in filter_empty_rows(data["rows"])]
    summary = data.get("summary") or {}
    embed: dict[str, Any] = {
        "quarters": [q["label"] for q in data["quarters"]],
        "rows": rows,
        "summary": {
            "subtitle": summary.get("subtitle", ""),
            "fiscalMapping": summary.get("fiscalMapping", ""),
            "stats": summary.get("stats", []),
            "defaultChartRows": summary.get("defaultChartRows", []),
        },
        "notes": data.get("notes") or [],
        "statementType": stype,
        "sections": None,
    }
    if stype != "income":
        sections = split_sections(filter_empty_rows(data["rows"]), data.get("sections") or [])
        embed["sections"] = [
            {"title": title, "rows": [_row_embed(r) for r in filter_empty_rows(section_rows)]}
            for title, section_rows in sections
        ]
    return embed


def load_statements(ticker: str) -> dict[str, dict[str, Any]]:
    t = normalize_ticker(ticker)
    loaded: dict[str, dict[str, Any]] = {}
    for stmt in STATEMENT_SUFFIX:
        path = json_path(t, stmt)
        if path.is_file():
            loaded[stmt] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def render_financials_canvas(ticker: str, out_path: Path, statements: dict[str, dict[str, Any]] | None = None) -> Path:
    if statements is None:
        statements = load_statements(ticker)

    if not statements:
        raise SystemExit(
            f"No JSON found for {normalize_ticker(ticker)}. "
            f"Expected files under {json_path(ticker, 'income').parent}"
        )

    t = normalize_ticker(ticker)
    company = next(iter(statements.values())).get("companyName") or t
    available = [key for key, _ in TAB_ORDER if key in statements]
    embeds = {key: prepare_statement_embed(statements[key]) for key in available}

    snapshot_block = "const STOCK_SNAPSHOT = null;"
    try:
        from stock_snapshot import fetch_snapshot

        snap = fetch_snapshot(t)
        d = snap["display"]
        embed_snap = {
            "source": snap["source"],
            "asOf": snap["asOf"],
            "price": d["price"],
            "fiftyTwoWeekLow": d["fiftyTwoWeekLow"],
            "fiftyTwoWeekHigh": d["fiftyTwoWeekHigh"],
            "marketCap": d["marketCap"],
            "trailingPE": d["trailingPE"],
        }
        snapshot_block = f"const STOCK_SNAPSHOT = {json.dumps(embed_snap, ensure_ascii=False)};"
    except Exception:
        pass

    src_lines = [f"//   {key}: {json_path(t, key)}" for key in available]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        "// GENERATED — do not edit by hand.\n"
        + "\n".join(src_lines)
        + f"\n// Generated: {generated}\n"
    )

    data_blocks = "\n".join(
        f"const {key.upper().replace('-', '_')}_DATA = {json.dumps(embeds[key], ensure_ascii=False)};"
        for key in available
    )

    pills = "\n".join(
        f'        <Pill active={{tab === "{key}"}} onClick={{() => setTab("{key}")}}>{label}</Pill>'
        for key, label in TAB_ORDER
        if key in available
    )

    panels = "\n".join(
        f'      {{tab === "{key}" && <StatementPanel tabKey="{key}" data={{{key.upper().replace("-", "_")}_DATA}} title="{label}" />}}'
        for key, label in TAB_ORDER
        if key in available
    )

    subtitle = jsx_text(
        f"{company} · Last 12 quarters · USD millions (except per-share on income). "
        "Source: SEC filings · JSON cache in json-data/"
    )

    template = (TEMPLATES_DIR / "financials_canvas.template.tsx").read_text(
        encoding="utf-8"
    )
    body = (
        template.replace("__HEADER__", header)
        .replace("__DATA_BLOCKS__", data_blocks)
        .replace("__STOCK_SNAPSHOT__", snapshot_block)
        .replace("__TICKER__", t)
        .replace("__SUBTITLE__", subtitle)
        .replace("__PILLS__", pills)
        .replace("__PANELS__", panels)
        .replace("__DEFAULT_TAB__", available[0])
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    return out_path


def financials_canvas_path(ticker: str, canvas_root: Path) -> Path:
    return canvas_root / f"{normalize_ticker(ticker).lower()}-financials.canvas.tsx"
