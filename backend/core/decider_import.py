"""Decider Store — generic Main-Factor / Sub-Factor bulk import parser + template.

The import sheet (downloadable XLSX or a shared Google-Sheet) now models
**main factors** and their **sub-factors** as first-class entities instead of
collapsing them into a single cell string.

SHEET 1  "Template Data"  — column A holds a row-type label; the option-metadata
columns sit to the left, and each SUB-FACTOR is its own column grouped under its
MAIN FACTOR:

  A2  "Main Factor"                          -> main factor name (spans its sub cols)
  A3  "Category (Mandatory/Optional)"        -> main-factor level
  A4  "Priority (1,2,3...)"                   -> main-factor level
  A5  "Factor Type (Quantitative/Qualitative)"-> main-factor level
  A6  "Sub-Factor"                           -> sub-factor name (one per column)
  A7  "Data Type (% / Number / Text)"        -> sub-factor level
  A8  "UI Object (Input Box / Slider / Dropdown)" -> sub-factor level
  A9  "Split % (total 100 per main factor)"  -> sub-factor level
  A10 header row (No | Product Model | Option Name | Affected Components |
                  Exemplary Companies | Description | Remarks | <sub-factor cols>)
  ...  one OPTION per row; each cell holds that option's value for the sub-factor.

SHEET 2  "Instructions"  — a colour-coded how-to-fill guide + worked example.

Parsed model
------------
  factors:  [{id, name, order, category, priority, factor_type,
              sub_factors:[{id, name, order, data_type, ui_object, split_pct}],
              possible_values:[sub-factor names]  # derived, for previews}]
  options:  [{id, name, product_model, affected_components, exemplary_companies,
              description, remarks, values:{sub_factor_id:{raw, num}}}]
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

# ── column-A row-label detection ──────────────────────────────────────────
_LABELS = {
    "main_factor": ("main factor",),
    "category":    ("category",),
    "priority":    ("priority",),
    "factor_type": ("factor type",),
    "sub_factor":  ("sub-factor", "sub factor"),
    "data_type":   ("data type",),
    "ui_object":   ("ui object",),
    "split":       ("split %", "split"),
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


def _to_num(raw: str) -> Optional[float]:
    """Parse '100', '40%', '₹1,200', '3.5' -> float; None when not numeric."""
    if not raw:
        return None
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", raw.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_value_cell(raw: Any) -> List[Dict[str, Any]]:
    """Legacy helper — "Solo, Startup (40%)" -> [{'value':'Solo','pct':100},…].

    Still used by the Store⇄ReviewNet sync/from-solutions paths.
    """
    txt = _cell(raw)
    if not txt or txt.upper() in ("NA", "N/A", "-", "—"):
        return []
    out: List[Dict[str, Any]] = []
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


# ── sheet readers ─────────────────────────────────────────────────────────
def _rows_from_xlsx(data: bytes) -> List[List[Any]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    # Prefer a sheet that looks like the data sheet (has a "Main Factor" label).
    ws = None
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(max_row=15, values_only=True):
            if row and any(_norm(c).startswith("main factor") for c in row if c):
                ws = sheet
                break
        if ws:
            break
    ws = ws or wb.worksheets[0]
    return [[c.value for c in row] for row in ws.iter_rows()]


def _rows_from_csv(text: str) -> List[List[Any]]:
    return [row for row in csv.reader(io.StringIO(text))]


def _find_label_row(rows: List[List[Any]], keys: Tuple[str, ...]) -> Optional[int]:
    for i, row in enumerate(rows):
        a = _norm(row[0] if row else "")
        if a and any(a.startswith(k) for k in keys):
            return i
    return None


def _find_header_row(rows: List[List[Any]]) -> Optional[int]:
    for i, row in enumerate(rows):
        cells = {_norm(c) for c in row if _cell(c)}
        has_name = any(c in ("pattern name", "option name", "name", "option") for c in cells)
        has_anchor = ("no" in cells) or ("product model" in cells) or ("description" in cells)
        if has_name and has_anchor:
            return i
    return None


def _ffill(row: List[Any], start: int, end: int) -> Dict[int, str]:
    """Forward-fill a row's cells across [start, end] (handles merged cells /
    blanks that should inherit the previous non-blank value)."""
    out: Dict[int, str] = {}
    cur = ""
    for ci in range(start, end + 1):
        v = _cell(row[ci]) if row and ci < len(row) else ""
        if v:
            cur = v
        out[ci] = cur
    return out


def parse_import(data: bytes = None, csv_text: str = None) -> Dict[str, Any]:
    """Parse the Main-Factor/Sub-Factor sheet -> {factors, options, warnings}.
    Raises ValueError with a human message when the layout can't be understood."""
    rows = _rows_from_csv(csv_text) if csv_text is not None else _rows_from_xlsx(data)
    if not rows:
        raise ValueError("The sheet is empty.")

    warnings: List[str] = []

    mf_i = _find_label_row(rows, _LABELS["main_factor"])
    sf_i = _find_label_row(rows, _LABELS["sub_factor"])
    header_i = _find_header_row(rows)
    if mf_i is None or sf_i is None:
        raise ValueError(
            "This sheet isn't in the new Main-Factor / Sub-Factor format. Download the "
            "latest Excel template (it has a 'Main Factor' and a 'Sub-Factor' row) and "
            "fill your data into the 'Template Data' sheet.")
    if header_i is None:
        raise ValueError(
            "Couldn't find the option header row. It must include an 'Option Name' cell "
            "and a 'No' (or 'Product Model'/'Description') cell.")

    header = rows[header_i]
    meta_col: Dict[int, str] = {}
    last_meta_col = -1
    for ci, h in enumerate(header):
        key = _META_ALIASES.get(_norm(h))
        if key and ci not in meta_col:
            meta_col[ci] = key
            last_meta_col = max(last_meta_col, ci)
    if last_meta_col < 0:
        raise ValueError("Couldn't map the option-metadata columns (No / Option Name / …).")

    first_sub = last_meta_col + 1
    max_col = max((len(r) for r in rows), default=first_sub) - 1
    if max_col < first_sub:
        raise ValueError("No sub-factor columns found to the right of the metadata block.")

    sub_row = rows[sf_i]
    # A sub-factor column = a column (right of metadata) with a sub-factor name.
    sub_cols = [ci for ci in range(first_sub, max_col + 1)
                if ci < len(sub_row) and _cell(sub_row[ci])]
    if not sub_cols:
        raise ValueError("No sub-factor columns detected in the 'Sub-Factor' row.")

    # Forward-filled main-factor / category / priority / type across the grid.
    mf_fill = _ffill(rows[mf_i], first_sub, max_col)
    cat_fill = _ffill(rows[_find_label_row(rows, _LABELS["category"])] if _find_label_row(rows, _LABELS["category"]) is not None else [], first_sub, max_col)
    pri_fill = _ffill(rows[_find_label_row(rows, _LABELS["priority"])] if _find_label_row(rows, _LABELS["priority"]) is not None else [], first_sub, max_col)
    typ_fill = _ffill(rows[_find_label_row(rows, _LABELS["factor_type"])] if _find_label_row(rows, _LABELS["factor_type"]) is not None else [], first_sub, max_col)

    dt_i = _find_label_row(rows, _LABELS["data_type"])
    ui_i = _find_label_row(rows, _LABELS["ui_object"])
    sp_i = _find_label_row(rows, _LABELS["split"])
    r_dt = rows[dt_i] if dt_i is not None else []
    r_ui = rows[ui_i] if ui_i is not None else []
    r_sp = rows[sp_i] if sp_i is not None else []

    def at(row: List[Any], ci: int) -> str:
        return _cell(row[ci]) if row and ci < len(row) else ""

    # Group contiguous sub-columns that share the same (filled) main-factor name.
    factors: List[Dict[str, Any]] = []
    col_to_sid: Dict[int, str] = {}
    order = 0
    i = 0
    while i < len(sub_cols):
        c0 = sub_cols[i]
        name = mf_fill.get(c0, "") or f"Factor {order + 1}"
        # collect the contiguous run of sub-cols sharing this main name
        run = [c0]
        j = i + 1
        while j < len(sub_cols) and mf_fill.get(sub_cols[j], "") == name:
            run.append(sub_cols[j])
            j += 1
        cat = _norm(cat_fill.get(c0, ""))
        pri_raw = pri_fill.get(c0, "")
        try:
            priority = int(float(pri_raw)) if pri_raw else 0
        except ValueError:
            priority = 0
        ftype = _norm(typ_fill.get(c0, ""))
        fid = str(uuid.uuid4())
        subs: List[Dict[str, Any]] = []
        for so, ci in enumerate(run):
            sid = str(uuid.uuid4())
            col_to_sid[ci] = sid
            sp_raw = at(r_sp, ci)
            try:
                split = float(re.sub(r"[^\d.]", "", sp_raw)) if sp_raw else 0.0
            except ValueError:
                split = 0.0
            subs.append({
                "id": sid,
                "name": re.sub(r"^\s*\d+[.)]\s*", "", at(sub_row, ci)) or f"Sub {so + 1}",
                "order": so,
                "data_type": at(r_dt, ci) or "%",
                "ui_object": at(r_ui, ci) or "Input Box",
                "split_pct": split,
            })
        # normalise / validate split %
        total = round(sum(s["split_pct"] for s in subs), 2)
        if total == 0:
            eq = round(100.0 / len(subs), 2) if subs else 0.0
            for s in subs:
                s["split_pct"] = eq
        elif abs(total - 100.0) > 1.0:
            warnings.append(f"'{name}': Split % totals {total:g}% (should be 100%).")
        factors.append({
            "id": fid,
            "name": re.sub(r"^\s*\d+[.)]\s*", "", name),
            "order": order,
            "category": ("mandatory" if cat.startswith("mand")
                         else "optional" if cat.startswith("opt") else ""),
            "priority": priority,
            "factor_type": ("quantitative" if ftype.startswith("quant") else "qualitative"),
            "sub_factors": subs,
            "possible_values": [s["name"] for s in subs],
        })
        order += 1
        i = j

    # Options
    options: List[Dict[str, Any]] = []
    dt_by_col = {ci: at(r_dt, ci) for ci in sub_cols}
    for ri in range(header_i + 1, len(rows)):
        row = rows[ri]
        if not row:
            continue
        rec: Dict[str, str] = {}
        for ci, key in meta_col.items():
            rec[key] = _cell(row[ci]) if ci < len(row) else ""
        name = rec.get("name", "")
        if not name:
            continue  # skip legend / blank rows
        values: Dict[str, Dict[str, Any]] = {}
        for ci, sid in col_to_sid.items():
            raw = _cell(row[ci]) if ci < len(row) else ""
            if not raw or raw.upper() in ("NA", "N/A", "-", "—"):
                continue
            is_text = _norm(dt_by_col.get(ci, "")).startswith("text")
            values[sid] = {"raw": raw, "num": None if is_text else _to_num(raw)}
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

    if not factors:
        raise ValueError("No main factors detected.")
    if not options:
        raise ValueError("No option rows found below the header row.")

    return {"factors": factors, "options": options, "warnings": warnings}


