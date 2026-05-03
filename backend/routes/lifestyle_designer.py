"""
Lifestyle Designer — Plan your ideal lifestyle allocation across 10 life areas.
Compare planned vs actual (from LEE logs). Manual override for actuals.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/lifestyle-designer", tags=["Lifestyle Designer"])

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

DAY_TYPES = ["weekday", "saturday", "sunday"]


@router.get("/meta")
async def get_meta():
    """Return life areas and day types."""
    return {"life_areas": LIFE_AREAS, "day_types": DAY_TYPES}


# ═══════════════════════════════════════════════════════════════
# PLAN CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/plans")
async def create_plan(request: Request, user: dict = Depends(get_current_user)):
    """Create a lifestyle plan.

    Body:
    {
        "name": "My Ideal Lifestyle",
        "description": "...",
        "allocations": {
            "weekday": {
                "holistic_health": { "hours": 2, "priority": "high", "notes": "" },
                "career": { "hours": 8, "priority": "high", "notes": "" },
                ...
            },
            "saturday": { ... },
            "sunday": { ... }
        }
    }
    """
    body = await request.json()
    plan_id = f"LDP-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # Validate allocations structure
    allocations = body.get("allocations", {})
    validated_allocs = {}
    for dt in DAY_TYPES:
        dt_allocs = allocations.get(dt, {})
        validated_allocs[dt] = {}
        for la in LIFE_AREAS:
            area_data = dt_allocs.get(la["id"], {})
            validated_allocs[dt][la["id"]] = {
                "hours": max(0, min(24, float(area_data.get("hours", 0)))),
                "priority": area_data.get("priority", "medium"),
                "notes": area_data.get("notes", ""),
            }

    doc = {
        "plan_id": plan_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "name": body.get("name", "My Lifestyle Plan"),
        "description": body.get("description", ""),
        "allocations": validated_allocs,
        "is_active": body.get("is_active", False),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }

    # If is_active, deactivate others first
    if doc["is_active"]:
        await db.lifestyle_plans.update_many(
            {"user_id": user["user_id"], "is_active": True},
            {"$set": {"is_active": False}}
        )
        doc["status"] = "active"

    await db.lifestyle_plans.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    """List all lifestyle plans."""
    plans = await db.lifestyle_plans.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return plans


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, user: dict = Depends(get_current_user)):
    """Get a specific plan."""
    doc = await db.lifestyle_plans.find_one(
        {"plan_id": plan_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Plan not found")
    return doc


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a lifestyle plan."""
    body = await request.json()
    existing = await db.lifestyle_plans.find_one(
        {"plan_id": plan_id, "user_id": user["user_id"]}
    )
    if not existing:
        raise HTTPException(404, "Plan not found")

    now = datetime.now(timezone.utc).isoformat()
    update: dict = {"updated_at": now}

    for f in ["name", "description", "status"]:
        if f in body:
            update[f] = body[f]

    if "allocations" in body:
        allocations = body["allocations"]
        validated = {}
        for dt in DAY_TYPES:
            dt_allocs = allocations.get(dt, existing.get("allocations", {}).get(dt, {}))
            validated[dt] = {}
            for la in LIFE_AREAS:
                area_data = dt_allocs.get(la["id"], {})
                validated[dt][la["id"]] = {
                    "hours": max(0, min(24, float(area_data.get("hours", 0)))),
                    "priority": area_data.get("priority", "medium"),
                    "notes": area_data.get("notes", ""),
                }
        update["allocations"] = validated

    await db.lifestyle_plans.update_one({"plan_id": plan_id}, {"$set": update})
    updated = await db.lifestyle_plans.find_one({"plan_id": plan_id}, {"_id": 0})
    return updated


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user: dict = Depends(get_current_user)):
    """Delete a plan."""
    result = await db.lifestyle_plans.delete_one(
        {"plan_id": plan_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Plan not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# ACTIVATE PLAN
# ═══════════════════════════════════════════════════════════════

@router.post("/plans/{plan_id}/activate")
async def activate_plan(plan_id: str, user: dict = Depends(get_current_user)):
    """Set a plan as the active plan (deactivates others)."""
    existing = await db.lifestyle_plans.find_one(
        {"plan_id": plan_id, "user_id": user["user_id"]}
    )
    if not existing:
        raise HTTPException(404, "Plan not found")

    now = datetime.now(timezone.utc).isoformat()
    # Deactivate all plans
    await db.lifestyle_plans.update_many(
        {"user_id": user["user_id"], "is_active": True},
        {"$set": {"is_active": False, "status": "draft", "updated_at": now}}
    )
    # Activate this one
    await db.lifestyle_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {"is_active": True, "status": "active", "updated_at": now}}
    )
    return {"message": "Plan activated", "plan_id": plan_id}


