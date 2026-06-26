"""Generic 12-quarter cash flow builder from SEC XBRL company facts."""

from __future__ import annotations

from typing import Any

from income_xbrl import (
    discover_quarters,
    fiscal_year_end_month,
    fmt_dollar,
    load_entity,
    load_usgaap,
    lookup_cik,
    to_num,
)
from sec_financials import json_path, latest_quarterly_filings, save_json
from statement_templates import CASH_FLOW_ROWS, row_from_spec, section_divider_row

CF_CONCEPTS: dict[str, list[str]] = {
    "Net Income": ["NetIncomeLoss", "ProfitLoss"],
    "Depreciation & Amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "_AmortizationOfIntangibleAssets": ["AmortizationOfIntangibleAssets"],
    "Share-Based Compensation Expense": [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
    ],
    "Changes in Trade Receivables": [
        "IncreaseDecreaseInAccountsReceivable",
        "IncreaseDecreaseInReceivables",
    ],
    "Changes in Inventories": ["IncreaseDecreaseInInventories"],
    "Changes in Accounts Payable": [
        "IncreaseDecreaseInAccountsPayable",
        "IncreaseDecreaseInAccountsPayableTrade",
    ],
    "Changes in Accrued Expenses": [
        "IncreaseDecreaseInAccruedLiabilities",
        "IncreaseDecreaseInEmployeeRelatedLiabilities",
    ],
    "Changes in Income Taxes Payable": [
        "IncreaseDecreaseInAccruedIncomeTaxesPayable",
        "IncreaseDecreaseInIncomeTaxesPayable",
    ],
    "Changes in Unearned Revenue": [
        "IncreaseDecreaseInContractWithCustomerLiability",
        "IncreaseDecreaseInDeferredRevenue",
    ],
    "Changes in Other Operating Activities": [
        "IncreaseDecreaseInOtherOperatingAssets",
        "IncreaseDecreaseInOtherOperatingLiabilities",
        "IncreaseDecreaseInOtherCurrentAssets",
        "IncreaseDecreaseInOtherCurrentLiabilities",
    ],
    "Cash from Operating Activities": ["NetCashProvidedByUsedInOperatingActivities"],
    "Capital Expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "Proceeds from Sale of Property, Plant & Equipment": [
        "ProceedsFromSaleOfPropertyPlantAndEquipment",
    ],
    "Purchases of Intangible Assets": ["PaymentsToAcquireIntangibleAssets"],
    "Purchases of Investments": [
        "PaymentsToAcquireInvestments",
        "PaymentsToAcquireAvailableForSaleSecuritiesDebt",
        "PaymentsToAcquireMarketableSecurities",
    ],
    "Proceeds from Sale of Investments": [
        "ProceedsFromMaturityPrepaymentAndCallOfAvailableForSaleSecurities",
        "ProceedsFromSaleOfAvailableForSaleSecuritiesDebt",
        "ProceedsFromSaleAndMaturityOfMarketableSecurities",
        "ProceedsFromSaleOfOtherInvestments",
    ],
    "Payments for Business Acquisitions": [
        "PaymentsToAcquireBusinessesNetOfCashAcquired",
        "PaymentsToAcquireBusinessesGross",
    ],
    "Proceeds from Business Divestments": [
        "ProceedsFromDivestitureOfBusinessesNetOfCashDivested",
    ],
    "Cash from Investing Activities": ["NetCashProvidedByUsedInInvestingActivities"],
    "Issuance of Short-Term Debt": ["ProceedsFromShortTermDebt"],
    "Repayments of Short-Term Debt": ["RepaymentsOfShortTermDebt"],
    "Issuance of Long-Term Debt": ["ProceedsFromIssuanceOfLongTermDebt"],
    "Repayments of Long-Term Debt": ["RepaymentsOfLongTermDebt"],
    "Issuance of Common Shares": [
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromStockOptionsExercised",
    ],
    "Repurchases of Common Shares": ["PaymentsForRepurchaseOfCommonStock"],
    "Common Share Dividends Paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "Other Financing Activities": ["ProceedsFromPaymentsForOtherFinancingActivities"],
    "Cash from Financing Activities": ["NetCashProvidedByUsedInFinancingActivities"],
    "Net Change in Cash": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ],
}

OUTFLOW_ROWS = {
    "Capital Expenditure",
    "Purchases of Intangible Assets",
    "Purchases of Investments",
    "Payments for Business Acquisitions",
    "Repayments of Short-Term Debt",
    "Repayments of Long-Term Debt",
    "Repurchases of Common Shares",
    "Common Share Dividends Paid",
}

OPTIONAL_CF_ROWS = {
    "Proceeds from Sale of Property, Plant & Equipment",
    "Purchases of Intangible Assets",
    "Payments for Business Acquisitions",
    "Proceeds from Business Divestments",
    "Issuance of Short-Term Debt",
    "Repayments of Short-Term Debt",
    "Issuance of Long-Term Debt",
    "Repayments of Long-Term Debt",
    "Issuance of Common Shares",
    "Repurchases of Common Shares",
    "Common Share Dividends Paid",
    "Other Financing Activities",
    "Changes in Inventories",
    "Changes in Accrued Expenses",
    "Changes in Income Taxes Payable",
    "Changes in Unearned Revenue",
}


