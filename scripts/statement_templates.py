"""Canonical Koyfin-aligned row order for income, balance sheet, and cash flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Display-value aliases when aligning legacy JSON → canonical labels.
LABEL_ALIASES: dict[str, str] = {
    "Total Revenues %Chg (YoY)": "Total Revenues %Chg",
    "Basic Weighted Avg Shares Outstanding": "Basic Weighted Average Shares Outstanding",
    "Diluted Weighted Avg Shares Outstanding": "Diluted Weighted Average Shares Outstanding",
    "Depreciation & Amortization (memo)": "Depreciation & Amortization (memo)",
    "EBITDA*": "EBITDA",
    "Accounts Receivable / Total Trade Receivables": "Total Trade Receivables",
    "Net Issuance / (Repurchase) of Common Shares": "Net Issuance / (Repurchases) of Common Shares",
}


@dataclass(frozen=True)
class RowSpec:
    label: str
    kind: str = "normal"
    unit: str = "$"
    plottable: bool = True
    derived: bool = False
    section: bool = False  # balance sheet / cash flow section divider


def _section(title: str) -> RowSpec:
    return RowSpec(title, kind="total", plottable=False, section=True)


# --- Income (single table, no section dividers) — union of AAPL / PANW / INTU Koyfin ---
INCOME_ROWS: list[RowSpec] = [
    RowSpec("Total Revenues", kind="total"),
    RowSpec("Total Revenues %Chg", kind="italic", unit="%", derived=True),
    RowSpec("Cost of Sales"),
    RowSpec("Gross Profit", kind="total", derived=True),
    RowSpec("Gross Profit Margin", kind="italic", unit="%", derived=True),
    RowSpec("Selling, General & Administrative Expenses"),
    RowSpec("Depreciation & Amortization Expenses"),
    RowSpec("Research & Development Expenses"),
    RowSpec("Other Operating Expenses"),
    RowSpec("Operating Profit", kind="total"),
    RowSpec("Operating Margin", kind="italic", unit="%", derived=True),
    RowSpec("Interest and Investment Income"),
    RowSpec("Interest Expense"),
    RowSpec("Non-Operating Income"),
    RowSpec("Total Non-Operating Income", kind="total"),
    RowSpec("Income Before Provision for Income Taxes", kind="total"),
    RowSpec("Provision for Income Taxes"),
    RowSpec("Consolidated Net Income", kind="total"),
    RowSpec("Net Income Attributable to Discontinued Operations"),
    RowSpec("Net Income Attributable to Common Shareholders", kind="total"),
    RowSpec("Basic EPS", unit="eps"),
    RowSpec("Diluted EPS", unit="eps"),
    RowSpec("Basic Weighted Average Shares Outstanding", kind="italic", unit="sh", plottable=False),
    RowSpec("Diluted Weighted Average Shares Outstanding", kind="italic", unit="sh", plottable=False),
    RowSpec("Shares Outstanding", kind="italic", unit="sh", plottable=False),
    RowSpec("EBITDA", kind="total", derived=True),
    RowSpec("Effective Tax Rate", kind="italic", unit="%", derived=True),
]

BALANCE_SHEET_ROWS: list[RowSpec] = [
    _section("Assets"),
    RowSpec("Cash and Cash Equivalents"),
    RowSpec("Short-Term Investments"),
    RowSpec("Total Cash and Cash Equivalents", kind="total", derived=True),
    RowSpec("Accounts Receivable"),
    RowSpec("Other Receivables"),
    RowSpec("Total Trade Receivables", kind="total", derived=True),
    RowSpec("Inventories"),
    RowSpec("Other Current Assets"),
    RowSpec("Total Current Assets", kind="total"),
    RowSpec("Net Property, Plant & Equipment"),
    RowSpec("Net Intangible Assets"),
    RowSpec("Goodwill"),
    RowSpec("Long-Term Investments"),
    RowSpec("Other Long-Term Assets"),
    RowSpec("Total Assets", kind="total"),
    _section("Liabilities"),
    RowSpec("Accounts Payable"),
    RowSpec("Accrued Expenses"),
    RowSpec("Short-Term Debt"),
    RowSpec("Current Portion of Long-Term Debt"),
    RowSpec("Current Portion of Leases"),
    RowSpec("Unearned Revenue"),
    RowSpec("Other Current Liabilities"),
    RowSpec("Total Current Liabilities", kind="total"),
    RowSpec("Long-Term Debt"),
    RowSpec("Leases"),
    RowSpec("Other Long-Term Liabilities"),
    RowSpec("Total Long-Term Liabilities", kind="total", derived=True),
    RowSpec("Total Liabilities", kind="total"),
    _section("Equity"),
    RowSpec("Common Stock"),
    RowSpec("Treasury Stock"),
    RowSpec("Additional Paid-In Capital"),
    RowSpec("Accumulated Other Comprehensive Income"),
    RowSpec("Retained Earnings"),
    RowSpec("Total Common Shareholders' Equity", kind="total"),
    RowSpec("Minority Interests and Other"),
    RowSpec("Total Shareholders' Equity", kind="total"),
    RowSpec("Total Liabilities and Shareholders' Equity", kind="total"),
]

CASH_FLOW_ROWS: list[RowSpec] = [
    _section("Operating Activities"),
    RowSpec("Net Income"),
    RowSpec("Depreciation & Amortization"),
    RowSpec("Share-Based Compensation Expense"),
    RowSpec("Other Adjustments", derived=True),
    RowSpec("Changes in Trade Receivables"),
    RowSpec("Changes in Inventories"),
    RowSpec("Changes in Accounts Payable"),
    RowSpec("Changes in Accrued Expenses"),
    RowSpec("Changes in Income Taxes Payable"),
    RowSpec("Changes in Unearned Revenue"),
    RowSpec("Changes in Other Operating Activities", derived=True),
    RowSpec("Cash from Operating Activities", kind="total"),
    _section("Investing Activities"),
    RowSpec("Capital Expenditure"),
    RowSpec("Proceeds from Sale of Property, Plant & Equipment"),
    RowSpec("Purchases of Intangible Assets"),
    RowSpec("Purchases of Investments"),
    RowSpec("Proceeds from Sale of Investments"),
    RowSpec("Payments for Business Acquisitions"),
    RowSpec("Proceeds from Business Divestments"),
    RowSpec("Other Investing Activities", derived=True),
    RowSpec("Cash from Investing Activities", kind="total"),
    _section("Financing Activities"),
    RowSpec("Issuance of Short-Term Debt"),
    RowSpec("Repayments of Short-Term Debt"),
    RowSpec("Net Issuance / (Repayments) of Short-Term Debt", derived=True),
    RowSpec("Issuance of Long-Term Debt"),
    RowSpec("Repayments of Long-Term Debt"),
    RowSpec("Net Issuance / (Repayments) of Long-Term Debt", derived=True),
    RowSpec("Issuance of Common Shares"),
    RowSpec("Repurchases of Common Shares"),
    RowSpec("Net Issuance / (Repurchases) of Common Shares", derived=True),
    RowSpec("Common Share Dividends Paid"),
    RowSpec("Other Financing Activities", derived=True),
    RowSpec("Cash from Financing Activities", kind="total"),
    _section("Free Cash Flow"),
    RowSpec("Free Cash Flow", kind="total", derived=True),
    RowSpec("NOPAT", derived=True),
    RowSpec("Levered Free Cash Flow", derived=True),
    RowSpec("Unlevered Free Cash Flow", derived=True),
    RowSpec("Net Change in Cash", kind="total"),
]

TEMPLATES: dict[str, list[RowSpec]] = {
    "income": INCOME_ROWS,
    "balance-sheet": BALANCE_SHEET_ROWS,
    "cash-flow": CASH_FLOW_ROWS,
}

ANCHOR_ROWS: dict[str, list[str]] = {
    "income": ["Total Revenues", "Consolidated Net Income"],
    "balance-sheet": ["Total Assets", "Total Liabilities", "Total Shareholders' Equity"],
    "cash-flow": ["Cash from Operating Activities", "Net Change in Cash"],
}


def canonical_label(label: str) -> str:
    return LABEL_ALIASES.get(label, label)


def template_labels(statement_type: str) -> list[str]:
    return [s.label for s in TEMPLATES[statement_type]]


def blank_values(n: int) -> list[str]:
    return ["—"] * n


def row_from_spec(spec: RowSpec, values: list[str], *, derived_override: bool | None = None) -> dict[str, Any]:
    return {
        "label": spec.label,
        "values": values,
        "kind": spec.kind,
        "unit": spec.unit,
        "plottable": spec.plottable,
        "derived": spec.derived if derived_override is None else derived_override,
    }


def section_divider_row(spec: RowSpec, n: int) -> dict[str, Any]:
    return {
        "label": spec.label,
        "values": [""] * n,
        "kind": "total",
        "unit": "$",
        "plottable": False,
        "derived": False,
        "sectionHeader": True,
    }
