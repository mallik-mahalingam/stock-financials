"""Generic 12-quarter income statement builder from SEC XBRL company facts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sec_financials import (
    data_dir,
    json_path,
    latest_quarterly_filings,
    lookup_cik,
    save_json,
    sec_get,
)
from statement_templates import INCOME_ROWS, row_from_spec

SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_usgaap(cik: str) -> dict:
    data = sec_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
    return data["facts"]["us-gaap"]


def load_entity(cik: str) -> dict:
    return sec_get(SEC_SUBMISSIONS.format(cik=cik))


def quarter_label(period_end: str) -> str:
    y, m, _ = period_end.split("-")
    return f"{MONTHS[int(m) - 1]} '{y[2:]}"


def fiscal_year_end_month(entity: dict) -> int:
    raw = entity.get("fiscalYearEnd") or entity.get("filings", {}).get("fiscalYearEnd") or "1231"
    return int(str(raw)[0:2])


def fiscal_quarter_label(period_end: str, fy_end_month: int) -> str:
    y, m, _ = map(int, period_end.split("-"))
    fy = y if m <= fy_end_month else y + 1
    start_month = (fy_end_month % 12) + 1
    elapsed = (m - start_month) if m >= start_month else (12 - start_month) + m
    q = elapsed // 3 + 1
    return f"Q{q} FY{fy % 100:02d}"


def discover_quarters(cik: str, n: int = 12, min_quarters: int = 4) -> list[dict[str, Any]]:
    entity = load_entity(cik)
    recent = entity["filings"]["recent"]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, form in enumerate(recent["form"]):
        if form not in ("10-Q", "10-K"):
            continue
        pe = recent.get("reportDate", [""])[i]
        if not pe or pe in seen:
            continue
        seen.add(pe)
        acc = recent["accessionNumber"][i]
        doc = recent.get("primaryDocument", [""])[i]
        out.append(
            {
                "label": quarter_label(pe),
                "periodEnd": pe,
                "fiscalLabel": fiscal_quarter_label(pe, fiscal_year_end_month(entity)),
                "source": {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "accessionNumber": acc,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}",
                },
            }
        )
        if len(out) >= n:
            break
    if len(out) < min_quarters:
        raise SystemExit(
            f"Only found {len(out)} quarter-ends in EDGAR submissions (need at least {min_quarters})"
        )
    return out


def months_between(s: str, e: str) -> float:
    sy, sm, sd = map(int, s.split("-"))
    ey, em, ed = map(int, e.split("-"))
    return (ey - sy) * 12 + (em - sm) + (ed - sd) / 30


def pick(usgaap: dict, concepts: list[str], end: str, unit: str = "USD", *, instant: bool = False, qtr: bool = True):
    for concept in concepts:
        c = usgaap.get(concept)
        if not c:
            continue
        cand = []
        for it in c.get("units", {}).get(unit, []):
            if it.get("end") != end:
                continue
            if instant:
                if it.get("start"):
                    continue
            else:
                if not it.get("start"):
                    continue
                dur = months_between(it["start"], it["end"])
                if qtr and not (2.5 <= dur <= 3.5):
                    continue
            if it.get("form") not in ("10-Q", "10-K"):
                continue
            cand.append(it)
        if cand:
            cand.sort(key=lambda x: x.get("filed", ""), reverse=True)
            if unit == "shares" and qtr and len(cand) > 1:
                scaled = sorted({round(it["val"] / 1e6, 1) for it in cand})
                if len(scaled) > 1 and max(scaled) / min(scaled) > 1.5:
                    return min(scaled)
            v = cand[0]["val"]
            if unit == "USD":
                return round(v / 1e6)
            if unit == "USD/shares":
                return round(v, 2)
            if unit == "shares":
                return round(v / 1e6, 1)
            return v
    return None


def _halve_if_double(value: float | None, prior: float | None) -> float | None:
    """Some filers duplicate share counts at ~2× (e.g. PANW 2025)."""
    if value is None or prior is None or prior == 0:
        return value
    ratio = value / prior
    if 1.85 <= ratio <= 2.15:
        return round(value / 2, 1)
    return value


def apply_share_duplicate_fix(
    *series_and_instant: list[float | None],
) -> None:
    """Fix ~2× duplicate share counts using instant shares as anchor (newest index 0)."""
    if len(series_and_instant) < 2:
        return
    instant = series_and_instant[-1]
    series_list = list(series_and_instant[:-1])
    n = len(instant)
    for i in range(n - 1, 0, -1):
        newer, older = i - 1, i
        if instant[newer] is None or instant[older] is None:
            continue
        if not (1.85 <= instant[newer] / instant[older] <= 2.15):
            continue
        for series in series_list:
            series[newer] = _halve_if_double(series[newer], series[older])
        instant[newer] = _halve_if_double(instant[newer], instant[older])


def annual(usgaap: dict, concept: str, end: str, unit: str = "USD"):
    y = int(end[:4])
    c = usgaap.get(concept)
    if not c:
        return None
    for it in c.get("units", {}).get(unit, []):
        if it.get("end") != end or it.get("start") != f"{y}-01-01":
            continue
        if it.get("form") != "10-K":
            continue
        v = it["val"]
        return round(v / 1e6) if unit == "USD" else round(v, 2) if unit == "USD/shares" else round(v / 1e6, 1)
    return None


def ytd9(usgaap: dict, concept: str, year: int, unit: str = "USD"):
    c = usgaap.get(concept)
    if not c:
        return None
    for it in c.get("units", {}).get(unit, []):
        if it.get("end") != f"{year}-09-30" or it.get("start") != f"{year}-01-01":
            continue
        if it.get("form") != "10-Q":
            continue
        v = it["val"]
        return round(v / 1e6) if unit == "USD" else round(v, 2) if unit == "USD/shares" else round(v / 1e6, 1)
    return None


def q4_flow_dec(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    year = int(end[:4])
    for concept in concepts:
        a = annual(usgaap, concept, end, unit)
        b = ytd9(usgaap, concept, year, unit)
        if a is not None and b is not None:
            if unit == "USD":
                return a - b
            if unit == "USD/shares":
                return round(a - b, 2)
            if unit == "shares":
                continue
            return a - b
    return None


def q4_flow_jan(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    """FY (Feb–Jan) minus YTD9 (Feb–Oct) for January fiscal year-end filers."""
    year = int(end[:4])
    fy_start = f"{year - 1}-02-01"
    ytd9_end = f"{year - 1}-10-31"
    return _q4_flow_fy_minus_ytd9(usgaap, concepts, end, fy_start, ytd9_end, unit)


def q4_flow_jul(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    """FY (Aug–Jul) minus YTD9 (Aug–Apr) for July fiscal year-end filers."""
    year = int(end[:4])
    fy_start = f"{year - 1}-08-01"
    ytd9_end = f"{year}-04-30"
    return _q4_flow_fy_minus_ytd9(usgaap, concepts, end, fy_start, ytd9_end, unit)


def _q4_flow_fy_minus_ytd9(
    usgaap: dict,
    concepts: list[str],
    end: str,
    fy_start: str,
    ytd9_end: str,
    unit: str = "USD",
):
    for concept in concepts:
        c = usgaap.get(concept)
        if not c:
            continue
        fy_val = ytd9_val = None
        for it in c.get("units", {}).get(unit, []):
            if it.get("form") not in ("10-Q", "10-K"):
                continue
            if it.get("end") == end and it.get("start") == fy_start:
                fy_val = it["val"]
            if it.get("end") == ytd9_end and it.get("start") == fy_start:
                ytd9_val = it["val"]
        if fy_val is not None and ytd9_val is not None:
            diff = fy_val - ytd9_val
            if unit == "USD":
                return round(diff / 1e6)
            if unit == "USD/shares":
                return round(diff, 2)
            if unit == "shares":
                continue
            return diff
    return None


def q4_flow_auto(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    """FY 10-K minus ~9M YTD 10-Q with same fiscal start (Sep/Oct FY, etc.)."""
    for concept in concepts:
        c = usgaap.get(concept)
        if not c:
            continue
        fy_val = fy_start = None
        for it in c.get("units", {}).get(unit, []):
            if it.get("end") != end or it.get("form") != "10-K" or not it.get("start"):
                continue
            fy_val = it["val"]
            fy_start = it["start"]
            break
        if fy_val is None or not fy_start:
            continue
        ytd9_val = None
        for it in c.get("units", {}).get(unit, []):
            if it.get("start") != fy_start or it.get("form") != "10-Q":
                continue
            dur = months_between(it["start"], it["end"])
            if 8.5 <= dur <= 9.5:
                ytd9_val = it["val"]
                break
        if ytd9_val is not None:
            diff = fy_val - ytd9_val
            if unit == "USD":
                return round(diff / 1e6)
            if unit == "USD/shares":
                return round(diff, 2)
            if unit == "shares":
                continue
            return diff
    return None


def is_fiscal_year_end(usgaap: dict, end: str) -> bool:
    for concept in ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "NetIncomeLoss"):
        c = usgaap.get(concept)
        if not c:
            continue
        for it in c.get("units", {}).get("USD", []):
            if it.get("end") == end and it.get("form") == "10-K" and it.get("start"):
                return True
    return end.endswith(FY_END_Q4_SUFFIXES)


def q4_flow(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    if end.endswith("-01-31"):
        v = q4_flow_jan(usgaap, concepts, end, unit)
        if v is not None:
            return v
    elif end.endswith("-07-31"):
        v = q4_flow_jul(usgaap, concepts, end, unit)
        if v is not None:
            return v
    elif end.endswith("-12-31"):
        v = q4_flow_dec(usgaap, concepts, end, unit)
        if v is not None:
            return v
    return q4_flow_auto(usgaap, concepts, end, unit)


def shares_from_eps(net_m: float | None, eps: float | None) -> float | None:
    if net_m is None or eps is None or eps == 0:
        return None
    return round(abs(net_m) / abs(eps), 1)


FY_END_Q4_SUFFIXES = ("-12-31", "-01-31", "-07-31", "-09-30")


def flow(usgaap: dict, concepts: list[str], end: str, unit: str = "USD"):
    v = pick(usgaap, concepts, end, unit, instant=False, qtr=True)
    if v is not None:
        return v
    if unit == "shares" and is_fiscal_year_end(usgaap, end):
        return None
    if is_fiscal_year_end(usgaap, end):
        return q4_flow(usgaap, concepts, end, unit)
    return None


def g(usgaap: dict, concepts: list[str], end: str, *, unit: str = "USD"):
    return flow(usgaap, concepts, end, unit)


REVENUE_CONCEPTS = [
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
]

COGS_CONCEPTS = ["CostOfRevenue", "CostOfGoodsAndServicesSold"]

# Legacy order kept for filers without a GrossProfit XBRL tag.
LEGACY_REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]


def _ties_gross_profit(rev: float, cogs: float, gp_tagged: float, *, tol: float = 1.0) -> bool:
    return abs(rev - cogs - gp_tagged) <= tol


def resolve_rev_cogs_gross(
    usgaap: dict,
    end: str,
    cogs_c: list[str],
) -> tuple[float | None, float | None, float | None, bool, str | None, str | None]:
    """Pick revenue + COGS that tie to tagged GrossProfit when available.

    Fintech-heavy filers (e.g. MELI) tag ``Revenues`` as net revenues *and* financial
    income while ``CostOfGoodsAndServicesSold`` is cost of net revenues *and* financial
    expenses. Using contract revenue with that broad COGS crushes gross margin.
    """
    gp_tagged = g(usgaap, ["GrossProfit"], end)
    cogs_derived, cogs_is_derived = resolve_cogs(usgaap, end, cogs_c)

    if gp_tagged is not None:
        for rev_concept in REVENUE_CONCEPTS:
            rev = g(usgaap, [rev_concept], end)
            if rev is None:
                continue
            for cogs_concept in COGS_CONCEPTS:
                cogs = g(usgaap, [cogs_concept], end)
                if cogs is None:
                    continue
                if _ties_gross_profit(rev, cogs, gp_tagged):
                    return rev, cogs, gp_tagged, False, rev_concept, cogs_concept
        if cogs_derived is not None:
            for rev_concept in REVENUE_CONCEPTS:
                rev = g(usgaap, [rev_concept], end)
                if rev is None:
                    continue
                if _ties_gross_profit(rev, cogs_derived, gp_tagged):
                    return rev, cogs_derived, gp_tagged, cogs_is_derived, rev_concept, "derived"

    rev = g(usgaap, LEGACY_REVENUE_CONCEPTS, end)
    cogs = cogs_derived
    if rev is not None and cogs is not None:
        gross = rev - cogs
        if gp_tagged is not None and not _ties_gross_profit(rev, cogs, gp_tagged):
            gross = gp_tagged
        return rev, cogs, gross, cogs_is_derived, None, None
    if gp_tagged is not None:
        return rev, cogs, gp_tagged, cogs_is_derived, None, None
    return rev, cogs, None, cogs_is_derived, None, None


def resolve_cogs(usgaap: dict, end: str, cogs_c: list[str]) -> tuple[float | None, bool]:
    """Return (cost of sales, derived?). Some filers (e.g. INTU) omit CostOfRevenue in XBRL."""
    direct = g(usgaap, cogs_c, end)
    if direct is not None:
        return direct, False
    ce = g(usgaap, ["CostsAndExpenses"], end)
    sm = g(usgaap, ["SellingAndMarketingExpense"], end)
    rd = g(usgaap, ["ResearchAndDevelopmentExpense"], end)
    ga = g(usgaap, ["GeneralAndAdministrativeExpense"], end)
    if ce is None or sm is None or rd is None or ga is None:
        return None, False
    opex = (sm or 0) + (rd or 0) + (ga or 0)
    opex += g(usgaap, ["AmortizationOfIntangibleAssets"], end) or 0
    opex += g(usgaap, ["RestructuringCharges"], end) or 0
    val = ce - opex
    return (val, True) if val >= 0 else (None, False)


def resolve_da(usgaap: dict, end: str, da_c: list[str]) -> tuple[float | None, bool]:
    direct = g(usgaap, da_c, end)
    if direct is not None:
        return direct, False
    parts = [
        g(usgaap, ["Depreciation"], end),
        g(usgaap, ["AmortizationOfIntangibleAssets"], end),
        g(usgaap, ["CostOfGoodsAndServicesSoldAmortization"], end),
    ]
    if all(p is None for p in parts):
        return None, False
    return sum(p or 0 for p in parts), True


from number_format import fmt_dollar, fmt_eps, fmt_margin, fmt_pct_yoy as fmt_pct, fmt_sh


def row(
    label: str,
    values: list[str],
    *,
    kind: str = "normal",
    unit: str = "$",
    plottable: bool = True,
    derived: bool = False,
) -> dict[str, Any]:
    return {
        "label": label,
        "values": values,
        "kind": kind,
        "unit": unit,
        "plottable": plottable,
        "derived": derived,
    }


def build_income_rows(usgaap: dict, period_ends: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(period_ends)
    cogs_c = COGS_CONCEPTS
    da_c = ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"]

    rev: list[float | None] = []
    cogs: list[float | None] = []
    cogs_derived: list[bool] = []
    gross: list[float | None] = []
    gp_tagged: list[float | None] = []
    rev_concepts: list[str | None] = []
    for e in period_ends:
        r, c, gpv, c_derived, rev_c, _cogs_c = resolve_rev_cogs_gross(usgaap, e, cogs_c)
        rev.append(r)
        cogs.append(c)
        cogs_derived.append(c_derived)
        gross.append(gpv)
        gp_tagged.append(g(usgaap, ["GrossProfit"], e))
        rev_concepts.append(rev_c)
    rd = [g(usgaap, ["ResearchAndDevelopmentExpense"], e) for e in period_ends]
    sm = [g(usgaap, ["SellingAndMarketingExpense"], e) for e in period_ends]
    ga = [g(usgaap, ["GeneralAndAdministrativeExpense"], e) for e in period_ends]
    sga = [(sm[i] or 0) + (ga[i] or 0) if sm[i] is not None or ga[i] is not None else None for i in range(n)]
    other_opex = [g(usgaap, ["RestructuringCharges"], e) for e in period_ends]
    op = [g(usgaap, ["OperatingIncomeLoss"], e) for e in period_ends]
    pretax = [
        g(usgaap, ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"], e)
        for e in period_ends
    ]
    tax = [g(usgaap, ["IncomeTaxExpenseBenefit"], e) for e in period_ends]
    net = [g(usgaap, ["NetIncomeLoss", "ProfitLoss"], e) for e in period_ends]
    eps_b = [g(usgaap, ["EarningsPerShareBasic"], e, unit="USD/shares") for e in period_ends]
    eps_d = [g(usgaap, ["EarningsPerShareDiluted"], e, unit="USD/shares") for e in period_ends]
    sh_b = [g(usgaap, ["WeightedAverageNumberOfSharesOutstandingBasic"], e, unit="shares") for e in period_ends]
    sh_d = [g(usgaap, ["WeightedAverageNumberOfDilutedSharesOutstanding"], e, unit="shares") for e in period_ends]
    shares_out = [
        pick(
            usgaap,
            ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
            e,
            unit="shares",
            instant=True,
            qtr=False,
        )
        for e in period_ends
    ]
    apply_share_duplicate_fix(sh_b, sh_d, shares_out)
    eps_d_derived = [False] * n
    eps_b_derived = [False] * n
    for i in range(n):
        if sh_b[i] and sh_d[i] and sh_d[i] / sh_b[i] > 1.5:
            sh_d[i] = sh_b[i]
    for i, e in enumerate(period_ends):
        if e.endswith(FY_END_Q4_SUFFIXES):
            if sh_b[i] is None:
                sh_b[i] = shares_from_eps(net[i], eps_b[i])
            if sh_d[i] is None:
                sh_d[i] = shares_from_eps(net[i], eps_d[i])
        if net[i] is not None and sh_d[i] not in (None, 0):
            implied = round(net[i] / sh_d[i], 2)
            tagged = eps_d[i]
            if tagged is not None and abs(net[i] - tagged * sh_d[i]) > 1:
                eps_d[i] = implied
                eps_d_derived[i] = True
            elif tagged is None:
                eps_d[i] = implied
                eps_d_derived[i] = True
        if net[i] is not None and sh_b[i] not in (None, 0):
            implied_b = round(net[i] / sh_b[i], 2)
            tagged_b = eps_b[i]
            if tagged_b is not None and abs(net[i] - tagged_b * sh_b[i]) > 1:
                eps_b[i] = implied_b
                eps_b_derived[i] = True
            elif tagged_b is None:
                eps_b[i] = implied_b
                eps_b_derived[i] = True
    da: list[float | None] = []
    da_derived: list[bool] = []
    for e in period_ends:
        v, d = resolve_da(usgaap, e, da_c)
        da.append(v)
        da_derived.append(d)
    nonop = [
        (pretax[i] - op[i]) if pretax[i] is not None and op[i] is not None else g(usgaap, ["NonoperatingIncomeExpense"], e)
        for i, e in enumerate(period_ends)
    ]

    yoy = []
    for i, r in enumerate(rev):
        j = i + 4
        if r is None or j >= n or rev[j] is None or rev[j] == 0:
            yoy.append(None)
        else:
            yoy.append((r - rev[j]) / abs(rev[j]) * 100)

    qoq = []
    for i, r in enumerate(rev):
        j = i + 1
        if r is None or j >= n or rev[j] is None or rev[j] == 0:
            qoq.append(None)
        else:
            qoq.append((r - rev[j]) / abs(rev[j]) * 100)

    gm = [(gross[i] / rev[i] * 100) if gross[i] is not None and rev[i] else None for i in range(n)]
    om = [(op[i] / rev[i] * 100) if op[i] is not None and rev[i] else None for i in range(n)]
    etr = [
        (tax[i] / pretax[i] * 100)
        if tax[i] is not None and pretax[i] is not None and abs(pretax[i]) >= 5
        else None
        for i in range(n)
    ]
    ebitda = [(op[i] + da[i]) if op[i] is not None and da[i] is not None else None for i in range(n)]

    interest_exp = [
        g(
            usgaap,
            ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
            e,
        )
        for e in period_ends
    ]
    interest_income = [
        g(
            usgaap,
            ["InterestIncomeOther", "InvestmentIncomeInterestAndDividend", "InterestIncomeExpenseNet"],
            e,
        )
        for e in period_ends
    ]
    # Prefer explicit other non-op when tagged; else pretax − operating − interest components
    other_nonop = [g(usgaap, ["OtherNonoperatingIncomeExpense"], e) for e in period_ends]
    total_nonop = []
    for i, e in enumerate(period_ends):
        tagged = g(usgaap, ["NonoperatingIncomeExpense"], e)
        if tagged is not None:
            total_nonop.append(tagged)
        elif pretax[i] is not None and op[i] is not None:
            total_nonop.append(pretax[i] - op[i])
        else:
            ii = interest_income[i] or 0
            ie = interest_exp[i] or 0
            oo = other_nonop[i] or 0
            if interest_income[i] is not None or interest_exp[i] is not None or other_nonop[i] is not None:
                total_nonop.append(ii - ie + oo)
            else:
                total_nonop.append(None)

    da_opex = [g(usgaap, da_c, e) for e in period_ends]
    for i, e in enumerate(period_ends):
        if da_opex[i] is None and da[i] is not None:
            da_opex[i] = da[i]

    discontinued = [
        g(usgaap, ["IncomeLossFromDiscontinuedOperationsNetOfTax", "DiscontinuedOperationIncomeLossFromDiscontinuedOperationNetOfTaxPerBasicShare"], e)
        for e in period_ends
    ]

    metrics: dict[str, list[float | None]] = {
        "Total Revenues": rev,
        "Total Revenues %Chg (YoY)": yoy,
        "Total Revenues %Chg (QoQ)": qoq,
        "Cost of Sales": cogs,
        "Gross Profit": gross,
        "Gross Profit Margin": gm,
        "Selling, General & Administrative Expenses": sga,
        "Depreciation & Amortization Expenses": da_opex,
        "Research & Development Expenses": rd,
        "Other Operating Expenses": [v if v is not None else None for v in other_opex],
        "Operating Profit": op,
        "Operating Margin": om,
        "Interest and Investment Income": interest_income,
        "Interest Expense": interest_exp,
        "Non-Operating Income": nonop,
        "Total Non-Operating Income": total_nonop,
        "Income Before Provision for Income Taxes": pretax,
        "Provision for Income Taxes": tax,
        "Consolidated Net Income": net,
        "Net Income Attributable to Discontinued Operations": discontinued,
        "Net Income Attributable to Common Shareholders": net,
        "Basic EPS": eps_b,
        "Diluted EPS": eps_d,
        "Basic Weighted Average Shares Outstanding": sh_b,
        "Diluted Weighted Average Shares Outstanding": sh_d,
        "Shares Outstanding": shares_out,
        "EBITDA": ebitda,
        "Effective Tax Rate": etr,
    }

    optional = {
        "Depreciation & Amortization Expenses",
        "Other Operating Expenses",
        "Interest and Investment Income",
        "Interest Expense",
        "Non-Operating Income",
        "Net Income Attributable to Discontinued Operations",
        "Shares Outstanding",
    }

    rows_out: list[dict[str, Any]] = []
    for spec in INCOME_ROWS:
        series = metrics.get(spec.label)
        if series is None:
            continue
        if spec.label in optional and all(v is None for v in series):
            continue
        if spec.unit == "$":
            derived_flags = {
                "Cost of Sales": cogs_derived,
                "Gross Profit": [cogs_derived[i] or gross[i] is None for i in range(n)],
                "EBITDA": [da_derived[i] or da[i] is None for i in range(n)],
            }
            dflags = derived_flags.get(spec.label, [False] * n)
            values = [
                fmt_dollar(
                    v,
                    derived=(dflags[i] if spec.label in derived_flags else spec.derived),
                )
                if v is not None
                else "—"
                for i, v in enumerate(series)
            ]
        elif spec.unit == "%":
            values = [fmt_pct(v) if spec.label.endswith("%Chg") else fmt_margin(v) for v in series]
        elif spec.unit == "eps":
            dflags = {
                "Basic EPS": eps_b_derived,
                "Diluted EPS": eps_d_derived,
            }
            dflags_row = dflags.get(spec.label, [False] * n)
            values = [
                fmt_eps(v) + ("*" if dflags_row[i] else "")
                if v is not None
                else "—"
                for i, v in enumerate(series)
            ]
        elif spec.unit == "sh":
            values = [fmt_sh(v) for v in series]
        else:
            values = [str(v) if v is not None else "—" for v in series]
        rows_out.append(row_from_spec(spec, values))

    scope_meta = {
        "revenueConcepts": rev_concepts,
        "usesTotalRevenues": any(c == "Revenues" for c in rev_concepts),
        "usesContractRevenueOnly": all(c in (None, "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax") for c in rev_concepts),
    }
    return rows_out, scope_meta


def to_num(s: str) -> float | None:
    if not s or s.strip() in ("—", "-", ""):
        return None
    neg = s.strip().startswith("(") and s.strip().endswith(")")
    s = s.replace(",", "").replace("$", "").replace("%", "").replace("+", "").strip("()").replace("*", "")
    if not s:
        return None
    v = float(s)
    return -v if neg else v


def verify_income_rows(
    rows: list[dict[str, Any]],
    n: int,
    *,
    gp_tagged: list[float | None] | None = None,
    scope_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by = {r["label"]: r["values"] for r in rows}
    gp_ok = op_ok = pt_ok = xbrl_gp_ok = True
    exc: list[str] = []
    xbrl_exc: list[str] = []
    rev_row = by.get("Total Revenues", ["—"] * n)
    cogs_row = by.get("Cost of Sales", ["—"] * n)
    gp_row = by.get("Gross Profit", ["—"] * n)
    tagged = gp_tagged or [None] * n
    for i in range(n):
        rev, cogs, gp = to_num(rev_row[i]), to_num(cogs_row[i]), to_num(gp_row[i])
        if rev is not None and cogs is not None and gp is not None and abs(rev - cogs - gp) > 1:
            gp_ok = False
            exc.append(f"col {i} gross profit")
        if tagged[i] is not None and gp is not None and abs(gp - tagged[i]) > 1:
            xbrl_gp_ok = False
            xbrl_exc.append(f"col {i} xbrl gross profit")
        if "Operating Profit" in by:
            op = to_num(by["Operating Profit"][i])
            gp = to_num(gp_row[i])
            sga = to_num(by.get("Selling, General & Administrative Expenses", ["—"] * n)[i])
            rd = to_num(by.get("Research & Development Expenses", ["—"] * n)[i])
            da_opex = to_num(by.get("Depreciation & Amortization Expenses", ["—"] * n)[i])
            other_opex = to_num(by.get("Other Operating Expenses", ["—"] * n)[i])
            if gp is not None and op is not None:
                calc = (gp or 0) - (sga or 0) - (rd or 0) - (da_opex or 0) - (other_opex or 0)
                if abs(calc - op) > 75:
                    op_ok = False
                    exc.append(f"col {i} operating profit")
        if all(k in by for k in ("Income Before Provision for Income Taxes", "Provision for Income Taxes", "Consolidated Net Income")):
            pretax = to_num(by["Income Before Provision for Income Taxes"][i])
            tax = to_num(by["Provision for Income Taxes"][i])
            net = to_num(by["Consolidated Net Income"][i])
            if pretax is not None and tax is not None and net is not None and abs(pretax - tax - net) > 2:
                pt_ok = False
                exc.append(f"col {i} pretax-tax-net")
    out: dict[str, Any] = {
        "grossProfitTies": gp_ok,
        "grossProfitMatchesXbrlTag": xbrl_gp_ok,
        "operatingProfitTies": op_ok,
        "pretaxMinusTaxTiesNetIncome": pt_ok,
        "exceptions": exc,
    }
    if xbrl_exc:
        out["xbrlGrossProfitExceptions"] = xbrl_exc
    if scope_meta:
        out.update(scope_meta)
    return out


def build_summary(quarters: list[dict], rows: list[dict], company: str, fy_end_month: int) -> dict[str, Any]:
    by = {r["label"]: r["values"] for r in rows}
    q0 = quarters[0]
    rev = by["Total Revenues"][0]
    yoy = by.get("Total Revenues %Chg (YoY)", by.get("Total Revenues %Chg", ["—"]))[0]
    om = by["Operating Margin"][0]
    eps = by["Diluted EPS"][0]
    ni = by["Consolidated Net Income"][0]
    fy_names = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
                7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
    fiscal_mapping = " · ".join(f"{q['label']} = {q['fiscalLabel']}" for q in quarters)
    return {
        "subtitle": (
            f"{company} · Last {len(quarters)} quarters · USD millions (except per-share). "
            f"Fiscal year ends {fy_names.get(fy_end_month, 'month ' + str(fy_end_month))}. "
            "Source: SEC XBRL (10-Q/10-K company facts)."
        ),
        "fiscalMapping": f"Fiscal mapping: {fiscal_mapping}.",
        "stats": [
            {"value": f"${rev}M", "label": f"Latest Revenue — {q0['fiscalLabel']} ({yoy} YoY)", "tone": "info"},
            {"value": om, "label": f"GAAP Operating Margin ({q0['fiscalLabel']})", "tone": "success"},
            {"value": f"${eps}", "label": f"Diluted EPS ({q0['fiscalLabel']})"},
            {"value": f"${ni}M", "label": f"GAAP Net Income ({q0['fiscalLabel']})"},
        ],
        "defaultChartRows": ["Total Revenues", "Operating Margin"],
        "notes": [
            "GAAP Three Months Ended from SEC XBRL company facts.",
            "Q4 flow lines derived as fiscal-year minus nine-month YTD when no standalone quarterly XBRL tag exists "
            "(Dec FY: Jan–Sep YTD; Jan FY: Feb–Oct YTD; Jul FY: Aug–Apr YTD).",
            "Q4 weighted-average shares* derived as |net income| ÷ EPS when XBRL only reports FY/9M WASO.",
            "Cost of sales* derived as CostsAndExpenses − S&M − R&D − G&A − amortization − restructuring "
            "when filer omits CostOfRevenue in XBRL (e.g. INTU).",
            "Revenue + COGS chosen to tie SEC GrossProfit XBRL tag when tagged (required for fintech filers "
            "where Revenues includes financial income and COGS includes financial expenses).",
            "D&A sums Depreciation + AmortizationOfIntangibleAssets + CostOfGoodsAndServicesSoldAmortization when no combined tag.",
            "SG&A = Sales & marketing + General & administrative. EBITDA* = Operating Profit + D&A.",
            "Effective tax rate omitted when |pretax| < $5M. Mark * on derived rows in Notes when validating.",
        ],
    }


def build_income_document(ticker: str) -> dict[str, Any]:
    t = ticker.strip().upper()
    cik = lookup_cik(t)
    entity = load_entity(cik)
    company = entity.get("name") or t
    fy_end = fiscal_year_end_month(entity)
    quarters = discover_quarters(cik, 12)
    period_ends = [q["periodEnd"] for q in quarters]
    usgaap = load_usgaap(cik)
    rows, scope_meta = build_income_rows(usgaap, period_ends)
    gp_tagged = [g(usgaap, ["GrossProfit"], e) for e in period_ends]
    verification = verify_income_rows(rows, len(quarters), gp_tagged=gp_tagged, scope_meta=scope_meta)
    if not verification.get("grossProfitMatchesXbrlTag", True):
        mismatches = verification.get("xbrlGrossProfitExceptions", [])
        raise SystemExit(
            f"Income build for {t}: gross profit does not match SEC GrossProfit XBRL tag "
            f"({', '.join(mismatches[:3])})"
        )
    latest = latest_quarterly_filings(cik, limit=1)[0]
    summary = build_summary(quarters, rows, company, fy_end)

    return {
        "schemaVersion": 1,
        "statementType": "income",
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
        "summary": summary,
        "notes": summary["notes"],
        "verification": verification,
    }


def write_income_json(ticker: str) -> Path:
    from statement_build import write_statement_json

    return write_statement_json(ticker, "income")
