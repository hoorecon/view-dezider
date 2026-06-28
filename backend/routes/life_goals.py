"""
Life Goals — part of the "My 360° Life" module.

IMPORTANT: Life Goals are stored in **db.gem_goals** (the Goal Execution Manager
collection) — GEM is the central connector between goals and every other module
(Goal Setter, Solution Finder, MyDezider, Pros & Cons, Action Tracker, …). A Life
Goal is a GEM goal carrying extra hierarchy fields (`lg_mode`, `lg_level`,
`parent_id`, `horizon`, `sub_type`). Regular GEM goals have no `lg_mode`.

Two ways to plan:
  • Mode "timeline"  : per Life Area, a goal with a target horizon
                       (This Quarter / 1yr / 3yr / 5yr / 10yr) + optional sub-type.
  • Mode "tree"      : a strict 7-level hierarchy
        L1 Overall Life Goal
        L2 10-Year  →  L3 5-Year  →  L4 3-Year
        L5 1-Year    (mapped to a Life Area)
        L6 Quarterly (mapped to a sub-type)
        L7 Monthly
     Each child references its parent (parent_id); deleting a node cascades.

Sub-types stay in the user-mandated order:
  Present Problem · Need · Future Risk · Aspiration.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends

from core.database import db
from core.auth import get_current_user
from routes.pna import LIFE_AREAS

router = APIRouter(prefix="/life-goals", tags=["Life Goals"])

# ── Canonical sub-types (mirror frontend src/constants/decisionTypes.ts) ──
SUB_TYPES = [
    {"id": "problem",    "name": "Present Problem", "color": "#EF4444", "icon": "alert-circle"},
    {"id": "need",       "name": "Need",            "color": "#F59E0B", "icon": "bulb"},
    {"id": "risk",       "name": "Future Risk",     "color": "#F97316", "icon": "warning"},
    {"id": "aspiration", "name": "Aspiration",      "color": "#10B981", "icon": "rocket"},
]
SUB_TYPE_IDS = [s["id"] for s in SUB_TYPES]

# ── 7-level config ──
LEVELS = [
    {"level": 1, "key": "overall",   "label": "Overall Life Goal", "horizon": "Lifetime"},
    {"level": 2, "key": "10yr",      "label": "10-Year Goal",      "horizon": "10 years"},
    {"level": 3, "key": "5yr",       "label": "5-Year Goal",       "horizon": "5 years"},
    {"level": 4, "key": "3yr",       "label": "3-Year Goal",       "horizon": "3 years"},
    {"level": 5, "key": "1yr",       "label": "1-Year Goal",       "horizon": "1 year",   "requires_life_area": True},
    {"level": 6, "key": "quarterly", "label": "Quarterly Goal",    "horizon": "Quarter",  "requires_sub_type": True},
    {"level": 7, "key": "monthly",   "label": "Monthly Goal",      "horizon": "Month"},
]
MAX_LEVEL = 7

# Timeline-mode horizons
HORIZONS = [
    {"id": "quarter", "name": "This Quarter"},
    {"id": "1yr",     "name": "1 Year"},
    {"id": "3yr",     "name": "3 Years"},
    {"id": "5yr",     "name": "5 Years"},
    {"id": "10yr",    "name": "10 Years"},
]
HORIZON_IDS = [h["id"] for h in HORIZONS]

STATUS_OPTIONS = ["active", "done", "paused"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_progress(v) -> int:
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return 0


def _public(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("/meta")
async def get_meta():
    """Config for the Life Goals UI."""
    return {
        "life_areas": LIFE_AREAS,
        "sub_types": SUB_TYPES,
        "levels": LEVELS,
        "horizons": HORIZONS,
        "statuses": STATUS_OPTIONS,
    }


@router.post("")
async def create_goal(request: Request, user: dict = Depends(get_current_user)):
    """Create a Life Goal (mode = 'timeline' or 'tree'). Stored in db.gem_goals."""
    body = await request.json()
    mode = body.get("mode", "timeline")
    if mode not in ("timeline", "tree"):
        raise HTTPException(400, "mode must be 'timeline' or 'tree'")
    if not (body.get("title") or "").strip():
        raise HTTPException(400, "title is required")

    sub_type = body.get("sub_type") or None
    if sub_type and sub_type not in SUB_TYPE_IDS:
        raise HTTPException(400, f"sub_type must be one of {SUB_TYPE_IDS}")

    goal_id = str(uuid.uuid4())
    # goal_type powers GEM filters; mirror the sub-type when set (defaults to aspiration)
    goal_type = sub_type or body.get("goal_type") or "aspiration"

    doc: dict = {
        "goal_id": goal_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": body.get("title", "").strip(),
        "description": body.get("description", ""),
        "smart_goal": "",
        "life_area": body.get("life_area") or "",
        "goal_type": goal_type,
        "sub_type": sub_type,
        "priority": body.get("priority", "medium"),
        "status": body.get("status", "active"),
        "project_status": "open",
        "target_date": body.get("target_date") or None,
        "progress_percent": _clean_progress(body.get("progress", 0)),
        "linked_smart_goal_id": None,
        "linked_decisions": [],
        "linked_solution_finders": [],
        "linked_solution_matrices": [],
        # ── Life Goal hierarchy ──
        "lg_mode": mode,
        "period_label": body.get("period_label") or None,
        "created_at": _now(),
        "updated_at": _now(),
    }

    if mode == "timeline":
        horizon = body.get("horizon")
        if horizon not in HORIZON_IDS:
            raise HTTPException(400, f"horizon must be one of {HORIZON_IDS}")
        if not doc["life_area"]:
            raise HTTPException(400, "life_area is required for timeline goals")
        doc["horizon"] = horizon
        doc["lg_level"] = None
        doc["parent_id"] = None
    else:  # tree
        level = body.get("level")
        if level not in range(1, MAX_LEVEL + 1):
            raise HTTPException(400, "level must be 1..7 for tree goals")
        parent_id = body.get("parent_id")
        if level == 1 and parent_id:
            raise HTTPException(400, "L1 (Overall) cannot have a parent")
        if level > 1:
            if not parent_id:
                raise HTTPException(400, f"L{level} requires a parent_id (level {level - 1})")
            parent = await db.gem_goals.find_one(
                {"goal_id": parent_id, "user_id": user["user_id"]})
            if not parent:
                raise HTTPException(404, "Parent goal not found")
            if parent.get("lg_level") != level - 1:
                raise HTTPException(400, f"Parent must be a level {level - 1} goal")
        cfg = next((l for l in LEVELS if l["level"] == level), {})
        if cfg.get("requires_life_area") and not doc["life_area"]:
            raise HTTPException(400, "A 1-Year (L5) goal must be mapped to a Life Area")
        if cfg.get("requires_sub_type") and sub_type not in SUB_TYPE_IDS:
            raise HTTPException(400, "A Quarterly (L6) goal must be mapped to a sub-type")
        doc["lg_level"] = level
        doc["parent_id"] = parent_id or None
        doc["horizon"] = None

    await db.gem_goals.insert_one(doc)
    return _public(doc)


@router.get("")
async def list_goals(request: Request, user: dict = Depends(get_current_user)):
    """List Life Goals (gem_goals with an lg_mode). Filters: mode, level, parent_id, life_area."""
    params = request.query_params
    query: dict = {"user_id": user["user_id"], "lg_mode": {"$exists": True, "$ne": None}}
    if params.get("mode"):
        query["lg_mode"] = params["mode"]
    if params.get("level"):
        try:
            query["lg_level"] = int(params["level"])
        except ValueError:
            pass
    if "parent_id" in params:
        query["parent_id"] = params["parent_id"] or None
    if params.get("life_area"):
        query["life_area"] = params["life_area"]

    items = await db.gem_goals.find(query, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return items


@router.get("/tree")
async def get_tree(user: dict = Depends(get_current_user)):
    """Return all tree-mode Life Goals flat (client nests by parent_id)."""
    items = await db.gem_goals.find(
        {"user_id": user["user_id"], "lg_mode": "tree"}, {"_id": 0}
    ).sort("created_at", 1).to_list(2000)
    return {"levels": LEVELS, "goals": items}


@router.get("/{goal_id}")
async def get_goal(goal_id: str, user: dict = Depends(get_current_user)):
    doc = await db.gem_goals.find_one(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Life Goal not found")
    return doc


@router.put("/{goal_id}")
async def update_goal(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    existing = await db.gem_goals.find_one(
        {"goal_id": goal_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Life Goal not found")

    allowed = ["title", "description", "status", "life_area",
               "target_date", "horizon", "period_label", "priority"]
    update = {k: body[k] for k in allowed if k in body}
    if "sub_type" in body:
        st = body["sub_type"] or None
        if st and st not in SUB_TYPE_IDS:
            raise HTTPException(400, f"sub_type must be one of {SUB_TYPE_IDS}")
        update["sub_type"] = st
        if st:
            update["goal_type"] = st
    if "progress" in body:
        update["progress_percent"] = _clean_progress(body["progress"])
    if update.get("status") == "done" and "progress_percent" not in update:
        update["progress_percent"] = 100
    update["updated_at"] = _now()

    await db.gem_goals.update_one({"goal_id": goal_id}, {"$set": update})
    updated = await db.gem_goals.find_one({"goal_id": goal_id}, {"_id": 0})
    return updated


async def _collect_descendants(user_id: str, goal_id: str) -> list:
    """BFS down the parent_id chain to find every descendant goal_id."""
    to_delete = []
    frontier = [goal_id]
    while frontier:
        children = await db.gem_goals.find(
            {"user_id": user_id, "parent_id": {"$in": frontier}}, {"goal_id": 1, "_id": 0}
        ).to_list(2000)
        ids = [c["goal_id"] for c in children]
        if not ids:
            break
        to_delete.extend(ids)
        frontier = ids
    return to_delete


@router.delete("/{goal_id}")
async def delete_goal(goal_id: str, user: dict = Depends(get_current_user)):
    """Delete a Life Goal. Tree goals cascade-delete their descendants."""
    existing = await db.gem_goals.find_one(
        {"goal_id": goal_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Life Goal not found")

    ids = [goal_id]
    if existing.get("lg_mode") == "tree":
        ids += await _collect_descendants(user["user_id"], goal_id)

    result = await db.gem_goals.delete_many(
        {"goal_id": {"$in": ids}, "user_id": user["user_id"]})
    return {"deleted": result.deleted_count, "ids": ids}