def _ytd_m(usgaap: dict, concepts: list[str], end: str, fy_start: str) -> float | None:
    for concept in concepts:
        c = usgaap.get(concept)
        if not c:
            continue
        for it in c.get("units", {}).get("USD", []):
            if it.get("end") != end or it.get("start") != fy_start:
                continue
            if it.get("form") not in ("10-Q", "10-K"):
                continue
            return round(it["val"] / 1e6)
    return None


def _fy_start_for_end(usgaap: dict, end: str) -> str | None:
    for concept in CF_CONCEPTS["Cash from Operating Activities"]:
        c = usgaap.get(concept)
        if not c:
            continue
        for it in c.get("units", {}).get("USD", []):
            if it.get("end") == end and it.get("start") and it.get("form") in ("10-Q", "10-K"):
                return it["start"]
    return None


def _quarterly_flow(
    usgaap: dict,
    concepts: list[str],
    end: str,
    prev_end: str | None,
    fy_start: str,
) -> float | None:
    cur = _ytd_m(usgaap, concepts, end, fy_start)
    if cur is None:
        return None
    if not prev_end:
        return cur
    prev_start = _fy_start_for_end(usgaap, prev_end)
    if prev_start != fy_start:
        return cur
    prev = _ytd_m(usgaap, concepts, prev_end, fy_start)
    if prev is None:
        return cur
    return cur - prev


def _normalize_outflow(label: str, v: float | None) -> float | None:
    if v is None:
        return None
    if label in OUTFLOW_ROWS and v > 0:
        return -v
    return v


def build_cf_series(usgaap: dict, period_ends: list[str]) -> dict[str, list[float | None]]:
    n = len(period_ends)
    fy_starts = [_fy_start_for_end(usgaap, e) for e in period_ends]
    prev_ends = [period_ends[i + 1] if i + 1 < n else None for i in range(n)]

    series: dict[str, list[float | None]] = {}
    for label, concepts in CF_CONCEPTS.items():
        if label.startswith("_"):
            continue
        vals: list[float | None] = []
        for i, end in enumerate(period_ends):
            fs = fy_starts[i]
            if not fs:
                vals.append(None)
                continue
            v = _normalize_outflow(label, _quarterly_flow(usgaap, concepts, end, prev_ends[i], fs))
            vals.append(v)
        series[label] = vals

    amort_concepts = CF_CONCEPTS["_AmortizationOfIntangibleAssets"]
    for i, end in enumerate(period_ends):
        fs = fy_starts[i]
        if not fs:
            continue
        base = series["Depreciation & Amortization"][i]
        extra = _quarterly_flow(usgaap, amort_concepts, end, prev_ends[i], fs)
        if base is not None and extra is not None and extra > 0:
            series["Depreciation & Amortization"][i] = base + extra

    series["Net Issuance / (Repayments) of Short-Term Debt"] = [
        (series["Issuance of Short-Term Debt"][i] or 0) + (series["Repayments of Short-Term Debt"][i] or 0)
        if series["Issuance of Short-Term Debt"][i] is not None or series["Repayments of Short-Term Debt"][i] is not None
        else None
        for i in range(n)
    ]
    series["Net Issuance / (Repayments) of Long-Term Debt"] = [
        (series["Issuance of Long-Term Debt"][i] or 0) + (series["Repayments of Long-Term Debt"][i] or 0)
        if series["Issuance of Long-Term Debt"][i] is not None or series["Repayments of Long-Term Debt"][i] is not None
        else None
        for i in range(n)
    ]
    series["Net Issuance / (Repurchases) of Common Shares"] = [
        (series["Issuance of Common Shares"][i] or 0) + (series["Repurchases of Common Shares"][i] or 0)
        if series["Issuance of Common Shares"][i] is not None or series["Repurchases of Common Shares"][i] is not None
        else None
        for i in range(n)
    ]

    wc_rows = [
        "Changes in Trade Receivables",
        "Changes in Inventories",
        "Changes in Accounts Payable",
        "Changes in Accrued Expenses",
        "Changes in Income Taxes Payable",
        "Changes in Unearned Revenue",
        "Changes in Other Operating Activities",
    ]
    op_inputs = ["Net Income", "Depreciation & Amortization", "Share-Based Compensation Expense"] + wc_rows
    series["Other Adjustments"] = []
    for i in range(n):
        op = series["Cash from Operating Activities"][i]
        if op is None:
            series["Other Adjustments"].append(None)
            continue
        parts = [series[r][i] for r in op_inputs]
        if all(v is None for v in parts):
            series["Other Adjustments"].append(None)
            continue
        series["Other Adjustments"].append(op - sum(v or 0 for v in parts))

    inv_rows = [
        "Capital Expenditure",
        "Proceeds from Sale of Property, Plant & Equipment",
        "Purchases of Intangible Assets",
        "Purchases of Investments",
        "Proceeds from Sale of Investments",
        "Payments for Business Acquisitions",
        "Proceeds from Business Divestments",
    ]
    series["Other Investing Activities"] = []
    for i in range(n):
        inv = series["Cash from Investing Activities"][i]
        if inv is None:
            series["Other Investing Activities"].append(None)
            continue
        parts = [series[r][i] for r in inv_rows]
        if all(v is None for v in parts):
            series["Other Investing Activities"].append(None)
            continue
        series["Other Investing Activities"].append(inv - sum(v or 0 for v in parts))

    op = series["Cash from Operating Activities"]
    capex = series["Capital Expenditure"]
    series["Free Cash Flow"] = [
        (op[i] + capex[i]) if op[i] is not None and capex[i] is not None else None for i in range(n)
    ]
    ni = series["Net Income"]
    tax_rate = 0.21
    series["NOPAT"] = [ni[i] * (1 - tax_rate) if ni[i] is not None else None for i in range(n)]
    series["Levered Free Cash Flow"] = list(series["Free Cash Flow"])
    series["Unlevered Free Cash Flow"] = list(series["Free Cash Flow"])
    return series


