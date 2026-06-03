"""
Back-fill / hygiene migration for Solution Box legacy items.
============================================================

Goal: make legacy records render consistent Life-area badges and be filterable,
WITHOUT inventing data we cannot derive deterministically.

What it does (idempotent):
  1. Canonicalises life-area values to the 10 canonical LifeArea ids used by the
     frontend (`src/constants/lifeAreas.ts`). e.g. 'Career' -> 'career',
     'Health' / 'Health & Fitness' -> 'holistic_health'.
       - collections/fields:
            decisions.life_area, decisions.folder
            pros_cons.life_area
            test123_sessions.life_area
            solution_finders.area_of_life
  2. Cross-fills decisions.folder <-> decisions.life_area when exactly one holds
     a valid canonical life area (the aggregator reads `folder or life_area`).
  3. Leaves unknown/junk/special values (e.g. 'lifestyle_analyzer', 'TEST_career')
     and records with no derivable life area UNTOUCHED — we never guess.

decision_type is intentionally NOT invented: legacy rows with no decision_type
keep it null (the UI handles absence gracefully).

Run:  python -m scripts.backfill_solution_box_meta            # apply
      python -m scripts.backfill_solution_box_meta --dry-run  # report only
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Canonical life areas (mirror of src/constants/lifeAreas.ts)
LIFE_AREAS = [
    ("holistic_health", "Holistic Health", "Health"),
    ("knowledge_skills", "Knowledge & Skills", "Knowledge"),
    ("relationships", "Relationships", "Relationships"),
    ("finance", "Finance", "Finance"),
    ("assets", "Assets", "Assets"),
    ("career", "Career", "Career"),
    ("hobbies_entertainment", "Hobbies & Entertainment", "Hobbies"),
    ("social_image", "Social Image & Influence", "Social Image"),
    ("social_contributions", "Social Contributions", "Contributions"),
    ("spirituality_religion", "Spirituality & Religion", "Spirituality"),
]

_IDS = {a[0] for a in LIFE_AREAS}
_NAME_MAP = {}
for _id, _name, _short in LIFE_AREAS:
    _NAME_MAP[_name.lower()] = _id
    _NAME_MAP[_short.lower()] = _id
# A few high-confidence aliases seen in real legacy data.
_NAME_MAP.update({
    "health": "holistic_health",
    "health & fitness": "holistic_health",
    "health and fitness": "holistic_health",
    "fitness": "holistic_health",
    "knowledge": "knowledge_skills",
    "knowledge and skills": "knowledge_skills",
})


def canonical(value):
    """Return a canonical life-area id, or None if not derivable (leave as-is)."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v in _IDS:
        return v  # already canonical
    vl = v.lower()
    if vl in _IDS:
        return vl  # pure case fix (e.g. 'Career')
    if vl in _NAME_MAP:
        return _NAME_MAP[vl]
    return None  # unknown / special / junk -> don't touch


def _now():
    return datetime.now(timezone.utc).isoformat()


def run(dry_run: bool = False):
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    report = {}

    def canon_field(coll, field):
        changed = 0
        for doc in db[coll].find({field: {"$nin": [None, ""]}}, {"_id": 1, field: 1}):
            cur = doc.get(field)
            new = canonical(cur)
            if new and new != cur:
                changed += 1
                if not dry_run:
                    db[coll].update_one(
                        {"_id": doc["_id"]},
                        {"$set": {field: new, "updated_at": _now()}},
                    )
        report[f"{coll}.{field}:canonicalised"] = changed

    # 1. Canonicalise life-area fields
    canon_field("decisions", "life_area")
    canon_field("decisions", "folder")
    canon_field("pros_cons", "life_area")
    canon_field("test123_sessions", "life_area")
    canon_field("solution_finders", "area_of_life")

    # 2. Cross-fill decisions.folder <-> life_area (canonical ids only)
    cross_la = cross_folder = 0
    for doc in db.decisions.find({}, {"_id": 1, "folder": 1, "life_area": 1}):
        folder = (doc.get("folder") or "").strip()
        la = (doc.get("life_area") or "").strip()
        c_folder = canonical(folder)
        c_la = canonical(la)
        updates = {}
        # life_area missing but folder is a valid canonical area -> fill life_area
        if not la and c_folder:
            updates["life_area"] = c_folder
            cross_la += 1
        # folder missing but life_area is a valid canonical area -> fill folder
        elif not folder and c_la:
            updates["folder"] = c_la
            cross_folder += 1
        if updates and not dry_run:
            updates["updated_at"] = _now()
            db.decisions.update_one({"_id": doc["_id"]}, {"$set": updates})
    report["decisions.life_area:cross_filled_from_folder"] = cross_la
    report["decisions.folder:cross_filled_from_life_area"] = cross_folder

    # 3. Diagnostics — what remains genuinely uninferrable (left untouched)
    no_la = db.decisions.count_documents({
        "$and": [
            {"$or": [{"folder": {"$exists": False}}, {"folder": None}, {"folder": ""}]},
            {"$or": [{"life_area": {"$exists": False}}, {"life_area": None}, {"life_area": ""}]},
        ]
    })
    no_type = db.decisions.count_documents(
        {"$or": [{"decision_type": {"$exists": False}}, {"decision_type": None}, {"decision_type": ""}]}
    )
    report["decisions:still_no_life_area (left as-is)"] = no_la
    report["decisions:still_no_decision_type (left as-is)"] = no_type

    print(("DRY-RUN — " if dry_run else "APPLIED — ") + "Solution Box meta back-fill")
    for k, v in report.items():
        print(f"  {k}: {v}")
    return report


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