# ── gsheet url -> csv export url ──────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════
# XLSX GENERATION (shared by template download + BMP data regeneration)
# ══════════════════════════════════════════════════════════════════════════
META_COLS = ["No", "Product Model", "Option Name", "Affected Components",
             "Exemplary Companies", "Description", "Remarks"]


def _styles():
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    thin = Side(style="thin", color="CBD5E1")
    return {
        "hdr_fill": PatternFill("solid", fgColor="1E3A8A"),
        "mf_fill": PatternFill("solid", fgColor="C7D2FE"),
        "sf_fill": PatternFill("solid", fgColor="E0E7FF"),
        "lbl_fill": PatternFill("solid", fgColor="F1F5F9"),
        "white": Font(color="FFFFFF", bold=True),
        "bold": Font(bold=True),
        "border": Border(left=thin, right=thin, top=thin, bottom=thin),
        "Alignment": Alignment,
        "Font": Font,
        "PatternFill": PatternFill,
    }


def _write_data_sheet(ws, factors: List[Dict[str, Any]], option_rows: List[List[Any]]):
    """factors: [{name, category, priority, factor_type,
                  sub_factors:[{name, data_type, ui_object, split_pct}]}].
       option_rows: raw cell rows already aligned to META_COLS + all sub cols."""
    import openpyxl
    st = _styles()
    Alignment = st["Alignment"]

    def put(r, c, v, *, fill=None, font=None, wrap=True):
        cell = ws.cell(r, c, v)
        if fill:
            cell.fill = fill
        if font:
            cell.font = font
        cell.alignment = Alignment(wrap_text=wrap, vertical="top")
        cell.border = st["border"]
        return cell

    nmeta = len(META_COLS)
    first_sub = nmeta + 1  # 1-based
    total_subs = sum(len(f["sub_factors"]) for f in factors)
    ncols = nmeta + total_subs

    # Title
    put(1, 1, "THE DECIDER STORE — Template Data (fill one option per row)",
        font=st["Font"](bold=True, size=13, color="1E3A8A"), wrap=False)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(ncols, 1))

    label_rows = [
        (2, "Main Factor"), (3, "Category (Mandatory/Optional)"),
        (4, "Priority (1,2,3...)"), (5, "Factor Type (Quantitative/Qualitative)"),
        (6, "Sub-Factor"), (7, "Data Type (% / Number / Text)"),
        (8, "UI Object (Input Box / Slider / Dropdown)"),
        (9, "Split % (must total 100 per main factor)"),
    ]
    for r, lbl in label_rows:
        put(r, 1, lbl, fill=st["lbl_fill"], font=st["bold"])
        for c in range(2, first_sub):
            put(r, c, "", fill=st["lbl_fill"])

    # Factor / sub-factor blocks
    col = first_sub
    for f in factors:
        subs = f["sub_factors"]
        span = len(subs)
        c0, c1 = col, col + span - 1
        # main-factor rows (merge across the span)
        for r, val in ((2, f["name"]), (3, f.get("category", "")),
                       (4, f.get("priority", "")), (5, f.get("factor_type", ""))):
            put(r, c0, val, fill=st["mf_fill"], font=(st["bold"] if r == 2 else None))
            for c in range(c0 + 1, c1 + 1):
                put(r, c, "", fill=st["mf_fill"])
            if span > 1:
                ws.merge_cells(start_row=r, start_column=c0, end_row=r, end_column=c1)
        # sub-factor rows (per column)
        for so, sub in enumerate(subs):
            c = c0 + so
            put(6, c, sub["name"], fill=st["sf_fill"], font=st["bold"])
            put(7, c, sub.get("data_type", "%"), fill=st["sf_fill"])
            put(8, c, sub.get("ui_object", "Input Box"), fill=st["sf_fill"])
            put(9, c, sub.get("split_pct", ""), fill=st["sf_fill"])
        col = c1 + 1

    # Header row (row 10)
    HROW = 10
    for i, h in enumerate(META_COLS):
        put(HROW, i + 1, h, fill=st["hdr_fill"], font=st["white"])
    col = first_sub
    for f in factors:
        for sub in f["sub_factors"]:
            put(HROW, col, sub["name"], fill=st["hdr_fill"], font=st["white"])
            col += 1

    # Option rows
    for ri, row in enumerate(option_rows):
        for ci, v in enumerate(row):
            put(HROW + 1 + ri, ci + 1, v)

    ws.column_dimensions["A"].width = 30
    for c in range(2, ncols + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 18


def _write_instructions_sheet(ws):
    """Colour-coded how-to-fill guide + worked example."""
    st = _styles()
    Alignment, Font, PatternFill = st["Alignment"], st["Font"], st["PatternFill"]

    # section colours
    C_MAIN = PatternFill("solid", fgColor="C7D2FE")   # indigo — main factor
    C_SUB = PatternFill("solid", fgColor="BBF7D0")    # green  — sub-factor
    C_SPLIT = PatternFill("solid", fgColor="FDE68A")  # amber  — split %
    C_OPT = PatternFill("solid", fgColor="FBCFE8")    # pink   — option values

    def put(r, c, v, *, fill=None, bold=False, italic=False, size=11, color="0F172A", wrap=True):
        cell = ws.cell(r, c, v)
        if fill:
            cell.fill = fill
        cell.font = Font(bold=bold, italic=italic, size=size, color=color)
        cell.alignment = Alignment(wrap_text=wrap, vertical="top")
        return cell

    put(1, 1, "HOW TO FILL THE DECIDER STORE TEMPLATE", bold=True, size=15, color="1E3A8A")
    ws.merge_cells("A1:F1")

    r = 3
    sections = [
        (C_MAIN, "① MAIN FACTOR (indigo rows 2-5)",
         "One MAIN FACTOR per group of columns. Type its name once in the 'Main Factor' "
         "row above its sub-factor columns. Set Category = Mandatory/Optional, Priority = "
         "1,2,3… (1 = most important) and Factor Type = Quantitative or Qualitative. "
         "These apply to the whole factor."),
        (C_SUB, "② SUB-FACTOR (green rows 6-8)",
         "Each MAIN FACTOR breaks into one or more SUB-FACTORS — one column each. Give each "
         "a name (e.g. 'Solo %'), a Data Type (% / Number / Text) and a UI Object "
         "(Input Box / Slider / Dropdown). Sub-factors can be one-per-value (Solo, Startup…) "
         "OR arbitrary measures (Setup Cost, Break-even…)."),
        (C_SPLIT, "③ SPLIT % (amber row 9)",
         "Split % is the WEIGHT of each sub-factor inside its main factor. The split % of all "
         "sub-factors under one main factor MUST TOTAL 100%. Example: Org Type → Solo 40, "
         "Startup 30, SME 20, Corporate 10 (= 100). Leave all blank to split equally."),
        (C_OPT, "④ OPTION VALUES (pink — rows 11 onward)",
         "One OPTION per row (fill No / Option Name / Description / Remarks on the left). In "
         "each sub-factor cell put THIS option's value for that sub-factor (e.g. Solo % = 100, "
         "Startup % = 40). Leave blank or 'NA' if not applicable. This is different from "
         "Split %: Split % is set once per factor; option values change every row."),
    ]
    for fill, title, body in sections:
        put(r, 1, title, fill=fill, bold=True, size=12)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        put(r + 1, 1, body, size=11)
        ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=6)
        ws.row_dimensions[r + 1].height = 58
        r += 3

    # Worked example
    put(r, 1, "WORKED EXAMPLE — Main Factor 'Org Type'", bold=True, size=13, color="1E3A8A")
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    r += 2

    put(r, 1, "Main Factor", fill=C_MAIN, bold=True)
    put(r, 2, "Org Type (Mandatory · Priority 1 · Qualitative)", fill=C_MAIN)
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    r += 1
    put(r, 1, "Sub-Factor", fill=C_SUB, bold=True)
    for i, v in enumerate(["Solo %", "Startup %", "SME %", "Corporate %"]):
        put(r, 2 + i, v, fill=C_SUB, bold=True)
    r += 1
    put(r, 1, "Split %", fill=C_SPLIT, bold=True)
    for i, v in enumerate([40, 30, 20, 10]):
        put(r, 2 + i, v, fill=C_SPLIT)
    put(r, 6, "= 100%", fill=C_SPLIT, italic=True)
    r += 1
    for opt, vals in [("AFFILIATION", [100, 40, 0, 0]), ("FREEMIUM", [60, 100, 80, 50])]:
        put(r, 1, opt, fill=C_OPT, bold=True)
        for i, v in enumerate(vals):
            put(r, 2 + i, v, fill=C_OPT)
        r += 1
    put(r + 1, 1, "↑ Split % (amber) = weights that total 100. Each option row (pink) = that "
                  "option's suitability value per sub-factor.", italic=True, color="475569")
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=6)

    ws.column_dimensions["A"].width = 16
    for c in "BCDEF":
        ws.column_dimensions[c].width = 20


