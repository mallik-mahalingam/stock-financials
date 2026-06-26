"""Generic 12-quarter balance sheet builder from SEC XBRL company facts."""

from __future__ import annotations

from typing import Any

from income_xbrl import discover_quarters, fiscal_year_end_month, fmt_dollar, load_entity, load_usgaap, lookup_cik, pick, to_num
from sec_financials import json_path, latest_quarterly_filings, save_json
from statement_templates import BALANCE_SHEET_ROWS, row_from_spec, section_divider_row

BS_CONCEPTS: dict[str, list[str]] = {
    "Cash and Cash Equivalents": ["CashAndCashEquivalentsAtCarryingValue", "Cash"],
    "Short-Term Investments": [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "RestrictedCashAndCashEquivalentsAtCarryingValue",
        "RestrictedCash",
    ],
    "Accounts Receivable": ["AccountsReceivableNetCurrent", "AccountsReceivableNet"],
    "Other Receivables": [
        "NontradeReceivablesCurrent",
        "NotesAndLoansReceivableNetCurrent",
        "OtherReceivables",
        "FinancingReceivable",
        "FinancingReceivableCurrent",
    ],
    "Inventories": ["InventoryNet", "Inventories"],
    "Other Current Assets": ["OtherAssetsCurrent", "PrepaidExpenseAndOtherAssetsCurrent"],
    "Total Current Assets": ["AssetsCurrent"],
    "Net Property, Plant & Equipment": [
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
    ],
    "Net Intangible Assets": [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ],
    "Goodwill": ["Goodwill"],
    "Long-Term Investments": [
        "LongTermInvestments",
        "MarketableSecuritiesNoncurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
    ],
    "Other Long-Term Assets": ["OtherAssetsNoncurrent", "OtherAssets"],
    "Total Assets": ["Assets"],
    "Accounts Payable": ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"],
    "Accrued Expenses": ["EmployeeRelatedLiabilitiesCurrent", "AccruedLiabilitiesCurrent"],
    "Short-Term Debt": [
        "ShortTermBorrowings",
        "DebtCurrent",
        "LongTermDebtCurrentMaturitiesRepaidOfPrincipalInNextTwelveMonths",
    ],
    "Current Portion of Long-Term Debt": [
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "ConvertibleDebtCurrent",
    ],
    "Current Portion of Leases": [
        "FinanceLeaseLiabilityCurrent",
        "OperatingLeaseLiabilityCurrent",
    ],
    "Unearned Revenue": [
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenueCurrent",
    ],
    "Other Current Liabilities": ["OtherLiabilitiesCurrent"],
    "Total Current Liabilities": ["LiabilitiesCurrent"],
    "Long-Term Debt": ["LongTermDebtNoncurrent", "LongTermDebt", "ConvertibleDebtNoncurrent"],
    "Leases": [
        "FinanceLeaseLiabilityNoncurrent",
        "OperatingLeaseLiabilityNoncurrent",
    ],
    "Other Long-Term Liabilities": ["OtherLiabilitiesNoncurrent"],
    "Total Long-Term Liabilities": ["LiabilitiesNoncurrent"],
    "Total Liabilities": ["Liabilities"],
    "Common Stock": ["CommonStockValue"],
    "Treasury Stock": ["TreasuryStockValue", "TreasuryStockCommon"],
    "Additional Paid-In Capital": [
        "AdditionalPaidInCapital",
        "AdditionalPaidInCapitalCommonStock",
        "CommonStocksIncludingAdditionalPaidInCapital",
    ],
    "Accumulated Other Comprehensive Income": [
        "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
    ],
    "Retained Earnings": ["RetainedEarningsAccumulatedDeficit"],
    "Total Common Shareholders' Equity": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "StockholdersEquity"],
    "Minority Interests and Other": ["MinorityInterest", "StockholdersEquityAttributableToNoncontrollingInterest"],
    "Total Shareholders' Equity": ["StockholdersEquity"],
    "Total Liabilities and Shareholders' Equity": ["LiabilitiesAndStockholdersEquity"],
}

OPTIONAL_BS_ROWS = {
    "Short-Term Investments",
    "Other Receivables",
    "Inventories",
    "Net Intangible Assets",
    "Goodwill",
    "Long-Term Investments",
    "Accrued Expenses",
    "Short-Term Debt",
    "Current Portion of Long-Term Debt",
    "Current Portion of Leases",
    "Unearned Revenue",
    "Long-Term Debt",
    "Leases",
    "Common Stock",
    "Treasury Stock",
    "Additional Paid-In Capital",
    "Minority Interests and Other",
}


def _instant(usgaap: dict, concepts: list[str], end: str) -> float | None:
    return pick(usgaap, concepts, end, instant=True, qtr=False)


