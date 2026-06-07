"""Services layer for the Decisions module.

Shared business logic used across the decision sub-routers (CRUD, assessment
import/export, AI assess). Keeping this here avoids duplication and keeps the
route handlers thin.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List

from core.database import db

logger = logging.getLogger(__name__)


async def consume_entitlement(user_id: str, decision_id: str, *, context: str = "create") -> None:
    """Consume one decision entitlement (prefers L2 bundle → L1) and pre-unlock
    the report so the PDF stays free.

    Subscriptions/admin-skip and users without a pack are not charged. This must
    never block the calling flow — failures are logged and swallowed.
    """
    try:
        from routes.sku_store import ensure_decision_entitlement
        await ensure_decision_entitlement(user_id, module="dezider", decision_id=decision_id)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("entitlement consume on decision %s failed: %s", context, e)


def ordered_factors(decision: dict) -> List[dict]:
    """Return factors ordered main → sub-factor with parent metadata.

    Used to build XLS / Google Sheet assessment templates.
    """
    factors = decision.get("factors", [])
    mains = [f for f in factors if not f.get("parent_id")]
    subs_by_parent: Dict[str, List[dict]] = {}
    for f in factors:
        if f.get("parent_id"):
            subs_by_parent.setdefault(f["parent_id"], []).append(f)
    ordered = []
    for m in mains:
        ordered.append({"id": m["id"], "name": m.get("name") or "", "parent_id": None,
                        "parent_name": "", "expected": m.get("expected_value"), "unit": m.get("unit") or ""})
        for s in subs_by_parent.get(m["id"], []):
            ordered.append({"id": s["id"], "name": s.get("name") or "", "parent_id": m["id"],
                            "parent_name": m.get("name") or "", "expected": s.get("expected_value"), "unit": s.get("unit") or ""})
    return ordered


async def apply_assessment_rows(decision: dict, rows: list, decision_id: str, user_id: str) -> int:
    """Apply parsed assessment rows (from XLS or Google Sheet) into a decision's
    option.assessments, recompute flat worth, persist. Returns rows applied.
    """
    factors = decision.get("factors", [])
    valid_factor_ids = {f["id"] for f in factors}
    options = decision.get("options", [])
    opt_by_id = {o["id"]: o for o in options}

    by_option: Dict[str, Dict[str, dict]] = {}
    applied = 0
    for r in rows:
        fid = r.get("factor_id")
        oid = r.get("option_id")
        if fid not in valid_factor_ids or oid not in opt_by_id:
            continue
        by_option.setdefault(oid, {})[fid] = r

    for oid, fmap in by_option.items():
        opt = opt_by_id[oid]
        asmts = opt.setdefault("assessments", [])
        existing = {a["factor_id"]: a for a in asmts if a.get("factor_id")}
        for fid, r in fmap.items():
            a = existing.get(fid)
            if not a:
                a = {"factor_id": fid, "percentage": None, "unit_value": "", "assessment_mode": "custom"}
                asmts.append(a)
                existing[fid] = a
            if "actual" in r:
                a["unit_value"] = r["actual"]
            if "assessment_pct" in r:
                a["percentage"] = int(r["assessment_pct"])
            applied += 1

    total_rating = sum(f.get("rating", 0) for f in factors if not f.get("parent_id"))
    for opt in options:
        worth = 0.0
        if total_rating > 0:
            for a in opt.get("assessments", []):
                f = next((x for x in factors if x["id"] == a["factor_id"] and not x.get("parent_id")), None)
                if f and a.get("percentage") is not None:
                    worth += (f.get("rating", 0) / total_rating) * max(0, min(100, a["percentage"]))
        opt["worth_percentage"] = round(min(100.0, max(0.0, worth)), 2)

    await db.decisions.update_one(
        {"id": decision_id, "user_id": user_id},
        {"$set": {"options": options, "updated_at": datetime.now(timezone.utc)}},
    )
    return applied
