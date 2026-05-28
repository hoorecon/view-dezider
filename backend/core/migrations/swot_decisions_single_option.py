"""
SWOT-converted Decisions — one-shot migration helper.

Goal
----
Existing decisions in `db.decisions` with `source_module == "swot"` that were
created BEFORE the single-option flow was introduced have `options: []`.
Inject a `"Current Scenario - <converted_at>"` option into each so the
/prr/[id] UI doesn't break when it tries to render Steps 6/7/9/10.

Idempotent
----------
- Only touches docs where `source_module == "swot"` AND `options` is empty.
- Subsequent boots see `options` already populated and skip the doc.
- Safe to call on every server start.

Migration log key in `db.migrations`:
    {"_id": "swot_decisions_single_option_v1"}
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from core.database import db

logger = logging.getLogger(__name__)


async def migrate_swot_decisions_single_option() -> dict:
    """
    Returns:  dict {scanned, fixed, skipped}
    """
    scanned = 0
    fixed = 0
    skipped = 0

    # Defensive — only target SWOT-sourced decisions
    cursor = db.decisions.find(
        {"source_module": "swot"},
        {"_id": 0, "id": 1, "options": 1, "created_at": 1, "mpps_option_id": 1},
    )

    async for doc in cursor:
        scanned += 1
        opts = doc.get("options") or []

        # Case A — doc has NO options yet (legacy converts from before the
        # single-option flow): inject a fresh "Current Scenario" option.
        if not opts:
            # Build the Current Scenario option with a timestamp from the doc's
            # created_at so re-running this migration always reproduces the same
            # label (idempotency aid for support / debugging).
            created = doc.get("created_at") or datetime.now(timezone.utc)
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    created = datetime.now(timezone.utc)
            label = f"Current Scenario - {created.strftime('%Y-%m-%d %H:%M')}"

            opt_id = str(uuid.uuid4())
            current_scenario = {
                "id": opt_id,
                "name": label,
                "description": "Auto-injected by SWOT→Decider single-option migration.",
                "order": 0,
                "is_default_scenario": True,
                # CRITICAL: must be present — calculateDynamicWorth on the
                # frontend reads option.assessments.find(...). Missing → crash.
                "assessments": [],
            }
            patch = {
                "options": [current_scenario],
                "allow_single_option": True,
                "updated_at": datetime.now(timezone.utc),
            }
            # Only set mpps_option_id if currently empty (don't overwrite user choice)
            if not doc.get("mpps_option_id"):
                patch["mpps_option_id"] = opt_id

            await db.decisions.update_one({"id": doc["id"]}, {"$set": patch})
            fixed += 1
            continue

        # Case B — doc already has options but they're missing the
        # `assessments` array (intermediate state from an earlier version of
        # this migration). Backfill `assessments: []` on each option so
        # Step 7's calculateDynamicWorth doesn't blow up.
        needs_assessments_backfill = any(
            ("assessments" not in o) or (o.get("assessments") is None)
            for o in opts
        )
        if needs_assessments_backfill:
            patched_opts = []
            for o in opts:
                no = dict(o)
                if "assessments" not in no or no.get("assessments") is None:
                    no["assessments"] = []
                patched_opts.append(no)
            patch = {
                "options": patched_opts,
                "allow_single_option": True,
                "updated_at": datetime.now(timezone.utc),
            }
            if not doc.get("mpps_option_id") and patched_opts:
                patch["mpps_option_id"] = patched_opts[0]["id"]
            await db.decisions.update_one({"id": doc["id"]}, {"$set": patch})
            fixed += 1
            continue

        # Doc is healthy
        skipped += 1

    # Record migration ran (also lets us inspect counts via Mongo shell)
    await db.migrations.update_one(
        {"_id": "swot_decisions_single_option_v1"},
        {
            "$set": {
                "last_run_at": datetime.now(timezone.utc),
                "scanned": scanned,
                "fixed": fixed,
                "skipped": skipped,
            }
        },
        upsert=True,
    )

    if fixed:
        logger.info(
            f"swot_decisions_single_option_v1: scanned={scanned} fixed={fixed} skipped={skipped}"
        )
    else:
        logger.debug(
            f"swot_decisions_single_option_v1: nothing to migrate (scanned={scanned})"
        )

    return {"scanned": scanned, "fixed": fixed, "skipped": skipped}
