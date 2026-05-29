"""
Template & Solution-Store taxonomy upgrade — v2.

Adds three multi-value classification arrays so a single template can serve
multiple Decision/Org contexts, and so Solution Store products can fan out
across scenarios irrespective of their primary life-area.

Schema additions
----------------
hos_decision_templates:
    applies_to_modules: list[str]   # ['dezider'] | ['dezider','swot']
    org_types:          list[str]   # multi-pick from 6 OrgTypes (empty = ALL)
    decision_types:     list[str]   # multi-pick from problem/need/aspiration (empty = ALL)
    factors[].swot_flag: 'S'|'W'|'O'|'T'|None  (SWOT templates only)

solutions_store:
    org_types:      list[str]
    decision_types: list[str]
    scenario_ids:   list[str]       # cross-life-area linkage

Idempotency
-----------
- Each doc gets the new fields only if they are missing. Re-runs are no-ops.
- Existing `acting_as_contexts` (legacy 3-value enum) is preserved AND mirrored
  into `org_types` so the new filter logic Just Works™ for legacy data:
      INDIVIDUAL    -> INDIVIDUAL
      ORGANIZATION  -> BUSINESS_ORG, ACADEMIC_ORG, NONPROFIT_ORG, ASSOCIATION
      GOVERNMENT    -> GOVERNMENT
- Existing `ask_type_id` is read once to derive `decision_types`:
      at_problem -> ['problem']
      at_need    -> ['need']
      at_aspiration -> ['aspiration']

Migration log key:  {"_id": "template_taxonomy_v2"}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.database import db

logger = logging.getLogger(__name__)


_LEGACY_ACTING_AS_TO_ORG_TYPES = {
    "INDIVIDUAL":   ["INDIVIDUAL"],
    "ORGANIZATION": ["BUSINESS_ORG", "ACADEMIC_ORG", "NONPROFIT_ORG", "ASSOCIATION"],
    "GOVERNMENT":   ["GOVERNMENT"],
}

_ASK_TYPE_ID_TO_DECISION_TYPES = {
    "at_problem":     ["problem"],
    "at_need":        ["need"],
    "at_aspiration":  ["aspiration"],
}


def _derive_org_types(acting_as_contexts: list) -> list:
    """Map legacy 3-value contexts → expanded 6-value org_types (deduped)."""
    out: list = []
    for v in (acting_as_contexts or []):
        for mapped in _LEGACY_ACTING_AS_TO_ORG_TYPES.get(str(v).upper(), []):
            if mapped not in out:
                out.append(mapped)
    return out


def _derive_decision_types(ask_type_id: str) -> list:
    return _ASK_TYPE_ID_TO_DECISION_TYPES.get(str(ask_type_id or "").lower(), [])


async def _migrate_templates() -> dict:
    scanned = 0
    fixed = 0
    skipped = 0

    cursor = db.hos_decision_templates.find(
        {},
        {"_id": 0, "id": 1, "acting_as_contexts": 1, "ask_type_id": 1,
         "applies_to_modules": 1, "org_types": 1, "decision_types": 1,
         "factors": 1},
    )

    async for doc in cursor:
        scanned += 1
        patch = {}

        if "applies_to_modules" not in doc:
            patch["applies_to_modules"] = ["dezider"]

        if "org_types" not in doc:
            patch["org_types"] = _derive_org_types(doc.get("acting_as_contexts") or [])

        if "decision_types" not in doc:
            patch["decision_types"] = _derive_decision_types(doc.get("ask_type_id") or "")

        # factors[].swot_flag — only backfill if factors exist and any is missing the key.
        factors = doc.get("factors") or []
        if factors and any("swot_flag" not in f for f in factors):
            new_factors = []
            for f in factors:
                nf = dict(f)
                if "swot_flag" not in nf:
                    nf["swot_flag"] = None
                new_factors.append(nf)
            patch["factors"] = new_factors

        if patch:
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.hos_decision_templates.update_one({"id": doc["id"]}, {"$set": patch})
            fixed += 1
        else:
            skipped += 1

    return {"scanned": scanned, "fixed": fixed, "skipped": skipped}


async def _migrate_solutions_store() -> dict:
    scanned = 0
    fixed = 0
    skipped = 0

    cursor = db.solutions_store.find(
        {},
        {"_id": 0, "solution_id": 1,
         "org_types": 1, "decision_types": 1, "scenario_ids": 1},
    )

    async for doc in cursor:
        scanned += 1
        patch = {}
        if "org_types" not in doc:
            patch["org_types"] = []
        if "decision_types" not in doc:
            patch["decision_types"] = []
        if "scenario_ids" not in doc:
            patch["scenario_ids"] = []

        if patch:
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.solutions_store.update_one(
                {"solution_id": doc["solution_id"]}, {"$set": patch}
            )
            fixed += 1
        else:
            skipped += 1

    return {"scanned": scanned, "fixed": fixed, "skipped": skipped}


async def migrate_template_taxonomy_v2() -> dict:
    """
    Returns: dict with per-collection {scanned, fixed, skipped} sub-dicts.
    """
    templates_stats = await _migrate_templates()
    solutions_stats = await _migrate_solutions_store()

    await db.migrations.update_one(
        {"_id": "template_taxonomy_v2"},
        {"$set": {
            "last_run_at": datetime.now(timezone.utc),
            "templates": templates_stats,
            "solutions": solutions_stats,
        }},
        upsert=True,
    )

    t = templates_stats; s = solutions_stats
    if t["fixed"] or s["fixed"]:
        logger.info(
            f"template_taxonomy_v2: templates(scanned={t['scanned']} fixed={t['fixed']} "
            f"skipped={t['skipped']}) solutions(scanned={s['scanned']} fixed={s['fixed']} "
            f"skipped={s['skipped']})"
        )
    else:
        logger.debug(
            f"template_taxonomy_v2: nothing to migrate "
            f"(templates_scanned={t['scanned']} solutions_scanned={s['scanned']})"
        )

    return {"templates": templates_stats, "solutions": solutions_stats}
