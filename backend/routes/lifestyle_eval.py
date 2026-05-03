"""
LEE — Lifestyle Effectiveness Evaluation
EVE Exercise #4: Track ACTUAL daily lifestyle vs PLANNED lifestyle.
Tracks time-slot activities across Weekdays, Saturday, Sunday.
Compares actual vs planned (from CTT, GEM, Routines).
"""
import uuid
from datetime import datetime, timezone, date as date_type
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# LIFE AREAS (same 10 areas as AALA for consistency)
# ═══════════════════════════════════════════════════════════════

LEE_LIFE_AREAS = [
    {"id": "holistic_health", "name": "Holistic Health", "icon": "fitness"},
    {"id": "knowledge_skills", "name": "Knowledge & Skills", "icon": "school"},
    {"id": "relationships", "name": "Relationships", "icon": "heart"},
    {"id": "finance", "name": "Finance", "icon": "cash"},
    {"id": "assets", "name": "Assets", "icon": "home"},
    {"id": "career", "name": "Career", "icon": "briefcase"},
    {"id": "personal_dreams", "name": "Personal Dreams Fulfillment", "icon": "star"},
    {"id": "social_image", "name": "Social Image & Influence", "icon": "people"},
    {"id": "social_contributions", "name": "Social Contributions", "icon": "hand-left"},
    {"id": "spirituality", "name": "Spirituality", "icon": "leaf"},
]

CATEGORIES = [
    {"id": "problem", "name": "Problem", "color": "#EF4444"},
    {"id": "need", "name": "Need", "color": "#F59E0B"},
    {"id": "aspiration", "name": "Aspiration", "color": "#10B981"},
]


# ═══════════════════════════════════════════════════════════════
# GET META (life areas + categories)
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/meta")
async def get_meta():
    """Return life areas and categories for the LEE module."""
    return {"life_areas": LEE_LIFE_AREAS, "categories": CATEGORIES}


# ═══════════════════════════════════════════════════════════════
# LOG DAILY ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.post("/lifestyle-eval/logs")
async def create_daily_log(request: Request, user: dict = Depends(get_current_user)):
    """Create or update a daily activity log."""
    body = await request.json()
    log_date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    day_type = body.get("day_type", "")

    # Auto-detect day_type from date if not provided
    if not day_type:
        try:
            d = datetime.strptime(log_date, "%Y-%m-%d")
            wd = d.weekday()  # 0=Mon, 5=Sat, 6=Sun
            if wd == 5:
                day_type = "saturday"
            elif wd == 6:
                day_type = "sunday"
            else:
                day_type = "weekday"
        except ValueError:
            day_type = "weekday"

    # Check if log already exists for this date
    existing = await db.lifestyle_eval_logs.find_one(
        {"user_id": user["user_id"], "date": log_date}
    )

    activities = body.get("activities", [])
    # Compute duration for each activity
    for act in activities:
        if not act.get("activity_id"):
            act["activity_id"] = f"ACT-{uuid.uuid4().hex[:8]}"
        # Auto-calc duration in minutes
        if act.get("from_time") and act.get("to_time"):
            act["duration_minutes"] = _calc_duration(act["from_time"], act["to_time"])

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        # Update existing
        await db.lifestyle_eval_logs.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "activities": activities,
                "day_type": day_type,
                "remarks": body.get("remarks", existing.get("remarks", "")),
                "updated_at": now,
            }}
        )
        log_id = existing.get("log_id")
    else:
        # Create new
        log_id = f"LEE-{uuid.uuid4().hex[:10].upper()}"
        doc = {
            "log_id": log_id,
            "user_id": user["user_id"],
            "org_id": user.get("org_id"),
            "date": log_date,
            "day_type": day_type,
            "activities": activities,
            "remarks": body.get("remarks", ""),
            "created_at": now,
            "updated_at": now,
        }
        await db.lifestyle_eval_logs.insert_one(doc)

    updated = await db.lifestyle_eval_logs.find_one(
        {"user_id": user["user_id"], "date": log_date}, {"_id": 0}
    )
    return updated


def _calc_duration(from_time: str, to_time: str) -> int:
    """Calculate duration in minutes between HH:MM times."""
    try:
        parts_from = from_time.split(":")
        parts_to = to_time.split(":")
        from_min = int(parts_from[0]) * 60 + int(parts_from[1])
        to_min = int(parts_to[0]) * 60 + int(parts_to[1])
        if to_min < from_min:
            to_min += 24 * 60  # next day
        return to_min - from_min
    except (ValueError, IndexError):
        return 0