def build_cf_rows(usgaap: dict, period_ends: list[str]) -> list[dict[str, Any]]:
    series = build_cf_series(usgaap, period_ends)
    n = len(period_ends)
    rows_out: list[dict[str, Any]] = []
    for spec in CASH_FLOW_ROWS:
        if spec.section:
            rows_out.append(section_divider_row(spec, n))
            continue
        data = series.get(spec.label)
        if data is None:
            continue
        if spec.label in OPTIONAL_CF_ROWS and all(v is None for v in data):
            continue
        values = [fmt_dollar(v, derived=spec.derived) if v is not None else "—" for v in data]
        rows_out.append(row_from_spec(spec, values))
    return rows_out


def _data_row_values(rows: list[dict[str, Any]], label: str) -> list[str] | None:
    matches = [r for r in rows if r["label"] == label and not r.get("sectionHeader")]
    return matches[-1]["values"] if matches else None


def verify_cf_rows(rows: list[dict[str, Any]], n: int) -> dict[str, Any]:
    by = {r["label"]: r["values"] for r in rows if not r.get("sectionHeader")}

    def num(label: str, i: int) -> float | None:
        vals = by.get(label, [])
        return to_num(vals[i]) if i < len(vals) else None

    section_ok = True
    exc: list[str] = []
    for i in range(n):
        op = num("Cash from Operating Activities", i)
        inv = num("Cash from Investing Activities", i)
        fin = num("Cash from Financing Activities", i)
        net = num("Net Change in Cash", i)
        if op is not None and inv is not None and fin is not None and net is not None:
            if abs(op + inv + fin - net) > 5:
                section_ok = False
                exc.append(f"col {i} O+I+F≠ΔCash")
    return {"sectionsTieToNetChangeInCash": section_ok, "exceptions": exc}


def build_cf_document(ticker: str) -> dict[str, Any]:
    t = ticker.strip().upper()
    cik = lookup_cik(t)
    entity = load_entity(cik)
    company = entity.get("name") or t
    fy_end = fiscal_year_end_month(entity)
    quarters = discover_quarters(cik, 12)
    period_ends = [q["periodEnd"] for q in quarters]
    usgaap = load_usgaap(cik)
    rows = build_cf_rows(usgaap, period_ends)
    verification = verify_cf_rows(rows, len(quarters))
    latest = latest_quarterly_filings(cik, limit=1)[0]
    q0 = quarters[0]
    op = _data_row_values(rows, "Cash from Operating Activities")[0]
    fcf_vals = _data_row_values(rows, "Free Cash Flow")
    fcf = fcf_vals[0] if fcf_vals else "—"
    return {
        "schemaVersion": 1,
        "statementType": "cash-flow",
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
                f"{company} · Last 12 quarters · USD millions · Three Months Ended. "
                "Source: SEC XBRL (10-Q/10-K company facts)."
            ),
            "fiscalMapping": " · ".join(f"{q['label']} = {q['fiscalLabel']}" for q in quarters),
            "stats": [
                {"value": f"${op}M", "label": f"Operating CF — {q0['fiscalLabel']}", "tone": "info"},
                {"value": f"${fcf}M", "label": "Free Cash Flow (latest)"},
            ],
            "defaultChartRows": ["Cash from Operating Activities", "Free Cash Flow"],
        },
        "notes": [
            "Standalone quarterly columns derived from fiscal-YTD XBRL flows (current YTD − prior-quarter YTD).",
            "CapEx and outflows shown negative (standard outflow convention).",
            "Free Cash Flow*, NOPAT*, Levered FCF*, Unlevered FCF* are derived memo lines.",
        ],
        "verification": verification,
    }


def write_cf_json(ticker: str):
    from statement_build import write_statement_json

    return write_statement_json(ticker, "cash-flow")
