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
        "achievable": body.get("achievable", ""),
        "realistic": body.get("realistic", ""),
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
    update = {"updated_at": now}
    for f in ["title", "life_area", "challenge", "specific", "measurable", "achievable",
              "realistic", "timebound", "milestones", "priority", "status", "progress_pct", "notes"]:
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