# ═══════════════════════════════════════════════════════════════
# GET DAILY LOG
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/logs/{log_date}")
async def get_daily_log(log_date: str, user: dict = Depends(get_current_user)):
    """Get the activity log for a specific date."""
    doc = await db.lifestyle_eval_logs.find_one(
        {"user_id": user["user_id"], "date": log_date}, {"_id": 0}
    )
    if not doc:
        return {"date": log_date, "activities": [], "exists": False}
    doc["exists"] = True
    return doc


# ═══════════════════════════════════════════════════════════════
# LIST LOGS (DATE RANGE)
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/logs")
async def list_logs(request: Request, user: dict = Depends(get_current_user)):
    """List activity logs with optional date range and day_type filter."""
    params = request.query_params
    query = {"user_id": user["user_id"]}

    if params.get("day_type"):
        query["day_type"] = params["day_type"]
    if params.get("from_date") and params.get("to_date"):
        query["date"] = {"$gte": params["from_date"], "$lte": params["to_date"]}
    elif params.get("from_date"):
        query["date"] = {"$gte": params["from_date"]}

    limit = int(params.get("limit", "30"))
    docs = await db.lifestyle_eval_logs.find(query, {"_id": 0}).sort("date", -1).to_list(limit)
    return docs


# ═══════════════════════════════════════════════════════════════
# DELETE LOG
# ═══════════════════════════════════════════════════════════════