# ═══════════════════════════════════════════════════════════════
# GET ACTIVE PLAN
# ═══════════════════════════════════════════════════════════════

@router.get("/active-plan")
async def get_active_plan(user: dict = Depends(get_current_user)):
    """Get the user's currently active lifestyle plan."""
    plan = await db.lifestyle_plans.find_one(
        {"user_id": user["user_id"], "is_active": True}, {"_id": 0}
    )
    if not plan:
        return {"active_plan": None, "message": "No active plan. Create and activate one."}
    return {"active_plan": plan}


# ═══════════════════════════════════════════════════════════════
# COMPARISON: PLANNED vs ACTUAL
# ═══════════════════════════════════════════════════════════════

@router.get("/comparison")
async def get_comparison(request: Request, user: dict = Depends(get_current_user)):
    """
    Compare active plan allocations vs actual time from LEE logs.
    Query params: ?days=7 (default 7, how many recent days to average)
    """
    params = request.query_params
    days = int(params.get("days", "7"))

    # 1. Get active plan
    plan = await db.lifestyle_plans.find_one(
        {"user_id": user["user_id"], "is_active": True}, {"_id": 0}
    )
    if not plan:
        raise HTTPException(400, "No active plan found. Create and activate a plan first.")

    # 2. Get recent LEE logs
    logs = await db.lifestyle_eval_logs.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("date", -1).to_list(days)

    # 3. Aggregate actuals by day_type and area
    actual_by_dt_area: dict = {}  # { day_type: { area: total_min } }
    dt_counts: dict = {}  # { day_type: count }

    for log in logs:
        dt = log.get("day_type", "weekday")
        dt_counts[dt] = dt_counts.get(dt, 0) + 1
        if dt not in actual_by_dt_area:
            actual_by_dt_area[dt] = {}
        for act in log.get("activities", []):
            area = act.get("area_of_life", "unclassified")
            dur = act.get("duration_minutes", 0)
            actual_by_dt_area[dt][area] = actual_by_dt_area[dt].get(area, 0) + dur

    # 4. Build comparison per day_type
    allocations = plan.get("allocations", {})
    comparison = {}

    for dt in DAY_TYPES:
        dt_allocs = allocations.get(dt, {})
        dt_actuals = actual_by_dt_area.get(dt, {})
        count = max(dt_counts.get(dt, 0), 1)

        comparison[dt] = {"areas": [], "total_planned_hours": 0, "total_actual_hours": 0}

        for la in LIFE_AREAS:
            planned = dt_allocs.get(la["id"], {})
            planned_hours = planned.get("hours", 0) if isinstance(planned, dict) else 0
            actual_min = dt_actuals.get(la["id"], 0)
            avg_actual_hours = round(actual_min / count / 60, 2)

            gap = round(avg_actual_hours - planned_hours, 2)
            pct = round((avg_actual_hours / planned_hours * 100) if planned_hours > 0 else (100 if avg_actual_hours > 0 else 0), 1)

            comparison[dt]["areas"].append({
                "area_id": la["id"],
                "area_name": la["name"],
                "icon": la["icon"],
                "color": la["color"],
                "planned_hours": planned_hours,
                "actual_hours": avg_actual_hours,
                "gap_hours": gap,
                "achievement_pct": pct,
                "priority": planned.get("priority", "medium") if isinstance(planned, dict) else "medium",
                "status": "over" if gap > 0.5 else "under" if gap < -0.5 else "on_track",
            })
            comparison[dt]["total_planned_hours"] += planned_hours
            comparison[dt]["total_actual_hours"] += avg_actual_hours

    return {
        "plan_id": plan["plan_id"],
        "plan_name": plan["name"],
        "comparison": comparison,
        "days_analyzed": len(logs),
        "day_type_counts": dt_counts,
    }


