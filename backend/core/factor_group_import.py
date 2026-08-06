"""Factor-Group flat-sheet importer (Decider Apps only).

Parses a **row-per-factor** spreadsheet like the IndusInd Current Account
comparison — where each factor lives on its own row with an optional
1–3-level Factor Group column and the option scores are in the columns
to the right.

Expected layout (case-insensitive header row):

    Factor Group | (Sub Group) | (Sub-Sub Group) | Factor | Sub Factor | Option1 | Option2 | ...
    "AQB & Cheque Book" |         |         | Average Quarterly Balance |           | ₹25,000 | ...
    "Cash Transactions" | "Cash Deposit" |    | Free Limit / month |          | ₹5L | ...

The first columns can be labelled any of:
  - "Factor Group", "Group", "Group 1"
  - "Sub Group", "Group 2"
  - "Sub-Sub Group", "Group 3"
  - "Factor", "Main Factor"
  - "Sub Factor" (optional)
Then everything to the right is treated as an **option column**, whose
header is the option name.

Returns a dict compatible with `POST /decider-store` (kind='app'):

    {
      "factors": [{ id, name, group_path?, sub_factors?: [{id, name, ...}] }],
      "options": [{ id, name, values: {sub_factor_id: {num?, raw?, txt?}} }],
      "warnings": [...]
    }
"""
from __future__ import annotations

import base64
import io
import re
import uuid
from typing import Any, Dict, List, Optional


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


# Header-label buckets. Order in the row doesn't matter — we detect by name.
_GROUP_ALIASES = {
    0: {"factor group", "group", "group 1", "l1 group"},
    1: {"sub group", "group 2", "l2 group"},
    2: {"sub-sub group", "sub sub group", "group 3", "l3 group"},
}
_FACTOR_ALIASES = {"factor", "main factor", "factor name"}
_SUB_FACTOR_ALIASES = {"sub factor", "sub-factor", "sub factor name"}


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _extract_num(text: str) -> Optional[float]:
    """Pull the first plausible number out of a cell like '₹5L' or '10%'."""
    if not text:
        return None
    t = text.replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    try:
        n = float(m.group(0))
    except ValueError:
        return None
    lo = text.lower()
    if "cr" in lo:
        n *= 1_00_00_000       # Indian crore
    elif "lakh" in lo or "l" in lo and "%" not in lo and "flat" not in lo:
        # heuristic: 'L' after a number often means lakh in Indian data
        if re.search(r"\d+\s*l\b", lo):
            n *= 1_00_000
    elif "k" in lo and re.search(r"\d+\s*k\b", lo):
        n *= 1_000
    return n


