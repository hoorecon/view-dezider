"""
Goal Setter Module — SMART Goal Framework
Helps users define goals using: Specific, Measurable, Achievable, Realistic, Time-bound.
Audio guide + structured SMART input + goal tracking.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/goal-setter", tags=["Goal Setter"])

# ═══════════════════════════════════════════════════════════════
# SMART FRAMEWORK DEFINITION
# ═══════════════════════════════════════════════════════════════

SMART_FRAMEWORK = {
    "description": "Define your best possible SMART goal. Focus on WHAT you really want without worrying about HOW.",
    "audio_url": "https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/unvj7j0c_Goal%20Setter.mp3",
    "fields": [
        {
            "id": "specific",
            "letter": "S",
            "name": "Specific",
            "prompt": "What exactly do you want to achieve? Mention the specificity here.",
            "hint": "Be precise about the outcome. E.g., 'Launch a SaaS product' not 'Start a business'",
            "color": "#3B82F6",
        },
        {
            "id": "measurable",
            "letter": "M",
            "name": "Measurable",
            "prompt": "How will you measure progress and success? Mention the metric here.",
            "hint": "E.g., '₹10L MRR within 12 months' or '50 paying customers'",
            "color": "#10B981",
        },
        {
            "id": "achievable",
            "letter": "A",
            "name": "Achievable",
            "prompt": "Is it achievable with your current capabilities and resources?",
            "hint": "Assess your skills, knowledge, finances, and support network",
            "color": "#F59E0B",
        },
        {
            "id": "realistic",
            "letter": "R",
            "name": "Realistic",
            "prompt": "Is it realistic in the world or environment you are going to be working in?",
            "hint": "Consider market conditions, competition, timing, and external factors",
            "color": "#8B5CF6",
        },
        {
            "id": "timebound",
            "letter": "T",
            "name": "Time-bound",
            "prompt": "What is the timeline? Specify milestones if possible.",
            "hint": "E.g., 'By Dec 2026: MVP launch. By Mar 2027: 20 customers. By Jun 2027: ₹10L MRR'",
            "color": "#EF4444",
        },
    ],
}


@router.get("/framework")
async def get_framework():
    """Return the SMART framework definition with audio URL."""
    return SMART_FRAMEWORK


# ═══════════════════════════════════════════════════════════════
# CRUD — SMART Goals
# ═══════════════════════════════════════════════════════════════

@router.post("/goals")
async def create_goal(request: Request, user: dict = Depends(get_current_user)):
    """Create a new SMART goal."""
    body = await request.json()
    goal_id = f"GOAL-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "goal_id": goal_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": body.get("title", ""),
        "life_area": body.get("life_area", ""),
        "challenge": body.get("challenge", ""),
        # SMART fields
        "specific": body.get("specific", ""),
        "measurable": body.get("measurable", ""),
        # New: structured metric array for Measurable section
        # Each metric: { name, unit, type, operator, target_value, set_by, owner_role }
        "metrics": body.get("metrics", []),
        "achievable": body.get("achievable", ""),
        # ── Phase-2: Skills selected from Contacts (Self / Others) for Achievable ──
        "achievable_skills": body.get("achievable_skills", []),
        "realistic": body.get("realistic", ""),
        # ── Phase-3: Resources & social links picked from Contacts for Realistic ──
        "realistic_resources": body.get("realistic_resources", []),
        "timebound": body.get("timebound", ""),
        "milestones": body.get("milestones", []),
        # Meta
        "priority": body.get("priority", "medium"),
        "status": body.get("status", "active"),
        "progress_pct": body.get("progress_pct", 0),
        "notes": body.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    await db.smart_goals.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/goals")
async def list_goals(request: Request, user: dict = Depends(get_current_user)):
    """List all SMART goals for the user."""
    query = {"user_id": user["user_id"]}
    params = request.query_params
    if params.get("status"):
        query["status"] = params["status"]
    if params.get("life_area"):
        query["life_area"] = params["life_area"]

    docs = await db.smart_goals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, user: dict = Depends(get_current_user)):
    doc = await db.smart_goals.find_one(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Goal not found")
    return doc


@router.put("/goals/{goal_id}")
async def update_goal(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    allowed = [
        "title", "life_area", "challenge", "specific", "measurable", "metrics",
        "achievable", "achievable_skills",
        "realistic", "realistic_resources",
        "timebound", "milestones",
        "priority", "status", "progress_pct", "notes",
    ]
    update = {"updated_at": now}
    for f in allowed:
        if f in body:
            update[f] = body[f]

    result = await db.smart_goals.update_one(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    doc = await db.smart_goals.find_one({"goal_id": goal_id}, {"_id": 0})
    return doc


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, user: dict = Depends(get_current_user)):
    result = await db.smart_goals.delete_one(
        {"goal_id": goal_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# MILESTONES — recursive mini-SMART grids under a Goal
# ═══════════════════════════════════════════════════════════════

VALID_MILESTONE_STATUSES = {"pending", "in_progress", "done", "blocked"}


def _make_milestone(body: dict) -> dict:
    """Build a milestone doc from request body (defensive defaults)."""
    return {
        "milestone_id": body.get("milestone_id") or f"ms_{uuid.uuid4().hex[:10]}",
        "title": (body.get("title") or "").strip(),
        "specific": body.get("specific", ""),
        "measurable": body.get("measurable", ""),
        "metrics": body.get("metrics", []),
        "achievable": body.get("achievable", ""),
        "achievable_skills": body.get("achievable_skills", []),
        "realistic": body.get("realistic", ""),
        "realistic_resources": body.get("realistic_resources", []),
        "timebound": body.get("timebound", ""),
        "target_date": body.get("target_date") or "",
        "order": int(body.get("order") or 0),
        "status": body.get("status", "pending") if body.get("status") in VALID_MILESTONE_STATUSES else "pending",
        "progress_pct": max(0, min(100, int(body.get("progress_pct") or 0))),
        "notes": body.get("notes", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/goals/{goal_id}/milestones")
async def add_milestone(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    goal = await db.smart_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    body = await request.json()
    milestone = _make_milestone(body)
    milestones = list(goal.get("milestones") or [])
    milestone["order"] = len(milestones)
    milestones.append(milestone)
    await db.smart_goals.update_one(
        {"goal_id": goal_id},
        {"$set": {"milestones": milestones, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return milestone


@router.put("/goals/{goal_id}/milestones/{milestone_id}")
async def update_milestone(
    goal_id: str, milestone_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    body = await request.json()
    goal = await db.smart_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = list(goal.get("milestones") or [])
    idx = next((i for i, m in enumerate(milestones) if m.get("milestone_id") == milestone_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Milestone not found")

    allowed = [
        "title", "specific", "measurable", "metrics",
        "achievable", "achievable_skills",
        "realistic", "realistic_resources",
        "timebound", "target_date", "order",
        "status", "progress_pct", "notes",
    ]
    for f in allowed:
        if f in body:
            if f == "status" and body[f] not in VALID_MILESTONE_STATUSES:
                continue
            if f == "progress_pct":
                milestones[idx][f] = max(0, min(100, int(body[f] or 0)))
            else:
                milestones[idx][f] = body[f]
    milestones[idx]["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.smart_goals.update_one(
        {"goal_id": goal_id},
        {"$set": {"milestones": milestones, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return milestones[idx]


@router.delete("/goals/{goal_id}/milestones/{milestone_id}")
async def delete_milestone(
    goal_id: str, milestone_id: str,
    user: dict = Depends(get_current_user),
):
    goal = await db.smart_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = [m for m in (goal.get("milestones") or []) if m.get("milestone_id") != milestone_id]
    # Reindex order
    for i, m in enumerate(milestones):
        m["order"] = i
    await db.smart_goals.update_one(
        {"goal_id": goal_id},
        {"$set": {"milestones": milestones, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"deleted": True, "remaining": len(milestones)}


@router.put("/goals/{goal_id}/milestones/{milestone_id}/status")
async def update_milestone_status(
    goal_id: str, milestone_id: str,
    request: Request, user: dict = Depends(get_current_user),
):
    """Lightweight status/progress updater — used by GEM read-only execution view."""
    body = await request.json()
    new_status = body.get("status")
    progress = body.get("progress_pct")
    if new_status and new_status not in VALID_MILESTONE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    goal = await db.smart_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = list(goal.get("milestones") or [])
    idx = next((i for i, m in enumerate(milestones) if m.get("milestone_id") == milestone_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if new_status:
        milestones[idx]["status"] = new_status
        if new_status == "done":
            milestones[idx]["progress_pct"] = 100
    if progress is not None:
        milestones[idx]["progress_pct"] = max(0, min(100, int(progress or 0)))
    milestones[idx]["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.smart_goals.update_one(
        {"goal_id": goal_id},
        {"$set": {"milestones": milestones, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return milestones[idx]


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def goal_dashboard(user: dict = Depends(get_current_user)):
    goals = await db.smart_goals.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    active = [g for g in goals if g.get("status") == "active"]
    completed = [g for g in goals if g.get("status") == "completed"]
    avg_progress = round(sum(g.get("progress_pct", 0) for g in active) / max(len(active), 1), 1)

    return {
        "total_goals": len(goals),
        "active_goals": len(active),
        "completed_goals": len(completed),
        "avg_progress": avg_progress,
        "recent_goals": goals[:5],
    }
