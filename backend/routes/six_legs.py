"""6 LeGs — 6 Level Goal Setting (per Custom Org only).

Levels:
  L1 Financial
  L2 Customer/Solution
  L3 7 Divisions (uses 7×7 master)
  L4 Team
  L5 Individual
  L6 L&D (Attitude/Knowledge/Skill)

Each goal can be linked into the existing Goal Setter via `goal_setter_id`,
and creates downstream Action Items / CTT / Lifestyle Dezider entries.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/six-legs", tags=["6 LeGs"])

VALID_LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")
LEVEL_LABELS = {
    "L1": "Financial",
    "L2": "Customer / Solution",
    "L3": "7 Divisions (Strategic)",
    "L4": "Team",
    "L5": "Individual",
    "L6": "Learning & Development",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LegGoalIn(BaseModel):
    user_org_id: str
    level: str  # L1..L6
    parent_goal_id: Optional[str] = None  # parent in the tree
    title: str
    description: Optional[str] = ""
    # Optional metrics by level
    metric_label: Optional[str] = ""
    metric_target: Optional[str] = ""
    metric_unit: Optional[str] = ""
    target_date: Optional[str] = None  # YYYY-MM-DD
    owner_name: Optional[str] = ""
    owner_contact_id: Optional[str] = None
    division_code: Optional[str] = None  # required when level=L3
    sub_team_code: Optional[str] = None
    status: str = "pending"  # pending|in_progress|on_track|at_risk|done
    # Optional bind into Goal Setter module
    goal_setter_id: Optional[str] = None
    notes: Optional[str] = ""


async def _own_org(user, user_org_id: str) -> dict:
    org = await db.user_orgs.find_one({"id": user_org_id, "owner_user_id": user["user_id"]})
    if not org:
        raise HTTPException(404, "User-Org not found or not yours")
    return org


@router.post("/goals")
async def create_goal(p: LegGoalIn, user: dict = Depends(get_current_user)):
    if p.level not in VALID_LEVELS:
        raise HTTPException(400, f"level must be one of {VALID_LEVELS}")
    await _own_org(user, p.user_org_id)
    if p.level == "L3" and not p.division_code:
        raise HTTPException(400, "division_code is required for L3 goals")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        **p.model_dump(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.six_legs_goals.insert_one(doc)
    doc.pop("_id", None)
    return {"goal": doc}


@router.get("/goals")
async def list_goals(
    user_org_id: str,
    level: Optional[str] = None,
    parent_goal_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    await _own_org(user, user_org_id)
    q: Dict[str, Any] = {"user_org_id": user_org_id, "user_id": user["user_id"]}
    if level:
        q["level"] = level
    if parent_goal_id:
        q["parent_goal_id"] = parent_goal_id
    rows = await db.six_legs_goals.find(q, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return {"goals": rows}


@router.get("/goals/tree/{user_org_id}")
async def goal_tree(user_org_id: str, user: dict = Depends(get_current_user)):
    """Return full hierarchy nested by level + parent."""
    await _own_org(user, user_org_id)
    rows = await db.six_legs_goals.find(
        {"user_org_id": user_org_id, "user_id": user["user_id"]},
        {"_id": 0},
    ).sort("created_at", 1).to_list(5000)
    by_id = {r["id"]: {**r, "children": []} for r in rows}
    roots: List[Dict[str, Any]] = []
    for r in rows:
        node = by_id[r["id"]]
        pid = r.get("parent_goal_id")
        if pid and pid in by_id:
            by_id[pid]["children"].append(node)
        else:
            roots.append(node)
    return {
        "tree": roots,
        "level_labels": LEVEL_LABELS,
        "total_goals": len(rows),
    }


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, p: LegGoalIn, user: dict = Depends(get_current_user)):
    existing = await db.six_legs_goals.find_one({"id": goal_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Not found")
    await db.six_legs_goals.update_one(
        {"id": goal_id},
        {"$set": {**p.model_dump(), "updated_at": _now()}},
    )
    return {"ok": True}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, user: dict = Depends(get_current_user)):
    # Soft cascade: also remove children
    async def _delete_recursive(gid: str):
        children = await db.six_legs_goals.find({"parent_goal_id": gid, "user_id": user["user_id"]}).to_list(500)
        for c in children:
            await _delete_recursive(c["id"])
        await db.six_legs_goals.delete_one({"id": gid, "user_id": user["user_id"]})
    existing = await db.six_legs_goals.find_one({"id": goal_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Not found")
    await _delete_recursive(goal_id)
    return {"ok": True}


@router.post("/goals/{goal_id}/convert-to-action")
async def convert_goal_to_action(goal_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Convert a leaf goal into a universal Action Item (which can then port to CTT or Lifestyle)."""
    g = await db.six_legs_goals.find_one({"id": goal_id, "user_id": user["user_id"]}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Not found")
    rec_type = (body.get("recurrence_type") or "one_time").lower()
    doc = {
        "action_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "source_module": "GOAL_SETTER",
        "source_id": goal_id,
        "source_label": f"6 LeGs · {LEVEL_LABELS.get(g.get('level'), g.get('level'))} · {g.get('title','')[:60]}",
        "source_subref": g.get("level"),
        "title": g.get("title"),
        "description": g.get("description") or "",
        "who": g.get("owner_name") or "",
        "by_when": g.get("target_date"),
        "recurrence_type": rec_type,
        "recurrence_frequency": body.get("recurrence_frequency") or ("daily" if rec_type == "recurring" else None),
        "recurrence_days": [],
        "recurrence_time": None,
        "recurrence_end_date": None,
        "priority": body.get("priority") or "medium",
        "status": "pending",
        "progress_pct": 0,
        "life_area": None,
        "notes": g.get("notes") or "",
        "ported_to": None, "ported_ref_id": None, "ported_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.action_items.insert_one(doc)
    doc.pop("_id", None)
    return {"action_item": doc}
