"""PDF renderer for the Solution Matrix tool.

Produces a multi-page PDF capturing every section of a matrix entry, including
the 15-cell Standard grid or the 60-cell Accurate grid (slot × TEPFI).

Returns: bytes (PDF body).
"""
from io import BytesIO
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

TEPFI_ORDER: List[str] = ["time", "energy", "people", "finance", "infrastructure"]
TEPFI_LABELS: Dict[str, str] = {
    "time": "Time",
    "energy": "Energy (Capacity)",
    "people": "People",
    "finance": "Finance",
    "infrastructure": "Infrastructure",
}

LAYERS: List[str] = ["matrix_self", "matrix_micro", "matrix_macro"]
LAYER_LABELS: Dict[str, str] = {"matrix_self": "SELF", "matrix_micro": "MICRO", "matrix_macro": "MACRO"}

ORG_TYPES: List[str] = ["individual", "org", "govt", "nature"]
ORG_LABELS: Dict[str, str] = {
    "individual": "Individual",
    "org": "Org",
    "govt": "Govt",
    "nature": "Nature",
}

LAYER_HEX: Dict[str, str] = {
    "matrix_self": "#10B981",
    "matrix_micro": "#6366F1",
    "matrix_macro": "#F59E0B",
}


def _cell_text(cell: Dict, field: str) -> str:
    if not isinstance(cell, dict):
        return ""
    # energy canonical; fall back to capacity (legacy)
    if field == "energy":
        return str(cell.get("energy") or cell.get("capacity") or "")
    return str(cell.get(field, "") or "")


def _influence_pair(cell: Dict, field: str) -> str:
    inf = (cell or {}).get("influences") or {}
    data = inf.get(field) or {}
    pos = str(data.get("positive", "") or "").strip()
    neg = str(data.get("negative", "") or "").strip()
    parts: List[str] = []
    if pos:
        parts.append(f"[+] {pos}")
    if neg:
        parts.append(f"[-] {neg}")
    return "\n".join(parts)


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="H0", parent=ss["Heading1"], fontSize=18, spaceAfter=8,
                          textColor=colors.HexColor("#1F2937")))
    ss.add(ParagraphStyle(name="H1", parent=ss["Heading2"], fontSize=13, spaceAfter=4,
                          textColor=colors.HexColor("#111827")))
    ss.add(ParagraphStyle(name="H2", parent=ss["Heading3"], fontSize=11, spaceAfter=3,
                          textColor=colors.HexColor("#374151")))
    ss.add(ParagraphStyle(name="Body", parent=ss["Normal"], fontSize=9, leading=12,
                          textColor=colors.HexColor("#1F2937")))
    ss.add(ParagraphStyle(name="Muted", parent=ss["Normal"], fontSize=8, leading=11,
                          textColor=colors.HexColor("#6B7280")))
    ss.add(ParagraphStyle(name="Cell", parent=ss["Normal"], fontSize=7, leading=9,
                          textColor=colors.HexColor("#111827")))
    ss.add(ParagraphStyle(name="CellHdr", parent=ss["Normal"], fontSize=7, leading=9,
                          textColor=colors.white, fontName="Helvetica-Bold"))
    return ss


def _kv_row(label: str, value: str, styles):
    return Table(
        [[Paragraph(f"<b>{label}</b>", styles["Body"]), Paragraph(value or "—", styles["Body"])]],
        colWidths=[4 * cm, 13 * cm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]),
    )


