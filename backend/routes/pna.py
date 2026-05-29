"""
PNA — Problems / Needs / Aspirations Framework
Track and manage P/N/A items across 10 life areas.
Connects to decisions, goals, and other modules.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/pna", tags=["PNA Framework"])

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════

LIFE_AREAS = [
    {"id": "holistic_health", "name": "Holistic Health", "icon": "fitness", "color": "#10B981"},
    {"id": "knowledge_skills", "name": "Knowledge & Skills", "icon": "school", "color": "#3B82F6"},
    {"id": "relationships", "name": "Relationships", "icon": "heart", "color": "#EC4899"},
    {"id": "finance", "name": "Finance", "icon": "cash", "color": "#F59E0B"},
    {"id": "assets", "name": "Assets", "icon": "home", "color": "#8B5CF6"},
    {"id": "career", "name": "Career", "icon": "briefcase", "color": "#0EA5E9"},
    {"id": "personal_dreams", "name": "Personal Dreams", "icon": "star", "color": "#F97316"},
    {"id": "social_image", "name": "Social Image & Influence", "icon": "people", "color": "#6366F1"},
    {"id": "social_contributions", "name": "Social Contributions", "icon": "hand-left", "color": "#14B8A6"},
    {"id": "spirituality", "name": "Spirituality", "icon": "leaf", "color": "#A855F7"},
]

CATEGORIES = [
    {"id": "problem", "name": "Problem", "color": "#EF4444", "icon": "alert-circle"},
    {"id": "need", "name": "Need", "color": "#F59E0B", "icon": "bulb"},
    {"id": "aspiration", "name": "Aspiration", "color": "#10B981", "icon": "rocket"},
]

STATUS_OPTIONS = ["open", "in_progress", "resolved", "deferred", "converted"]
PRIORITY_OPTIONS = ["critical", "high", "medium", "low"]


@router.get("/meta")
async def get_meta():
    """Return life areas, categories, statuses, and priorities for the PNA module."""
    return {
        "life_areas": LIFE_AREAS,
        "categories": CATEGORIES,
        "statuses": STATUS_OPTIONS,
        "priorities": PRIORITY_OPTIONS,
    }


# ═══════════════════════════════════════════════════════════════
# PNA ITEMS CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/items")
async def create_item(request: Request, user: dict = Depends(get_current_user)):
    """Create a PNA item."""
    body = await request.json()
    item_id = f"PNA-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    category = body.get("category", "need")
    if category not in ["problem", "need", "aspiration"]:
        raise HTTPException(400, "category must be problem, need, or aspiration")

    doc = {
        "item_id": item_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "life_area": body.get("life_area", ""),
        "category": category,
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "priority": body.get("priority", "medium"),
        "status": body.get("status", "open"),
        "impact_score": body.get("impact_score", 5),  # 1-10
        "urgency_score": body.get("urgency_score", 5),  # 1-10
        "tags": body.get("tags", []),
        "linked_decision_id": body.get("linked_decision_id"),
        "linked_goal_id": body.get("linked_goal_id"),
        "linked_goal_title": body.get("linked_goal_title"),
        "action_plan": body.get("action_plan", ""),
        "target_date": body.get("target_date"),
        "resolved_date": None,
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    await db.pna_items.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/items")
async def list_items(request: Request, user: dict = Depends(get_current_user)):
    """List PNA items with filters."""
    params = request.query_params
    query: dict = {"user_id": user["user_id"]}

    if params.get("life_area"):
        query["life_area"] = params["life_area"]
    if params.get("category"):
        query["category"] = params["category"]
    if params.get("status"):
        query["status"] = params["status"]
    if params.get("priority"):
        query["priority"] = params["priority"]

    limit = int(params.get("limit", "200"))
    items = await db.pna_items.find(query, {"_id": 0}).sort("updated_at", -1).to_list(limit)
    return items


@router.get("/items/{item_id}")
async def get_item(item_id: str, user: dict = Depends(get_current_user)):
    """Get a single PNA item."""
    doc = await db.pna_items.find_one(
        {"item_id": item_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "PNA item not found")
    return doc


@router.put("/items/{item_id}")
async def update_item(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a PNA item."""
    body = await request.json()
    existing = await db.pna_items.find_one(
        {"item_id": item_id, "user_id": user["user_id"]}
    )
    if not existing:
        raise HTTPException(404, "PNA item not found")

    allowed = [
        "life_area", "category", "title", "description", "priority",
        "status", "impact_score", "urgency_score", "tags",
        "linked_decision_id", "linked_goal_id", "linked_goal_title", "action_plan",
        "target_date", "notes",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Auto-set resolved_date when status changes to resolved
    if body.get("status") == "resolved" and existing.get("status") != "resolved":
        update["resolved_date"] = datetime.now(timezone.utc).isoformat()
    elif body.get("status") and body["status"] != "resolved":
        update["resolved_date"] = None

    await db.pna_items.update_one({"item_id": item_id}, {"$set": update})
    updated = await db.pna_items.find_one({"item_id": item_id}, {"_id": 0})
    return updated


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, user: dict = Depends(get_current_user)):
    """Delete a PNA item."""
    result = await db.pna_items.delete_one(
        {"item_id": item_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "PNA item not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# BULK STATUS UPDATE
# ═══════════════════════════════════════════════════════════════

@router.post("/items/bulk-status")
async def bulk_update_status(request: Request, user: dict = Depends(get_current_user)):
    """Update status of multiple items at once."""
    body = await request.json()
    item_ids = body.get("item_ids", [])
    new_status = body.get("status", "")
    if new_status not in STATUS_OPTIONS:
        raise HTTPException(400, f"Invalid status. Use: {STATUS_OPTIONS}")
    if not item_ids:
        raise HTTPException(400, "No item_ids provided")

    now = datetime.now(timezone.utc).isoformat()
    update_data: dict = {"status": new_status, "updated_at": now}
    if new_status == "resolved":
        update_data["resolved_date"] = now

    result = await db.pna_items.update_many(
        {"item_id": {"$in": item_ids}, "user_id": user["user_id"]},
        {"$set": update_data}
    )
    return {"updated": result.modified_count}


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def pna_dashboard(user: dict = Depends(get_current_user)):
    """Get PNA dashboard — counts by area, category, status."""
    items = await db.pna_items.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(500)

    total = len(items)
    by_category = {"problem": 0, "need": 0, "aspiration": 0}
    by_status = {}
    by_area = {}
    by_priority = {}
    open_critical = 0

    for item in items:
        cat = item.get("category", "need")
        by_category[cat] = by_category.get(cat, 0) + 1

        st = item.get("status", "open")
        by_status[st] = by_status.get(st, 0) + 1

        area = item.get("life_area", "unclassified")
        if area not in by_area:
            by_area[area] = {"problem": 0, "need": 0, "aspiration": 0, "total": 0}
        by_area[area][cat] = by_area[area].get(cat, 0) + 1
        by_area[area]["total"] += 1

        pri = item.get("priority", "medium")
        by_priority[pri] = by_priority.get(pri, 0) + 1

        if st in ["open", "in_progress"] and pri in ["critical", "high"]:
            open_critical += 1

    # Build area summaries with metadata
    area_summaries = []
    for la in LIFE_AREAS:
        counts = by_area.get(la["id"], {"problem": 0, "need": 0, "aspiration": 0, "total": 0})
        area_summaries.append({
            "area_id": la["id"],
            "area_name": la["name"],
            "icon": la["icon"],
            "color": la["color"],
            **counts,
        })

    # Recent items
    recent = sorted(items, key=lambda x: x.get("updated_at", ""), reverse=True)[:5]

    return {
        "total": total,
        "by_category": by_category,
        "by_status": by_status,
        "by_priority": by_priority,
        "area_summaries": area_summaries,
        "open_critical": open_critical,
        "recent": recent,
    }


# ═══════════════════════════════════════════════════════════════
# AREA DETAIL
# ═══════════════════════════════════════════════════════════════

@router.get("/areas/{area_id}")
async def get_area_detail(area_id: str, user: dict = Depends(get_current_user)):
    """Get all PNA items for a specific life area, grouped by category."""
    items = await db.pna_items.find(
        {"user_id": user["user_id"], "life_area": area_id}, {"_id": 0}
    ).sort("priority", 1).to_list(200)

    area_meta = next((a for a in LIFE_AREAS if a["id"] == area_id), None)
    if not area_meta:
        raise HTTPException(404, "Life area not found")

    problems = [i for i in items if i.get("category") == "problem"]
    needs = [i for i in items if i.get("category") == "need"]
    aspirations = [i for i in items if i.get("category") == "aspiration"]

    return {
        "area": area_meta,
        "problems": problems,
        "needs": needs,
        "aspirations": aspirations,
        "total": len(items),
        "open_count": sum(1 for i in items if i.get("status") in ["open", "in_progress"]),
        "resolved_count": sum(1 for i in items if i.get("status") == "resolved"),
    }


# ═══════════════════════════════════════════════════════════════
# CONVERT PNA ITEM TO DECISION / GOAL
# ═══════════════════════════════════════════════════════════════

@router.post("/items/{item_id}/convert-to-decision")
async def convert_to_decision(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Create a PRR decision from a PNA item and link them."""
    item = await db.pna_items.find_one(
        {"item_id": item_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not item:
        raise HTTPException(404, "PNA item not found")

    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    cat_label = {"problem": "Problem", "need": "Need", "aspiration": "Aspiration"}.get(item["category"], "Item")
    decision_doc = {
        "id": decision_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": f"[{cat_label}] {item['title']}",
        "context": item.get("description", "") + (f"\n\nAction Plan: {item['action_plan']}" if item.get("action_plan") else ""),
        "factors": [],
        "options": [],
        "chosen_option_id": None,
        "decision_case": None,
        "notes": f"Auto-created from PNA item: {item_id}",
        "reflection": "",
        "final_notes": "",
        "folder": None,
        "life_area": item.get("life_area"),
        "decision_type": "standard",
        "rating_gap_multiplier": 1.0,
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
        "_source_pna_id": item_id,
    }
    await db.decisions.insert_one(decision_doc)

    # Link PNA item to decision
    await db.pna_items.update_one(
        {"item_id": item_id},
        {"$set": {
            "linked_decision_id": decision_id,
            "status": "converted",
            "updated_at": now,
        }}
    )

    return {"decision_id": decision_id, "message": f"Decision created from PNA {cat_label}"}


@router.post("/items/{item_id}/convert-to-goal")
async def convert_to_goal(item_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Create a GEM goal from a PNA item and link them."""
    item = await db.pna_items.find_one(
        {"item_id": item_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not item:
        raise HTTPException(404, "PNA item not found")

    goal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    goal_doc = {
        "goal_id": goal_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": item["title"],
        "description": item.get("description", ""),
        "life_area": item.get("life_area", ""),
        "priority": item.get("priority", "medium"),
        "status": "active",
        "progress": 0,
        "target_date": item.get("target_date"),
        "milestones": [],
        "tasks": [],
        "notes": f"Auto-created from PNA item: {item_id}",
        "created_at": now,
        "updated_at": now,
        "_source_pna_id": item_id,
    }
    await db.gem_goals.insert_one(goal_doc)

    # Link PNA item to goal
    await db.pna_items.update_one(
        {"item_id": item_id},
        {"$set": {
            "linked_goal_id": goal_id,
            "status": "converted",
            "updated_at": now,
        }}
    )

    return {"goal_id": goal_id, "message": "GEM Goal created from PNA item"}
