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
from datetime import datetime, timedelta, timezone
from io import StringIO
import csv
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse

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


async def _evaluate_rules(ctx: dict) -> tuple[str, Optional[dict]]:
    """Returns (action, matched_rule_dict_or_None)."""
    rules = await db.review_rules.find({"is_active": True}, {"_id": 0}).sort("priority", 1).to_list(200)
    for r in rules:
        try:
            if all(_evaluate_condition(c, ctx) for c in (r.get("conditions") or [])):
                # Increment match counter (best-effort, fire-and-forget pattern)
                try:
                    await db.review_rules.update_one(
                        {"rule_id": r["rule_id"]},
                        {
                            "$inc": {
                                "match_count": 1,
                                f"action_counts.{r['action']}": 1,
                            },
                            "$set": {"last_matched_at": _now()},
                        },
                    )
                except Exception:
                    pass
                return r["action"], r
        except Exception as e:
            logger.warning("rule %s eval error: %s", r.get("rule_id"), e)
    return "HOLD_FOR_ADMIN", None     # default


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
    action, matched_rule = await _evaluate_rules(ctx)
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
        "matched_rule_id": matched_rule.get("rule_id") if matched_rule else None,
        "matched_rule_name": matched_rule.get("name") if matched_rule else None,
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
    # Notify owner / org of the new review (skip if review was auto-rejected)
    if status != "rejected":
        await _emit_review_notifications(doc, sol, kind="new_review")
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
    # Notify the original reviewer that the owner replied
    fresh_doc = await db.review_net.find_one({"review_id": review_id}, {"_id": 0}) or rv
    await _emit_review_notifications(fresh_doc, sol, kind="owner_reply")
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


# ---------------------------------------------------------------------------
# Rule analytics
# ---------------------------------------------------------------------------
@router.get("/admin/rules/analytics")
async def rule_analytics(user: dict = Depends(require_admin)):
    """Per-rule + global analytics: how many reviews each rule auto-handled,
    pending queue size, total reviews, action distribution, last 7-day trend."""

    # Per-rule rollup straight from the rules collection
    rules = await db.review_rules.find({}, {"_id": 0}).sort("priority", 1).to_list(200)
    rules_out: List[dict] = []
    for r in rules:
        action_counts = r.get("action_counts") or {}
        rules_out.append({
            "rule_id": r["rule_id"],
            "name": r["name"],
            "action": r["action"],
            "priority": r.get("priority", 100),
            "is_active": bool(r.get("is_active", True)),
            "match_count": int(r.get("match_count") or 0),
            "auto_approved": int(action_counts.get("AUTO_APPROVE") or 0),
            "auto_rejected": int(action_counts.get("AUTO_REJECT") or 0),
            "held": int(action_counts.get("HOLD_FOR_ADMIN") or 0),
            "last_matched_at": r.get("last_matched_at"),
            "conditions_count": len(r.get("conditions") or []),
        })

    # Global review-status distribution (cheap aggregate on indexed status)
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    cursor = db.review_net.aggregate(pipeline)
    status_dist: Dict[str, int] = {}
    async for row in cursor:
        status_dist[row["_id"] or "unknown"] = int(row["n"])

    total_reviews = sum(status_dist.values())
    pending = status_dist.get("pending", 0)
    auto_approved = status_dist.get("auto_approved", 0)
    approved = status_dist.get("approved", 0)
    rejected = status_dist.get("rejected", 0)

    # Reviews per matched_rule (for reviews where rule_id was stamped)
    pipe2 = [
        {"$match": {"matched_rule_id": {"$ne": None}}},
        {"$group": {
            "_id": {"rule_id": "$matched_rule_id", "rule_name": "$matched_rule_name"},
            "n": {"$sum": 1},
        }},
        {"$sort": {"n": -1}},
    ]
    by_rule: List[dict] = []
    async for row in db.review_net.aggregate(pipe2):
        by_rule.append({
            "rule_id": row["_id"]["rule_id"],
            "rule_name": row["_id"]["rule_name"],
            "review_count": int(row["n"]),
        })

    # 7-day trend (UTC midnights)
    trend: Dict[str, Dict[str, int]] = {}
    seven_days_ago = _now() - timedelta(days=7)
    cur = db.review_net.find(
        {"created_at": {"$gte": seven_days_ago}},
        {"_id": 0, "status": 1, "created_at": 1},
    )
    async for r in cur:
        d = r["created_at"]
        if isinstance(d, datetime):
            day = d.strftime("%Y-%m-%d")
        else:
            day = str(d)[:10]
        trend.setdefault(day, {"pending": 0, "auto_approved": 0, "approved": 0, "rejected": 0})
        s = r.get("status") or "pending"
        if s in trend[day]:
            trend[day][s] += 1

    return {
        "rules": rules_out,
        "global": {
            "total_reviews": total_reviews,
            "pending": pending,
            "auto_approved": auto_approved,
            "approved": approved,
            "rejected": rejected,
            "auto_rate_pct": round((auto_approved / total_reviews) * 100, 1) if total_reviews else 0,
            "manual_queue_pct": round((pending / total_reviews) * 100, 1) if total_reviews else 0,
        },
        "reviews_by_matched_rule": by_rule,
        "last_7_days": [
            {"day": day, **counts}
            for day, counts in sorted(trend.items())
        ],
    }



