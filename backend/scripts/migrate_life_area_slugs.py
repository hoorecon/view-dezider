"""
Migrate legacy life-area slugs to canonical Admin Central Catalog IDs.

WHY
---
Before v3.20, ~20 user-facing screens hardcoded their own life-area arrays
using short slugs (`career`, `finance`, `holistic_health`, …). The master
Admin Central Catalog uses canonical IDs (`la_career`, `la_finance`,
`la_health`, …). DB rows written by those legacy screens therefore stored
the slug form, breaking cross-module joins.

This idempotent migration sweeps every collection that stores a
`life_area_id` (or similarly-named) field and rewrites legacy slugs to the
canonical IDs in-place. The reverse is NOT done — frontend reads now flow
through `useLifeAreas` / `/api/catalog/life-areas` which return both forms.

Run:
    cd /app/backend && python -m scripts.migrate_life_area_slugs
    cd /app/backend && python -m scripts.migrate_life_area_slugs --dry-run

Safe to re-run; rows already on the canonical form are left untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

# Make this script runnable from either:
#   cd /opt/dezider/backend && python3 -m scripts.migrate_life_area_slugs
#   cd /app/backend && python -m scripts.migrate_life_area_slugs
#   /any/path/python3 /full/path/to/migrate_life_area_slugs.py
# by computing the backend dir from this file's own location, not a
# hardcoded container path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_HERE)  # parent of scripts/
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from core.database import db  # noqa: E402

logger = logging.getLogger("migrate_life_area_slugs")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── canonical mapping (matches /app/backend/data/hos_seed_data.py) ─────
SLUG_TO_CANONICAL: Dict[str, str] = {
    "holistic_health":        "la_health",
    "knowledge_skills":       "la_knowledge",
    "relationships":          "la_relationships",
    "finance":                "la_finance",
    "career":                 "la_career",
    "assets":                 "la_assets",
    "hobbies_entertainment":  "la_hobbies",
    "social_image":           "la_social_image",
    "social_contributions":   "la_contribution",
    "spirituality_religion":  "la_spirituality",
}

# Already-canonical values: skip (no-op).
CANONICAL_IDS = set(SLUG_TO_CANONICAL.values())

# Collections + the field name(s) we touch in each. Each entry may list more
# than one field (e.g. an array of nested doc keys or a sub-doc path).
COLLECTIONS: List[Tuple[str, List[str]]] = [
    # Solution Finder
    ("simple_solutions", ["area_of_life", "life_area_id"]),
    ("solution_box_index", ["life_area_id"]),

    # Pros & Cons (decisions)
    ("decisions", ["life_area_id"]),
    ("pros_cons_decisions", ["life_area_id"]),

    # SWOT
    ("swot_decisions", ["life_area_id"]),

    # Goals & Manifestation
    ("gem_goals", ["life_area_id"]),
    ("gem_flight_plans", ["life_area_id"]),
    ("manifestations", ["life_area_id"]),

    # Capabilities & Resources Index (TEPFI)
    ("capabilities_index", ["life_area_id"]),
    ("tepfi_overrides", ["life_area_id"]),

    # CTT / Action Tracker
    ("ctt_projects", ["life_area_id"]),
    ("ctt_tasks", ["life_area_id"]),
    ("action_items", ["life_area_id"]),

    # Lifestyle suite
    ("lifestyle_plans", ["life_area_id"]),
    ("lifestyle_routines", ["life_area_id"]),
    ("lifestyle_logs", ["life_area_id"]),
    ("lifestyle_designer_blocks", ["life_area_id"]),

    # AIM Manager / Emotional Gatekeeper
    ("aim_entries", ["life_area_id"]),
    ("eg_sessions", ["life_area_id"]),

    # Solution Matrix (Solutions Store consumers)
    ("solution_matrices", ["life_area_id"]),
    ("solutions_store", ["life_area_id"]),

    # Review Net
    ("review_net_reviews", ["life_area_id"]),

    # Misc — Social Learning saved templates
    ("social_learning_templates", ["life_area_id"]),
]


async def _migrate_one(coll_name: str, fields: List[str], dry_run: bool) -> Dict[str, int]:
    """Walk one collection and rewrite each legacy slug found in `fields`."""
    coll = db[coll_name]
    total_scanned = 0
    total_updated = 0
    per_value: Dict[str, int] = {}

    try:
        exists = await db.list_collection_names(filter={"name": coll_name})
    except Exception:
        exists = []
    if not exists:
        return {"scanned": 0, "updated": 0, "missing_collection": 1}

    for legacy_slug, canonical_id in SLUG_TO_CANONICAL.items():
        for field in fields:
            q = {field: legacy_slug}
            count = await coll.count_documents(q)
            total_scanned += count
            if count == 0:
                continue
            per_value[f"{field}:{legacy_slug}→{canonical_id}"] = count
            if dry_run:
                continue
            res = await coll.update_many(q, {"$set": {field: canonical_id}})
            total_updated += res.modified_count or 0

    return {"scanned": total_scanned, "updated": total_updated, "details": per_value}


async def main(dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "APPLY"
    logger.info("Starting life-area slug migration [%s]", mode)

    grand_scanned = 0
    grand_updated = 0
    grand_missing = 0
    per_coll_report: Dict[str, Dict[str, Any]] = {}

    for coll_name, fields in COLLECTIONS:
        try:
            result = await _migrate_one(coll_name, fields, dry_run)
        except Exception as e:
            logger.error("  %s — ERROR: %s", coll_name, e)
            per_coll_report[coll_name] = {"error": str(e)}
            continue
        if result.get("missing_collection"):
            grand_missing += 1
            continue
        scanned = result.get("scanned", 0)
        updated = result.get("updated", 0)
        if scanned == 0:
            continue
        grand_scanned += scanned
        grand_updated += updated
        per_coll_report[coll_name] = result
        logger.info("  %-32s scanned=%-6d updated=%-6d", coll_name, scanned, updated)
        for k, v in result.get("details", {}).items():
            logger.info("      %s = %d", k, v)

    logger.info("─" * 60)
    logger.info("TOTAL  collections_with_data=%d  missing=%d  rows_scanned=%d  rows_updated=%d",
                len(per_coll_report), grand_missing, grand_scanned, grand_updated)
    if dry_run:
        logger.info("Dry-run only — no writes performed. Re-run without --dry-run to apply.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Report what would change without writing.")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run))
