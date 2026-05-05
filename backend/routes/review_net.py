"""
ReviewNet — REST routes.

Endpoints (all under /api/review-net):

PUBLIC factor catalog (auth-required for write):
  GET    /factors?solution_id=X | catalog_node_id=X       resolved factors (hierarchical)
  POST   /factors                                          (admin) create custom factor
  PUT    /factors/{factor_id}                              (admin)
  DELETE /factors/{factor_id}                              (admin)
  POST   /factors/seed                                     (admin) idempotent seed

REVIEWS:
  POST   /reviews                                          submit a review (eligibility-checked)
  GET    /reviews?solution_id=X[&segment=...]              list approved reviews
  GET    /reviews/{review_id}                              single
  POST   /reviews/{review_id}/helpful                      vote 👍/👎
  POST   /reviews/{review_id}/reply                        owner-only reply
  GET    /aggregates?solution_id=X                         segmented aggregates (3 segments × per factor)

ELIGIBILITY:
  GET    /eligibility/{solution_id}                        is_eligible + reason
  PUT    /eligibility/{solution_id}                        publisher / admin sets policy

ADMIN moderation:
  GET    /admin/moderation-queue
  POST   /admin/moderate/{review_id}
  GET    /admin/rules
  POST   /admin/rules
  PUT    /admin/rules/{rule_id}
  DELETE /admin/rules/{rule_id}
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_current_user, require_admin
from core.database import db
from data.review_net_seed import GLOBAL_FACTORS, LIFE_AREA_FACTORS, SUB_AREA_FACTORS
from models.review_net_models import (
    ELIGIBILITY_POLICIES,
    SUBSEGMENTS_BY_SEGMENT,
    EligibilityPolicy,
    HelpfulVote,
    ModerationRuleCreate,
    ModerationRuleUpdate,
    OwnerReply,
    QualitativeFactorCreate,
    QualitativeFactorUpdate,
    ReviewModerate,
    ReviewSubmit,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review-net", tags=["ReviewNet"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "factor"


def _strip_id(d: dict) -> dict:
    if d and "_id" in d:
        d.pop("_id", None)
    return d


async def _resolve_solution(solution_id: str) -> dict:
    sol = await db.solutions_store.find_one({"solution_id": solution_id}, {"_id": 0})
    if not sol:
        raise HTTPException(404, "solution not found")
    return sol


async def _ancestor_node_chain(catalog_node_id: Optional[str]) -> List[dict]:
    """Walk a catalog node up to root, return ancestors (deepest first)."""
    chain: List[dict] = []
    cur_id = catalog_node_id
    while cur_id:
        node = await db.catalog_nodes.find_one({"node_id": cur_id}, {"_id": 0})
        if not node:
            break
        chain.append(node)
        cur_id = node.get("parent_id")
    return chain


# ---------------------------------------------------------------------------
# Factor seed (idempotent)
# ---------------------------------------------------------------------------
@router.post("/factors/seed")
async def seed_factors(user: dict = Depends(require_admin)):
    inserted = 0
    skipped = 0

    async def _upsert(scope_type: str, scope_id: Optional[str], items: List[dict]):
        nonlocal inserted, skipped
        for idx, f in enumerate(items, start=1):
            slug = _slug(f["slug"])
            factor_id = f"qf_{scope_id or 'global'}_{slug}"
            existing = await db.review_factors.find_one({"factor_id": factor_id}, {"_id": 1})
            doc = {
                "factor_id": factor_id,
                "name": f["name"],
                "slug": slug,
                "description": f.get("description"),
                "scope_type": scope_type,
                "scope_id": scope_id,
                "sort_order": idx,
                "is_active": True,
                "is_immutable": True,    # seeded factors should not be edit-renamed by accident
                "updated_at": _now(),
            }
            if existing:
                skipped += 1
                continue
            doc["created_at"] = _now()
            await db.review_factors.insert_one(doc)
            inserted += 1

    await _upsert("global", None, GLOBAL_FACTORS)
    for la_id, items in LIFE_AREA_FACTORS.items():
        await _upsert("life_area", la_id, items)
    for sa_id, items in SUB_AREA_FACTORS.items():
        await _upsert("sub_area", sa_id, items)

    # ensure indexes
    await db.review_factors.create_index("factor_id", unique=True)
    await db.review_factors.create_index([("scope_type", 1), ("scope_id", 1)])
    await db.review_factors.create_index("is_active")

    total = await db.review_factors.count_documents({})
    return {"ok": True, "inserted": inserted, "skipped_existing": skipped, "total": total}


@router.post("/factors")
async def create_factor(body: QualitativeFactorCreate, user: dict = Depends(require_admin)):
    slug = _slug(body.slug or body.name)
    factor_id = f"qf_{(body.scope_id or 'global')}_{slug}"
    existing = await db.review_factors.find_one({"factor_id": factor_id}, {"_id": 1})
    if existing:
        factor_id = f"{factor_id}_{int(_now().timestamp())}"
    doc = {
        "factor_id": factor_id,
        "name": body.name,
        "slug": slug,
        "description": body.description,
        "scope_type": body.scope_type,
        "scope_id": body.scope_id,
        "sort_order": body.sort_order,
        "is_active": True,
        "is_immutable": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.review_factors.insert_one(doc)
    return _strip_id(doc)


@router.put("/factors/{factor_id}")
async def update_factor(factor_id: str, body: QualitativeFactorUpdate, user: dict = Depends(require_admin)):
    doc = await db.review_factors.find_one({"factor_id": factor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "factor not found")
    set_doc: Dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        set_doc["name"] = body.name
    if body.description is not None:
        set_doc["description"] = body.description
    if body.sort_order is not None:
        set_doc["sort_order"] = body.sort_order
    if body.is_active is not None:
        set_doc["is_active"] = body.is_active
    await db.review_factors.update_one({"factor_id": factor_id}, {"$set": set_doc})
    return _strip_id(await db.review_factors.find_one({"factor_id": factor_id}, {"_id": 0}))


@router.delete("/factors/{factor_id}")
async def delete_factor(factor_id: str, user: dict = Depends(require_admin)):
    doc = await db.review_factors.find_one({"factor_id": factor_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "factor not found")
    if doc.get("is_immutable"):
        raise HTTPException(403, "cannot delete a seeded immutable factor; deactivate instead")
    await db.review_factors.delete_one({"factor_id": factor_id})
    return {"ok": True}


@router.get("/factors")
async def resolve_factors(
    solution_id: Optional[str] = Query(None),
    catalog_node_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """Return resolved factors (deduped by slug, closer scope wins)."""
    factors_by_slug: Dict[str, dict] = {}

    async def _collect(scope_type: str, scope_id: Optional[str]):
        cur = db.review_factors.find(
            {"scope_type": scope_type, "scope_id": scope_id, "is_active": True},
            {"_id": 0},
        )
        async for f in cur:
            factors_by_slug.setdefault(f["slug"], f)

    # 1) Global lowest priority
    await _collect("global", None)

    # 2) life_area / sub_area / catalog_node hierarchy
    if solution_id:
        sol = await _resolve_solution(solution_id)
        catalog_node_id = catalog_node_id or sol.get("catalog_node_id")
        # life_area_id may also exist on the solution
        if sol.get("life_area_id"):
            await _collect("life_area", sol["life_area_id"])
        if sol.get("sub_area_id"):
            await _collect("sub_area", sol["sub_area_id"])
        # solution-specific custom factors
        await _collect("solution", solution_id)

    if catalog_node_id:
        ancestors = await _ancestor_node_chain(catalog_node_id)
        # deepest last so closer wins
        for n in reversed(ancestors):
            await _collect("life_area", n.get("life_area_id"))
            if n.get("sub_area_id"):
                await _collect("sub_area", n["sub_area_id"])
            await _collect("catalog_node", n["node_id"])

    # Sort and return
    items = sorted(factors_by_slug.values(), key=lambda f: (f.get("sort_order", 999), f["name"]))
    return {"factors": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Eligibility policy
# ---------------------------------------------------------------------------
async def _policy_for(solution_id: str) -> dict:
    pol = await db.review_policies.find_one({"solution_id": solution_id}, {"_id": 0})
    if pol:
        return pol
    return {
        "solution_id": solution_id,
        "policy": "ALL_AUTHENTICATED",
        "allowed_segments": ["individual", "organization", "government"],
        "invited_user_ids": [],
        "employee_org_ids": [],
        "admin_overridden": False,
    }


@router.get("/eligibility/{solution_id}")
async def get_eligibility(solution_id: str, user: dict = Depends(get_current_user)):
    pol = await _policy_for(solution_id)
    user_id = user["user_id"]
    is_eligible = True
    reason = "ok"

    if pol["policy"] == "VERIFIED_BUYERS_ONLY":
        bought = await db.time_store_purchases.find_one(
            {"solution_id": solution_id, "user_id": user_id}, {"_id": 1}
        )
        if not bought:
            is_eligible = False
            reason = "VERIFIED_BUYERS_ONLY: no purchase record found"
    elif pol["policy"] == "INVITED_ONLY":
        if user_id not in (pol.get("invited_user_ids") or []):
            is_eligible = False
            reason = "INVITED_ONLY: user not on invite list"
    elif pol["policy"] == "EMPLOYEES_ONLY":
        if not (user.get("org_id") and user["org_id"] in (pol.get("employee_org_ids") or [])):
            is_eligible = False
            reason = "EMPLOYEES_ONLY: user not employee of allowed org"

    return {"policy": pol, "is_eligible": is_eligible, "reason": reason}


@router.put("/eligibility/{solution_id}")
async def set_eligibility(
    solution_id: str,
    body: EligibilityPolicy,
    user: dict = Depends(get_current_user),
):
    sol = await _resolve_solution(solution_id)
    role = (user.get("role") or "user").lower()
    is_admin = role in ("admin", "co_admin", "super_admin")
    is_publisher = (sol.get("created_by") == user["user_id"]) or (sol.get("org_id") and sol.get("org_id") == user.get("org_id"))
    if not (is_admin or is_publisher):
        raise HTTPException(403, "only the publisher or an admin can configure eligibility")

    if body.policy not in ELIGIBILITY_POLICIES:
        raise HTTPException(400, f"invalid policy. allowed: {ELIGIBILITY_POLICIES}")

    doc = {
        "solution_id": solution_id,
        "policy": body.policy,
        "allowed_segments": body.allowed_segments or list(SUBSEGMENTS_BY_SEGMENT.keys()),
        "invited_user_ids": body.invited_user_ids or [],
        "employee_org_ids": body.employee_org_ids or [],
        "admin_overridden": is_admin and not is_publisher,
        "configured_by": user["user_id"],
        "configured_role": role,
        "updated_at": _now(),
    }
    await db.review_policies.update_one(
        {"solution_id": solution_id}, {"$set": doc}, upsert=True
    )
    await db.review_policies.create_index("solution_id", unique=True)
    return doc


# ---------------------------------------------------------------------------
# Moderation rule engine
# ---------------------------------------------------------------------------
def _avg(ratings: Dict[str, int]) -> float:
    if not ratings:
        return 0.0
    return sum(ratings.values()) / len(ratings)


def _evaluate_condition(c: dict, ctx: dict) -> bool:
    field = c["field"]
    val = c["value"]
    if field == "rating_min":
        return all(r >= val for r in ctx["ratings"].values())
    if field == "rating_max":
        return all(r <= val for r in ctx["ratings"].values())
    if field == "overall_min":
        return ctx["avg"] >= val
    if field == "overall_max":
        return ctx["avg"] <= val
    if field == "comment_max_length":
        return len(ctx["comment"] or "") <= val
    if field == "is_verified_buyer":
        return bool(ctx["is_verified_buyer"]) == bool(val)
    if field == "reviewer_min_prior_approved":
        return ctx["prior_approved"] >= val
    if field == "comment_contains_blocklist":
        text = (ctx["comment"] or "").lower()
        for w in (val or []):
            if w.lower() in text:
                return True
        return False
    return False


async def _evaluate_rules(ctx: dict) -> str:
    rules = await db.review_rules.find({"is_active": True}, {"_id": 0}).sort("priority", 1).to_list(200)
    for r in rules:
        try:
            if all(_evaluate_condition(c, ctx) for c in (r.get("conditions") or [])):
                return r["action"]
        except Exception as e:
            logger.warning("rule %s eval error: %s", r.get("rule_id"), e)
    return "HOLD_FOR_ADMIN"     # default


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@router.post("/reviews")
async def submit_review(body: ReviewSubmit, user: dict = Depends(get_current_user)):
    sol = await _resolve_solution(body.solution_id)

    # Eligibility check
    elig = await get_eligibility(body.solution_id, user)
    if not elig["is_eligible"]:
        raise HTTPException(403, f"not eligible: {elig['reason']}")

    pol = elig["policy"]
    if body.reviewer_segment not in (pol.get("allowed_segments") or list(SUBSEGMENTS_BY_SEGMENT.keys())):
        raise HTTPException(403, f"segment '{body.reviewer_segment}' not allowed for this solution")

    # Subsegment validation
    subseg = body.reviewer_subsegment
    if subseg and subseg not in SUBSEGMENTS_BY_SEGMENT[body.reviewer_segment]:
        raise HTTPException(400, f"invalid sub-segment '{subseg}' for segment {body.reviewer_segment}")

    # Verified buyer check
    bought = await db.time_store_purchases.find_one(
        {"solution_id": body.solution_id, "user_id": user["user_id"]}, {"_id": 1}
    )
    is_verified = bool(bought)

    # Prior approved review count
    prior_approved = await db.review_net.count_documents(
        {"reviewer_id": user["user_id"], "status": {"$in": ["approved", "auto_approved"]}}
    )

    avg = _avg(body.factor_ratings)
    ctx = {
        "ratings": body.factor_ratings,
        "avg": avg,
        "comment": body.comment,
        "is_verified_buyer": is_verified,
        "prior_approved": prior_approved,
    }
    action = await _evaluate_rules(ctx)
    if action == "AUTO_APPROVE":
        status = "auto_approved"
    elif action == "AUTO_REJECT":
        status = "rejected"
    else:
        status = "pending"

    review_id = f"rv_{uuid.uuid4().hex[:14]}"
    doc = {
        "review_id": review_id,
        "solution_id": body.solution_id,
        "solution_name": sol.get("name") or sol.get("title"),
        "catalog_node_id": sol.get("catalog_node_id"),
        "reviewer_id": user["user_id"],
        "reviewer_name": user.get("name") or user.get("email"),
        "reviewer_segment": body.reviewer_segment,
        "reviewer_subsegment": subseg,
        "factor_ratings": body.factor_ratings,
        "overall_rating": round(avg, 2),
        "title": body.title,
        "comment": body.comment,
        "is_verified_buyer": is_verified,
        "status": status,
        "moderation_action": action,
        "moderation_note": None,
        "helpful_yes_count": 0,
        "helpful_no_count": 0,
        "owner_reply": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.review_net.insert_one(doc)
    await db.review_net.create_index("solution_id")
    await db.review_net.create_index("reviewer_id")
    await db.review_net.create_index([("solution_id", 1), ("status", 1)])
    return _strip_id(doc)


@router.get("/reviews")
async def list_reviews(
    solution_id: str = Query(...),
    segment: Optional[str] = Query(None),
    subsegment: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}}
    if segment:
        q["reviewer_segment"] = segment
    if subsegment:
        q["reviewer_subsegment"] = subsegment
    cur = db.review_net.find(q, {"_id": 0}).sort("created_at", -1)
    items = [_strip_id(d) for d in await cur.to_list(200)]
    return {"items": items, "count": len(items)}


@router.get("/reviews/{review_id}")
async def get_review(review_id: str, user: dict = Depends(get_current_user)):
    rv = await db.review_net.find_one({"review_id": review_id}, {"_id": 0})
    if not rv:
        raise HTTPException(404, "review not found")
    return _strip_id(rv)


@router.post("/reviews/{review_id}/helpful")
async def vote_helpful(review_id: str, body: HelpfulVote, user: dict = Depends(get_current_user)):
    rv = await db.review_net.find_one({"review_id": review_id}, {"_id": 0})
    if not rv:
        raise HTTPException(404, "review not found")
    if rv["reviewer_id"] == user["user_id"]:
        raise HTTPException(400, "cannot vote on your own review")

    prev = await db.review_helpfulness.find_one(
        {"review_id": review_id, "user_id": user["user_id"]}, {"_id": 0}
    )

    inc: Dict[str, int] = {}
    if prev:
        # toggle / change
        if prev.get("helpful") == body.helpful:
            return {"ok": True, "noop": True}
        if prev["helpful"]:
            inc["helpful_yes_count"] = -1
        else:
            inc["helpful_no_count"] = -1

    if body.helpful:
        inc["helpful_yes_count"] = inc.get("helpful_yes_count", 0) + 1
    else:
        inc["helpful_no_count"] = inc.get("helpful_no_count", 0) + 1

    await db.review_net.update_one({"review_id": review_id}, {"$inc": inc, "$set": {"updated_at": _now()}})
    await db.review_helpfulness.update_one(
        {"review_id": review_id, "user_id": user["user_id"]},
        {"$set": {"helpful": body.helpful, "updated_at": _now()}},
        upsert=True,
    )
    return {"ok": True, "helpful": body.helpful}


@router.post("/reviews/{review_id}/reply")
async def owner_reply(review_id: str, body: OwnerReply, user: dict = Depends(get_current_user)):
    rv = await db.review_net.find_one({"review_id": review_id}, {"_id": 0})
    if not rv:
        raise HTTPException(404, "review not found")
    sol = await _resolve_solution(rv["solution_id"])
    role = (user.get("role") or "user").lower()
    is_admin = role in ("admin", "co_admin", "super_admin")
    is_owner = (sol.get("created_by") == user["user_id"]) or (sol.get("org_id") and sol.get("org_id") == user.get("org_id"))
    if not (is_owner or is_admin):
        raise HTTPException(403, "only the solution owner or admin can reply")

    reply = {
        "content": body.content,
        "by_user_id": user["user_id"],
        "by_user_name": user.get("name") or user.get("email"),
        "is_official": True,
        "created_at": _now(),
    }
    await db.review_net.update_one(
        {"review_id": review_id}, {"$set": {"owner_reply": reply, "updated_at": _now()}}
    )
    return reply


@router.get("/aggregates")
async def aggregates(solution_id: str = Query(...), user: dict = Depends(get_current_user)):
    """Return per-segment + overall aggregates per qualitative factor."""
    cur = db.review_net.find(
        {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}},
        {"_id": 0},
    )
    reviews = await cur.to_list(2000)
    if not reviews:
        return {"solution_id": solution_id, "total_reviews": 0, "segments": {}, "overall": {}}

    # segment -> factor_id -> [ratings]
    seg_buckets: Dict[str, Dict[str, List[int]]] = {}
    overall_buckets: Dict[str, List[int]] = {}
    seg_overall_sum: Dict[str, List[float]] = {}

    for r in reviews:
        seg = r.get("reviewer_segment") or "individual"
        seg_buckets.setdefault(seg, {})
        seg_overall_sum.setdefault(seg, [])
        seg_overall_sum[seg].append(float(r.get("overall_rating") or 0))
        for fid, rating in (r.get("factor_ratings") or {}).items():
            seg_buckets[seg].setdefault(fid, []).append(int(rating))
            overall_buckets.setdefault(fid, []).append(int(rating))

    def _avg(lst: List[float]) -> Dict[str, Any]:
        if not lst:
            return {"avg": 0, "count": 0}
        return {"avg": round(sum(lst) / len(lst), 2), "count": len(lst)}

    segments_out: Dict[str, Any] = {}
    for seg, by_fid in seg_buckets.items():
        per_factor = {fid: _avg(rs) for fid, rs in by_fid.items()}
        overall = _avg(seg_overall_sum.get(seg, []))
        segments_out[seg] = {"per_factor": per_factor, "overall": overall, "review_count": overall["count"]}

    overall_per_factor = {fid: _avg(rs) for fid, rs in overall_buckets.items()}
    overall_avg = sum([s["overall"]["avg"] * s["overall"]["count"] for s in segments_out.values()])
    total = sum([s["overall"]["count"] for s in segments_out.values()])
    overall_global = round((overall_avg / total) if total else 0, 2)

    return {
        "solution_id": solution_id,
        "total_reviews": total,
        "segments": segments_out,
        "overall": {"per_factor": overall_per_factor, "average": overall_global, "count": total},
    }


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------
@router.get("/admin/moderation-queue")
async def admin_queue(
    status: str = Query("pending"),
    user: dict = Depends(require_admin),
):
    q: Dict[str, Any] = {"status": status} if status != "all" else {}
    cur = db.review_net.find(q, {"_id": 0}).sort("created_at", 1)
    items = [_strip_id(d) for d in await cur.to_list(500)]
    return {"items": items, "count": len(items)}


@router.post("/admin/moderate/{review_id}")
async def admin_moderate(review_id: str, body: ReviewModerate, user: dict = Depends(require_admin)):
    rv = await db.review_net.find_one({"review_id": review_id}, {"_id": 0})
    if not rv:
        raise HTTPException(404, "review not found")
    new_status = "approved" if body.decision == "approve" else "rejected"
    await db.review_net.update_one(
        {"review_id": review_id},
        {"$set": {
            "status": new_status,
            "moderation_action": body.decision,
            "moderation_note": body.note,
            "moderated_by": user["user_id"],
            "updated_at": _now(),
        }},
    )
    return {"ok": True, "review_id": review_id, "status": new_status}


@router.get("/admin/rules")
async def list_rules(user: dict = Depends(require_admin)):
    cur = db.review_rules.find({}, {"_id": 0}).sort("priority", 1)
    return {"items": [_strip_id(d) for d in await cur.to_list(200)]}


@router.post("/admin/rules")
async def create_rule(body: ModerationRuleCreate, user: dict = Depends(require_admin)):
    rule_id = f"rl_{uuid.uuid4().hex[:10]}"
    doc = {
        "rule_id": rule_id,
        "name": body.name,
        "description": body.description,
        "conditions": [c.model_dump() for c in body.conditions],
        "action": body.action,
        "priority": body.priority,
        "is_active": True,
        "created_by": user["user_id"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.review_rules.insert_one(doc)
    await db.review_rules.create_index("rule_id", unique=True)
    return _strip_id(doc)


@router.put("/admin/rules/{rule_id}")
async def update_rule(rule_id: str, body: ModerationRuleUpdate, user: dict = Depends(require_admin)):
    existing = await db.review_rules.find_one({"rule_id": rule_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "rule not found")
    set_doc: Dict[str, Any] = {"updated_at": _now()}
    if body.name is not None: set_doc["name"] = body.name
    if body.description is not None: set_doc["description"] = body.description
    if body.conditions is not None: set_doc["conditions"] = [c.model_dump() for c in body.conditions]
    if body.action is not None: set_doc["action"] = body.action
    if body.priority is not None: set_doc["priority"] = body.priority
    if body.is_active is not None: set_doc["is_active"] = body.is_active
    await db.review_rules.update_one({"rule_id": rule_id}, {"$set": set_doc})
    return _strip_id(await db.review_rules.find_one({"rule_id": rule_id}, {"_id": 0}))


@router.delete("/admin/rules/{rule_id}")
async def delete_rule(rule_id: str, user: dict = Depends(require_admin)):
    res = await db.review_rules.delete_one({"rule_id": rule_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "rule not found")
    return {"ok": True}
