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


# ========================
# ROUTINE COMPLETION TRACKING + STREAKS
# ========================

@router.post("/lifestyle/routines/{routine_id}/complete")
async def mark_routine_complete(routine_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Mark a routine as completed for today. Tracks streaks."""
    routine = await db.lifestyle_routines.find_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Check if already completed today
    existing = await db.routine_completions.find_one({
        "routine_id": routine_id, "user_id": user["user_id"], "date": today,
    })
    if existing:
        raise HTTPException(status_code=400, detail="Already completed today")

    completion = {
        "completion_id": str(uuid.uuid4()),
        "routine_id": routine_id,
        "user_id": user["user_id"],
        "date": today,
        "notes": body.get("notes", ""),
        "value": body.get("value"),  # Optional: actual value achieved
        "completed_at": now.isoformat(),
    }
    await db.routine_completions.insert_one(completion)

    # Calculate streak
    streak = await _calculate_streak(routine_id, user["user_id"], routine.get("frequency", "daily"))

    # Update routine with latest streak
    await db.lifestyle_routines.update_one(
        {"routine_id": routine_id},
        {"$set": {
            "current_streak": streak,
            "last_completed": today,
            "total_completions": (routine.get("total_completions", 0) + 1),
            "updated_at": now.isoformat(),
        }}
    )

    return {
        "message": "Routine completed!",
        "date": today,
        "current_streak": streak,
        "total_completions": routine.get("total_completions", 0) + 1,
    }


@router.delete("/lifestyle/routines/{routine_id}/uncomplete")
async def undo_routine_completion(routine_id: str, user: dict = Depends(get_current_user)):
    """Undo today's completion for a routine."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await db.routine_completions.delete_one({
        "routine_id": routine_id, "user_id": user["user_id"], "date": today,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No completion found for today")

    # Recalculate streak
    routine = await db.lifestyle_routines.find_one({"routine_id": routine_id}, {"_id": 0})
    if routine:
        streak = await _calculate_streak(routine_id, user["user_id"], routine.get("frequency", "daily"))
        total = max(0, routine.get("total_completions", 1) - 1)
        await db.lifestyle_routines.update_one(
            {"routine_id": routine_id},
            {"$set": {"current_streak": streak, "total_completions": total, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    return {"message": "Completion undone"}


@router.get("/lifestyle/routines/{routine_id}/completions")
async def get_routine_completions(routine_id: str, user: dict = Depends(get_current_user), days: int = 30):
    """Get completion history for a routine (default last 30 days)."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    completions = await db.routine_completions.find(
        {"routine_id": routine_id, "user_id": user["user_id"], "date": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("date", -1).to_list(days)
    return {"completions": completions, "total": len(completions)}


@router.get("/lifestyle/today-status")
async def get_today_status(user: dict = Depends(get_current_user)):
    """Get today's completion status for all active routines."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0}
    ).to_list(200)

    # Get today's completions
    completed_today = await db.routine_completions.find(
        {"user_id": user["user_id"], "date": today},
        {"_id": 0}
    ).to_list(200)
    completed_ids = {c["routine_id"] for c in completed_today}

    # Filter routines by frequency relevance to today
    now = datetime.now(timezone.utc)
    day_of_week = now.weekday()  # 0=Monday
    day_of_month = now.day

    today_routines = []
    for r in routines:
        freq = r.get("frequency", "daily")
        relevant = False
        if freq == "hourly":
            relevant = True
        elif freq == "daily":
            relevant = True
        elif freq == "weekly":
            relevant = day_of_week == 0  # Mondays (or could be configurable)
        elif freq == "fortnightly":
            relevant = day_of_month in [1, 15]
        elif freq == "monthly":
            relevant = day_of_month == 1

        if relevant:
            r["completed_today"] = r["routine_id"] in completed_ids
            today_routines.append(r)

    done_count = sum(1 for r in today_routines if r["completed_today"])

    return {
        "date": today,
        "routines": today_routines,
        "total_due": len(today_routines),
        "completed": done_count,
        "completion_rate": round((done_count / len(today_routines) * 100) if today_routines else 0, 1),
    }


async def _calculate_streak(routine_id: str, user_id: str, frequency: str) -> int:
    """Calculate the current streak for a routine based on its frequency."""
    from datetime import timedelta
    completions = await db.routine_completions.find(
        {"routine_id": routine_id, "user_id": user_id},
        {"_id": 0, "date": 1}
    ).sort("date", -1).to_list(365)

    if not completions:
        return 0

    dates = sorted(set(c["date"] for c in completions), reverse=True)
    streak = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Determine gap tolerance based on frequency
    if frequency == "daily":
        max_gap = 1
    elif frequency == "weekly":
        max_gap = 7
    elif frequency == "fortnightly":
        max_gap = 14
    elif frequency == "monthly":
        max_gap = 31
    else:
        max_gap = 1

    for i, d in enumerate(dates):
        if i == 0:
            # Check if last completion is recent enough
            diff = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days
            if diff > max_gap:
                return 0
            streak = 1
        else:
            diff = (datetime.strptime(dates[i - 1], "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days
            if diff <= max_gap:
                streak += 1
            else:
                break

    return streak


# ========================
# GOOGLE CALENDAR RECURRING SYNC FOR ROUTINES
# ========================

@router.post("/lifestyle/routines/{routine_id}/sync-calendar")
async def sync_routine_to_calendar(routine_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Create a recurring Google Calendar event for a lifestyle routine."""
    routine = await db.lifestyle_routines.find_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    # Check Google Calendar connection
    from routes.google_calendar import get_google_credentials
    creds = await get_google_credentials(user["user_id"])
    if not creds:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    tz = body.get("timezone", "Asia/Kolkata")

    freq = routine.get("frequency", "daily")
    time_slot = routine.get("time_slot", "09:00")
    name = routine.get("name", "Routine")

    # Build recurrence rule
    rrule_freq = {
        "hourly": "HOURLY",
        "daily": "DAILY",
        "weekly": "WEEKLY",
        "fortnightly": "WEEKLY;INTERVAL=2",
        "monthly": "MONTHLY",
    }.get(freq, "DAILY")

    # Build event
    now = datetime.now(timezone.utc)
    start_date = now.strftime("%Y-%m-%d")

    # Parse time slot
    if ":" in time_slot:
        start_time = time_slot[:5]
    else:
        start_time = "09:00"

    # Calculate end time (30 min default)
    start_h, start_m = int(start_time[:2]), int(start_time[3:5])
    end_m = start_m + 30
    end_h = start_h + (end_m // 60)
    end_m = end_m % 60
    end_time = f"{end_h:02d}:{end_m:02d}"

    event_body = {
        "summary": f"🔄 {name}",
        "description": f"Lifestyle Routine: {routine.get('description', '')}\n\nLife Area: {routine.get('life_area', '')}\nFrequency: {freq}\nPriority: {routine.get('priority', 'medium')}\n\n[View Dezider Lifestyle Routine: {routine_id}]",
        "start": {"dateTime": f"{start_date}T{start_time}:00", "timeZone": tz},
        "end": {"dateTime": f"{start_date}T{end_time}:00", "timeZone": tz},
        "recurrence": [f"RRULE:FREQ={rrule_freq}"],
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 10}],
        },
        "colorId": "2",  # Green for routines
    }

    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(calendarId="primary", body=event_body).execute()

        # Save calendar event ID on routine
        await db.lifestyle_routines.update_one(
            {"routine_id": routine_id},
            {"$set": {
                "google_calendar_event_id": event.get("id"),
                "google_calendar_link": event.get("htmlLink", ""),
                "synced_to_calendar": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

        return {
            "message": f"Recurring {freq} event created in Google Calendar",
            "event_id": event.get("id"),
            "html_link": event.get("htmlLink", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar sync error: {str(e)}")


@router.delete("/lifestyle/routines/{routine_id}/unsync-calendar")
async def unsync_routine_from_calendar(routine_id: str, user: dict = Depends(get_current_user)):
    """Remove the recurring calendar event for a routine."""
    routine = await db.lifestyle_routines.find_one(
        {"routine_id": routine_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found")

    event_id = routine.get("google_calendar_event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Routine is not synced to calendar")

    from routes.google_calendar import get_google_credentials
    creds = await get_google_credentials(user["user_id"])
    if creds:
        try:
            from googleapiclient.discovery import build
            service = build("calendar", "v3", credentials=creds)
            service.events().delete(calendarId="primary", eventId=event_id).execute()
        except Exception:
            pass  # Event might already be deleted

    await db.lifestyle_routines.update_one(
        {"routine_id": routine_id},
        {"$unset": {"google_calendar_event_id": "", "google_calendar_link": "", "synced_to_calendar": ""}}
    )
    return {"message": "Calendar sync removed"}


# ========================
# AUTO-DETECT ROUTINE TASKS IN CTT
# ========================

@router.post("/lifestyle/auto-detect-from-ctt")
async def auto_detect_routines_from_ctt(user: dict = Depends(get_current_user)):
    """
    Smart detection: Find recurring/routine-type tasks in CTT that aren't yet
    in Lifestyle. Uses frequency hints and naming patterns.
    """
    # Get all CTT tasks
    ctt_tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(500)

    # Get existing routine source IDs
    existing = await db.lifestyle_routines.find(
        {"user_id": user["user_id"]},
        {"source_ctt_task_id": 1}
    ).to_list(200)
    existing_sources = {e.get("source_ctt_task_id") for e in existing if e.get("source_ctt_task_id")}

    # Detect routine-like tasks
    routine_keywords = [
        "daily", "weekly", "monthly", "routine", "habit", "regular", "recurring",
        "exercise", "meditation", "workout", "reading", "journal", "review",
        "meeting", "standup", "sync", "check", "practice", "study", "walk",
        "breakfast", "lunch", "dinner", "sleep", "wake", "morning", "evening",
    ]

    suggestions = []
    for task in ctt_tasks:
        if task["task_id"] in existing_sources:
            continue

        task_text = (task.get("task", "") + " " + task.get("sub_task", "")).lower()
        is_routine_flag = task.get("is_routine", False)
        freq = task.get("frequency", "")

        # Score how "routine-like" this task is
        score = 0
        if is_routine_flag:
            score += 5
        if freq and freq in ["hourly", "daily", "weekly", "fortnightly", "monthly"]:
            score += 3
        for kw in routine_keywords:
            if kw in task_text:
                score += 1

        if score >= 2:
            suggestions.append({
                "task_id": task["task_id"],
                "task": task.get("task", ""),
                "sub_task": task.get("sub_task", ""),
                "life_area": task.get("life_area", ""),
                "frequency": freq or "daily",
                "priority": task.get("priority", "medium"),
                "from_time": task.get("from_time", ""),
                "confidence_score": min(10, score),
                "is_routine_flag": is_routine_flag,
            })

    suggestions.sort(key=lambda x: x["confidence_score"], reverse=True)

    return {
        "suggestions": suggestions[:20],
        "total_found": len(suggestions),
        "message": f"Found {len(suggestions)} potential routines in your CTT tasks",
    }


@router.post("/lifestyle/bulk-import-from-ctt")
async def bulk_import_from_ctt(request: Request, user: dict = Depends(get_current_user)):
    """Import specific CTT tasks as routines (user selects from suggestions)."""
    body = await request.json()
    task_ids = body.get("task_ids", [])

    if not task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")

    now = datetime.now(timezone.utc).isoformat()
    imported = 0

    for tid in task_ids:
        task = await db.ctt_tasks.find_one({"task_id": tid, "user_id": user["user_id"]}, {"_id": 0})
        if not task:
            continue

        # Check duplicate
        existing = await db.lifestyle_routines.find_one({
            "user_id": user["user_id"], "source_ctt_task_id": tid
        })
        if existing:
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
            "is_active": True,
            "current_streak": 0,
            "total_completions": 0,
            "source_ctt_task_id": tid,
            "created_at": now,
            "updated_at": now,
        }
        await db.lifestyle_routines.insert_one(doc)
        imported += 1

    return {"imported": imported, "total_requested": len(task_ids)}
