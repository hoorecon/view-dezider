"""
Public Help Feed — Collaboration Epic Phase C.

A decision owner can mark a step as "Ask the public for help". This publishes a
read-only snapshot of that step to a public feed where any signed-in user can
view and contribute suggestions. The owner reviews each contribution
(accept / dismiss), can close the request, and can merge accepted suggestions
back into their decision (new factors or options, depending on the step).

Collections:
  • public_help_posts          — one per (decision, step) ask
  • public_help_contributions  — community suggestions on a post
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.database import db
from core.helpers import create_notification
from core import karma as karma_engine

router = APIRouter(prefix="/public-help", tags=["Public Help Feed"])

STEP_NAMES = {
    1: "Context & Options", 2: "List Factors", 3: "Classify Factors", 4: "Prioritize Factors",
    5: "Calculate Ratings", 6: "Define Options", 7: "Assess & Calculate", 8: "Case-1 Results",
    9: "MPPS Analysis", 10: "Final Decision",
}
# steps whose accepted suggestions merge as OPTIONS rather than FACTORS
OPTION_STEPS = {6, 7}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip(d: dict) -> dict:
    if d and "_id" in d:
        d.pop("_id", None)
    return d


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class AskPublicRequest(BaseModel):
    step_number: int = Field(..., ge=1, le=10)
    message: str = Field("", max_length=1500)


class ContributeRequest(BaseModel):
    body: str = Field("", max_length=3000)
    suggestions: List[str] = Field(default_factory=list)   # discrete factor/option ideas


# ---------------------------------------------------------------------------
# owner: publish a step to the public feed
# ---------------------------------------------------------------------------
@router.post("/decisions/{decision_id}/ask-public")
async def ask_public(decision_id: str, body: AskPublicRequest, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")

    # idempotent: reuse an existing OPEN post for the same (decision, step)
    existing = await db.public_help_posts.find_one(
        {"decision_id": decision_id, "step_number": body.step_number, "status": "open"}, {"_id": 0}
    )
    if existing:
        if body.message:
            await db.public_help_posts.update_one(
                {"post_id": existing["post_id"]},
                {"$set": {"ask_message": body.message.strip(), "updated_at": _now()}},
            )
            existing["ask_message"] = body.message.strip()
        return _strip(existing)

    snapshot = {
        "factors": [
            {"id": f.get("id"), "name": f.get("name"), "category": f.get("category")}
            for f in decision.get("factors", [])
        ],
        "options": [
            {"id": o.get("id"), "name": o.get("name")} for o in decision.get("options", [])
        ],
    }
    post = {
        "post_id": f"php_{uuid.uuid4().hex[:12]}",
        "decision_id": decision_id,
        "owner_id": user["user_id"],
        "owner_name": user.get("name") or user.get("email"),
        "step_number": body.step_number,
        "step_name": STEP_NAMES.get(body.step_number, f"Step {body.step_number}"),
        "title": decision.get("title", ""),
        "context": decision.get("context", ""),
        "life_area_id": decision.get("life_area_id") or decision.get("life_area"),
        "snapshot": snapshot,
        "ask_message": body.message.strip(),
        "status": "open",
        "contribution_count": 0,
        "accepted_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.public_help_posts.insert_one(post)
    return _strip(post)


# ---------------------------------------------------------------------------
# public feed + detail
# ---------------------------------------------------------------------------
@router.get("/feed")
async def public_feed(
    search: Optional[str] = Query(None),
    step_number: Optional[int] = Query(None, ge=1, le=10),
    include_closed: bool = Query(False),
    limit: int = Query(50, le=200),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if not include_closed:
        q["status"] = "open"
    if step_number:
        q["step_number"] = step_number
    if search:
        import re
        rx = re.escape(search.strip())
        q["$or"] = [
            {"title": {"$regex": rx, "$options": "i"}},
            {"context": {"$regex": rx, "$options": "i"}},
            {"ask_message": {"$regex": rx, "$options": "i"}},
        ]
    cur = db.public_help_posts.find(q, {"_id": 0}).sort("created_at", -1)
    items = [_strip(d) for d in await cur.to_list(limit)]
    return {"items": items, "count": len(items)}


@router.get("/mine")
async def my_posts(user: dict = Depends(get_current_user)):
    cur = db.public_help_posts.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": [_strip(d) for d in await cur.to_list(100)]}


@router.get("/{post_id}")
async def get_post(post_id: str, user: dict = Depends(get_current_user)):
    post = await db.public_help_posts.find_one({"post_id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(404, "Help post not found")
    is_owner = post["owner_id"] == user["user_id"]
    cur = db.public_help_contributions.find({"post_id": post_id}, {"_id": 0}).sort("created_at", -1)
    contributions = [_strip(d) for d in await cur.to_list(300)]
    # non-owners see all (it's a public feed) but flag which is theirs
    for c in contributions:
        c["is_mine"] = c["contributor_id"] == user["user_id"]
    return {"post": _strip(post), "contributions": contributions, "is_owner": is_owner}


# ---------------------------------------------------------------------------
# contribute
# ---------------------------------------------------------------------------
@router.post("/{post_id}/contribute")
async def contribute(post_id: str, body: ContributeRequest, user: dict = Depends(get_current_user)):
    post = await db.public_help_posts.find_one({"post_id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(404, "Help post not found")
    if post["status"] != "open":
        raise HTTPException(409, "This help request is closed")
    if post["owner_id"] == user["user_id"]:
        raise HTTPException(400, "You cannot contribute to your own request")
    suggestions = [s.strip() for s in (body.suggestions or []) if s and s.strip()]
    if not body.body.strip() and not suggestions:
        raise HTTPException(400, "Add a note or at least one suggestion")
    doc = {
        "contribution_id": f"phc_{uuid.uuid4().hex[:12]}",
        "post_id": post_id,
        "decision_id": post["decision_id"],
        "contributor_id": user["user_id"],
        "contributor_name": user.get("name") or user.get("email"),
        "body": body.body.strip(),
        "suggestions": suggestions,
        "status": "pending",
        "created_at": _now(),
        "reviewed_at": None,
    }
    await db.public_help_contributions.insert_one(doc)
    await db.public_help_posts.update_one({"post_id": post_id}, {"$inc": {"contribution_count": 1}, "$set": {"updated_at": _now()}})
    try:
        await create_notification(
            post["owner_id"], "public_help",
            "New public contribution",
            f'{doc["contributor_name"]} responded to your public help request on "{post.get("title") or "a decision"}"',
            {"post_id": post_id},
        )
    except Exception:
        pass
    return _strip(doc)


# ---------------------------------------------------------------------------
# owner review
# ---------------------------------------------------------------------------
async def _require_owner_contribution(contribution_id: str, user: dict):
    c = await db.public_help_contributions.find_one({"contribution_id": contribution_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Contribution not found")
    post = await db.public_help_posts.find_one({"post_id": c["post_id"]}, {"_id": 0})
    if not post or post["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the request owner can review contributions")
    return c, post


@router.post("/contributions/{contribution_id}/accept")
async def accept_contribution(contribution_id: str, user: dict = Depends(get_current_user)):
    c, post = await _require_owner_contribution(contribution_id, user)
    if c["status"] == "accepted":
        return {"ok": True, "status": "accepted"}
    await db.public_help_contributions.update_one(
        {"contribution_id": contribution_id}, {"$set": {"status": "accepted", "reviewed_at": _now()}}
    )
    if c["status"] != "accepted":
        await db.public_help_posts.update_one({"post_id": c["post_id"]}, {"$inc": {"accepted_count": 1}})
    try:
        await karma_engine.award_karma(
            c["contributor_id"], "contribution_accepted",
            ref={"post_id": c["post_id"], "contribution_id": contribution_id},
            reason="Public-help contribution accepted",
        )
    except Exception:
        pass
    try:
        await create_notification(
            c["contributor_id"], "public_help",
            "Your contribution was accepted 🎉",
            f'{post.get("owner_name") or "The owner"} accepted your input on "{post.get("title") or "a decision"}"',
            {"post_id": c["post_id"]},
        )
    except Exception:
        pass
    return {"ok": True, "status": "accepted"}


@router.post("/contributions/{contribution_id}/dismiss")
async def dismiss_contribution(contribution_id: str, user: dict = Depends(get_current_user)):
    c, post = await _require_owner_contribution(contribution_id, user)
    was_accepted = c["status"] == "accepted"
    await db.public_help_contributions.update_one(
        {"contribution_id": contribution_id}, {"$set": {"status": "dismissed", "reviewed_at": _now()}}
    )
    if was_accepted:
        await db.public_help_posts.update_one({"post_id": c["post_id"]}, {"$inc": {"accepted_count": -1}})
    return {"ok": True, "status": "dismissed"}


@router.post("/{post_id}/close")
async def close_post(post_id: str, user: dict = Depends(get_current_user)):
    post = await db.public_help_posts.find_one({"post_id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(404, "Help post not found")
    if post["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the owner can close")
    await db.public_help_posts.update_one({"post_id": post_id}, {"$set": {"status": "closed", "updated_at": _now()}})
    return {"ok": True, "status": "closed"}


@router.post("/{post_id}/merge-accepted")
async def merge_accepted(post_id: str, user: dict = Depends(get_current_user)):
    """Append accepted suggestions into the decision as new factors (most steps)
    or new options (steps 6/7). De-duplicates by case-insensitive name."""
    post = await db.public_help_posts.find_one({"post_id": post_id}, {"_id": 0})
    if not post:
        raise HTTPException(404, "Help post not found")
    if post["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the owner can merge")
    decision = await db.decisions.find_one({"id": post["decision_id"], "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")

    accepted = await db.public_help_contributions.find(
        {"post_id": post_id, "status": "accepted"}, {"_id": 0}
    ).to_list(300)
    suggestions: List[str] = []
    for c in accepted:
        suggestions.extend(c.get("suggestions") or [])
    suggestions = [s.strip() for s in suggestions if s and s.strip()]
    if not suggestions:
        raise HTTPException(400, "No accepted suggestions to merge")

    as_options = post["step_number"] in OPTION_STEPS
    added = 0
    if as_options:
        options = decision.get("options", [])
        existing_names = {(o.get("name") or "").strip().lower() for o in options}
        for s in suggestions:
            if s.lower() in existing_names:
                continue
            options.append({"id": f"o_{uuid.uuid4().hex[:8]}", "name": s, "assessments": []})
            existing_names.add(s.lower())
            added += 1
        await db.decisions.update_one(
            {"id": post["decision_id"]},
            {"$set": {"options": options, "updated_at": datetime.now(timezone.utc)}},
        )
    else:
        factors = decision.get("factors", [])
        existing_names = {(f.get("name") or "").strip().lower() for f in factors}
        order = len(factors)
        for s in suggestions:
            if s.lower() in existing_names:
                continue
            factors.append({
                "id": f"f_{uuid.uuid4().hex[:8]}", "name": s, "category": "primary",
                "rating": 0, "order": order, "parent_id": None, "weight": None,
            })
            existing_names.add(s.lower())
            order += 1
            added += 1
        await db.decisions.update_one(
            {"id": post["decision_id"]},
            {"$set": {"factors": factors, "updated_at": datetime.now(timezone.utc)}},
        )
    return {"ok": True, "merged_as": "options" if as_options else "factors", "added": added}