def build_bs_series(usgaap: dict, period_ends: list[str]) -> dict[str, list[float | None]]:
    n = len(period_ends)
    series: dict[str, list[float | None]] = {}
    for label, concepts in BS_CONCEPTS.items():
        series[label] = [_instant(usgaap, concepts, e) for e in period_ends]

    for i, e in enumerate(period_ends):
        emp = pick(usgaap, ["EmployeeRelatedLiabilitiesCurrent"], e, instant=True, qtr=False)
        acc = pick(usgaap, ["AccruedLiabilitiesCurrent"], e, instant=True, qtr=False)
        if emp is not None:
            series["Accrued Expenses"][i] = emp
        elif acc is not None:
            series["Accrued Expenses"][i] = acc
        if emp is not None and acc is not None and abs(acc - (emp or 0)) > 1:
            series["Other Current Liabilities"][i] = acc

        treasury = series["Treasury Stock"][i]
        if treasury is not None and treasury > 0:
            series["Treasury Stock"][i] = -treasury

    # Derived subtotals when components exist
    for i in range(n):
        cash = series["Cash and Cash Equivalents"][i]
        sti = series["Short-Term Investments"][i]
        if cash is not None or sti is not None:
            series.setdefault("Total Cash and Cash Equivalents", [None] * n)
            series["Total Cash and Cash Equivalents"][i] = (cash or 0) + (sti or 0)

        ar = series["Accounts Receivable"][i]
        oth = series["Other Receivables"][i]
        if ar is not None or oth is not None:
            series.setdefault("Total Trade Receivables", [None] * n)
            series["Total Trade Receivables"][i] = (ar or 0) + (oth or 0)

    if "Total Cash and Cash Equivalents" not in series:
        series["Total Cash and Cash Equivalents"] = [None] * n
    if "Total Trade Receivables" not in series:
        series["Total Trade Receivables"] = [None] * n

    for i in range(n):
        lt = series["Total Long-Term Liabilities"][i]
        if lt is None:
            total_l = series["Total Liabilities"][i]
            cur_l = series["Total Current Liabilities"][i]
            if total_l is not None and cur_l is not None:
                series["Total Long-Term Liabilities"][i] = total_l - cur_l

    return series


def build_bs_rows(usgaap: dict, period_ends: list[str]) -> list[dict[str, Any]]:
    series = build_bs_series(usgaap, period_ends)
    n = len(period_ends)
    rows_out: list[dict[str, Any]] = []
    for spec in BALANCE_SHEET_ROWS:
        if spec.section:
            rows_out.append(section_divider_row(spec, n))
            continue
        data = series.get(spec.label)
        if data is None:
            continue
        if spec.label in OPTIONAL_BS_ROWS and all(v is None for v in data):
            continue
        derived_flags = spec.label in ("Total Cash and Cash Equivalents", "Total Trade Receivables")
        values = [
            fmt_dollar(v, derived=derived_flags) if v is not None else "—"
            for v in data
        ]
        rows_out.append(row_from_spec(spec, values))
    return rows_out


def verify_bs_rows(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    by = {r["label"]: r["values"] for r in rows}

    def num(label: str, i: int) -> float | None:
        vals = by.get(label, [])
        return to_num(vals[i]) if i < len(vals) else None

    ok = True
    exc: list[str] = []
    for i in range(n):
        assets = num("Total Assets", i)
        liab = num("Total Liabilities", i)
        equity = num("Total Shareholders' Equity", i)
        if assets is not None and liab is not None and equity is not None:
            if abs(assets - liab - equity) > 2:
                ok = False
                exc.append(f"col {i} A≠L+E")
    return {"assetsEqualsLiabilitiesPlusEquity": ok, "exceptions": exc}


def build_bs_document(ticker: str) -> dict[str, Any]:
    t = ticker.strip().upper()
    cik = lookup_cik(t)
    entity = load_entity(cik)
    company = entity.get("name") or t
    fy_end = fiscal_year_end_month(entity)
    quarters = discover_quarters(cik, 12)
    period_ends = [q["periodEnd"] for q in quarters]
    usgaap = load_usgaap(cik)
    rows = build_bs_rows(usgaap, period_ends)
    verification = verify_bs_rows(rows, len(quarters))
    latest = latest_quarterly_filings(cik, limit=1)[0]
    q0 = quarters[0]
    assets = next(r["values"][0] for r in rows if r["label"] == "Total Assets")
    return {
        "schemaVersion": 1,
        "statementType": "balance-sheet",
        "ticker": t,
        "companyName": company,
        "currency": "USD",
        "unit": "millions",
        "fiscalYearEndMonth": fy_end,
        "edgar": {
            "cik": cik.zfill(10),
            "latestQuarterlyFilingDate": latest["filingDate"],
            "latestQuarterlyForm": latest["form"],
            "latestQuarterlyAccession": latest["accessionNumber"],
            "latestQuarterlyUrl": latest["url"],
        },
        "quarters": quarters,
        "rows": rows,
        "summary": {
            "subtitle": (
                f"{company} · Last 12 quarters · USD millions · Period-end snapshots. "
                "Source: SEC XBRL (10-Q/10-K company facts)."
            ),
            "fiscalMapping": " · ".join(f"{q['label']} = {q['fiscalLabel']}" for q in quarters),
            "stats": [
                {"value": f"${assets}M", "label": f"Total Assets — {q0['fiscalLabel']}", "tone": "info"},
            ],
            "defaultChartRows": ["Total Assets", "Total Shareholders' Equity"],
        },
        "notes": [
            "Period-end instant tags from SEC XBRL company facts.",
            "Total Cash* = Cash + Short-Term Investments; Total Trade Receivables* = A/R + Other Receivables when split.",
        ],
        "verification": verification,
    }


def write_bs_json(ticker: str):
    from statement_build import write_statement_json

    return write_statement_json(ticker, "balance-sheet")
