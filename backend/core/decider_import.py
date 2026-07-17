"""Decider Store — Option × Factor bulk import parser.

Parses the standard "Business Model Assessment" style layout (used by the
downloadable XLSX / shared Google-Sheet template) into a structured
{factors: [...], options: [...]} payload that a Decider Store template stores
and later clones into a MyDezider decision.

LAYOUT CONTRACT (column A holds a row-type label; factor columns live to the
right of the fixed option-metadata block):

  A2  "Factor Name"              -> factor display names (one per factor column)
  A3  "Possible Values"          -> comma-separated allowed values per factor
  A4  "Main Factor - Data Type"  -> Text | Number
  A5  "Main Factor - Select Type"-> Single-Select | Multi-Select
  A6  "Main Factor - UI Object"  -> Check Box | Radio | Dropdown
  A7  "Sub Factor - Data Type"   -> % | NA
  A8  "Sub Factor - Select Type" -> Suitability % per value | NA
  A9  "Sub Factor - UI Object"   -> Input Box | NA
  A10 "Factor Group"             -> Quantitative | Qualitative   (optional)
  A11 "Classification"           -> Mandatory | Optional          (optional)
  A12 "Priority"                 -> 1..10                          (optional)
  A?  header row  (No | Product Model | Option Name | Affected Components |
                   Exemplary Companies | Description | Remarks | <factor cols>)
  ...  one option per row below the header row.

Factor cell format: "Value1, Value2 (40%), Value3 (100%)" — a value with no
(nn%) suffix is treated as 100%.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

# ── column-A row-label detection ──────────────────────────────────────────
_LABELS = {
    "factor_name":  ("factor name", "factors influencing"),
    "possible":     ("possible value",),
    "main_dtype":   ("main factor - data type", "main factor data type"),
    "main_select":  ("main factor - select type", "main factor select type"),
    "main_ui":      ("main factor - ui object", "main factor ui object"),
    "sub_dtype":    ("sub factor - data type", "sub factor data type"),
    "sub_select":   ("sub factor - select type", "sub factor select type"),
    "sub_ui":       ("sub factor - ui object", "sub factor ui object"),
    "group":        ("factor group", "group (quant"),
    "classify":     ("classification",),
    "priority":     ("priority",),
}

# option-metadata header aliases -> canonical key
_META_ALIASES = {
    "no": "no", "s.no": "no", "sno": "no", "#": "no",
    "product model": "product_model",
    "pattern name": "name", "option name": "name", "name": "name", "option": "name",
    "affected bm components": "affected_components", "affected components": "affected_components",
    "exemplary companies": "exemplary_companies", "examples": "exemplary_companies",
    "pattern description": "description", "description": "description",
    "biz coach remarks": "remarks", "remarks": "remarks", "coach remarks": "remarks",
}


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _cell(v: Any) -> str:
    return "" if v is None else re.sub(r"\s+", " ", str(v).replace("\n", " ")).strip()


def parse_value_cell(raw: Any) -> List[Dict[str, Any]]:
    """"Solo, Startup (40%)" -> [{'value':'Solo','pct':100},{'value':'Startup','pct':40}]."""
    txt = _cell(raw)
    if not txt or txt.upper() in ("NA", "N/A", "-", "—"):
        return []
    out: List[Dict[str, Any]] = []
    # split on commas that are NOT inside parentheses
    parts = re.split(r",(?![^(]*\))", txt)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.search(r"\((\d+(?:\.\d+)?)\s*%?\)", p)
        pct = float(m.group(1)) if m else 100.0
        label = re.sub(r"\s*\(\s*\d+(?:\.\d+)?\s*%?\s*\)\s*", "", p).strip()
        if label:
            out.append({"value": label, "pct": pct})
    return out


def _rows_from_xlsx(data: bytes) -> List[List[Any]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.worksheets[0]
    return [[c.value for c in row] for row in ws.iter_rows()]


def _rows_from_csv(text: str) -> List[List[Any]]:
    return [row for row in csv.reader(io.StringIO(text))]


def _find_label_row(rows: List[List[Any]], keys: Tuple[str, ...]) -> Optional[int]:
    for i, row in enumerate(rows):
        a = _norm(row[0] if row else "")
        if any(a.startswith(k) or k in a for k in keys):
            return i
    return None


def _find_header_row(rows: List[List[Any]]) -> Optional[int]:
    for i, row in enumerate(rows):
        cells = {_norm(c) for c in row if _cell(c)}
        has_name = any(c in ("pattern name", "option name", "name", "option") for c in cells)
        has_no_or_model = ("no" in cells) or ("product model" in cells) or ("description" in cells)
        if has_name and has_no_or_model:
            return i
    return None


def parse_import(data: bytes = None, csv_text: str = None) -> Dict[str, Any]:
    """Return {'factors': [...], 'options': [...], 'warnings': [...]}. Raises
    ValueError with a human message when the layout can't be understood."""
    rows = _rows_from_csv(csv_text) if csv_text is not None else _rows_from_xlsx(data)
    if not rows:
        raise ValueError("The sheet is empty.")

    header_i = _find_header_row(rows)
    if header_i is None:
        raise ValueError(
            "Couldn't find the option header row. It must include a 'No' (or "
            "'Product Model') cell and a 'Pattern name' / 'Option Name' cell.")

    header = rows[header_i]
    # Map metadata columns from the header row.
    meta_col: Dict[int, str] = {}
    last_meta_col = -1
    for ci, h in enumerate(header):
        key = _META_ALIASES.get(_norm(h))
        if key:
            meta_col[ci] = key
            last_meta_col = max(last_meta_col, ci)

    # Factor name row (label "Factor Name", else the row just above Possible Values).
    fn_i = _find_label_row(rows, _LABELS["factor_name"])
    pv_i = _find_label_row(rows, _LABELS["possible"])
    if fn_i is None and pv_i is not None:
        fn_i = pv_i - 1
    if fn_i is None:
        raise ValueError("Couldn't find the 'Factor Name' row.")

    fn_row = rows[fn_i]
    # Factor columns = columns beyond the metadata block that carry a factor name.
    factor_cols = [ci for ci in range(last_meta_col + 1, len(fn_row)) if _cell(fn_row[ci])]
    if not factor_cols:
        # fall back: any col with a name to the right of col G (index 6)
        factor_cols = [ci for ci in range(max(last_meta_col + 1, 7), len(fn_row)) if _cell(fn_row[ci])]
    if not factor_cols:
        raise ValueError("No factor columns detected in the 'Factor Name' row.")

    def lbl_row(key: str) -> List[Any]:
        i = _find_label_row(rows, _LABELS[key])
        return rows[i] if i is not None else []

    r_pv, r_mdt, r_mst, r_mui = lbl_row("possible"), lbl_row("main_dtype"), lbl_row("main_select"), lbl_row("main_ui")
    r_sdt, r_sst, r_sui = lbl_row("sub_dtype"), lbl_row("sub_select"), lbl_row("sub_ui")
    r_grp, r_cls, r_pri = lbl_row("group"), lbl_row("classify"), lbl_row("priority")

    def at(row: List[Any], ci: int) -> str:
        return _cell(row[ci]) if row and ci < len(row) else ""

    factors: List[Dict[str, Any]] = []
    col_to_fid: Dict[int, str] = {}
    for order, ci in enumerate(factor_cols):
        name = re.sub(r"^\s*\d+\.\s*", "", _cell(fn_row[ci]))  # strip "1. "
        fid = str(uuid.uuid4())
        col_to_fid[ci] = fid
        sub_dt = at(r_sdt, ci)
        has_sub_pct = "%" in sub_dt
        grp = _norm(at(r_grp, ci))
        cls = _norm(at(r_cls, ci))
        pri_raw = at(r_pri, ci)
        try:
            priority = int(float(pri_raw)) if pri_raw else 0
        except ValueError:
            priority = 0
        factors.append({
            "id": fid,
            "name": name,
            "order": order,
            "possible_values": [v.strip() for v in re.split(r"[,\n]", at(r_pv, ci)) if v.strip()],
            "data_type": at(r_mdt, ci) or "Text",
            "select_type": at(r_mst, ci) or "Multi-Select",
            "ui_object": at(r_mui, ci) or "Check Box",
            "sub_data_type": sub_dt or "NA",
            "sub_select_type": at(r_sst, ci) or "NA",
            "sub_ui_object": at(r_sui, ci) or "NA",
            "has_sub_pct": has_sub_pct,
            "factor_type": ("quantitative" if grp.startswith("quant") else "qualitative"),
            "category": ("mandatory" if cls.startswith("mand") else ("optional" if cls.startswith("opt") else "")),
            "priority": priority,
        })

    options: List[Dict[str, Any]] = []
    for ri in range(header_i + 1, len(rows)):
        row = rows[ri]
        if not row:
            continue
        rec: Dict[str, Any] = {}
        for ci, key in meta_col.items():
            rec[key] = _cell(row[ci]) if ci < len(row) else ""
        name = rec.get("name", "")
        if not name:
            continue  # skip legend/example/blank rows
        values: Dict[str, List[Dict[str, Any]]] = {}
        for ci, fid in col_to_fid.items():
            parsed = parse_value_cell(row[ci] if ci < len(row) else "")
            if parsed:
                values[fid] = parsed
        options.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "product_model": rec.get("product_model", ""),
            "affected_components": rec.get("affected_components", ""),
            "exemplary_companies": rec.get("exemplary_companies", ""),
            "description": rec.get("description", ""),
            "remarks": rec.get("remarks", ""),
            "values": values,
        })

    if not options:
        raise ValueError("No option rows found below the header row.")

    return {"factors": factors, "options": options, "warnings": []}


