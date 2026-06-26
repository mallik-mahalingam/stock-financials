"""Align statement JSON rows to canonical order."""

from __future__ import annotations

from typing import Any

from statement_templates import (
    TEMPLATES,
    blank_values,
    canonical_label,
    row_from_spec,
    section_divider_row,
    template_labels,
)

MISSING = frozenset({"—", "-", "", " "})


def _has_any_data(values: list[str]) -> bool:
    return any(v not in MISSING for v in values)


def align_statement_rows(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (aligned rows, warnings). Drops all-blank non-section rows."""
    stmt = data.get("statementType") or ""
    template = TEMPLATES.get(stmt)
    if not template:
        return data.get("rows") or [], [f"unknown statementType: {stmt}"]

    n = len(data.get("quarters") or [])
    by_label: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for row in data.get("rows") or []:
        label = canonical_label(row.get("label", ""))
        if label in by_label:
            warnings.append(f"duplicate row label merged: {label}")
        by_label[label] = {**row, "label": label}

    out: list[dict[str, Any]] = []
    for spec in template:
        if spec.section:
            out.append(section_divider_row(spec, n))
            continue
        existing = by_label.get(spec.label)
        if existing:
            vals = existing.get("values") or blank_values(n)
            if len(vals) != n:
                warnings.append(f"{spec.label}: expected {n} values, got {len(vals)}")
                vals = (vals + blank_values(n))[:n]
            out.append(
                row_from_spec(
                    spec,
                    vals,
                    derived_override=existing.get("derived", spec.derived),
                )
            )
            continue
        vals = blank_values(n)
        if _has_any_data(vals):
            out.append(row_from_spec(spec, vals))
        # omit all-blank optional rows

    extra = set(by_label) - set(template_labels(stmt))
    for label in sorted(extra):
        row = by_label[label]
        if _has_any_data(row.get("values") or []):
            warnings.append(f"non-template row with data preserved at end: {label}")
            out.append(row)

    return out, warnings


def row_order_errors(data: dict[str, Any]) -> list[str]:
    stmt = data.get("statementType") or ""
    expected = [s.label for s in TEMPLATES.get(stmt, []) if not s.section]
    actual = [canonical_label(r["label"]) for r in data.get("rows") or [] if not _is_section_row(r, stmt)]
    # compare relative order of labels present in both
    exp_idx = {l: i for i, l in enumerate(expected)}
    filtered = [l for l in actual if l in exp_idx]
    if filtered != sorted(filtered, key=lambda l: exp_idx[l]):
        return ["row order does not match canonical template"]
    return []


def _is_section_row(row: dict[str, Any], stmt: str) -> bool:
    if stmt in ("balance-sheet", "cash-flow") and all(v in MISSING for v in row.get("values") or []):
        labels = template_labels(stmt)
        if row.get("label") in labels:
            spec = next(s for s in TEMPLATES[stmt] if s.label == row["label"])
            return spec.section
    return False
