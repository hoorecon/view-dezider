"""Lifestyle Dezider (Routine Manager) + Lifestyle Analyzer (PRR-based Self-Assessment)."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

FREQUENCIES = ["hourly", "daily", "weekly", "fortnightly", "monthly"]
LIFE_AREAS = [
    "career", "finance", "relationships", "holistic_health", "assets",
    "knowledge_skills", "social_image", "social_contributions",
    "hobbies_entertainment", "spirituality_religion",
]


# ========================
# LIFESTYLE ROUTINES CRUD
# ========================

@router.post("/lifestyle/routines")
async def create_routine(request: Request, user: dict = Depends(get_current_user)):
    """Create a lifestyle routine."""
    body = await request.json()
    routine_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "routine_id": routine_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "name": body.get("name", ""),
        "description": body.get("description", ""),
        "life_area": body.get("life_area", ""),
        "frequency": body.get("frequency", "daily"),
        "time_slot": body.get("time_slot", ""),
        "priority": body.get("priority", "medium"),
        "category": body.get("category", "primary"),
        "expected_value": body.get("expected_value", ""),
        "unit": body.get("unit", ""),
        "is_active": body.get("is_active", True),
        "source_ctt_task_id": body.get("source_ctt_task_id"),
        "created_at": now,
        "updated_at": now,
    }
    await db.lifestyle_routines.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/lifestyle/routines")
async def list_routines(request: Request, user: dict = Depends(get_current_user)):
    """List all lifestyle routines."""
    query: dict = {"user_id": user["user_id"]}
    params = request.query_params

    if params.get("life_area"):
        query["life_area"] = params["life_area"]
    if params.get("frequency"):
        query["frequency"] = params["frequency"]
    if params.get("is_active") is not None:
        query["is_active"] = params.get("is_active", "true").lower() == "true"

    routines = await db.lifestyle_routines.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return routines


@router.get("/lifestyle/routines/{routine_id}")
async def get_routine(routine_id: str, user: dict = Depends(get_current_user)):
    routine = await db.lifestyle_routines.find_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")
    return routine


@router.put("/lifestyle/routines/{routine_id}")
async def update_routine(routine_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    routine = await db.lifestyle_routines.find_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    allowed = [
        "name", "description", "life_area", "frequency", "time_slot",
        "priority", "category", "expected_value", "unit", "is_active",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.lifestyle_routines.update_one({"routine_id": routine_id}, {"$set": update})
    updated = await db.lifestyle_routines.find_one({"routine_id": routine_id}, {"_id": 0})
    return updated


@router.delete("/lifestyle/routines/{routine_id}")
async def delete_routine(routine_id: str, user: dict = Depends(get_current_user)):
    result = await db.lifestyle_routines.delete_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Routine not found")
    return {"message": "Routine deleted"}


# ========================
# IMPORT FROM CTT
# ========================

@router.post("/lifestyle/import-from-ctt")
async def import_routines_from_ctt(user: dict = Depends(get_current_user)):
    """Import routine tasks from CTT into Lifestyle Routines. Deduplicates by source_ctt_task_id."""
    ctt_routines = await db.ctt_tasks.find(
        {"user_id": user["user_id"], "is_routine": True},
        {"_id": 0}
    ).to_list(200)

    existing_sources = set()
    existing = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "source_ctt_task_id": {"$ne": None}},
        {"source_ctt_task_id": 1}
    ).to_list(200)
    for e in existing:
        if e.get("source_ctt_task_id"):
            existing_sources.add(e["source_ctt_task_id"])

    imported = 0
    now = datetime.now(timezone.utc).isoformat()
    for task in ctt_routines:
        if task["task_id"] in existing_sources:
            continue

        doc = {
            "routine_id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "org_id": user.get("org_id"),
            "name": task.get("task", ""),
            "description": task.get("sub_task", "") or task.get("remarks", ""),
            "life_area": task.get("life_area", ""),
            "frequency": task.get("frequency", "daily"),
            "time_slot": task.get("from_time", ""),
            "priority": task.get("priority", "medium"),
            "category": "primary",
            "expected_value": "",
            "unit": "",
            "is_active": task.get("current_status") != "cancelled",
            "source_ctt_task_id": task["task_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.lifestyle_routines.insert_one(doc)
        imported += 1

    return {"imported": imported, "total_ctt_routines": len(ctt_routines)}


# ========================
# LIFESTYLE ANALYZER (PRR-based Assessment)
# ========================

@router.post("/lifestyle/start-assessment")
async def start_lifestyle_assessment(request: Request, user: dict = Depends(get_current_user)):
    """
    Create a new Lifestyle Analyzer assessment as a PRR Decision.
    - Factors = Active routines (grouped by frequency relevant to the period)
    - Single option = 'My Lifestyle' being assessed
    - Returns decision_id to navigate to the PRR flow.
    """
    body = await request.json()
    period = body.get("period", "daily")  # daily, weekly, monthly
    assessment_title = body.get("title", "")

    # Fetch active routines
    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0}
    ).to_list(200)

    if not routines:
        raise HTTPException(
            status_code=400,
            detail="No active routines found. Add routines to your Lifestyle Dezider first."
        )

    # Filter routines by frequency relevance to period
    freq_map = {
        "daily": ["hourly", "daily"],
        "weekly": ["hourly", "daily", "weekly"],
        "monthly": ["hourly", "daily", "weekly", "fortnightly", "monthly"],
    }
    relevant_freqs = freq_map.get(period, FREQUENCIES)
    relevant_routines = [r for r in routines if r.get("frequency", "daily") in relevant_freqs]

    if not relevant_routines:
        raise HTTPException(
            status_code=400,
            detail=f"No routines found for {period} assessment period."
        )

    # Build PRR factors from routines
    factors = []
    for idx, routine in enumerate(relevant_routines):
        factor_id = str(uuid.uuid4())
        factors.append({
            "id": factor_id,
            "name": routine["name"],
            "category": routine.get("category", "primary"),
            "rating": 0,
            "order": idx,
            "unit": routine.get("unit", ""),
            "expected_value": routine.get("expected_value", None),
            "data_type": None,
            "operator": None,
            "gap_multiplier": 1.0,
            "parent_id": None,
            "weight": None,
            # Extra metadata for lifestyle context
            "_routine_id": routine["routine_id"],
            "_frequency": routine.get("frequency", "daily"),
            "_life_area": routine.get("life_area", ""),
            "_time_slot": routine.get("time_slot", ""),
        })

    # Create the single option: "My Lifestyle"
    option_id = str(uuid.uuid4())
    option = {
        "id": option_id,
        "name": "My Lifestyle",
        "assessments": [],
        "worth_percentage": 0.0,
    }

    # Auto-generate title
    now = datetime.now(timezone.utc)
    if not assessment_title:
        date_str = now.strftime("%d %b %Y")
        assessment_title = f"Lifestyle Assessment ({period.title()}) - {date_str}"

    # Get user's org_id
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    org_id = user_doc.get("org_id") if user_doc else None

    decision_id = str(uuid.uuid4())
    decision_doc = {
        "id": decision_id,
        "user_id": user["user_id"],
        "org_id": org_id,
        "title": assessment_title,
        "context": f"Lifestyle effectiveness assessment ({period}) using PRR framework. "
                   f"Each routine is a factor. Rate how well 'My Lifestyle' meets each routine today.",
        "factors": factors,
        "options": [option],
        "chosen_option_id": None,
        "decision_case": None,
        "notes": "",
        "reflection": "",
        "final_notes": "",
        "folder": "lifestyle_analyzer",
        "life_area": None,
        "decision_type": "lifestyle_analyzer",
        "rating_gap_multiplier": 1.0,
        "mpps_option_id": None,
        "mpps_improvements": [],
        "mpps_projected_worth": None,
        "mpps_timeframe": None,
        "status": "in_progress",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        # Lifestyle-specific metadata
        "_lifestyle_period": period,
        "_routine_count": len(relevant_routines),
    }

    await db.decisions.insert_one(decision_doc)

    return {
        "decision_id": decision_id,
        "title": assessment_title,
        "factors_count": len(factors),
        "period": period,
        "message": "Lifestyle assessment created. Navigate to PRR flow to complete it.",
    }


@router.get("/lifestyle/assessments")
async def list_lifestyle_assessments(request: Request, user: dict = Depends(get_current_user)):
    """List completed lifestyle analyzer assessments (PRR decisions with folder=lifestyle_analyzer)."""
    params = request.query_params
    query: dict = {
        "user_id": user["user_id"],
        "folder": "lifestyle_analyzer",
    }
    if params.get("period"):
        query["_lifestyle_period"] = params["period"]

    assessments = await db.decisions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    results = []
    for a in assessments:
        # Extract effectiveness score from the single option
        options = a.get("options", [])
        effectiveness = options[0].get("worth_percentage", 0) if options else 0
        factors_count = len(a.get("factors", []))
        assessed_count = 0
        if options:
            assessed_count = len([
                ass for ass in options[0].get("assessments", [])
                if ass.get("percentage") is not None or ass.get("assessment_mode")
            ])

        results.append({
            "decision_id": a["id"],
            "title": a["title"],
            "period": a.get("_lifestyle_period", "daily"),
            "effectiveness_pct": round(effectiveness, 1),
            "factors_count": factors_count,
            "assessed_count": assessed_count,
            "status": a.get("status", "draft"),
            "created_at": a.get("created_at"),
            "is_complete": assessed_count >= factors_count and factors_count > 0,
        })

    return results


@router.get("/lifestyle/analytics")
async def lifestyle_analytics(request: Request, user: dict = Depends(get_current_user)):
    """Get lifestyle effectiveness trends over time."""
    params = request.query_params
    period = params.get("period", "daily")
    limit = int(params.get("limit", "30"))

    query: dict = {
        "user_id": user["user_id"],
        "folder": "lifestyle_analyzer",
    }
    if period != "all":
        query["_lifestyle_period"] = period

    assessments = await db.decisions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)

    # Build trend data
    trend = []
    area_scores: dict = {}
    total_effectiveness = 0
    completed_count = 0

    for a in assessments:
        options = a.get("options", [])
        effectiveness = options[0].get("worth_percentage", 0) if options else 0
        factors = a.get("factors", [])
        assessed = 0
        if options:
            assessed = len([
                ass for ass in options[0].get("assessments", [])
                if ass.get("percentage") is not None or ass.get("assessment_mode")
            ])
        is_complete = assessed >= len(factors) and len(factors) > 0

        if is_complete:
            completed_count += 1
            total_effectiveness += effectiveness

        created_str = a.get("created_at", "")
        if isinstance(created_str, str) and len(created_str) >= 10:
            date_str = created_str[:10]
        else:
            date_str = str(created_str)[:10] if created_str else ""

        trend.append({
            "date": date_str,
            "effectiveness": round(effectiveness, 1),
            "is_complete": is_complete,
            "period": a.get("_lifestyle_period", "daily"),
        })

        # Aggregate by life area (from factor metadata)
        for f in factors:
            area = f.get("_life_area", "other")
            if area:
                area_scores.setdefault(area, {"total": 0, "count": 0})
                # Get this factor's assessment percentage
                if options:
                    for ass in options[0].get("assessments", []):
                        if ass.get("factor_id") == f["id"] and ass.get("percentage") is not None:
                            area_scores[area]["total"] += ass["percentage"]
                            area_scores[area]["count"] += 1

    # Calculate area averages
    area_averages = {}
    for area, data in area_scores.items():
        area_averages[area] = round(data["total"] / max(data["count"], 1), 1)

    avg_effectiveness = round(total_effectiveness / max(completed_count, 1), 1) if completed_count > 0 else 0

    # Calculate streak (consecutive assessments with >= 60% effectiveness)
    streak = 0
    for t in trend:
        if t["is_complete"] and t["effectiveness"] >= 60:
            streak += 1
        else:
            break

    return {
        "trend": trend,
        "area_averages": area_averages,
        "avg_effectiveness": avg_effectiveness,
        "total_assessments": len(assessments),
        "completed_assessments": completed_count,
        "current_streak": streak,
    }


@router.get("/lifestyle/dashboard")
async def lifestyle_dashboard(user: dict = Depends(get_current_user)):
    """Overview stats for the Lifestyle Dezider."""
    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(200)

    active_routines = [r for r in routines if r.get("is_active", True)]

    # Count by frequency
    by_frequency: dict = {}
    for r in active_routines:
        freq = r.get("frequency", "daily")
        by_frequency[freq] = by_frequency.get(freq, 0) + 1

    # Count by life area
    by_area: dict = {}
    for r in active_routines:
        area = r.get("life_area", "other")
        by_area[area] = by_area.get(area, 0) + 1

    # Latest assessment
    latest = await db.decisions.find_one(
        {"user_id": user["user_id"], "folder": "lifestyle_analyzer"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    latest_effectiveness = 0
    latest_date = None
    if latest:
        options = latest.get("options", [])
        latest_effectiveness = options[0].get("worth_percentage", 0) if options else 0
        latest_date = latest.get("created_at")

    # Recent trend (last 7 assessments)
    recent = await db.decisions.find(
        {"user_id": user["user_id"], "folder": "lifestyle_analyzer"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(7)

    recent_scores = []
    for a in recent:
        opts = a.get("options", [])
        score = opts[0].get("worth_percentage", 0) if opts else 0
        recent_scores.append(round(score, 1))

    return {
        "total_routines": len(routines),
        "active_routines": len(active_routines),
        "by_frequency": by_frequency,
        "by_area": by_area,
        "latest_effectiveness": round(latest_effectiveness, 1),
        "latest_date": latest_date,
        "recent_scores": recent_scores,
    }
