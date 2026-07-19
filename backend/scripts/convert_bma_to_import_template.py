"""Convert the user's `Business_Model_Assessments.xlsx` (BMA) into the exact
`decider_store_import_template.xlsx` shape used by /admin/decider-store import.

Parsing rules (locked in with user on 2026-07-19):
  • For each Main Factor cell like "Solo, Startup (40%)":
      - Unnamed sub-factors  → 0
      - Named without (%)    → 100
      - Named with (X%)      → X
  • Sub-factor split % per main factor: EQUAL split (auto), can be edited later
    via Admin → Edit Data.
  • Category = "Mandatory" for all 10 main factors (all are decision-critical).
  • Priority = 1..10 as per the numbered order in the source file.
  • factor_type = "Qualitative" for all 10 (multi-select checkboxes → %).

Usage:
  python -m backend.scripts.convert_bma_to_import_template \
      --src /app/scratch/BMA.xlsx --out /app/scratch/Business_Model_Chooser_ready.xlsx
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Allow running as a bare script too.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.decider_import import (  # type: ignore  # noqa: E402
    _write_data_sheet,
    _write_instructions_sheet,
)

# ── main factor / sub-factor names (canonical) ───────────────────────────
MAIN_FACTORS: List[Dict[str, Any]] = [
    {
        "name": "Org Type", "priority": 1,
        "subs": ["Solo", "Startup", "SME", "Corporate"],
        "aliases": {"solo": "Solo", "startup": "Startup", "startups": "Startup",
                    "sme": "SME", "smes": "SME", "corporate": "Corporate",
                    "corporates": "Corporate"},
    },
    {
        "name": "Solution Category", "priority": 2,
        "subs": ["Product", "Service"],
        "aliases": {"product": "Product", "products": "Product",
                    "service": "Service", "services": "Service",
                    "being a platform": "Service", "platform": "Service",
                    "prodcut": "Product"},
    },
    {
        "name": "Nature of Solution", "priority": 3,
        "subs": ["Pain Reliever", "Gain Creator"],
        "aliases": {"pain reliever": "Pain Reliever", "pain relievers": "Pain Reliever",
                    "gain creator": "Gain Creator", "gain creators": "Gain Creator"},
    },
    {
        "name": "Intensity, Urgency & Frequency of Need Perception", "priority": 4,
        "subs": ["Low", "Medium", "High"],
        "aliases": {"low": "Low", "medium": "Medium", "mediuim": "Medium",
                    "high": "High"},
    },
    {
        "name": "Affordability", "priority": 5,
        "subs": ["Low", "Medium", "High"],
        "aliases": {"low": "Low", "medium": "Medium", "high": "High"},
    },
    {
        "name": "Revenue Model", "priority": 6,
        "subs": ["B2B", "B2C"],
        "aliases": {"b2b": "B2B", "b2c": "B2C"},
    },
    {
        "name": "Tech Orientation", "priority": 7,
        "subs": ["Traditional", "High Tech"],
        "aliases": {"traditional": "Traditional", "tradotional": "Traditional",
                    "high tech": "High Tech", "high ticket": "High Tech",
                    "hightech": "High Tech"},
    },
    {
        "name": "Distribution Channels", "priority": 8,
        "subs": ["Offline - Direct", "Offline - Channel",
                 "Online - Direct", "Online - Channel"],
        "aliases": {"offline - direct": "Offline - Direct",
                    "offline direct": "Offline - Direct",
                    "offline-direct": "Offline - Direct",
                    "offline - channel": "Offline - Channel",
                    "offline channel": "Offline - Channel",
                    "offline-channel": "Offline - Channel",
                    "online - direct": "Online - Direct",
                    "online direct": "Online - Direct",
                    "online-direct": "Online - Direct",
                    "online - channel": "Online - Channel",
                    "online channel": "Online - Channel",
                    "online-channel": "Online - Channel"},
    },
    {
        "name": "Value Creation", "priority": 9,
        "subs": ["Single Point - Normal Solution", "Single Point - Deeper Solution",
                 "Multiple Points - Normal Solution", "Multiple Points - Deeper Solution"],
        "aliases": {
            "single point - normal solution": "Single Point - Normal Solution",
            "single point normal solution": "Single Point - Normal Solution",
            "single-point normal": "Single Point - Normal Solution",
            "single point - deeper solution": "Single Point - Deeper Solution",
            "single point deeper solution": "Single Point - Deeper Solution",
            "single point  - deeper solution": "Single Point - Deeper Solution",
            "multiple points - normal solution": "Multiple Points - Normal Solution",
            "multiple point - normal solution": "Multiple Points - Normal Solution",
            "multiple point normal solution": "Multiple Points - Normal Solution",
            "multiple points normal solution": "Multiple Points - Normal Solution",
            "multiple points - deeper solution": "Multiple Points - Deeper Solution",
            "multiple point - deeper solution": "Multiple Points - Deeper Solution",
            "multiple point deeper solution": "Multiple Points - Deeper Solution",
            "multiple points deeper solution": "Multiple Points - Deeper Solution",
            "multiple point deeper solutions": "Multiple Points - Deeper Solution",
            # source typos observed in Business_Model_Assessments.xlsx
            "single ponint - normal solution": "Single Point - Normal Solution",
            "single ponint - deeper solution": "Single Point - Deeper Solution",
            "multiple points - normal soltuion": "Multiple Points - Normal Solution",
            "multiple point - normal soltuion": "Multiple Points - Normal Solution",
            "single pont - deepere solution": "Single Point - Deeper Solution",
            # shortened forms in the source (e.g. "Multiple points - Normal & Deeper Solution")
            "single point - normal": "Single Point - Normal Solution",
            "single point - deeper": "Single Point - Deeper Solution",
            "multiple points - normal": "Multiple Points - Normal Solution",
            "multiple points - deeper": "Multiple Points - Deeper Solution",
            "multiple point - normal": "Multiple Points - Normal Solution",
            "multiple point - deeper": "Multiple Points - Deeper Solution",
        },
    },
    {
        "name": "Differentiation Strategy", "priority": 10,
        "subs": ["Premium Value Driven", "Delivery Cost Driven"],
        "aliases": {"premium value driven": "Premium Value Driven",
                    "premium value driver": "Premium Value Driven",
                    "delivery cost driven": "Delivery Cost Driven",
                    "delivery cost driver": "Delivery Cost Driven"},
    },
]

# ── source layout ────────────────────────────────────────────────────────
SRC_HEADER_ROW = 10        # option meta header
SRC_FIRST_DATA_ROW = 12    # legend is on Row 11, patterns start at Row 12
SRC_MAIN_FACTOR_COLS = list(range(8, 18))  # cols H..Q → 10 main factors


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _build_alias_regex(factor: Dict[str, Any]) -> List[Tuple[str, "re.Pattern[str]"]]:
    """For each sub-factor, build a regex that matches any of its aliases (or the
    canonical name), followed optionally by "(X%)".  Longer aliases first so
    "single point - deeper solution" wins over "single point"."""
    per_sub: Dict[str, List[str]] = {sub: [sub] for sub in factor["subs"]}
    for alias, canonical in factor["aliases"].items():
        if canonical in per_sub and alias not in per_sub[canonical]:
            per_sub[canonical].append(alias)
    out: List[Tuple[str, "re.Pattern[str]"]] = []
    for sub, aliases in per_sub.items():
        aliases = sorted(set(aliases), key=len, reverse=True)
        alt = "|".join(re.escape(a) for a in aliases)
        # allow inner extra whitespace (source has "Single point  - Deeper")
        alt_ws = alt.replace(r"\ ", r"\s+")
        pat = re.compile(
            rf"(?<![A-Za-z])(?:{alt_ws})(?![A-Za-z])"
            rf"(?:\s*\(\s*(\d+(?:\.\d+)?)\s*%?[^)]*\))?",
            re.IGNORECASE,
        )
        out.append((sub, pat))
    # sort so the longest canonical name is scanned FIRST — prevents 'Low' from
    # accidentally masking 'Below' etc.
    out.sort(key=lambda kv: -len(kv[0]))
    return out


def parse_cell(txt: str, factor: Dict[str, Any]) -> Dict[str, float]:
    """Return {sub_name: value} for one main-factor cell.

    Rules (locked with user 2026-07-19):
      • unmentioned sub-factor      → left OUT of the dict (caller fills 0)
      • mentioned without "(X%)"    → 100
      • mentioned with "(X%)"       → X   (last mention wins)
    """
    out: Dict[str, float] = {}
    if not txt:
        return out
    patterns = _build_alias_regex(factor)
    # Mark spans that have already been assigned so a longer alias eats its own
    # inner substring (e.g. "Single Point - Deeper Solution" consumes "Single
    # Point"). We do this by nulling matched spans in a mutable copy.
    scan = list(txt)
    for sub, pat in patterns:
        last_pct: float = None  # type: ignore[assignment]
        for m in pat.finditer("".join(scan)):
            grp = m.group(1)
            last_pct = float(grp) if grp else 100.0
            # blank out the matched span so shorter aliases inside it don't
            # re-match (e.g. "Single Point" inside "Single Point - Deeper …").
            for i in range(m.start(), m.end()):
                scan[i] = " "
        if last_pct is not None:
            out[sub] = last_pct
    return out


def _sanitise_multiline_name(name: Any) -> str:
    """`'CROWD-\\nFUNDING'` -> `'CROWD-FUNDING'`."""
    return re.sub(r"\s+", " ", str(name or "").replace("\n", "")).strip()


def read_source(src_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    import openpyxl
    wb = openpyxl.load_workbook(src_path, data_only=True)
    ws = wb.worksheets[0]
    rows = [[c.value for c in row] for row in ws.iter_rows()]

    # Build option list.
    options: List[Dict[str, Any]] = []
    stats = {"cells_parsed": 0, "cells_unmapped": 0, "unmapped_examples": []}
    for r_idx in range(SRC_FIRST_DATA_ROW - 1, len(rows)):
        row = rows[r_idx]
        if not row or row[0] is None:
            continue
        # meta cols: A=No, B=Product Model, C=Pattern Name, D=Affected, E=Examples,
        #            F=Description, G=Remarks
        no = row[0]
        if not isinstance(no, (int, float)):
            continue
        name = _sanitise_multiline_name(row[2])
        if not name:
            continue
        values: Dict[str, Dict[str, float]] = {}
        for mf, col_idx in zip(MAIN_FACTORS, SRC_MAIN_FACTOR_COLS):
            cell = row[col_idx - 1] if col_idx - 1 < len(row) else None
            txt = str(cell) if cell is not None else ""
            parsed = parse_cell(txt, mf)
            values[mf["name"]] = parsed
            stats["cells_parsed"] += 1
            if txt and not parsed:
                stats["cells_unmapped"] += 1
                if len(stats["unmapped_examples"]) < 5:
                    stats["unmapped_examples"].append(f"{name} / {mf['name']}: {txt!r}")
        options.append({
            "no": int(no),
            "product_model": _sanitise_multiline_name(row[1]) if len(row) > 1 else "",
            "name": name,
            "affected_components": _sanitise_multiline_name(row[3]) if len(row) > 3 else "",
            "exemplary_companies": (str(row[4]).replace("\n", ", ").strip() if len(row) > 4 and row[4] else ""),
            "description": (str(row[5]).replace("\n", " ").strip() if len(row) > 5 and row[5] else ""),
            "remarks": (str(row[6]).replace("\n", " ").strip() if len(row) > 6 and row[6] else ""),
            "values": values,
        })

    # Build factor blocks in template shape (v2: Checkbox multi-select main UI,
    # each sub-factor column is a selectable VALUE — no 100% split rule; the
    # Step-2 refiner defaults to Suitability >= 60%, user-overridable).
    factors: List[Dict[str, Any]] = []
    for mf in MAIN_FACTORS:
        sub_blocks = [
            {"name": sub, "data_type": "%", "ui_object": "Input Box",
             "split_pct": "", "role": "value",
             "default_operator": ">=", "default_expected": 60}
            for sub in mf["subs"]
        ]
        factors.append({
            "name": mf["name"],
            "category": "Mandatory",
            "priority": mf["priority"],
            "factor_type": "Qualitative",
            "ui_object": "checkbox",
            "sub_factors": sub_blocks,
        })

    return factors, options, stats


def build_option_rows(factors: List[Dict[str, Any]],
                      options: List[Dict[str, Any]]) -> List[List[Any]]:
    """Meta cols + one cell per sub-factor (in declaration order)."""
    rows: List[List[Any]] = []
    for opt in options:
        meta = [
            opt["no"], opt["product_model"], opt["name"],
            opt["affected_components"], opt["exemplary_companies"],
            opt["description"], opt["remarks"],
        ]
        cells: List[Any] = []
        for f in factors:
            parsed_for_factor: Dict[str, float] = opt["values"].get(f["name"], {})
            for sub in f["sub_factors"]:
                v = parsed_for_factor.get(sub["name"], 0)
                cells.append(v)
        rows.append(meta + cells)
    return rows


def write_workbook(factors: List[Dict[str, Any]],
                   option_rows: List[List[Any]],
                   out_path: Path) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Data"
    _write_data_sheet(ws, factors, option_rows)
    ws2 = wb.create_sheet("Instructions")
    _write_instructions_sheet(ws2)
    wb.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    factors, options, stats = read_source(Path(args.src))
    option_rows = build_option_rows(factors, options)
    write_workbook(factors, option_rows, Path(args.out))

    print(f"✅ Wrote {args.out}")
    print(f"   • Main factors : {len(factors)}")
    print(f"   • Sub-factors  : {sum(len(f['sub_factors']) for f in factors)}")
    print(f"   • Options      : {len(options)}")
    print(f"   • Cells parsed : {stats['cells_parsed']} (unmapped={stats['cells_unmapped']})")
    if stats["unmapped_examples"]:
        print("   • Sample unmapped cells:")
        for e in stats["unmapped_examples"]:
            print(f"       - {e}")


if __name__ == "__main__":
    main()
