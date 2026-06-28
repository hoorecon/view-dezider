"""
Financial Model exports — Phase 2.

Investor-ready and Bank-ready (CMA) report builders in:
  • Excel (.xlsx) — openpyxl, multi-sheet. (Also serves the "Google Sheets" path:
    an .xlsx imports natively into Google Sheets via File → Import.)
  • PDF — reportlab (landscape, banded tables).

All builders return raw `bytes`. Numbers are divided by `unit_div` and the chosen
unit is shown in each sheet header (e.g. "Figures in ₹ Lakhs").
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

CURRENCY_SYMBOL = {"INR": "Rs ", "USD": "$", "EUR": "EUR ", "GBP": "GBP ", "AED": "AED ", "SGD": "S$"}

NAVY = "003087"
LIGHT = "EEF2FF"
GREY = "F1F5F9"


# ───────────────────────── shared helpers ─────────────────────────

def _f(v: Any, div: float) -> float:
    try:
        return round(float(v) / (div or 1), 2)
    except (TypeError, ValueError):
        return 0.0


def _years(computed: Dict[str, Any]) -> List[str]:
    return computed.get("year_labels") or [f"Year {i + 1}" for i in range(computed.get("projection_years", 5))]


# P&L / BS / CF / Ratio row maps (key, label, is_pct)
PNL_ROWS = [("revenue", "Revenue", False), ("cogs", "Cost of Goods Sold", False),
            ("gross_profit", "Gross Profit", False), ("other_income", "Other Income", False),
            ("opex", "Operating Expenses", False), ("ebitda", "EBITDA", False),
            ("depreciation", "Depreciation", False), ("ebit", "EBIT", False),
            ("interest", "Interest", False), ("pbt", "Profit Before Tax", False),
            ("tax", "Tax", False), ("pat", "Profit After Tax (PAT)", False),
            ("dividend", "Dividend", False), ("retained", "Retained Earnings", False)]
BS_ROWS = [("gross_block", "Gross Block", False), ("acc_depreciation", "Less: Acc. Depreciation", False),
           ("net_block", "Net Block", False), ("inventory", "Inventory", False),
           ("debtors", "Debtors / Receivables", False), ("cash", "Cash & Bank", False),
           ("total_current_assets", "Total Current Assets", False), ("total_assets", "TOTAL ASSETS", False),
           ("equity_capital", "Share Capital", False), ("reserves", "Reserves & Surplus", False),
           ("net_worth", "Net Worth", False), ("debt", "Debt / Borrowings", False),
           ("creditors", "Creditors / Payables", False),
           ("total_current_liabilities", "Total Current Liabilities", False),
           ("total_liabilities", "TOTAL LIABILITIES", False)]
CF_ROWS = [("opening_cash", "Opening Cash", False), ("cfo", "Cash from Operations", False),
           ("cfi", "Cash from Investing", False), ("cff", "Cash from Financing", False),
           ("net_change", "Net Change in Cash", False), ("closing_cash", "Closing Cash", False)]
RATIO_ROWS = [("current_ratio", "Current Ratio", False), ("quick_ratio", "Quick Ratio", False),
              ("debt_equity", "Debt / Equity", False), ("interest_coverage", "Interest Coverage", False),
              ("dscr", "DSCR", False), ("gross_margin_pct", "Gross Margin %", True),
              ("ebitda_margin_pct", "EBITDA Margin %", True), ("net_margin_pct", "Net Margin %", True),
              ("roce_pct", "ROCE %", True), ("roe_pct", "ROE %", True),
              ("debtor_days", "Debtor Days", False), ("inventory_days", "Inventory Days", False),
              ("creditor_days", "Creditor Days", False)]


# ───────────────────────── Excel ─────────────────────────

def _thin():
    s = Side(style="thin", color="D9D9D9")
    return Border(left=s, right=s, top=s, bottom=s)


def _block(ws, row: int, title: str, years: List[str], rows: List, data: Dict[str, Any],
           div: float, ratio_mode: bool = False) -> int:
    n = len(years)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=n + 1)
    c = ws.cell(row=row, column=1, value=title)
    c.font = Font(bold=True, size=12, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    row += 1
    hdr = ws.cell(row=row, column=1, value="Particulars")
    hdr.font = Font(bold=True); hdr.fill = PatternFill("solid", fgColor=LIGHT)
    for j, y in enumerate(years):
        h = ws.cell(row=row, column=2 + j, value=y)
        h.font = Font(bold=True); h.fill = PatternFill("solid", fgColor=LIGHT)
        h.alignment = Alignment(horizontal="right")
    row += 1
    for key, label, is_pct in rows:
        strong = label.isupper() or label in ("EBITDA", "Net Worth", "Profit After Tax (PAT)", "Closing Cash")
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = Font(bold=strong)
        series = data.get(key) or []
        for j in range(n):
            v = series[j] if j < len(series) else 0
            if is_pct:
                cell = ws.cell(row=row, column=2 + j, value=round(float(v or 0), 1))
                cell.number_format = '0.0"%"'
            elif ratio_mode:
                cell = ws.cell(row=row, column=2 + j, value=round(float(v or 0), 2))
                cell.number_format = '0.00'
            else:
                cell = ws.cell(row=row, column=2 + j, value=_f(v, div))
                cell.number_format = '#,##0'
            cell.font = Font(bold=strong)
        row += 1
    return row + 1


def _autosize(ws, ncols: int):
    ws.column_dimensions["A"].width = 30
    for j in range(2, ncols + 2):
        ws.column_dimensions[get_column_letter(j)].width = 15


def _cover_sheet(wb, model, computed, unit_label, title):
    ws = wb.active
    ws.title = "Cover"
    v = computed.get("valuation", {})
    s = computed.get("summary", {})
    rows = [
        (title, ""),
        ("Model", model.get("name", "Financial Model")),
        ("Currency", model.get("currency", "INR")),
        ("Figures in", unit_label),
        ("Projection years", str(computed.get("projection_years", 5))),
        ("", ""),
        ("Enterprise Value", v.get("enterprise_value")),
        ("Equity Value", v.get("equity_value")),
        ("Per-Share Price", v.get("per_share")),
        ("Revenue CAGR %", s.get("revenue_cagr_pct")),
        ("Average DSCR", s.get("dscr_avg")),
        ("Minimum DSCR", s.get("min_dscr")),
    ]
    r = 1
    for k, val in rows:
        a = ws.cell(row=r, column=1, value=k)
        if r == 1:
            a.font = Font(bold=True, size=16, color=NAVY)
        else:
            a.font = Font(bold=True)
        ws.cell(row=r, column=2, value=val)
        r += 1
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 28


def build_investor_xlsx(model, computed, div, unit_label) -> bytes:
    wb = Workbook()
    _cover_sheet(wb, model, computed, unit_label, "Investor Report")
    years = _years(computed)
    n = len(years)
    pl = wb.create_sheet("P&L"); _block(pl, 1, f"Profit & Loss (in {unit_label})", years, PNL_ROWS, computed["pnl"], div); _autosize(pl, n)
    bs = wb.create_sheet("Balance Sheet"); _block(bs, 1, f"Balance Sheet (in {unit_label})", years, BS_ROWS, computed["balance_sheet"], div); _autosize(bs, n)
    cf = wb.create_sheet("Cash Flow"); _block(cf, 1, f"Cash Flow (in {unit_label})", years, CF_ROWS, computed["cash_flow"], div); _autosize(cf, n)
    rt = wb.create_sheet("Ratios"); _block(rt, 1, "Financial Ratios", years, RATIO_ROWS, computed["ratios"], div, ratio_mode=True); _autosize(rt, n)
    # DCF
    dv = wb.create_sheet("DCF Valuation")
    r = _block(dv, 1, f"Discounted Cash Flow — FCFF (in {unit_label})", years,
               [("fcff", "Free Cash Flow (FCFF)", False), ("pv_fcff", "PV of FCFF", False)],
               computed["valuation"], div)
    v = computed["valuation"]
    for k, val in [("Sum of PV (FCFF)", v.get("sum_pv_fcff")), ("Terminal Value", v.get("terminal_value")),
                   ("PV of Terminal Value", v.get("pv_terminal")), ("Enterprise Value", v.get("enterprise_value")),
                   ("Less: Net Debt", v.get("net_debt")), ("Equity Value", v.get("equity_value"))]:
        dv.cell(row=r, column=1, value=k).font = Font(bold=True)
        c = dv.cell(row=r, column=2, value=_f(val, div)); c.number_format = '#,##0'; r += 1
    dv.cell(row=r, column=1, value="Per-Share Price").font = Font(bold=True)
    dv.cell(row=r, column=2, value=round(float(v.get("per_share") or 0), 2)).number_format = '#,##0.00'; r += 1
    dv.cell(row=r, column=1, value="WACC %").font = Font(bold=True); dv.cell(row=r, column=2, value=v.get("wacc_pct")); r += 1
    dv.cell(row=r, column=1, value="Terminal growth %").font = Font(bold=True); dv.cell(row=r, column=2, value=v.get("terminal_growth_pct"))
    _autosize(dv, n)
    out = BytesIO(); wb.save(out); return out.getvalue()


def build_cma_xlsx(model, computed, extras, div, unit_label) -> bytes:
    wb = Workbook()
    _cover_sheet(wb, model, computed, unit_label, "CMA Report (Bank-ready)")
    years = _years(computed); n = len(years)
    op = wb.create_sheet("Form II Operating Stmt"); _block(op, 1, f"Operating Statement / P&L (in {unit_label})", years, PNL_ROWS, computed["pnl"], div); _autosize(op, n)
    bsf = wb.create_sheet("Form III Balance Sheet"); _block(bsf, 1, f"Balance Sheet (in {unit_label})", years, BS_ROWS, computed["balance_sheet"], div); _autosize(bsf, n)
    rt = wb.create_sheet("Ratio Analysis"); _block(rt, 1, "Ratio Analysis", years, RATIO_ROWS, computed["ratios"], div, ratio_mode=True); _autosize(rt, n)

    # MPBF & Working Capital
    mp = wb.create_sheet("Form IV-V MPBF & WC")
    mpbf_data = {
        "wc_cycle_days": extras["wc_cycle_days"], "working_capital_gap": extras["working_capital_gap"],
        "mpbf_method_1": extras["mpbf_method_1"], "mpbf_method_2": extras["mpbf_method_2"],
    }
    _block(mp, 1, f"Working-Capital Cycle & Max Permissible Bank Finance (in {unit_label})", years,
           [("wc_cycle_days", "Net WC Cycle (days)", False), ("working_capital_gap", "Working Capital Gap", False),
            ("mpbf_method_1", "MPBF — Tandon Method I", False), ("mpbf_method_2", "MPBF — Tandon Method II", False)],
           mpbf_data, div)
    # WC-cycle in days should not be unit-divided -> overwrite that row format
    _autosize(mp, n)

    # Break-even
    be = wb.create_sheet("Break-even")
    be_keys = [("fixed_cost", "Fixed Cost", False), ("variable_cost", "Variable Cost (COGS)", False),
               ("be_sales", "Break-even Sales", False)]
    be_data = {k: [row[k] for row in extras["break_even"]] for k, _l, _p in be_keys}
    be_data["contribution_margin_pct"] = [row["contribution_margin_pct"] for row in extras["break_even"]]
    be_data["margin_of_safety_pct"] = [row["margin_of_safety_pct"] for row in extras["break_even"]]
    r = _block(be, 1, f"Break-even Analysis (in {unit_label})", years, be_keys, be_data, div)
    _block(be, r, "Margins (%)", years,
           [("contribution_margin_pct", "Contribution Margin %", True),
            ("margin_of_safety_pct", "Margin of Safety %", True)], be_data, div)
    _autosize(be, n)

    # Fund Flow
    ff = wb.create_sheet("Form VI Fund Flow")
    ff_rows = [
        ("ffo", "Funds From Operations"), ("new_debt", "Add: New Debt"), ("new_equity", "Add: New Equity"),
        ("dec_wc", "Add: Decrease in WC"), ("total_sources", "TOTAL SOURCES"),
        ("capex", "Capex"), ("debt_repayment", "Debt Repayment"), ("dividend", "Dividend"),
        ("inc_wc", "Increase in WC"), ("total_uses", "TOTAL USES"), ("net", "Net Surplus/(Deficit)"),
    ]
    ff_data: Dict[str, List[float]] = {k: [] for k, _ in ff_rows}
    for fr in extras["fund_flow"]:
        ff_data["ffo"].append(fr["sources"]["funds_from_operations"])
        ff_data["new_debt"].append(fr["sources"]["new_debt"])
        ff_data["new_equity"].append(fr["sources"]["new_equity"])
        ff_data["dec_wc"].append(fr["sources"]["decrease_in_working_capital"])
        ff_data["total_sources"].append(fr["total_sources"])
        ff_data["capex"].append(fr["uses"]["capex"])
        ff_data["debt_repayment"].append(fr["uses"]["debt_repayment"])
        ff_data["dividend"].append(fr["uses"]["dividend"])
        ff_data["inc_wc"].append(fr["uses"]["increase_in_working_capital"])
        ff_data["total_uses"].append(fr["total_uses"])
        ff_data["net"].append(fr["net"])
    _block(ff, 1, f"Fund Flow Statement (in {unit_label})", years,
           [(k, lbl, False) for k, lbl in ff_rows], ff_data, div); _autosize(ff, n)

    # Cash Flow
    cf = wb.create_sheet("Cash Flow"); _block(cf, 1, f"Cash Flow (in {unit_label})", years, CF_ROWS, computed["cash_flow"], div); _autosize(cf, n)

    # DSCR & Stress
    ds = wb.create_sheet("DSCR & Stress")
    dscr_data = {sc["label"]: sc["dscr"] for sc in extras["dscr_stress"]}
    _block(ds, 1, "DSCR — Debt Service Coverage Ratio (Base + Stress scenarios)", years,
           [(sc["label"], sc["label"], False) for sc in extras["dscr_stress"]], dscr_data, div, ratio_mode=True)
    _autosize(ds, n)

    out = BytesIO(); wb.save(out); return out.getvalue()


# ───────────────────────── PDF ─────────────────────────

def _pstyles():
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading1"], textColor=colors.HexColor("#003087"), fontSize=15)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#003087"), fontSize=11)
    nrm = ss["Normal"]
    return h, h2, nrm


def _pdf_table(years: List[str], rows: List, data: Dict[str, Any], div: float,
               ratio_mode: bool = False) -> Table:
    head = ["Particulars"] + years
    body = [head]
    for key, label, is_pct in rows:
        series = data.get(key) or []
        line = [label]
        for j in range(len(years)):
            v = series[j] if j < len(series) else 0
            if is_pct:
                line.append(f"{round(float(v or 0),1)}%")
            elif ratio_mode:
                line.append(f"{round(float(v or 0),2)}")
            else:
                line.append(f"{_f(v, div):,.0f}")
        body.append(line)
    col0 = 58 * mm
    colw = [col0] + [ (247 * mm - col0) / max(1, len(years)) ] * len(years)
    t = Table(body, colWidths=colw, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003087")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FF")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D9D9")),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    # bold TOTAL/strong rows
    for i, (key, label, _ip) in enumerate(rows, start=1):
        if label.isupper() or label in ("EBITDA", "Net Worth", "Profit After Tax (PAT)", "Closing Cash"):
            style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EEF2FF")))
    t.setStyle(TableStyle(style))
    return t


def _pdf_doc(elements) -> bytes:
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    doc.build(elements)
    return out.getvalue()


def _cover_para(model, computed, unit_label, title, h, nrm):
    v = computed.get("valuation", {}); s = computed.get("summary", {})
    el = [Paragraph(title, h),
          Paragraph(f"<b>{model.get('name','Financial Model')}</b> &nbsp; | &nbsp; Currency: {model.get('currency','INR')} &nbsp; | &nbsp; Figures in {unit_label}", nrm),
          Spacer(1, 6)]
    kv = [["Enterprise Value", f"{_f(v.get('enterprise_value'),1):,.0f}"],
          ["Equity Value", f"{_f(v.get('equity_value'),1):,.0f}"],
          ["Per-Share Price", f"{round(float(v.get('per_share') or 0),2):,.2f}"],
          ["Revenue CAGR", f"{s.get('revenue_cagr_pct',0)}%"],
          ["Average DSCR", f"{s.get('dscr_avg',0)}x"], ["Minimum DSCR", f"{s.get('min_dscr',0)}x"]]
    t = Table(kv, colWidths=[60 * mm, 60 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D9D9")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF"))]))
    el.append(t); el.append(Spacer(1, 10))
    return el


def build_investor_pdf(model, computed, div, unit_label) -> bytes:
    h, h2, nrm = _pstyles()
    years = _years(computed)
    el = _cover_para(model, computed, unit_label, "Investor Report", h, nrm)
    for title, rows, data, rm in [
        ("Profit & Loss", PNL_ROWS, computed["pnl"], False),
        ("Balance Sheet", BS_ROWS, computed["balance_sheet"], False),
        ("Cash Flow", CF_ROWS, computed["cash_flow"], False),
        ("Financial Ratios", RATIO_ROWS, computed["ratios"], True),
    ]:
        el.append(Paragraph(title, h2)); el.append(Spacer(1, 3))
        el.append(_pdf_table(years, rows, data, div, ratio_mode=rm)); el.append(Spacer(1, 10))
    return _pdf_doc(el)


def build_cma_pdf(model, computed, extras, div, unit_label) -> bytes:
    h, h2, nrm = _pstyles()
    years = _years(computed)
    el = _cover_para(model, computed, unit_label, "CMA Report (Bank-ready)", h, nrm)
    blocks = [
        ("Operating Statement (P&L)", PNL_ROWS, computed["pnl"], False),
        ("Balance Sheet", BS_ROWS, computed["balance_sheet"], False),
        ("Ratio Analysis", RATIO_ROWS, computed["ratios"], True),
    ]
    for title, rows, data, rm in blocks:
        el.append(Paragraph(title, h2)); el.append(Spacer(1, 3))
        el.append(_pdf_table(years, rows, data, div, ratio_mode=rm)); el.append(Spacer(1, 10))

    # MPBF & WC
    el.append(PageBreak()); el.append(Paragraph("Working Capital & MPBF (Tandon)", h2)); el.append(Spacer(1, 3))
    mpbf_data = {"wc_cycle_days": extras["wc_cycle_days"], "working_capital_gap": extras["working_capital_gap"],
                 "mpbf_method_1": extras["mpbf_method_1"], "mpbf_method_2": extras["mpbf_method_2"]}
    el.append(_pdf_table(years, [("wc_cycle_days", "Net WC Cycle (days)", False),
                                 ("working_capital_gap", "Working Capital Gap", False),
                                 ("mpbf_method_1", "MPBF — Method I", False),
                                 ("mpbf_method_2", "MPBF — Method II", False)], mpbf_data, div))
    el.append(Spacer(1, 10))

    # Break-even
    be_data = {"fixed_cost": [r["fixed_cost"] for r in extras["break_even"]],
               "be_sales": [r["be_sales"] for r in extras["break_even"]],
               "margin_of_safety_pct": [r["margin_of_safety_pct"] for r in extras["break_even"]]}
    el.append(Paragraph("Break-even Analysis", h2)); el.append(Spacer(1, 3))
    el.append(_pdf_table(years, [("fixed_cost", "Fixed Cost", False), ("be_sales", "Break-even Sales", False),
                                 ("margin_of_safety_pct", "Margin of Safety %", True)], be_data, div))
    el.append(Spacer(1, 10))

    # Fund flow (totals)
    ff_data = {"total_sources": [r["total_sources"] for r in extras["fund_flow"]],
               "total_uses": [r["total_uses"] for r in extras["fund_flow"]],
               "net": [r["net"] for r in extras["fund_flow"]]}
    el.append(Paragraph("Fund Flow (summary)", h2)); el.append(Spacer(1, 3))
    el.append(_pdf_table(years, [("total_sources", "Total Sources", False), ("total_uses", "Total Uses", False),
                                 ("net", "Net Surplus/(Deficit)", False)], ff_data, div))
    el.append(Spacer(1, 10))

    # DSCR stress
    el.append(Paragraph("DSCR — Base &amp; Stress Scenarios", h2)); el.append(Spacer(1, 3))
    dscr_data = {sc["label"]: sc["dscr"] for sc in extras["dscr_stress"]}
    el.append(_pdf_table(years, [(sc["label"], sc["label"], False) for sc in extras["dscr_stress"]],
                         dscr_data, div, ratio_mode=True))
    return _pdf_doc(el)