# sample factors for the downloadable blank/sample template
_SAMPLE_FACTORS = [
    {"name": "Org Type", "category": "Mandatory", "priority": 1, "factor_type": "Qualitative",
     "sub_factors": [
         {"name": "Solo %", "data_type": "%", "ui_object": "Input Box", "split_pct": 25},
         {"name": "Startup %", "data_type": "%", "ui_object": "Input Box", "split_pct": 25},
         {"name": "SME %", "data_type": "%", "ui_object": "Input Box", "split_pct": 25},
         {"name": "Corporate %", "data_type": "%", "ui_object": "Input Box", "split_pct": 25},
     ]},
    {"name": "Solution Category", "category": "Mandatory", "priority": 2, "factor_type": "Qualitative",
     "sub_factors": [
         {"name": "Product %", "data_type": "%", "ui_object": "Input Box", "split_pct": 50},
         {"name": "Service %", "data_type": "%", "ui_object": "Input Box", "split_pct": 50},
     ]},
    {"name": "Affordability", "category": "Optional", "priority": 3, "factor_type": "Qualitative",
     "sub_factors": [
         {"name": "Low %", "data_type": "%", "ui_object": "Input Box", "split_pct": 34},
         {"name": "Medium %", "data_type": "%", "ui_object": "Input Box", "split_pct": 33},
         {"name": "High %", "data_type": "%", "ui_object": "Input Box", "split_pct": 33},
     ]},
]


