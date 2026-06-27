"""
Option Publishing — Epic Phase 3B/3C
====================================
Publish a COMPLETED decision's Option values into the existing modules:

  • Quantitative factors -> a Solutions Store solution (db.solutions_store), one
    per published option. Cash is earned on PAID usage.
  • Qualitative factors  -> ReviewNet review dimensions on that solution (the
    solution is made reviewable via db.review_policies); ReviewNet yields Karma.

Monetization is resolved against the admin Central-Catalog L0–L3 payout config
(core.payout_engine). FREE usage (and ReviewNet) => Karma; PAID Store usage => Cash.

Usage events (someone applies a published solution to their decision, or an
explicit record-usage call) credit the publisher:
  • free use  -> Karma  = karma_solution_store * (1 + star/5)
  • paid use  -> Cash   = payment_min + (payment_max-payment_min)*(avg★/5)*(#ratings/3000)

Gating: Solution-Store publish is allowed ONLY from a Completed (100%) flow.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import karma as karma_engine
from core.auth import get_current_user
from core.database import db
from core.payout_engine import compute_cash_payout, compute_karma, resolve_payout_config

log = logging.getLogger("option_publish")
router = APIRouter(prefix="/option-publish", tags=["Option Publishing"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _review_stats(solution_id: str) -> tuple[float, int]:
    """avg overall rating + count of PUBLISHED ReviewNet reviews for a solution."""
    pipeline = [
        {"$match": {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}}},
        {"$group": {"_id": None, "avg": {"$avg": "$overall_rating"}, "count": {"$sum": 1}}},
    ]
    agg = [r async for r in db.review_net.aggregate(pipeline)]
    if agg:
        return float(agg[0].get("avg") or 0), int(agg[0].get("count") or 0)
    return 0.0, 0


async def _is_decision_completed(decision: dict) -> bool:
    from routes.solution_box import _progress_decider
    return _progress_decider(decision).get("status") == "completed"


async def record_solution_usage(
    sol: dict,
    beneficiary_id: str,
    *,
    star_rating: Optional[float] = None,
    source: str = "apply_to_option",
) -> Optional[dict]:
    """Credit the publisher of `sol` for one usage by `beneficiary_id`.

    Returns the credit result, or None when no reward applies (self-use, missing
    publisher). Safe to call fire-and-forget — never raises to the caller path.
    """
    try:
        publisher_id = sol.get("created_by")
        solution_id = sol.get("solution_id")
        if not publisher_id or not solution_id or publisher_id == beneficiary_id:
            return None

        monet = sol.get("monetization") or {}
        mode = (monet.get("mode") or "free").lower()       # free | paid
        node_id = sol.get("catalog_node_id")
        cfg = await resolve_payout_config(db, node_id)

        prior = await db.solution_usages.count_documents(
            {"solution_id": solution_id, "beneficiary_id": beneficiary_id}
        )
        free_quota = int(cfg.get("free_usage_solution_store") or 0)
        # PAID listing: first `free_quota` uses (per beneficiary) are still free → Karma.
        # FREE listing: every use is free → Karma.
        is_free_use = (mode != "paid") or (prior < free_quota)

        result: Dict[str, Any] = {
            "solution_id": solution_id,
            "publisher_id": publisher_id,
            "kind": "free" if is_free_use else "paid",
            "source": source,
        }

        if is_free_use:
            pts = compute_karma(int(cfg.get("karma_solution_store") or 0), star_rating)
            if pts > 0:
                await karma_engine.award_karma_points(
                    publisher_id, pts, event="solution_store_free_use",
                    reason=f'Free use of your Store solution "{sol.get("name") or solution_id}"',
                    ref={"solution_id": solution_id, "beneficiary_id": beneficiary_id},
                )
            result.update({"reward_kind": "karma", "karma": pts})
        else:
            avg, cnt = await _review_stats(solution_id)
            gross = compute_cash_payout(cfg, avg, cnt)
            # apply platform commission (shared with marketplace earnings config)
            commission_pct = 0
            try:
                from routes.earnings import get_config as _earn_cfg
                ecfg = await _earn_cfg()
                commission_pct = max(0, min(100, int(ecfg.get("platform_commission_percent", 0) or 0)))
            except Exception:
                commission_pct = 0
            commission = round(gross * commission_pct / 100, 2)
            net = round(gross - commission, 2)
            entry = {
                "entry_id": f"earn_{uuid.uuid4().hex[:12]}",
                "user_id": publisher_id,
                "source": "solution_store_usage",
                "solution_id": solution_id,
                "listing_title": sol.get("name"),
                "buyer_id": beneficiary_id,
                "gross_inr": gross,
                "commission_inr": commission,
                "net_inr": net,
                "avg_rating": avg,
                "num_ratings": cnt,
                "status": "available",
                "payout_id": None,
                "created_at": _now(),
            }
            await db.earnings_ledger.insert_one(entry)
            try:
                from core.helpers import create_notification
                await create_notification(
                    publisher_id, "earnings", "You earned money 💰",
                    f'You earned ₹{net} from a paid use of "{sol.get("name") or "your solution"}".',
                    {"solution_id": solution_id},
                )
            except Exception:
                pass
            result.update({"reward_kind": "cash", "cash_inr": net, "gross_inr": gross,
                           "avg_rating": avg, "num_ratings": cnt})

        await db.solution_usages.insert_one({
            "usage_id": f"use_{uuid.uuid4().hex[:12]}",
            "solution_id": solution_id,
            "beneficiary_id": beneficiary_id,
            "publisher_id": publisher_id,
            "kind": result["kind"],
            "reward_kind": result.get("reward_kind"),
            "amount": result.get("cash_inr") if result.get("reward_kind") == "cash" else result.get("karma"),
            "star_rating": star_rating,
            "catalog_node_id": node_id,
            "source": source,
            "created_at": _now(),
        })
        return result
    except Exception as e:  # never break the caller flow
        log.warning("record_solution_usage failed: %s", str(e)[:200])
        return None


# ---------------------------------------------------------------------------
# request models
# ---------------------------------------------------------------------------
class PublishBody(BaseModel):
    decision_id: str
    option_ids: Optional[List[str]] = None           # None => all options
    factor_ids: Optional[List[str]] = None           # None => all factors (unlisted are skipped)
    factor_types: Dict[str, str] = {}                # factor_id -> 'quantitative'|'qualitative'
    catalog_node_id: Optional[str] = None
    life_area_id: Optional[str] = None
    sub_area_id: Optional[str] = None
    solution_type: str = "PRODUCT"                   # one of SOLUTION_TYPES
    monetization: str = "free"                       # 'free' | 'paid'
    visibility: str = "PRIVATE"                      # 'PRIVATE' | 'PUBLIC'
    description: Optional[str] = None


class RecordUsageBody(BaseModel):
    solution_id: str
    star_rating: Optional[float] = None


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.get("/source/{decision_id}")
async def publish_source(decision_id: str, user: dict = Depends(get_current_user)):
    """Decision options + factors + completion status — powers the publish modal."""
    dec = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not dec:
        raise HTTPException(404, "Decision not found")
    from routes.solution_box import _progress_decider
    prog = _progress_decider(dec)
    factors = [
        {
            "id": f.get("id"),
            "name": f.get("name") or "Factor",
            "unit": f.get("unit"),
            "operator": f.get("operator"),
            "default_kind": "quantitative",
        }
        for f in (dec.get("factors") or [])
        if f.get("id")
    ]
    options = [
        {"id": o.get("id"), "name": o.get("name") or "Option"}
        for o in (dec.get("options") or [])
        if o.get("id")
    ]
    return {
        "decision_id": decision_id,
        "name": dec.get("name") or dec.get("title") or "Decision",
        "type": dec.get("type", "decider"),
        "status": prog.get("status"),
        "progress_pct": prog.get("progress_pct"),
        "is_completed": prog.get("status") == "completed",
        "catalog_node_id": dec.get("catalog_node_id"),
        "life_area_id": dec.get("life_area_id"),
        "sub_area_id": dec.get("sub_area_id"),
        "factors": factors,
        "options": options,
    }


@router.post("/publish")
async def publish_options(body: PublishBody, user: dict = Depends(get_current_user)):
    from models.solutions_store_data import SOLUTION_TYPES

    dec = await db.decisions.find_one(
        {"id": body.decision_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not dec:
        raise HTTPException(404, "Decision not found")

    # Gating — Solution Store publish requires a Completed (100%) flow.
    if not await _is_decision_completed(dec):
        raise HTTPException(
            400,
            "Solution Store publishing is allowed only from a Completed (100%) flow. Finish the assessment first.",
        )

    sol_type = (body.solution_type or "PRODUCT").upper()
    if sol_type not in SOLUTION_TYPES:
        raise HTTPException(400, f"solution_type must be one of {SOLUTION_TYPES}")

    mode = (body.monetization or "free").lower()
    if mode not in ("free", "paid"):
        raise HTTPException(400, "monetization must be 'free' or 'paid'")
    # Store paid usage => cash; free => karma (per product rules).
    reward_kind = "cash" if mode == "paid" else "karma"

    visibility = (body.visibility or "PRIVATE").upper()
    if visibility not in ("PRIVATE", "PUBLIC"):
        raise HTTPException(400, "visibility must be PRIVATE or PUBLIC")

    factors = {f["id"]: f for f in (dec.get("factors") or []) if f.get("id")}
    if body.factor_ids is not None:
        keep = set(body.factor_ids)
        factors = {fid: f for fid, f in factors.items() if fid in keep}
    quant_ids = [fid for fid in factors if body.factor_types.get(fid, "quantitative") != "qualitative"]
    qual_ids = [fid for fid in factors if body.factor_types.get(fid) == "qualitative"]
    if not quant_ids:
        raise HTTPException(400, "At least one factor must remain Quantitative to publish to the Store.")

    options = {o["id"]: o for o in (dec.get("options") or []) if o.get("id")}
    target_ids = body.option_ids or list(options.keys())
    target_ids = [oid for oid in target_ids if oid in options]
    if not target_ids:
        raise HTTPException(400, "No valid options selected to publish.")

    node_id = body.catalog_node_id or dec.get("catalog_node_id")
    cfg = await resolve_payout_config(db, node_id)
    payout_snapshot = {k: cfg.get(k) for k in (
        "free_usage_solution_store", "payment_min", "payment_max",
        "karma_solution_store", "karma_reviewnet",
    )}

    qualitative_factors = [{"factor_id": fid, "factor_name": factors[fid].get("name") or "Factor"} for fid in qual_ids]
    now = _now()
    created: List[dict] = []

    for oid in target_ids:
        opt = options[oid]
        assess_by_factor = {a.get("factor_id"): a for a in (opt.get("assessments") or []) if a.get("factor_id")}
        quantitative_factors = []
        for fid in quant_ids:
            f = factors[fid]
            a = assess_by_factor.get(fid) or {}
            quantitative_factors.append({
                "factor_id": fid,
                "name": f.get("name") or "Factor",
                "unit": f.get("unit"),
                "operator": f.get("operator"),
                "value": a.get("actual_value"),
                "percentage": a.get("percentage"),
            })

        solution_id = str(uuid.uuid4())
        is_admin = user.get("role") in ("super_admin", "co_admin", "admin")
        approval_status = "approved" if (visibility != "PUBLIC" or is_admin) else "pending"
        sol_doc = {
            "solution_id": solution_id,
            "type": sol_type,
            "name": opt.get("name") or dec.get("name") or "Published Option",
            "description": body.description or f'Published from decision "{dec.get("name") or dec.get("title") or ""}"',
            "life_area_id": body.life_area_id or dec.get("life_area_id"),
            "sub_area_id": body.sub_area_id or dec.get("sub_area_id"),
            "category_id": dec.get("category_id"),
            "catalog_node_id": node_id,
            "org_types": [],
            "decision_types": [],
            "scenario_ids": [],
            "visibility": visibility,
            "approval_status": approval_status,
            "is_authorized": bool(is_admin and visibility == "PUBLIC"),
            "created_by": user["user_id"],
            "created_by_name": user.get("name", ""),
            "org_id": user.get("org_id"),
            "country": "IN",
            "language": "en",
            "quantitative_factors": quantitative_factors,
            "qualitative_factors": qualitative_factors,
            "type_specific": {},
            # ── monetization (Phase 3) ──
            "monetization": {
                "mode": mode,
                "reward_kind": reward_kind,
                "catalog_node_id": node_id,
                "payout_config_snapshot": payout_snapshot,
            },
            "published_from_option": True,
            "source": {
                "decision_id": body.decision_id,
                "option_id": oid,
                "option_name": opt.get("name"),
            },
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        await db.solutions_store.insert_one(sol_doc)

        # Make it reviewable in ReviewNet (qualitative factors).
        await db.review_policies.update_one(
            {"solution_id": solution_id},
            {"$set": {
                "solution_id": solution_id,
                "policy": "ALL_AUTHENTICATED",
                "allowed_segments": ["individual", "organization", "government"],
                "invited_user_ids": [],
                "employee_org_ids": [],
                "configured_by": user["user_id"],
                "updated_at": now,
            }},
            upsert=True,
        )
        sol_doc.pop("_id", None)
        created.append({
            "solution_id": solution_id,
            "name": sol_doc["name"],
            "quantitative_count": len(quantitative_factors),
            "qualitative_count": len(qualitative_factors),
        })

    return {
        "ok": True,
        "published_count": len(created),
        "monetization": mode,
        "reward_kind": reward_kind,
        "catalog_node_id": node_id,
        "payout_config": payout_snapshot,
        "quantitative_factor_ids": quant_ids,
        "qualitative_factor_ids": qual_ids,
        "solutions": created,
    }


@router.post("/record-usage")
async def record_usage(body: RecordUsageBody, user: dict = Depends(get_current_user)):
    """Record a usage of a published solution and credit the publisher
    (cash for paid usage beyond the free quota, else Karma)."""
    sol = await db.solutions_store.find_one(
        {"solution_id": body.solution_id, "status": "active"}, {"_id": 0}
    )
    if not sol:
        raise HTTPException(404, "Solution not found")
    res = await record_solution_usage(
        sol, user["user_id"], star_rating=body.star_rating, source="record_usage"
    )
    if res is None:
        return {"ok": False, "reason": "no reward (self-use or missing publisher)"}
    return {"ok": True, **res}


@router.get("/my-published")
async def my_published(user: dict = Depends(get_current_user)):
    """List the current user's option-published Store solutions + usage/earning stats."""
    cur = db.solutions_store.find(
        {"created_by": user["user_id"], "published_from_option": True, "status": "active"},
        {"_id": 0},
    ).sort("created_at", -1)
    items = await cur.to_list(200)
    for it in items:
        avg, cnt = await _review_stats(it["solution_id"])
        usages = await db.solution_usages.count_documents({"solution_id": it["solution_id"]})
        it["review_avg"] = avg
        it["review_count"] = cnt
        it["usage_count"] = usages
    return {"items": items, "count": len(items)}