# ── gsheet url -> csv export url (shared with store_ingestion) ─────────────
def gsheet_to_csv_url(url: str) -> str:
    u = (url or "").strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", u)
    if not m:
        return u
    sid = m.group(1)
    gid = "0"
    g = re.search(r"[#&?]gid=(\d+)", u)
    if g:
        gid = g.group(1)
    return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"


# ── generate the downloadable XLSX import template ─────────────────────────
def build_import_template_xlsx(sample: bool = True) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Option-Factor Import"

    META = ["No", "Product Model", "Option Name", "Affected Components",
            "Exemplary Companies", "Description", "Remarks"]
    FACTORS = [
        ("Org Type", "Solo, Startup, SME, Corporate", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Solution Category", "Product, Service", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Nature of Solution", "Pain Reliever, Gain Creator", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Intensity/Urgency/Frequency", "Low, Medium, High", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Affordability", "Low, Medium, High", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Revenue Model", "B2B, B2C", "Text", "Multi-Select", "Check Box", "NA", "Qualitative"),
        ("Tech Orientation", "Traditional, High Tech", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Distribution Channels", "Offline - Direct, Offline - Channel, Online - Direct, Online - Channel", "Text", "Multi-Select", "Check Box", "NA", "Qualitative"),
        ("Value Creation", "Single Point - Normal, Single Point - Deeper, Multiple Points - Normal, Multiple Points - Deeper", "Text", "Multi-Select", "Check Box", "%", "Qualitative"),
        ("Differentiation Strategy", "Premium Value Driven, Delivery Cost Driven", "Text", "Multi-Select", "Check Box", "NA", "Qualitative"),
    ]
    ncols = len(META) + len(FACTORS)
    first_fc = len(META) + 1  # 1-based first factor column

    hdr_fill = PatternFill("solid", fgColor="1E3A8A")
    lbl_fill = PatternFill("solid", fgColor="E0E7FF")
    fac_fill = PatternFill("solid", fgColor="C7D2FE")
    white = Font(color="FFFFFF", bold=True)
    bold = Font(bold=True)
    thin = Side(style="thin", color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def put(r, c, v, *, fill=None, font=None, wrap=True):
        cell = ws.cell(r, c, v)
        if fill: cell.fill = fill
        if font: cell.font = font
        cell.alignment = Alignment(wrap_text=wrap, vertical="top")
        cell.border = border
        return cell

    # Title
    put(1, 1, "THE DECIDER STORE — Option × Factor Import Template", font=Font(bold=True, size=13, color="1E3A8A"), wrap=False)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)

    # Meta label rows (col A carries the row-type label)
    label_rows = [
        (2, "Factor Name"), (3, "Possible Values"),
        (4, "Main Factor - Data Type"), (5, "Main Factor - Select Type"),
        (6, "Main Factor - UI Object"), (7, "Sub Factor - Data Type"),
        (8, "Sub Factor - Select Type"), (9, "Sub Factor - UI Object"),
        (10, "Factor Group"), (11, "Classification (optional)"), (12, "Priority 1-10 (optional)"),
    ]
    for r, lbl in label_rows:
        put(r, 1, lbl, fill=lbl_fill, font=bold)
        for c in range(2, first_fc):
            put(r, c, "", fill=lbl_fill)

    for idx, (name, pv, dt, st, ui, sub, grp) in enumerate(FACTORS):
        c = first_fc + idx
        put(2, c, name, fill=fac_fill, font=bold)
        put(3, c, pv, fill=fac_fill)
        put(4, c, dt, fill=fac_fill)
        put(5, c, st, fill=fac_fill)
        put(6, c, ui, fill=fac_fill)
        put(7, c, sub, fill=fac_fill)
        put(8, c, "Suitability % per value" if sub == "%" else "NA", fill=fac_fill)
        put(9, c, "Input Box" if sub == "%" else "NA", fill=fac_fill)
        put(10, c, grp, fill=fac_fill)
        put(11, c, "", fill=fac_fill)
        put(12, c, "", fill=fac_fill)

    # Column-header row (row 13)
    HROW = 13
    for i, h in enumerate(META):
        put(HROW, i + 1, h, fill=hdr_fill, font=white)
    for idx, (name, *_rest) in enumerate(FACTORS):
        put(HROW, first_fc + idx, name, fill=hdr_fill, font=white)

    if sample:
        sample_rows = [
            [1, "How Value", "AFFILIATION", "How, Value", "Amazon Associates, Pinterest",
             "Pay partners a commission for referred sales.", "More about HOW you connect.",
             "Solo (100%), Startup (40%)", "Product (50%), Service (50%)", "Gain Creator (100%)",
             "Medium (70%), Low (40%)", "High (100%)", "B2B", "High Tech (100%)",
             "Online - Direct", "Multiple Points - Normal (65%)", "Premium Value Driven"],
            [2, "Who What Value", "AIKIDO", "Who, What, Value", "Six Flags, Nintendo (Wii)",
             "Offer the opposite of the competition's value proposition.", "Contrarian positioning.",
             "Startup (40%), SME (50%)", "Product (50%), Service (50%)", "Pain Reliever (70%)",
             "High (70%), Medium (40%)", "Medium (40%)", "B2C", "High Tech (75%), Traditional (60%)",
             "Online - Direct, Offline - Direct", "Single Point - Deeper (70%)", "Delivery Cost Driven"],
        ]
        for r_off, row in enumerate(sample_rows):
            for c_off, v in enumerate(row):
                put(HROW + 1 + r_off, c_off + 1, v)

    # Instruction row at the very bottom
    note_r = HROW + (3 if sample else 1) + 1
    put(note_r, 1,
        f"HOW TO FILL: One option per row from row {HROW + 1}. In each factor cell list the "
        f"applicable value(s); add a per-value suitability like 'Startup (40%)'. A value with no "
        f"(nn%) suffix counts as 100%. Leave a cell blank or 'NA' if not applicable. Separate "
        f"multiple values with commas.",
        font=Font(italic=True, color="475569"), wrap=True)
    ws.merge_cells(start_row=note_r, start_column=1, end_row=note_r, end_column=ncols)

    # widths
    ws.column_dimensions["A"].width = 26
    for c in range(2, ncols + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 22

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