def build_import_template_xlsx(sample: bool = True) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Data"

    option_rows: List[List[Any]] = []
    if sample:
        # META_COLS = No, Product Model, Option Name, Affected Components,
        #             Exemplary Companies, Description, Remarks
        # then sub cols: Solo,Startup,SME,Corporate, Product,Service, Low,Medium,High
        option_rows = [
            [1, "", "AFFILIATION", "How, Value", "Amazon Associates, Pinterest",
             "Pay partners a commission for referred sales.", "About HOW you share revenue.",
             100, 40, 0, 0,  60, 40,  40, 70, 100],
            [2, "", "FREEMIUM", "Value, Revenue", "Spotify, Dropbox, LinkedIn",
             "Free basic tier; paid premium upgrade.", "Conversion rate is key.",
             60, 100, 80, 50,  50, 50,  100, 70, 40],
        ]
    _write_data_sheet(ws, _SAMPLE_FACTORS, option_rows)

    ws2 = wb.create_sheet("Instructions")
    _write_instructions_sheet(ws2)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_data_xlsx_from_model(factors: List[Dict[str, Any]],
                               options: List[Dict[str, Any]]) -> bytes:
    """Write a NEW-format workbook (Data + Instructions) from a parsed model —
    used to (re)generate the seeded BMP data file."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Data"

    # ordered sub-factor ids across all factors (matches column order)
    sub_ids: List[str] = []
    for f in factors:
        for s in f["sub_factors"]:
            sub_ids.append(s["id"])

    option_rows: List[List[Any]] = []
    for i, opt in enumerate(options, start=1):
        meta = [i, opt.get("product_model", ""), opt.get("name", ""),
                opt.get("affected_components", ""), opt.get("exemplary_companies", ""),
                opt.get("description", ""), opt.get("remarks", "")]
        vals = opt.get("values") or {}
        cells: List[Any] = []
        for sid in sub_ids:
            v = vals.get(sid)
            cells.append("" if v is None else v.get("raw", ""))
        option_rows.append(meta + cells)

    _write_data_sheet(ws, factors, option_rows)
    ws2 = wb.create_sheet("Instructions")
    _write_instructions_sheet(ws2)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