@router.delete("/lifestyle-eval/logs/{log_date}")
async def delete_log(log_date: str, user: dict = Depends(get_current_user)):
    """Delete a daily activity log."""
    result = await db.lifestyle_eval_logs.delete_one(
        {"user_id": user["user_id"], "date": log_date}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# SUMMARY / ANALYTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/summary")
async def get_summary(request: Request, user: dict = Depends(get_current_user)):
    """
    Get aggregated summary of time spent per life area across day types.
    Returns avg time per area for weekdays, saturday, sunday.
    """
    params = request.query_params
    limit = int(params.get("limit", "30"))

    logs = await db.lifestyle_eval_logs.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("date", -1).to_list(limit)

    # Aggregate by day_type → area_of_life → total_minutes, count
    agg = {}  # { day_type: { area: { total_min, count, categories: { cat: min } } } }
    day_counts = {"weekday": 0, "saturday": 0, "sunday": 0}

    for log in logs:
        dt = log.get("day_type", "weekday")
        day_counts[dt] = day_counts.get(dt, 0) + 1
        if dt not in agg:
            agg[dt] = {}

        for act in log.get("activities", []):
            area = act.get("area_of_life", "unclassified")
            dur = act.get("duration_minutes", 0)
            cat = act.get("category", "need")

            if area not in agg[dt]:
                agg[dt][area] = {"total_minutes": 0, "activity_count": 0, "categories": {}}
            agg[dt][area]["total_minutes"] += dur
            agg[dt][area]["activity_count"] += 1
            agg[dt][area]["categories"][cat] = agg[dt][area]["categories"].get(cat, 0) + dur

    # Compute averages
    summary = {}
    for dt, areas in agg.items():
        count = max(day_counts.get(dt, 1), 1)
        summary[dt] = {}
        for area, data in areas.items():
            summary[dt][area] = {
                "avg_minutes": round(data["total_minutes"] / count, 1),
                "total_minutes": data["total_minutes"],
                "activity_count": data["activity_count"],
                "days_tracked": count,
                "categories": {
                    cat: round(mins / count, 1) for cat, mins in data["categories"].items()
                },
            }

    return {
        "summary": summary,
        "day_counts": day_counts,
        "total_logs": len(logs),
        "life_areas": LEE_LIFE_AREAS,
    }


# ═══════════════════════════════════════════════════════════════
# PLANNED VS ACTUAL COMPARISON
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/planned-vs-actual")
async def planned_vs_actual(request: Request, user: dict = Depends(get_current_user)):
    """
    Compare actual lifestyle (from LEE logs) against planned lifestyle
    (derived from CTT tasks, Lifestyle Routines, and GEM goals).
    """
    params = request.query_params
    log_date = params.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # 1. Get actual activities for the date
    actual_log = await db.lifestyle_eval_logs.find_one(
        {"user_id": user["user_id"], "date": log_date}, {"_id": 0}
    )
    actual_activities = actual_log.get("activities", []) if actual_log else []

    # 2. Get planned tasks from CTT for this date
    ctt_tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"], "due_date": log_date, "status": {"$ne": "cancelled"}},
        {"_id": 0, "title": 1, "life_area": 1, "priority": 1, "status": 1, "estimated_hours": 1}
    ).to_list(100)

    # 3. Get active lifestyle routines
    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0, "name": 1, "life_area": 1, "frequency": 1, "time_slot": 1}
    ).to_list(100)

    # 4. Get active GEM goals
    gem_goals = await db.gem_goals.find(
        {"user_id": user["user_id"], "status": {"$in": ["active", "in_progress"]}},
        {"_id": 0, "title": 1, "life_area": 1, "priority": 1}
    ).to_list(50)

    # 5. Aggregate actual time by area
    actual_by_area = {}
    for act in actual_activities:
        area = act.get("area_of_life", "unclassified")
        dur = act.get("duration_minutes", 0)
        if area not in actual_by_area:
            actual_by_area[area] = {"total_minutes": 0, "activities": []}
        actual_by_area[area]["total_minutes"] += dur
        actual_by_area[area]["activities"].append({
            "activity": act.get("activity", ""),
            "from": act.get("from_time", ""),
            "to": act.get("to_time", ""),
            "duration": dur,
            "category": act.get("category", ""),
        })

    # 6. Aggregate planned by area
    planned_by_area = {}
    for task in ctt_tasks:
        area = task.get("life_area", "career")
        if area not in planned_by_area:
            planned_by_area[area] = {"tasks": [], "routines": [], "goals": []}
        planned_by_area[area]["tasks"].append(task.get("title", ""))

    for routine in routines:
        area = routine.get("life_area", "")
        if area:
            if area not in planned_by_area:
                planned_by_area[area] = {"tasks": [], "routines": [], "goals": []}
            planned_by_area[area]["routines"].append(routine.get("name", ""))

    for goal in gem_goals:
        area = goal.get("life_area", "")
        if area:
            if area not in planned_by_area:
                planned_by_area[area] = {"tasks": [], "routines": [], "goals": []}
            planned_by_area[area]["goals"].append(goal.get("title", ""))

    # 7. Build comparison
    all_areas = set(list(actual_by_area.keys()) + list(planned_by_area.keys()))
    comparison = []
    for area in sorted(all_areas):
        actual = actual_by_area.get(area, {"total_minutes": 0, "activities": []})
        planned = planned_by_area.get(area, {"tasks": [], "routines": [], "goals": []})
        has_planned = bool(planned["tasks"] or planned["routines"] or planned["goals"])
        has_actual = actual["total_minutes"] > 0

        comparison.append({
            "area_id": area,
            "area_name": next((a["name"] for a in LEE_LIFE_AREAS if a["id"] == area), area),
            "actual_minutes": actual["total_minutes"],
            "actual_activities": actual["activities"],
            "planned_tasks": planned.get("tasks", []),
            "planned_routines": planned.get("routines", []),
            "planned_goals": planned.get("goals", []),
            "has_planned": has_planned,
            "has_actual": has_actual,
            "gap": "covered" if has_planned and has_actual else
                   "missed" if has_planned and not has_actual else
                   "unplanned" if not has_planned and has_actual else "none",
        })

    return {
        "date": log_date,
        "comparison": comparison,
        "total_actual_minutes": sum(a["total_minutes"] for a in actual_by_area.values()),
        "planned_areas": len(planned_by_area),
        "actual_areas": len(actual_by_area),
    }


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/lifestyle-eval/dashboard")
async def lee_dashboard(user: dict = Depends(get_current_user)):
    """LEE dashboard — recent logs, coverage stats, top areas."""
    total_logs = await db.lifestyle_eval_logs.count_documents({"user_id": user["user_id"]})
    recent = await db.lifestyle_eval_logs.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("date", -1).to_list(7)

    # Recent week stats
    total_activities = 0
    total_minutes = 0
    area_minutes = {}
    for log in recent:
        for act in log.get("activities", []):
            total_activities += 1
            dur = act.get("duration_minutes", 0)
            total_minutes += dur
            area = act.get("area_of_life", "unclassified")
            area_minutes[area] = area_minutes.get(area, 0) + dur

    # Top areas
    top_areas = sorted(area_minutes.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_logs": total_logs,
        "recent_logs": [{"date": l["date"], "day_type": l.get("day_type", ""), "activity_count": len(l.get("activities", []))} for l in recent],
        "week_stats": {
            "total_activities": total_activities,
            "total_minutes": total_minutes,
            "total_hours": round(total_minutes / 60, 1),
            "areas_covered": len(area_minutes),
        },
        "top_areas": [{"area_id": a[0], "area_name": next((la["name"] for la in LEE_LIFE_AREAS if la["id"] == a[0]), a[0]), "minutes": a[1]} for a in top_areas],
    }
