"""Financial-Model base-year template (.xlsx) + deterministic importer.

Users download a labelled template, fill their numbers, and re-import it (as an
uploaded Excel/CSV or via a Google Sheet link). Parsing is label-based and
deterministic — no AI credits are spent. The same parser handles rows coming
from openpyxl, a CSV, or a Google Sheet.
"""
import io
import re
from typing import Any, Dict, List, Tuple

# (label shown in template, assumption key, kind)  kind = "scalar" | "series"
TEMPLATE_FIELDS: List[Tuple[str, str, str]] = [
    ("Year-1 revenue", "year1_revenue", "scalar"),
    ("Revenue growth % p.a.", "revenue_growth_pct", "scalar"),
    ("Revenue by year (Y1..Y5)", "revenue_by_year", "series"),
    ("Gross margin %", "gross_margin_pct", "scalar"),
    ("Opex % of revenue", "opex_pct", "scalar"),
    ("Other income %", "other_income_pct", "scalar"),
    ("Opening gross block", "opening_gross_block", "scalar"),
    ("Capex by year (Y1..Y5)", "capex_by_year", "series"),
    ("Depreciation % of gross block", "depreciation_pct", "scalar"),
    ("Debtor days", "debtor_days", "scalar"),
    ("Inventory days", "inventory_days", "scalar"),
    ("Creditor days", "creditor_days", "scalar"),
    ("Opening debtors", "opening_debtors", "scalar"),
    ("Opening inventory", "opening_inventory", "scalar"),
    ("Opening creditors", "opening_creditors", "scalar"),
    ("Opening debt", "opening_debt", "scalar"),
    ("Interest rate %", "interest_rate_pct", "scalar"),
    ("New debt by year (Y1..Y5)", "new_debt_by_year", "series"),
    ("Repayment by year (Y1..Y5)", "repayment_by_year", "series"),
    ("Opening equity capital", "opening_equity_capital", "scalar"),
    ("Opening cash", "opening_cash", "scalar"),
    ("New equity by year (Y1..Y5)", "new_equity_by_year", "series"),
    ("Shares outstanding", "shares_outstanding", "scalar"),
    ("Tax rate %", "tax_rate_pct", "scalar"),
    ("Dividend payout %", "dividend_payout_pct", "scalar"),
    ("WACC %", "wacc_pct", "scalar"),
    ("Terminal growth %", "terminal_growth_pct", "scalar"),
    ("Risk-free rate %", "risk_free_pct", "scalar"),
    ("Beta", "beta", "scalar"),
    ("Market risk premium %", "market_risk_premium_pct", "scalar"),
    ("Cost of debt %", "cost_of_debt_pct", "scalar"),
    ("Market cap", "market_cap", "scalar"),
    ("Minority interest", "minority_interest", "scalar"),
    ("Preference capital", "preference_capital", "scalar"),
    ("Non-operating assets", "non_operating_assets", "scalar"),
]


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


# precompute normalized label -> (key, kind)
_LABEL_MAP = {_norm(lbl): (key, kind) for lbl, key, kind in TEMPLATE_FIELDS}


def _to_num(v: Any):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "").replace("\u20b9", "").replace("$", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def build_template_xlsx() -> bytes:
    """Return a labelled .xlsx the user fills and re-imports. Opens in Excel and
    Google Sheets alike."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = "Inputs"
    head_fill = PatternFill("solid", fgColor="003087")
    head_font = Font(color="FFFFFF", bold=True)
    ws["A1"] = "JELCOS — Financial Model: Base-Year Inputs"
    ws["A1"].font = Font(bold=True, size=13, color="003087")
    ws["A2"] = "Fill the value cells (yellow). Keep the labels in column A unchanged. Series fields use Year-1..Year-5."
    ws["A2"].font = Font(italic=True, size=9, color="666666")

    headers = ["Input", "Year 1 / Value", "Year 2", "Year 3", "Year 4", "Year 5"]
    r = 4
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center")
    value_fill = PatternFill("solid", fgColor="FFF7CC")
    r = 5
    for lbl, key, kind in TEMPLATE_FIELDS:
        ws.cell(row=r, column=1, value=lbl)
        ncols = 5 if kind == "series" else 1
        for c in range(2, 2 + ncols):
            ws.cell(row=r, column=c).fill = value_fill
        r += 1
    ws.column_dimensions["A"].width = 34
    for col in "BCDEF":
        ws.column_dimensions[col].width = 15
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_rows_to_assumptions(rows: List[List[Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """Map template rows -> assumptions patch. Returns (patch, matched_labels)."""
    patch: Dict[str, Any] = {}
    matched: List[str] = []
    for row in rows or []:
        if not row:
            continue
        label = _norm(row[0])
        if not label or label not in _LABEL_MAP:
            continue
        key, kind = _LABEL_MAP[label]
        cells = list(row[1:])
        if kind == "series":
            vals = [_to_num(c) for c in cells[:5]]
            vals = [v for v in vals if v is not None]
            if vals:
                patch[key] = vals
                matched.append(key)
        else:
            val = next((_to_num(c) for c in cells if _to_num(c) is not None), None)
            if val is not None:
                patch[key] = val
                matched.append(key)
    return patch, matched