def parse_factor_group_sheet(data: bytes) -> Dict[str, Any]:
    """Parse XLSX -> {factors, options, warnings}. Raises ValueError on bad layout."""
    try:
        import openpyxl
    except Exception as e:  # pragma: no cover
        raise ValueError(f"openpyxl not available: {e}")

    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    ws = wb.active
    rows: List[List[Any]] = [[c.value for c in r] for r in ws.iter_rows()]
    # Drop fully-empty rows.
    rows = [r for r in rows if any(_cell(x) for x in r)]
    if len(rows) < 2:
        raise ValueError("Sheet must have a header row + at least one factor row.")

    header = [_cell(x) for x in rows[0]]
    header_norm = [_norm(x) for x in header]

    # Map columns.
    group_cols: Dict[int, int] = {}   # level (0/1/2) -> col index
    for lvl, aliases in _GROUP_ALIASES.items():
        for ci, h in enumerate(header_norm):
            if h in aliases:
                group_cols[lvl] = ci
                break
    factor_col: Optional[int] = None
    for ci, h in enumerate(header_norm):
        if h in _FACTOR_ALIASES:
            factor_col = ci
            break
    sub_factor_col: Optional[int] = None
    for ci, h in enumerate(header_norm):
        if h in _SUB_FACTOR_ALIASES:
            sub_factor_col = ci
            break
    if factor_col is None:
        raise ValueError(
            "Couldn't find the 'Factor' column. Add a header cell named "
            "'Factor' (case-insensitive)."
        )

    # Option columns = everything strictly to the right of factor/sub-factor
    # (and any group columns), with a non-empty header.
    used_cols = set(group_cols.values()) | {factor_col}
    if sub_factor_col is not None:
        used_cols.add(sub_factor_col)
    right_start = max(used_cols) + 1
    option_cols: List[int] = [
        ci for ci in range(right_start, len(header)) if _cell(header[ci])
    ]
    if not option_cols:
        raise ValueError(
            "No option columns found to the right of the Factor / Sub-Factor block. "
            "Add one column per option (e.g., 'T25', 'T50', 'T100')."
        )

    warnings: List[str] = []
    factors: List[Dict[str, Any]] = []
    factor_by_name: Dict[str, Dict[str, Any]] = {}
    # Forward-fill group columns (top-down) so blank cells inherit.
    last_group: Dict[int, str] = {}
    options: Dict[int, Dict[str, Any]] = {
        ci: {"id": str(uuid.uuid4()), "name": _cell(header[ci]), "values": {}}
        for ci in option_cols
    }

    for r in rows[1:]:
        # Update forward-filled group values.
        for lvl, ci in group_cols.items():
            v = _cell(r[ci]) if ci < len(r) else ""
            if v:
                last_group[lvl] = v
        gp = [last_group[l] for l in sorted(group_cols.keys()) if last_group.get(l)]

        f_name = _cell(r[factor_col]) if factor_col < len(r) else ""
        sf_name = ""
        if sub_factor_col is not None and sub_factor_col < len(r):
            sf_name = _cell(r[sub_factor_col])
        if not f_name and not sf_name:
            continue

        # Same factor + new sub-factor row: append sub-factor.
        key = f_name or "(unnamed factor)"
        if key in factor_by_name:
            factor = factor_by_name[key]
        else:
            factor = {
                "id": str(uuid.uuid4()),
                "name": key,
                "order": len(factors),
                "category": "primary",
                "priority": 5,
                "factor_type": "quantitative",
                "sub_factors": [],
            }
            if gp:
                factor["group_path"] = list(gp)
            factors.append(factor)
            factor_by_name[key] = factor

        target_id: str
        if sf_name:
            sub = {
                "id": str(uuid.uuid4()),
                "name": sf_name,
                "data_type": "Text",
                "split_pct": 0,
            }
            factor["sub_factors"].append(sub)
            target_id = sub["id"]
        else:
            # Singleton factor: use factor id directly (matches subsOf()).
            target_id = factor["id"]

        # Pull each option's cell into the option.values keyed by target_id.
        for ci in option_cols:
            raw = _cell(r[ci]) if ci < len(r) else ""
            if not raw:
                continue
            n = _extract_num(raw)
            entry: Dict[str, Any] = {"raw": raw, "txt": raw}
            if n is not None:
                entry["num"] = n
            options[ci]["values"][target_id] = entry

    # Even-split sub-factors that had 0 split_pct.
    for f in factors:
        subs = f.get("sub_factors") or []
        if subs:
            share = round(100.0 / len(subs), 2)
            for i, sf in enumerate(subs):
                # last one absorbs rounding remainder
                sf["split_pct"] = share if i < len(subs) - 1 else round(100.0 - share * (len(subs) - 1), 2)
        else:
            f.pop("sub_factors", None)

    return {
        "factors": factors,
        "options": [options[ci] for ci in option_cols],
        "warnings": warnings,
    }


def parse_from_b64(b64: str) -> Dict[str, Any]:
    if not b64:
        raise ValueError("Empty file payload.")
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    return parse_factor_group_sheet(base64.b64decode(b64))
