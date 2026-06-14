"""
Decision-mode rename: `awareness` → `consciousness`.

One-shot, idempotent migration that updates legacy `assessments` docs:
  • `dominant_mode == "awareness"`  →  `"consciousness"`
  • `mode_scores.awareness`  →  `mode_scores.consciousness`  (preserves value)

Why?
  Mode label was renamed for South-India 25–45 audience clarity. The DB enum
  is renamed too so historical records render correctly with the new label
  without runtime mapping shims.

Idempotency:
  • Migration log doc: `{"_id": "decision_mode_awareness_to_consciousness_v1"}`
  • Re-runs scan zero unmigrated records and skip.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.database import db

logger = logging.getLogger(__name__)

_MIGRATION_ID = "decision_mode_awareness_to_consciousness_v1"


async def migrate_decision_mode_awareness_to_consciousness() -> dict:
    scanned = 0
    fixed = 0
    skipped = 0

    cursor = db.assessments.find(
        {
            "$or": [
                {"dominant_mode": "awareness"},
                {"mode_scores.awareness": {"$exists": True}},
            ]
        },
        {"_id": 1, "dominant_mode": 1, "mode_scores": 1},
    )

    async for doc in cursor:
        scanned += 1
        update_ops: dict = {}
        unset_ops: dict = {}

        if doc.get("dominant_mode") == "awareness":
            update_ops["dominant_mode"] = "consciousness"

        ms = doc.get("mode_scores") or {}
        if isinstance(ms, dict) and "awareness" in ms:
            # Preserve the numeric value under the new key. If
            # `mode_scores.consciousness` already exists (mixed-state record),
            # the new value wins — but only when it's the larger / non-zero
            # one, to be safe.
            existing_c = ms.get("consciousness")
            old_val = ms.get("awareness")
            try:
                old_f = float(old_val)
            except Exception:
                old_f = 0.0
            try:
                cur_f = float(existing_c) if existing_c is not None else None
            except Exception:
                cur_f = None
            new_val = old_f if (cur_f is None or old_f > cur_f) else cur_f
            update_ops["mode_scores.consciousness"] = new_val
            unset_ops["mode_scores.awareness"] = ""

        if not update_ops and not unset_ops:
            skipped += 1
            continue

        ops: dict = {}
        if update_ops:
            ops["$set"] = update_ops
        if unset_ops:
            ops["$unset"] = unset_ops
        await db.assessments.update_one({"_id": doc["_id"]}, ops)
        fixed += 1

    await db.migrations.update_one(
        {"_id": _MIGRATION_ID},
        {"$set": {
            "last_run_at": datetime.now(timezone.utc),
            "scanned": scanned,
            "fixed": fixed,
            "skipped": skipped,
        }},
        upsert=True,
    )

    if fixed:
        logger.info(
            f"{_MIGRATION_ID}: scanned={scanned} fixed={fixed} skipped={skipped}"
        )
    else:
        logger.debug(
            f"{_MIGRATION_ID}: nothing to migrate (scanned={scanned})"
        )

    return {"scanned": scanned, "fixed": fixed, "skipped": skipped}