# ═══════════════════════════════════════════════════════════════
# MANUAL OVERRIDE
# ═══════════════════════════════════════════════════════════════

@router.post("/overrides")
async def save_override(request: Request, user: dict = Depends(get_current_user)):
    """
    Manually override actual hours for a specific date and area.
    Stored separately so original LEE data isn't corrupted.
    """
    body = await request.json()
    override_date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    area = body.get("life_area", "")
    hours = max(0, min(24, float(body.get("hours", 0))))
    reason = body.get("reason", "")

    now = datetime.now(timezone.utc).isoformat()
    override_id = f"OVR-{uuid.uuid4().hex[:8].upper()}"

    await db.lifestyle_overrides.update_one(
        {"user_id": user["user_id"], "date": override_date, "life_area": area},
        {"$set": {
            "override_id": override_id,
            "user_id": user["user_id"],
            "date": override_date,
            "life_area": area,
            "override_hours": hours,
            "reason": reason,
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True
    )
    return {"message": "Override saved", "date": override_date, "life_area": area, "hours": hours}


@router.get("/overrides")
async def list_overrides(request: Request, user: dict = Depends(get_current_user)):
    """List manual overrides."""
    params = request.query_params
    query: dict = {"user_id": user["user_id"]}
    if params.get("date"):
        query["date"] = params["date"]
    if params.get("life_area"):
        query["life_area"] = params["life_area"]

    overrides = await db.lifestyle_overrides.find(query, {"_id": 0}).sort("date", -1).to_list(100)
    return overrides


@router.delete("/overrides/{override_date}/{life_area}")
async def delete_override(override_date: str, life_area: str, user: dict = Depends(get_current_user)):
    """Delete a manual override."""
    result = await db.lifestyle_overrides.delete_one(
        {"user_id": user["user_id"], "date": override_date, "life_area": life_area}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Override not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def ld_dashboard(user: dict = Depends(get_current_user)):
    """Lifestyle Designer dashboard."""
    plans = await db.lifestyle_plans.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(50)

    active_plan = next((p for p in plans if p.get("is_active")), None)
    total_plans = len(plans)

    # Quick comparison snippet (weekday only)
    quick_comparison = None
    if active_plan:
        logs = await db.lifestyle_eval_logs.find(
            {"user_id": user["user_id"], "day_type": "weekday"}, {"_id": 0}
        ).sort("date", -1).to_list(7)

        if logs:
            area_mins: dict = {}
            for log in logs:
                for act in log.get("activities", []):
                    area = act.get("area_of_life", "")
                    area_mins[area] = area_mins.get(area, 0) + act.get("duration_minutes", 0)

            count = len(logs)
            weekday_allocs = active_plan.get("allocations", {}).get("weekday", {})
            on_track = 0
            total_areas = 0
            for la in LIFE_AREAS:
                planned = weekday_allocs.get(la["id"], {})
                planned_hrs = planned.get("hours", 0) if isinstance(planned, dict) else 0
                if planned_hrs > 0:
                    total_areas += 1
                    actual_hrs = round(area_mins.get(la["id"], 0) / count / 60, 2)
                    if abs(actual_hrs - planned_hrs) <= 1:
                        on_track += 1

            quick_comparison = {
                "on_track": on_track,
                "total_areas": total_areas,
                "pct": round(on_track / max(total_areas, 1) * 100, 1),
                "days_analyzed": count,
            }

    return {
        "total_plans": total_plans,
        "active_plan": {
            "plan_id": active_plan["plan_id"],
            "name": active_plan["name"],
        } if active_plan else None,
        "quick_comparison": quick_comparison,
    }
