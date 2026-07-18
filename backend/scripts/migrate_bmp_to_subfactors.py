"""One-off: convert the OLD-format Business_Model_Assessments.xlsx (collapsed
value strings) into the NEW Main-Factor/Sub-Factor format.

Reads scripts/data/bmp_old_parsed.json (dumped from the old parser) and writes a
new-format scripts/data/Business_Model_Assessments.xlsx (old one backed up).
"""
import json
import os
import re
import shutil
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, os.path.dirname(HERE))
from core.decider_import import build_data_xlsx_from_model, parse_import  # noqa: E402

DATA = os.path.join(HERE, "data")
OLD_JSON = os.path.join(DATA, "bmp_old_parsed.json")
XLSX = os.path.join(DATA, "Business_Model_Assessments.xlsx")

# canonical clean sub-values (order matters) + main-factor metadata
CANON = [
    ("Org Type", ["Solo", "Startup", "SME", "Corporate"]),
    ("Solution Category", ["Product", "Service"]),
    ("Nature of Solution [From Customer Perspective]", ["Pain Reliever", "Gain Creator"]),
    ("Intensity, Urgency & Frequency of Need Perception", ["Low", "Medium", "High"]),
    ("Affordability", ["Low", "Medium", "High"]),
    ("Revenue Model", ["B2B", "B2C"]),
    ("Tech Orientation", ["Traditional", "High Tech"]),
    ("Distribution Channels", ["Offline - Direct", "Offline - Channel",
                               "Online - Direct", "Online - Channel"]),
    ("Value Creation", ["Single Point - Normal", "Single Point - Deeper",
                        "Multiple Points - Normal", "Multiple Points - Deeper"]),
    ("Differentiation Strategy [From Org Perspective]",
     ["Premium Value Driven", "Delivery Cost Driven"]),
]


def _n(s):
    s = re.sub(r"\bsolutions?\b", "", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    old = json.load(open(OLD_JSON))
    old_factors = old["factors"]
    old_options = old["options"]

    # map old factor name -> old factor id
    oldfid_by_name = {f["name"]: f["id"] for f in old_factors}

    factors = []
    # per (factor_index, sub_index) -> sub id, plus normalized sub labels
    sub_ids = {}      # (fi, si) -> sid
    for fi, (fname, subvals) in enumerate(CANON):
        subs = []
        eq = round(100.0 / len(subvals), 2)
        for si, val in enumerate(subvals):
            sid = str(uuid.uuid4())
            sub_ids[(fi, si)] = sid
            subs.append({"id": sid, "name": f"{val} %", "order": si,
                         "data_type": "%", "ui_object": "Input Box", "split_pct": eq})
        factors.append({
            "id": str(uuid.uuid4()), "name": fname, "order": fi,
            "category": "Mandatory", "priority": fi + 1, "factor_type": "Qualitative",
            "sub_factors": subs, "possible_values": [s["name"] for s in subs],
        })

    # normalized canonical sub-labels for matching
    canon_norm = {fi: [_n(v) for v in subvals] for fi, (_, subvals) in enumerate(CANON)}

    options = []
    for opt in old_options:
        values = {}
        for fi, (fname, subvals) in enumerate(CANON):
            oldfid = oldfid_by_name.get(fname)
            entries = (opt.get("values") or {}).get(oldfid) or []
            # concat text for corrupt-cell substring matching
            concat = _n(" ".join(e.get("value", "") for e in entries))
            for si, cn in enumerate(canon_norm[fi]):
                pct = None
                for e in entries:
                    if _n(e.get("value", "")) == cn:
                        pct = e.get("pct"); break
                if pct is None and cn and cn in concat:
                    # corrupt/garbled cell -> assign the max pct present
                    pcts = [e.get("pct") for e in entries if e.get("pct") is not None]
                    pct = max(pcts) if pcts else None
                if pct is not None:
                    sid = sub_ids[(fi, si)]
                    values[sid] = {"raw": str(int(pct)) if float(pct).is_integer() else str(pct),
                                   "num": float(pct)}
        options.append({
            "id": opt.get("id") or str(uuid.uuid4()),
            "name": opt.get("name", ""), "product_model": opt.get("product_model", ""),
            "affected_components": opt.get("affected_components", ""),
            "exemplary_companies": opt.get("exemplary_companies", ""),
            "description": opt.get("description", ""), "remarks": opt.get("remarks", ""),
            "values": values,
        })

    xlsx = build_data_xlsx_from_model(factors, options)
    if os.path.exists(XLSX):
        shutil.copy(XLSX, XLSX + ".old_backup")
    open(XLSX, "wb").write(xlsx)

    # verify by re-parsing
    p = parse_import(data=xlsx)
    nsub = sum(len(f["sub_factors"]) for f in p["factors"])
    filled = sum(len(o["values"]) for o in p["options"])
    print(f"Wrote {XLSX}: {len(p['factors'])} factors / {nsub} sub-factors / "
          f"{len(p['options'])} options / {filled} filled cells / warnings={p['warnings']}")


if __name__ == "__main__":
    main()
