#!/usr/bin/env python3
"""SEC financial JSON cache: EDGAR staleness checks, validation, canvas render."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
STATEMENT_SUFFIX = {
    "income": "income",
    "balance-sheet": "balance-sheet",
    "cash-flow": "cash-flow",
}
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
DOMESTIC_QUARTERLY_FORMS = ("10-Q", "10-K")
FPI_QUARTERLY_FORMS = ("6-K", "6-K/A")
FPI_DOC_HINTS = (
    "quarterly",
    "caq",
    "consolidated",
    "consolidatedreport",
    "fsx",
    "result",
    "earnings",
    "interim",
    "financial",
)


def is_fpi_quarterly_doc(doc: str) -> bool:
    dl = doc.lower()
    return any(h in dl for h in FPI_DOC_HINTS)
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DEFAULT_DIR = REPO_ROOT / "json-data"
SCHEMA_DIR = REPO_ROOT / "schema"
TEMPLATES_DIR = REPO_ROOT / "templates"

from statement_templates import ANCHOR_ROWS, INCOME_ROWS, row_from_spec

MISSING_CELL = frozenset({"—", "-", "", " "})


def data_dir() -> Path:
    return Path(os.environ.get("STOCK_FINANCIALS_DIR", DEFAULT_DIR)).expanduser()


def canvas_dir() -> Path:
    override = os.environ.get("STOCK_FINANCIALS_CANVAS_DIR")
    if override:
        return Path(override).expanduser()
    return REPO_ROOT / "canvas"


def resolve_canvas_dir(arg: str | None) -> Path:
    return Path(arg).expanduser() if arg else canvas_dir()


def sec_user_agent() -> str:
    # SEC blocks generic UAs — must identify app + contact email.
    return os.environ.get("SEC_USER_AGENT", "mallik70 stock-financials research mallik70@example.com")


def sec_get(url: str) -> Any:
    import time

    req = urllib.request.Request(url, headers={"User-Agent": sec_user_agent(), "Accept": "application/json"})
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except OSError as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise last_err  # type: ignore[misc]


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def json_path(ticker: str, statement: str) -> Path:
    suffix = STATEMENT_SUFFIX.get(statement, statement)
    return data_dir() / f"{normalize_ticker(ticker)}-{suffix}.json"


def lookup_cik(ticker: str) -> str:
    tickers = sec_get(SEC_TICKERS)
    t = normalize_ticker(ticker)
    for entry in tickers.values():
        if entry.get("ticker") == t:
            return str(entry["cik_str"]).zfill(10)
    raise SystemExit(f"Unknown ticker: {ticker}")


def is_fpi(cik: str) -> bool:
    """Foreign private issuer: files 6-K/20-F instead of 10-Q/10-K."""
    sub = sec_get(SEC_SUBMISSIONS.format(cik=cik))
    recent = sub["filings"]["recent"]
    forms = set(recent.get("form", [])[:120])
    has_domestic = bool(forms & set(DOMESTIC_QUARTERLY_FORMS))
    has_fpi = bool(forms & set(FPI_QUARTERLY_FORMS))
    return has_fpi and not has_domestic


def quarterly_forms_for_cik(cik: str) -> tuple[str, ...]:
    return FPI_QUARTERLY_FORMS if is_fpi(cik) else DOMESTIC_QUARTERLY_FORMS


def latest_quarterly_filings(
    cik: str,
    limit: int = 8,
    forms: tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    sub = sec_get(SEC_SUBMISSIONS.format(cik=cik))
    recent = sub["filings"]["recent"]
    if forms is None:
        forms = quarterly_forms_for_cik(cik)
    out: list[dict[str, str]] = []
    for i, form in enumerate(recent["form"]):
        if form not in forms:
            continue
        doc = recent.get("primaryDocument", [""])[i] or ""
        if form in FPI_QUARTERLY_FORMS and "quarterly" not in doc.lower():
            if not is_fpi_quarterly_doc(doc):
                continue
        pe = recent.get("reportDate", [""])[i] or ""
        if form in FPI_QUARTERLY_FORMS and not pe:
            continue
        acc = recent["accessionNumber"][i].replace("-", "")
        out.append(
            {
                "form": form,
                "filingDate": recent["filingDate"][i],
                "accessionNumber": recent["accessionNumber"][i],
                "reportDate": pe,
                "primaryDocument": doc,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}",
            }
        )
        if len(out) >= limit:
            break
    return out


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def missing_data_columns(data: dict[str, Any]) -> list[str]:
    quarters = data.get("quarters") or []
    rows = data.get("rows") or []
    stmt = data.get("statementType") or ""
    anchors = ANCHOR_ROWS.get(stmt, [])
    if not quarters or not anchors:
        return []
    labels = [q["label"] for q in quarters]
    by = {r["label"]: r.get("values") or [] for r in rows}
    missing: list[str] = []
    for anchor in anchors:
        vals = by.get(anchor, [])
        for i, label in enumerate(labels):
            if i >= len(vals) or vals[i] in MISSING_CELL:
                missing.append(f"{anchor} @ {label}")
    return missing


def validate_income(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if data.get("statementType") != "income":
        errors.append("statementType must be 'income'")
    quarters = data.get("quarters") or []
    rows = data.get("rows") or []
    n = len(quarters)
    if not quarters:
        errors.append("quarters must not be empty")
    if n != 12:
        errors.append(f"expected 12 quarters, found {n}")
    for i, row in enumerate(rows):
        vals = row.get("values") or []
        if len(vals) != n:
            errors.append(f"row '{row.get('label')}' has {len(vals)} values, expected {n}")
    errors.extend(f"missing data: {m}" for m in missing_data_columns(data))
    verification = data.get("verification") or {}
    if verification.get("grossProfitMatchesXbrlTag") is False:
        mismatches = verification.get("xbrlGrossProfitExceptions") or verification.get("exceptions") or []
        hint = ", ".join(mismatches[:3]) if mismatches else "see verification"
        errors.append(f"gross profit does not match SEC GrossProfit XBRL tag ({hint})")
    from statement_align import row_order_errors

    errors.extend(row_order_errors(data))
    return errors


def validate_statement(data: dict[str, Any]) -> list[str]:
    stmt = data.get("statementType") or ""
    if stmt == "income":
        return validate_income(data)
    errors: list[str] = []
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if data.get("statementType") != stmt:
        errors.append(f"unexpected statementType {stmt!r}")
    quarters = data.get("quarters") or []
    rows = data.get("rows") or []
    n = len(quarters)
    if not quarters:
        errors.append("quarters must not be empty")
    if n != 12:
        errors.append(f"expected 12 quarters, found {n}")
    for row in rows:
        vals = row.get("values") or []
        if len(vals) != n:
            errors.append(f"row '{row.get('label')}' has {len(vals)} values, expected {n}")
    errors.extend(f"missing data: {m}" for m in missing_data_columns(data))
    from statement_align import row_order_errors

    errors.extend(row_order_errors(data))
    return errors


def check_staleness(ticker: str, statement: str) -> dict[str, Any]:
    path = json_path(ticker, statement)
    cik = lookup_cik(ticker)
    filings = latest_quarterly_filings(cik, limit=1)
    latest = filings[0] if filings else None

    result: dict[str, Any] = {
        "ticker": normalize_ticker(ticker),
        "statement": statement,
        "jsonPath": str(path),
        "jsonExists": path.is_file(),
        "needsUpdate": False,
        "reason": "",
        "cik": cik,
        "latestEdgarFiling": latest,
    }

    if not path.is_file():
        result["needsUpdate"] = True
        result["reason"] = "JSON file missing"
        return result

    try:
        data = load_json(path)
    except (json.JSONDecodeError, OSError) as e:
        result["needsUpdate"] = True
        result["reason"] = f"JSON unreadable: {e}"
        return result

    val_errors = validate_statement(data)
    coverage = missing_data_columns(data)

    if val_errors:
        result["needsUpdate"] = True
        result["reason"] = "; ".join(val_errors[:3])
        result["validationErrors"] = val_errors
        return result

    if coverage:
        result["needsUpdate"] = True
        result["reason"] = f"missing anchor data: {', '.join(coverage[:3])}"
        result["missingColumns"] = coverage
        return result

    result["updatedAt"] = data.get("updatedAt")
    result["quarterCount"] = len(data.get("quarters") or [])
    result["latestPeriodEnd"] = (data.get("quarters") or [{}])[0].get("periodEnd")

    if not latest:
        result["reason"] = "Could not fetch EDGAR filings"
        return result

    stored_date = (data.get("edgar") or {}).get("latestQuarterlyFilingDate")
    if not stored_date:
        result["needsUpdate"] = True
        result["reason"] = "JSON missing edgar.latestQuarterlyFilingDate"
        return result

    if latest["filingDate"] > stored_date:
        result["needsUpdate"] = True
        result["reason"] = f"Newer EDGAR filing ({latest['form']} {latest['filingDate']}) vs JSON ({stored_date})"
        return result

    result["reason"] = "JSON is current"
    return result


def ts_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def jsx_text(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def render_row_def(row: dict[str, Any]) -> str:
    parts = [f'label: "{ts_escape(row["label"])}"', f'vals: {json.dumps(row["values"])}']
    if row.get("kind"):
        parts.append(f'kind: "{row["kind"]}"')
    if row.get("unit"):
        parts.append(f'unit: "{row["unit"]}"')
    if row.get("plottable") is False:
        parts.append("plottable: false")
    return "{ " + ", ".join(parts) + " }"


def render_income_canvas(data: dict[str, Any], out_path: Path) -> None:
    errors = validate_income(data)
    if errors:
        raise SystemExit("Invalid income JSON:\n" + "\n".join(errors))

    ticker = data["ticker"]
    quarters = [q["label"] for q in data["quarters"]]
    rows_ts = ",\n".join("  " + render_row_def(r) for r in data["rows"])
    summary = data.get("summary") or {}
    stats = summary.get("stats") or []
    default_chart = summary.get("defaultChartRows") or ["Total Revenues"]
    notes = data.get("notes") or []
    subtitle = summary.get("subtitle") or (
        f"Last {len(quarters)} quarters · USD millions (except per-share). Source: SEC 10-Q/10-K press releases."
    )
    fiscal_mapping = summary.get("fiscalMapping") or ""

    stat_blocks = []
    for s in stats:
        tone = f' tone="{s["tone"]}"' if s.get("tone") else ""
        stat_blocks.append(f'        <Stat value="{jsx_text(s["value"])}" label="{jsx_text(s["label"])}"{tone} />')
    if not stat_blocks:
        stat_blocks = ['        <Stat value="—" label="Latest Revenue" tone="info" />']

    note_blocks = [f'          <Text size="small">{jsx_text(n)}</Text>' for n in notes]
    if not note_blocks:
        note_blocks = ['          <Text size="small">See JSON notes in ~/src/stock-financials/json-data.</Text>']

    src_json = json_path(ticker, "income")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"// GENERATED — do not edit by hand.\n// Source: {src_json}\n// Generated: {generated}\n"

    fiscal_line = (
        f'        <Text tone="secondary" size="small">{jsx_text(fiscal_mapping)}</Text>'
        if fiscal_mapping
        else ""
    )

    template_path = TEMPLATES_DIR / "income_canvas.template.tsx"
    template = template_path.read_text(encoding="utf-8")
    body = (
        template.replace("__GENERATED_HEADER__", header)
        .replace("__QUARTERS_JSON__", json.dumps(quarters))
        .replace("__INCOME_ROWS__", rows_ts)
        .replace("__TICKER__", ticker)
        .replace("__SUBTITLE__", jsx_text(subtitle))
        .replace("__FISCAL_MAPPING_LINE__", fiscal_line)
        .replace("__STATS__", "\n".join(stat_blocks))
        .replace("__DEFAULT_CHART_ROWS__", json.dumps(default_chart))
        .replace("__NOTES__", "\n".join(note_blocks))
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")


def cmd_check(args: argparse.Namespace) -> None:
    if args.statement:
        print(json.dumps(check_staleness(args.ticker, args.statement), indent=2))
        return
    results = {stmt: check_staleness(args.ticker, stmt) for stmt in STATEMENT_SUFFIX}
    print(json.dumps({"ticker": normalize_ticker(args.ticker), "statements": results}, indent=2))


def check_all(ticker: str) -> dict[str, dict[str, Any]]:
    return {stmt: check_staleness(ticker, stmt) for stmt in STATEMENT_SUFFIX}


def cmd_edgar(args: argparse.Namespace) -> None:
    cik = lookup_cik(args.ticker)
    filings = latest_quarterly_filings(cik, limit=args.limit)
    print(json.dumps({"ticker": normalize_ticker(args.ticker), "cik": cik, "filings": filings}, indent=2))


def cmd_path(args: argparse.Namespace) -> None:
    if args.statement:
        print(json_path(args.ticker, args.statement))
        return
    t = normalize_ticker(args.ticker)
    for stmt in STATEMENT_SUFFIX:
        print(f"{stmt}: {json_path(t, stmt)}")


def cmd_validate(args: argparse.Namespace) -> None:
    data = load_json(Path(args.file))
    errors = validate_statement(data)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("OK")


def cmd_render(args: argparse.Namespace) -> None:
    canvas_dir = resolve_canvas_dir(args.canvas_dir)
    if args.statement == "income":
        path = json_path(args.ticker, "income")
        if not path.is_file():
            raise SystemExit(f"Missing JSON: {path}")
        data = load_json(path)
        out = canvas_dir / f"{normalize_ticker(args.ticker).lower()}-income.canvas.tsx"
        render_income_canvas(data, out)
        print(str(out))
        return

    from render_financials_canvas import financials_canvas_path, render_financials_canvas

    out = render_financials_canvas(
        args.ticker,
        financials_canvas_path(args.ticker, canvas_dir),
    )
    print(str(out))


def align_ticker(ticker: str, statement: str | None = None) -> list[str]:
    from statement_align import align_statement_rows

    t = normalize_ticker(ticker)
    stmts = [statement] if statement else list(STATEMENT_SUFFIX)
    paths: list[str] = []
    for stmt in stmts:
        path = json_path(t, stmt)
        if not path.is_file():
            continue
        data = load_json(path)
        rows, warnings = align_statement_rows(data)
        data["rows"] = rows
        save_json(path, data)
        paths.append(str(path))
        for w in warnings:
            print(f"  warn [{stmt}]: {w}", file=sys.stderr)
    return paths


def cmd_align(args: argparse.Namespace) -> None:
    paths = align_ticker(args.ticker, args.statement)
    if not paths:
        raise SystemExit(f"No JSON found for {args.ticker}")
    for p in paths:
        errors = validate_statement(load_json(Path(p)))
        if errors:
            print(f"validate {p}:\n" + "\n".join(errors), file=sys.stderr)
            raise SystemExit(1)
        print(p)


def cmd_build(args: argparse.Namespace) -> None:
    from statement_build import write_statement_json

    path = write_statement_json(args.ticker, args.statement or "income")
    print(str(path))


def sync_ticker(ticker: str, canvas_dir: Path) -> dict[str, Any]:
    t = normalize_ticker(ticker)
    checks = check_all(t)
    needs_any = checks["income"]["needsUpdate"] or any(
        not json_path(t, stmt).is_file() for stmt in ("balance-sheet", "cash-flow")
    )
    if needs_any:
        from statement_build import write_all_json

        try:
            write_all_json(t)
        except SystemExit as e:
            if not json_path(t, "income").is_file():
                raise
            # income exists; BS/CF may be unavailable for this filer format
            if str(e) and "income" in str(e).lower():
                raise

    from render_financials_canvas import financials_canvas_path, load_statements, render_financials_canvas

    statements = load_statements(t)
    if not statements:
        raise SystemExit(
            f"No JSON for {t}. Income build failed or no files under {json_path(t, 'income').parent}"
        )
    out = render_financials_canvas(t, financials_canvas_path(t, canvas_dir))
    missing = [stmt for stmt in STATEMENT_SUFFIX if stmt not in statements]
    coverage_gaps = {
        stmt: missing_data_columns(data)
        for stmt, data in statements.items()
        if missing_data_columns(data)
    }
    return {
        "ticker": t,
        "canvasPath": str(out),
        "available": list(statements.keys()),
        "missingJson": missing,
        "missingColumns": coverage_gaps,
        "checks": checks,
        "incomeRefreshed": checks["income"]["needsUpdate"],
    }


def cmd_sync(args: argparse.Namespace) -> None:
    canvas_dir = resolve_canvas_dir(args.canvas_dir)
    if args.statement == "income":
        status = check_staleness(args.ticker, "income")
        if status["needsUpdate"]:
            from income_xbrl import write_income_json

            write_income_json(args.ticker)
        path = json_path(args.ticker, "income")
        data = load_json(path)
        out = canvas_dir / f"{normalize_ticker(args.ticker).lower()}-income.canvas.tsx"
        render_income_canvas(data, out)
        print(json.dumps({"jsonPath": str(path), "canvasPath": str(out), "wasStale": status["needsUpdate"]}, indent=2))
        return

    result = sync_ticker(args.ticker, canvas_dir)
    if result["missingJson"]:
        result["note"] = (
            "Missing JSON for: "
            + ", ".join(result["missingJson"])
            + ". Build balance sheet / cash flow from SEC filings per skill, then re-run sync."
        )
    if result.get("missingColumns"):
        result["coverageNote"] = (
            "Anchor row gaps remain — fill missing quarters in JSON, then re-run sync: "
            + "; ".join(
                f"{stmt}: {', '.join(gaps[:3])}{'…' if len(gaps) > 3 else ''}"
                for stmt, gaps in result["missingColumns"].items()
            )
        )
    print(json.dumps(result, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="SEC financial JSON cache utilities")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="Check JSON staleness (all statements if statement omitted)")
    c.add_argument("ticker")
    c.add_argument("statement", nargs="?", choices=list(STATEMENT_SUFFIX), default=None)
    c.set_defaults(func=cmd_check)

    e = sub.add_parser("edgar", help="List recent quarterly SEC filings from EDGAR")
    e.add_argument("ticker")
    e.add_argument("--limit", type=int, default=8)
    e.set_defaults(func=cmd_edgar)

    pt = sub.add_parser("path", help="Print JSON file path(s)")
    pt.add_argument("ticker")
    pt.add_argument("statement", nargs="?", choices=list(STATEMENT_SUFFIX), default=None)
    pt.set_defaults(func=cmd_path)

    v = sub.add_parser("validate", help="Validate JSON file")
    v.add_argument("file")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("render", help="Render tabbed financials canvas (pass income for legacy single canvas)")
    r.add_argument("ticker")
    r.add_argument("statement", nargs="?", choices=["income"], default=None)
    r.add_argument("--canvas-dir", default=None, help=f"Default: {REPO_ROOT / 'canvas'}")
    r.set_defaults(func=cmd_render)

    al = sub.add_parser("align", help="Reorder JSON rows to canonical template")
    al.add_argument("ticker")
    al.add_argument("statement", nargs="?", choices=list(STATEMENT_SUFFIX), default=None)
    al.set_defaults(func=cmd_align)

    b = sub.add_parser("build", help="Build statement JSON from SEC XBRL")
    b.add_argument("ticker")
    b.add_argument("statement", nargs="?", choices=list(STATEMENT_SUFFIX), default=None)
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("sync", help="Refresh income if stale, render tabbed financials canvas")
    s.add_argument("ticker")
    s.add_argument("statement", nargs="?", choices=["income"], default=None)
    s.add_argument("--canvas-dir", default=None, help=f"Default: {REPO_ROOT / 'canvas'}")
    s.set_defaults(func=cmd_sync)

    args = p.parse_args()
    try:
        args.func(args)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"SEC HTTP {e.code}: {e.reason}") from e


if __name__ == "__main__":
    main()
