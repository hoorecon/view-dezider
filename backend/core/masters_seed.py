"""
Masters seeding — loads reference data (religions, castes, languages,
occupations, skills, drives, traits) from data/masters_seed.json into the
`masters` collection. Idempotent: only (re)seeds the immutable starter rows
when the bundled seed version changes. Admin-created/edited rows are never
touched, and admin edits/deletes to seed rows are preserved across reseeds.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from core.database import db

logger = logging.getLogger("masters_seed")

SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "masters_seed.json")

# Supported master types
MASTER_TYPES = [
    "religion", "caste", "language", "occupation", "skill", "drive", "trait",
    # Platform-Experts (Collaboration Epic B2)
    "expert_type", "experience_range", "fees_per_min", "available_timing",
]

# JSON key -> master type
_KEY_TO_TYPE = {
    "religions": "religion",
    "castes": "caste",
    "languages": "language",
    "occupations": "occupation",
    "skills": "skill",
    "drives": "drive",
    "traits": "trait",
    "expert_types": "expert_type",
    "experience_ranges": "experience_range",
    "fees_per_min": "fees_per_min",
    "available_timings": "available_timing",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


async def ensure_masters_seeded_on_boot():
    """Seed masters once per seed-version. Safe to call on every boot."""
    try:
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # pragma: no cover
        logger.error(f"masters seed file unreadable: {e}")
        return

    version = data.get("version", "0")
    meta = await db.app_config.find_one({"key": "masters_seed"})
    if meta and (meta.get("value") or {}).get("version") == version:
        logger.info(f"Masters seed v{version} already present — skipping.")
        return

    inserted = 0
    for json_key, mtype in _KEY_TO_TYPE.items():
        items = data.get(json_key, []) or []
        for order, it in enumerate(items):
            value = (it.get("value") or "").strip()
            if not value:
                continue
            parent = (it.get("parent") or None)
            # Identity for a seed row = (type, value, parent). Don't duplicate.
            existing = await db.masters.find_one({
                "type": mtype,
                "value_lower": value.lower(),
                "parent_lower": (parent or "").lower(),
            })
            if existing:
                continue
            await db.masters.insert_one({
                "master_id": str(uuid.uuid4()),
                "type": mtype,
                "value": value,
                "value_lower": value.lower(),
                "parent": parent,
                "parent_lower": (parent or "").lower(),
                "order": order,
                "active": True,
                "is_seed": True,
                "created_at": _now(),
                "updated_at": _now(),
            })
            inserted += 1

    await db.app_config.update_one(
        {"key": "masters_seed"},
        {"$set": {"key": "masters_seed", "value": {"version": version, "updated_at": _now()}}},
        upsert=True,
    )
    logger.info(f"Masters seed v{version} applied — inserted {inserted} new rows.")


async def dedup_masters_on_boot():
    """Remove duplicate masters rows.

    Production databases accumulated duplicate rows (e.g. 'Accounting' twice,
    'Financial Analysis' thrice) from earlier seeding runs that pre-dated the
    (type, value_lower, parent_lower) identity check. This scans for any such
    duplicate groups and keeps a single canonical row per group, deleting the
    rest. Idempotent + cheap: if there are no duplicates it does nothing.

    Preference order for the row to KEEP: seed rows first, then lowest `order`,
    then earliest `created_at`.

    Version-gated: runs ONCE (per DEDUP_VERSION) and is an instant no-op on
    every subsequent boot/worker, so it never adds latency to multi-worker
    startups after the first successful run.
    """
    DEDUP_VERSION = "2026-06-02-01"
    try:
        meta = await db.app_config.find_one({"key": "masters_dedup"})
        if meta and (meta.get("value") or {}).get("version") == DEDUP_VERSION:
            return  # already deduped at this version — fast no-op
    except Exception:
        pass
    try:
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "type": "$type",
                        "value_lower": {"$ifNull": ["$value_lower", ""]},
                        "parent_lower": {"$ifNull": ["$parent_lower", ""]},
                    },
                    "ids": {"$addToSet": "$master_id"},
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
        groups = await db.masters.aggregate(pipeline).to_list(None)
        total_removed = 0
        for g in (groups or []):
            ids = [i for i in (g.get("ids") or []) if i]
            if len(ids) <= 1:
                continue
            # Fetch the rows to decide which one to keep.
            docs = await db.masters.find({"master_id": {"$in": ids}}).to_list(None)
            if len(docs) <= 1:
                continue
            docs.sort(key=lambda d: (
                0 if d.get("is_seed") else 1,
                d.get("order", 1_000_000),
                d.get("created_at", ""),
            ))
            keep_id = docs[0].get("master_id")
            remove_ids = [d.get("master_id") for d in docs[1:] if d.get("master_id") and d.get("master_id") != keep_id]
            if remove_ids:
                res = await db.masters.delete_many({"master_id": {"$in": remove_ids}})
                total_removed += res.deleted_count

        if total_removed:
            logger.info(f"Masters dedup — removed {total_removed} duplicate rows across {len(groups)} groups.")

        # Mark done so this never runs again at this version (fast no-op on
        # all future boots / workers).
        await db.app_config.update_one(
            {"key": "masters_dedup"},
            {"$set": {"key": "masters_dedup", "value": {"version": DEDUP_VERSION, "updated_at": _now()}}},
            upsert=True,
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Masters dedup failed: {e}")