# ---------------------------------------------------------------------------
# My pending reviews (author-visible only)
# ---------------------------------------------------------------------------
@router.get("/my-pending")
async def my_pending(
    solution_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {"reviewer_id": user["user_id"], "status": "pending"}
    if solution_id:
        q["solution_id"] = solution_id
    cur = db.review_net.find(q, {"_id": 0}).sort("created_at", -1)
    items = [_strip_id(d) for d in await cur.to_list(50)]
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# CSV export / import (admin)
# ---------------------------------------------------------------------------
CSV_EXPORT_COLUMNS = [
    "review_id", "solution_id", "solution_name", "reviewer_name",
    "reviewer_segment", "reviewer_subsegment", "is_verified_buyer",
    "overall_rating", "title", "comment", "factor_ratings_json",
    "status", "moderation_action", "matched_rule_name",
    "helpful_yes_count", "helpful_no_count",
    "owner_reply_content", "created_at",
]


@router.get("/admin/reviews/export.csv")
async def export_reviews_csv(
    solution_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(require_admin),
):
    q: Dict[str, Any] = {}
    if solution_id:
        q["solution_id"] = solution_id
    if status:
        q["status"] = status

    if org_id:
        sol_ids = [
            s["solution_id"]
            async for s in db.solutions_store.find(
                {"$or": [{"org_id": org_id}, {"posted_by_org_id": org_id}]},
                {"_id": 0, "solution_id": 1},
            )
        ]
        if not sol_ids:
            return StreamingResponse(iter([",".join(CSV_EXPORT_COLUMNS) + "\n"]), media_type="text/csv")
        q["solution_id"] = {"$in": sol_ids}

    cursor = db.review_net.find(q, {"_id": 0}).sort("created_at", -1).limit(20000)

    async def _iter():
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(CSV_EXPORT_COLUMNS)
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)

        import json as _json
        async for r in cursor:
            row = [
                r.get("review_id", ""),
                r.get("solution_id", ""),
                r.get("solution_name", ""),
                r.get("reviewer_name", ""),
                r.get("reviewer_segment", ""),
                r.get("reviewer_subsegment", ""),
                "1" if r.get("is_verified_buyer") else "0",
                r.get("overall_rating", ""),
                r.get("title", ""),
                (r.get("comment") or "").replace("\r", " ").replace("\n", " "),
                _json.dumps(r.get("factor_ratings") or {}),
                r.get("status", ""),
                r.get("moderation_action", ""),
                r.get("matched_rule_name", ""),
                r.get("helpful_yes_count") or 0,
                r.get("helpful_no_count") or 0,
                ((r.get("owner_reply") or {}).get("content") or "").replace("\r", " ").replace("\n", " "),
                (r.get("created_at").isoformat() if isinstance(r.get("created_at"), datetime) else str(r.get("created_at") or "")),
            ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    headers = {
        "Content-Disposition": f"attachment; filename=review_net_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    }
    return StreamingResponse(_iter(), media_type="text/csv", headers=headers)


@router.post("/admin/reviews/import")
async def import_reviews_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    auto_status: str = Query("approved"),     # imported reviews land directly with this status
    user: dict = Depends(require_admin),
):
    """Import historical / customer-feedback reviews via CSV.
    Required columns: solution_id, reviewer_name, overall_rating
    Optional: reviewer_segment, reviewer_subsegment, comment, title, factor_ratings_json,
              is_verified_buyer (0/1), created_at (iso)
    """
    if auto_status not in ("approved", "auto_approved", "pending"):
        raise HTTPException(400, "auto_status must be approved | auto_approved | pending")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "CSV has no data rows")

    import json as _json
    ok = 0
    skipped: List[dict] = []
    sample_inserted: List[dict] = []

    # cache solutions to validate FK
    sol_cache: Dict[str, dict] = {}

    for idx, raw_row in enumerate(rows):
        try:
            sid = (raw_row.get("solution_id") or "").strip()
            if not sid:
                raise ValueError("missing solution_id")
            if sid not in sol_cache:
                sol_cache[sid] = await db.solutions_store.find_one({"solution_id": sid}, {"_id": 0}) or {}
            sol = sol_cache[sid]
            if not sol:
                raise ValueError(f"solution_id {sid} not found")

            seg = (raw_row.get("reviewer_segment") or "individual").strip()
            if seg not in SUBSEGMENTS_BY_SEGMENT:
                raise ValueError(f"invalid reviewer_segment '{seg}'")
            sub = (raw_row.get("reviewer_subsegment") or "").strip() or None
            if sub and sub not in SUBSEGMENTS_BY_SEGMENT[seg]:
                raise ValueError(f"invalid sub-segment '{sub}' for {seg}")

            try:
                overall = float(raw_row.get("overall_rating") or 0)
            except Exception:
                raise ValueError("overall_rating must be a number")

            factor_ratings: Dict[str, int] = {}
            fr_raw = (raw_row.get("factor_ratings_json") or "").strip()
            if fr_raw:
                try:
                    factor_ratings = {k: int(v) for k, v in _json.loads(fr_raw).items()}
                except Exception:
                    raise ValueError("factor_ratings_json is not valid JSON map of factor_id→1..5")

            doc = {
                "review_id": f"rv_imp_{uuid.uuid4().hex[:12]}",
                "solution_id": sid,
                "solution_name": sol.get("name") or sol.get("title"),
                "catalog_node_id": sol.get("catalog_node_id"),
                "reviewer_id": (raw_row.get("reviewer_id") or f"imported_{user['user_id']}").strip(),
                "reviewer_name": (raw_row.get("reviewer_name") or "Imported reviewer").strip(),
                "reviewer_segment": seg,
                "reviewer_subsegment": sub,
                "factor_ratings": factor_ratings,
                "overall_rating": round(overall, 2),
                "title": (raw_row.get("title") or "").strip() or None,
                "comment": (raw_row.get("comment") or "").strip() or None,
                "is_verified_buyer": (raw_row.get("is_verified_buyer") or "").strip() in ("1", "true", "True", "yes"),
                "status": auto_status,
                "moderation_action": "imported",
                "moderation_note": f"CSV imported by {user['user_id']}",
                "matched_rule_id": None,
                "matched_rule_name": None,
                "helpful_yes_count": 0,
                "helpful_no_count": 0,
                "owner_reply": None,
                "imported": True,
                "imported_at": _now(),
                "created_at": _now(),
                "updated_at": _now(),
            }

            ts = (raw_row.get("created_at") or "").strip()
            if ts:
                try:
                    doc["created_at"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    pass

            if not dry_run:
                await db.review_net.insert_one(doc)
                if len(sample_inserted) < 5:
                    sample_inserted.append({
                        "review_id": doc["review_id"],
                        "solution_id": doc["solution_id"],
                        "overall_rating": doc["overall_rating"],
                        "status": doc["status"],
                    })
            ok += 1

        except Exception as e:
            skipped.append({"row": idx + 2, "error": str(e), "raw": dict(list(raw_row.items())[:4])})

    if not dry_run:
        await db.review_net.create_index("imported")

    return {
        "ok": True,
        "dry_run": dry_run,
        "rows_total": len(rows),
        "rows_accepted": ok,
        "rows_skipped": len(skipped),
        "errors": skipped[:50],
        "sample_inserted": sample_inserted,
    }


# ---------------------------------------------------------------------------
# Notifications hooks (in-app + optional email/push if admin configured)
# ---------------------------------------------------------------------------
async def _emit_review_notifications(review_doc: dict, sol: dict, kind: str = "new_review"):
    """Push a notification when a new review is submitted, or when an owner
    replies. Channels are gated by `notifications_config` in DB; missing
    creds = silently disabled.
    `kind` is "new_review" or "owner_reply".
    """
    try:
        cfg = await db.notifications_config.find_one({"_id": "global"}, {"_id": 0}) or {}

        if kind == "new_review":
            # notify owner / org
            recipient_id = sol.get("created_by") or sol.get("posted_by_user_id")
            target_org = sol.get("org_id") or sol.get("posted_by_org_id")
            title = "New review on your listing"
            message = f"{review_doc.get('reviewer_name', 'Someone')} reviewed “{sol.get('name') or sol.get('title') or 'your solution'}” – {review_doc.get('overall_rating', '?')}/5"
            url = f"/tools/solution-detail?solution_id={review_doc.get('solution_id')}"
        elif kind == "owner_reply":
            recipient_id = review_doc.get("reviewer_id")
            target_org = None
            title = "The provider replied to your review"
            message = f"{(review_doc.get('owner_reply') or {}).get('by_user_name', 'Provider')} replied to your review of “{sol.get('name') or sol.get('title') or 'a solution'}”"
            url = f"/tools/solution-detail?solution_id={review_doc.get('solution_id')}"
        else:
            return

        # 1) in-app notification (always on)
        if cfg.get("in_app_enabled", True) and recipient_id:
            await db.notifications.insert_one({
                "id": f"nt_rn_{uuid.uuid4().hex[:10]}",
                "user_id": recipient_id,
                "title": title,
                "message": message,
                "type": "review_net",
                "read": False,
                "url": url,
                "created_at": _now(),
            })

        # 2) email (if configured + enabled)
        if cfg.get("email_enabled") and cfg.get("email_provider") and recipient_id:
            try:
                # MOCK send — real send wired when SendGrid/SMTP creds land
                await db.notifications_log.insert_one({
                    "channel": "email",
                    "kind": kind,
                    "to_user_id": recipient_id,
                    "to_org_id": target_org,
                    "title": title,
                    "message": message,
                    "provider": cfg.get("email_provider"),
                    "status": "queued_mock",
                    "created_at": _now(),
                })
            except Exception as e:
                logger.warning("email notification mock log error: %s", e)

        # 3) push (if configured + enabled)
        if cfg.get("push_enabled") and cfg.get("push_provider") and recipient_id:
            try:
                await db.notifications_log.insert_one({
                    "channel": "push",
                    "kind": kind,
                    "to_user_id": recipient_id,
                    "to_org_id": target_org,
                    "title": title,
                    "message": message,
                    "provider": cfg.get("push_provider"),
                    "status": "queued_mock",
                    "created_at": _now(),
                })
            except Exception as e:
                logger.warning("push notification mock log error: %s", e)
    except Exception as e:
        logger.warning("notification emit failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# Notifications config (admin)
# ---------------------------------------------------------------------------
@router.get("/admin/notifications-config")
async def get_notifications_config(user: dict = Depends(require_admin)):
    cfg = await db.notifications_config.find_one({"_id": "global"}, {"_id": 0}) or {}
    # mask credentials
    out = dict(cfg)
    for masked in ("email_api_key", "smtp_password", "push_server_key", "fcm_service_account"):
        if out.get(masked):
            out[masked] = "•••configured•••"
    return {
        "in_app_enabled": cfg.get("in_app_enabled", True),
        "email_enabled": cfg.get("email_enabled", False),
        "email_provider": cfg.get("email_provider") or "",        # sendgrid | smtp
        "email_from_address": cfg.get("email_from_address") or "",
        "email_api_key_set": bool(cfg.get("email_api_key")) or bool(cfg.get("smtp_password")),
        "smtp_host": cfg.get("smtp_host") or "",
        "smtp_port": cfg.get("smtp_port") or 587,
        "smtp_user": cfg.get("smtp_user") or "",
        "push_enabled": cfg.get("push_enabled", False),
        "push_provider": cfg.get("push_provider") or "",          # fcm | expo
        "push_credentials_set": bool(cfg.get("push_server_key")) or bool(cfg.get("fcm_service_account")),
        "updated_at": cfg.get("updated_at"),
    }


@router.put("/admin/notifications-config")
async def update_notifications_config(body: dict, user: dict = Depends(require_admin)):
    set_doc: Dict[str, Any] = {"_id": "global", "updated_at": _now(), "updated_by": user["user_id"]}

    bool_fields = ("in_app_enabled", "email_enabled", "push_enabled")
    str_fields = (
        "email_provider", "email_from_address",
        "smtp_host", "smtp_user",
        "push_provider",
    )
    secret_fields = ("email_api_key", "smtp_password", "push_server_key", "fcm_service_account")

    for f in bool_fields:
        if f in body:
            set_doc[f] = bool(body[f])
    for f in str_fields:
        if f in body and body[f] is not None:
            set_doc[f] = str(body[f]).strip()
    if "smtp_port" in body and body["smtp_port"]:
        try:
            set_doc["smtp_port"] = int(body["smtp_port"])
        except Exception:
            raise HTTPException(400, "smtp_port must be an integer")
    for f in secret_fields:
        if f in body and body[f] and body[f] != "•••configured•••":
            set_doc[f] = body[f]

    # Auto-disable a channel if creds are missing for its provider
    if set_doc.get("email_enabled"):
        provider = set_doc.get("email_provider")
        existing_cfg = await db.notifications_config.find_one({"_id": "global"}) or {}
        merged = {**existing_cfg, **set_doc}
        has_creds = (
            (provider == "sendgrid" and merged.get("email_api_key")) or
            (provider == "smtp" and merged.get("smtp_host") and merged.get("smtp_password"))
        )
        if not has_creds:
            set_doc["email_enabled"] = False
            set_doc["email_disabled_reason"] = "credentials missing"
    if set_doc.get("push_enabled"):
        provider = set_doc.get("push_provider")
        existing_cfg = await db.notifications_config.find_one({"_id": "global"}) or {}
        merged = {**existing_cfg, **set_doc}
        has_creds = (
            (provider == "fcm" and (merged.get("push_server_key") or merged.get("fcm_service_account"))) or
            (provider == "expo")    # Expo Push needs no API key for outgoing
        )
        if not has_creds:
            set_doc["push_enabled"] = False
            set_doc["push_disabled_reason"] = "credentials missing"

    await db.notifications_config.update_one({"_id": "global"}, {"$set": set_doc}, upsert=True)
    return await get_notifications_config(user)