def _standard_grid(entry: Dict, styles) -> Table:
    """15-cell Standard mode grid: 3 layers (rows) × 5 TEPFI (cols)."""
    header = [Paragraph("Layer", styles["CellHdr"])]
    for t in TEPFI_ORDER:
        header.append(Paragraph(TEPFI_LABELS[t], styles["CellHdr"]))
    rows: List[List] = [header]
    for layer_key in LAYERS:
        layerset = entry.get(layer_key) or {}
        cell = (layerset.get("aggregate") or layerset.get("individual") or {})
        row = [Paragraph(f"<b>{LAYER_LABELS[layer_key]}</b>", styles["Cell"])]
        for t in TEPFI_ORDER:
            txt = _cell_text(cell, t)
            infl = _influence_pair(cell, t)
            body = txt + (("\n\n" + infl) if infl else "")
            row.append(Paragraph(body.replace("\n", "<br/>") or "—", styles["Cell"]))
        rows.append(row)
    col_widths = [2.6 * cm] + [4.0 * cm] * len(TEPFI_ORDER)
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B5563")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _accurate_grid(entry: Dict, styles) -> Table:
    """60-cell Accurate mode grid: 12 rows (3 layers × 4 orgtypes) × 5 TEPFI."""
    header = [Paragraph("Layer", styles["CellHdr"]), Paragraph("OrgType", styles["CellHdr"])]
    for t in TEPFI_ORDER:
        header.append(Paragraph(TEPFI_LABELS[t], styles["CellHdr"]))
    rows: List[List] = [header]
    for layer_key in LAYERS:
        layerset = entry.get(layer_key) or {}
        for ot in ORG_TYPES:
            cell = layerset.get(ot) or {}
            row = [
                Paragraph(f"<b>{LAYER_LABELS[layer_key]}</b>", styles["Cell"]),
                Paragraph(f"<b>{ORG_LABELS[ot]}</b>", styles["Cell"]),
            ]
            for t in TEPFI_ORDER:
                txt = _cell_text(cell, t)
                infl = _influence_pair(cell, t)
                body = txt + (("\n\n" + infl) if infl else "")
                row.append(Paragraph(body.replace("\n", "<br/>") or "—", styles["Cell"]))
            rows.append(row)
    col_widths = [1.8 * cm, 2.0 * cm] + [4.4 * cm] * len(TEPFI_ORDER)
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    style_cmds: List = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B5563")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]
    # Colour-band each layer's 4 orgtype rows
    for i, layer_key in enumerate(LAYERS):
        start = 1 + (i * 4)
        end = start + 3
        style_cmds.append(("BACKGROUND", (0, start), (0, end), colors.HexColor(LAYER_HEX[layer_key])))
        style_cmds.append(("TEXTCOLOR", (0, start), (0, end), colors.white))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _action_items_table(action_items: List[Dict], styles) -> Table:
    header = [
        Paragraph("#", styles["CellHdr"]),
        Paragraph("WHAT", styles["CellHdr"]),
        Paragraph("WHO", styles["CellHdr"]),
        Paragraph("BY WHEN", styles["CellHdr"]),
        Paragraph("STATUS", styles["CellHdr"]),
    ]
    rows = [header]
    for i, item in enumerate(action_items or [], start=1):
        rows.append([
            Paragraph(str(i), styles["Cell"]),
            Paragraph(str(item.get("what", "") or ""), styles["Cell"]),
            Paragraph(str(item.get("who", "") or ""), styles["Cell"]),
            Paragraph(str(item.get("by_when", "") or ""), styles["Cell"]),
            Paragraph(str(item.get("status", "") or ""), styles["Cell"]),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("—", styles["Cell"])] * 5)
    tbl = Table(rows, colWidths=[0.8 * cm, 6.0 * cm, 3.2 * cm, 3.0 * cm, 2.4 * cm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B5563")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def render_matrix_pdf(entry: Dict) -> bytes:
    """Render a Solution Matrix entry to a landscape-A4 PDF bytes payload."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    s = _styles()
    mode = str(entry.get("matrix_mode") or "accurate").lower()
    story: List = []

    # ── Header
    story.append(Paragraph("Solution Matrix Export", s["H0"]))
    mode_label = "Standard (15 cells — 5 TEPFI × 3 layers)" if mode == "standard" else "Accurate (60 cells — 5 TEPFI × 12 layer-orgtypes)"
    story.append(Paragraph(f"Mode: <b>{mode_label}</b>", s["Muted"]))
    story.append(Spacer(1, 6))

    # ── Goal & context
    story.append(Paragraph("Context", s["H1"]))
    story.append(_kv_row("Area of Life", str(entry.get("area_of_life", "") or "—"), s))
    story.append(_kv_row("SMART Goal", str(entry.get("smart_goal", "") or "—"), s))
    story.append(_kv_row("Created", str(entry.get("created_at", "") or "—"), s))
    story.append(_kv_row("Status", str(entry.get("status", "") or "—"), s))
    story.append(Spacer(1, 10))

    # ── Concerns
    story.append(Paragraph("Concerns", s["H1"]))
    story.append(_kv_row("All Concerns (Q1)", str(entry.get("q1_all_concerns", "") or "—"), s))
    story.append(_kv_row("Priority Concerns (Q2)", str(entry.get("q2_priority_concerns", "") or "—"), s))
    story.append(Spacer(1, 10))

    # ── Simpler Solutions
    story.append(Paragraph("Simpler Solutions (3.1.1)", s["H1"]))
    story.append(_kv_row("Solutions", str(entry.get("simpler_solutions", "") or "—"), s))
    story.append(_kv_row("Capabilities", str(entry.get("simpler_capabilities", "") or "—"), s))
    story.append(_kv_row("Resources", str(entry.get("simpler_resources", "") or "—"), s))
    story.append(_kv_row("Help Aspect", str(entry.get("simpler_help_aspect", "") or "—"), s))
    story.append(_kv_row("Help Level", str(entry.get("simpler_help_level", "") or "—"), s))
    story.append(_kv_row("Help From", str(entry.get("simpler_help_from", "") or "—"), s))
    story.append(PageBreak())

    # ── Matrix (3.1.2)
    story.append(Paragraph("Solution Matrix (3.1.2)", s["H1"]))
    story.append(Paragraph(mode_label, s["Muted"]))
    story.append(Spacer(1, 4))
    if mode == "standard":
        story.append(_standard_grid(entry, s))
    else:
        story.append(_accurate_grid(entry, s))
    story.append(PageBreak())

    # ── Risk
    story.append(Paragraph("Risk Management (Q4)", s["H1"]))
    story.append(_kv_row("Negative Consequences", str(entry.get("q4_negative_consequences", "") or "—"), s))
    story.append(_kv_row("Mitigation Plans", str(entry.get("q4_mitigation_plans", "") or "—"), s))
    story.append(_kv_row("Contingency Plans", str(entry.get("q4_contingency_plans", "") or "—"), s))
    story.append(Spacer(1, 10))

    # ── Action Plan
    story.append(Paragraph("Action Plan (Q5)", s["H1"]))
    story.append(_action_items_table(entry.get("action_items") or [], s))

    # Legal disclaimer footer — shared with other PDF exports.
    from utils.pdf_disclaimer import legal_disclaimer_flowables
    story.extend(legal_disclaimer_flowables(top_gap_mm=6))

    doc.build(story)
    return buf.getvalue()
