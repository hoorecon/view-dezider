"""CTT (Centralized Task Tracker) + GEM (Goals Execution Manager) + TEPFI Resource Matrix + Calendar endpoints."""
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

LIFE_AREAS = [
    "career", "finance", "relationships", "holistic_health", "assets",
    "knowledge_skills", "social_image", "social_contributions",
    "hobbies_entertainment", "spirituality_religion",
]

TEPFI_DIMENSIONS = ["time", "effort", "people", "finance", "infrastructure"]
TEPFI_LAYERS = ["self", "micro", "macro"]

# ========================
# CTT TASKS
# ========================

@router.post("/ctt/tasks")
async def create_ctt_task(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "task_id": task_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        # Source tracking
        "source_type": body.get("source_type", "manual"),
        "source_id": body.get("source_id"),
        # Org/Team fields
        "company": body.get("company", ""),
        "division": body.get("division", ""),
        "team": body.get("team", ""),
        "project": body.get("project", ""),
        # Task details
        "task_logged_by": body.get("task_logged_by", user.get("name", "")),
        "task": body.get("task", ""),
        "sub_task": body.get("sub_task", ""),
        "current_status": body.get("current_status", "open"),
        "remarks": body.get("remarks", ""),
        "priority": body.get("priority", "medium"),
        "deadline": body.get("deadline"),
        "task_owners": body.get("task_owners", []),
        # Dependencies
        "internal_dependency": body.get("internal_dependency", ""),
        "external_dependency": body.get("external_dependency", ""),
        "internal_help": body.get("internal_help", ""),
        "external_help": body.get("external_help", ""),
        # Time
        "task_duration": body.get("task_duration", ""),
        "from_time": body.get("from_time"),
        "to_time": body.get("to_time"),
        # Categorization
        "life_area": body.get("life_area", ""),
        "decision_type": body.get("decision_type", ""),
        "goal_id": body.get("goal_id"),
        # Routine
        "is_routine": body.get("is_routine", False),
        "frequency": body.get("frequency"),
        # Day-wise status {"2025-12-19": "done", "2025-12-20": "in_progress"}
        "day_status": body.get("day_status", {}),
        "created_at": now,
        "updated_at": now,
    }
    await db.ctt_tasks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/ctt/tasks")
async def list_ctt_tasks(request: Request, user: dict = Depends(get_current_user)):
    query: dict = {"user_id": user["user_id"]}
    params = request.query_params
    if params.get("life_area"):
        query["life_area"] = params["life_area"]
    if params.get("decision_type"):
        query["decision_type"] = params["decision_type"]
    if params.get("status"):
        query["current_status"] = params["status"]
    if params.get("priority"):
        query["priority"] = params["priority"]
    if params.get("is_routine") is not None:
        query["is_routine"] = params["is_routine"].lower() == "true"
    if params.get("goal_id"):
        query["goal_id"] = params["goal_id"]
    if params.get("source_type"):
        query["source_type"] = params["source_type"]

    tasks = await db.ctt_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return tasks


@router.get("/ctt/tasks/{task_id}")
async def get_ctt_task(task_id: str, user: dict = Depends(get_current_user)):
    task = await db.ctt_tasks.find_one(
        {"task_id": task_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/ctt/tasks/{task_id}")
async def update_ctt_task(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    task = await db.ctt_tasks.find_one({"task_id": task_id, "user_id": user["user_id"]})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    allowed = [
        "company", "division", "team", "project", "task_logged_by",
        "task", "sub_task", "current_status", "remarks", "priority",
        "deadline", "task_owners", "internal_dependency", "external_dependency",
        "internal_help", "external_help", "task_duration", "from_time", "to_time",
        "life_area", "decision_type", "goal_id", "is_routine", "frequency",
        "day_status", "source_type", "source_id",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.ctt_tasks.update_one({"task_id": task_id}, {"$set": update})
    updated = await db.ctt_tasks.find_one({"task_id": task_id}, {"_id": 0})
    return updated


@router.put("/ctt/tasks/{task_id}/day-status")
async def update_day_status(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update day-wise status for a task. Body: {date: status} — empty status removes the date."""
    body = await request.json()
    task = await db.ctt_tasks.find_one({"task_id": task_id, "user_id": user["user_id"]})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    day_status = task.get("day_status", {})
    for date_key, status_val in body.items():
        if status_val and isinstance(status_val, str) and status_val.strip():
            day_status[date_key] = status_val.strip()
        else:
            day_status.pop(date_key, None)

    await db.ctt_tasks.update_one(
        {"task_id": task_id},
        {"$set": {"day_status": day_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Day status updated", "day_status": day_status}


@router.delete("/ctt/tasks/{task_id}")
async def delete_ctt_task(task_id: str, user: dict = Depends(get_current_user)):
    result = await db.ctt_tasks.delete_one({"task_id": task_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}


@router.post("/ctt/aggregate")
async def aggregate_action_items(request: Request, user: dict = Depends(get_current_user)):
    """Pull action items from Decisions, Solution Finders, and Solution Matrices into CTT."""
    imported = 0
    now = datetime.now(timezone.utc).isoformat()

    # From Decisions
    decisions = await db.prr_decisions.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(200)
    for dec in decisions:
        steps = dec.get("steps", {})
        # Step 10 often has action plan
        step10 = steps.get("10", {})
        action_items = step10.get("action_items", step10.get("actions", []))
        if isinstance(action_items, list):
            for item in action_items:
                action_text = item.get("action", item.get("description", item.get("text", "")))
                if not action_text:
                    continue
                existing = await db.ctt_tasks.find_one({
                    "user_id": user["user_id"],
                    "source_type": "decision",
                    "source_id": dec.get("decision_id"),
                    "task": action_text,
                })
                if not existing:
                    task_doc = {
                        "task_id": str(uuid.uuid4()),
                        "user_id": user["user_id"],
                        "org_id": user.get("org_id"),
                        "source_type": "decision",
                        "source_id": dec.get("decision_id"),
                        "task": action_text,
                        "sub_task": "",
                        "task_logged_by": user.get("name", ""),
                        "current_status": item.get("status", "open"),
                        "priority": item.get("priority", "medium"),
                        "deadline": item.get("by_when", item.get("deadline")),
                        "task_owners": [item.get("who", item.get("owner", ""))] if item.get("who") or item.get("owner") else [],
                        "life_area": dec.get("life_area", dec.get("folder", "")),
                        "decision_type": dec.get("decision_type", ""),
                        "project": dec.get("title", ""),
                        "is_routine": False,
                        "day_status": {},
                        "company": "", "division": "", "team": "",
                        "remarks": "", "internal_dependency": "", "external_dependency": "",
                        "internal_help": "", "external_help": "",
                        "task_duration": "", "from_time": None, "to_time": None,
                        "frequency": None, "goal_id": None,
                        "created_at": now, "updated_at": now,
                    }
                    await db.ctt_tasks.insert_one(task_doc)
                    imported += 1

    # From Solution Finders
    finders = await db.solution_finders.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(200)
    for sf in finders:
        for item in (sf.get("action_items") or []):
            action_text = item.get("action", "")
            if not action_text:
                continue
            existing = await db.ctt_tasks.find_one({
                "user_id": user["user_id"],
                "source_type": "solution_finder",
                "source_id": sf.get("entry_id"),
                "task": action_text,
            })
            if not existing:
                task_doc = {
                    "task_id": str(uuid.uuid4()),
                    "user_id": user["user_id"],
                    "org_id": user.get("org_id"),
                    "source_type": "solution_finder",
                    "source_id": sf.get("entry_id"),
                    "task": action_text,
                    "sub_task": "",
                    "task_logged_by": user.get("name", ""),
                    "current_status": item.get("status", "open"),
                    "priority": "medium",
                    "deadline": item.get("by_when"),
                    "task_owners": [item.get("who", "")] if item.get("who") else [],
                    "life_area": sf.get("area_of_life", ""),
                    "decision_type": "",
                    "project": sf.get("smart_goal", ""),
                    "is_routine": False,
                    "day_status": {},
                    "company": "", "division": "", "team": "",
                    "remarks": "", "internal_dependency": "", "external_dependency": "",
                    "internal_help": "", "external_help": "",
                    "task_duration": "", "from_time": None, "to_time": None,
                    "frequency": None, "goal_id": None,
                    "created_at": now, "updated_at": now,
                }
                await db.ctt_tasks.insert_one(task_doc)
                imported += 1

    # From Solution Matrices
    matrices = await db.solution_matrices.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(200)
    for sm in matrices:
        for item in (sm.get("action_items") or []):
            action_text = item.get("what", item.get("action", ""))
            if not action_text:
                continue
            existing = await db.ctt_tasks.find_one({
                "user_id": user["user_id"],
                "source_type": "solution_matrix",
                "source_id": sm.get("entry_id"),
                "task": action_text,
            })
            if not existing:
                task_doc = {
                    "task_id": str(uuid.uuid4()),
                    "user_id": user["user_id"],
                    "org_id": user.get("org_id"),
                    "source_type": "solution_matrix",
                    "source_id": sm.get("entry_id"),
                    "task": action_text,
                    "sub_task": "",
                    "task_logged_by": user.get("name", ""),
                    "current_status": item.get("status", "open"),
                    "priority": "medium",
                    "deadline": item.get("by_when"),
                    "task_owners": [item.get("who", "")] if item.get("who") else [],
                    "life_area": sm.get("area_of_life", ""),
                    "decision_type": "",
                    "project": sm.get("smart_goal", ""),
                    "is_routine": False,
                    "day_status": {},
                    "company": "", "division": "", "team": "",
                    "remarks": "", "internal_dependency": "", "external_dependency": "",
                    "internal_help": "", "external_help": "",
                    "task_duration": "", "from_time": None, "to_time": None,
                    "frequency": None, "goal_id": None,
                    "created_at": now, "updated_at": now,
                }
                await db.ctt_tasks.insert_one(task_doc)
                imported += 1

    return {"message": f"Imported {imported} new action items into CTT", "imported": imported}


@router.get("/ctt/tasks/{task_id}/calendar-url")
async def get_calendar_url(task_id: str, user: dict = Depends(get_current_user)):
    """Generate a Google Calendar add-event URL for a task."""
    task = await db.ctt_tasks.find_one(
        {"task_id": task_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    title = task.get("task", "Untitled Task")
    details = f"Project: {task.get('project', '')}\nPriority: {task.get('priority', '')}\nRemarks: {task.get('remarks', '')}"
    if task.get("sub_task"):
        details += f"\nSub-task: {task['sub_task']}"

    # Build date params
    deadline = task.get("deadline", "")
    from_time = task.get("from_time", "")
    to_time = task.get("to_time", "")

    # Google Calendar URL format
    base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
    params = f"&text={quote(title)}&details={quote(details)}"

    if from_time and to_time:
        params += f"&dates={quote(from_time)}/{quote(to_time)}"
    elif deadline:
        params += f"&dates={quote(deadline)}/{quote(deadline)}"

    return {"calendar_url": base + params, "task_id": task_id}


@router.get("/ctt/stats")
async def get_ctt_stats(user: dict = Depends(get_current_user)):
    """Get CTT dashboard stats."""
    tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(1000)

    total = len(tasks)
    by_status = {}
    by_priority = {}
    by_life_area = {}
    by_source = {}
    routine_count = 0

    for t in tasks:
        s = t.get("current_status", "open")
        by_status[s] = by_status.get(s, 0) + 1
        p = t.get("priority", "medium")
        by_priority[p] = by_priority.get(p, 0) + 1
        la = t.get("life_area", "")
        if la:
            by_life_area[la] = by_life_area.get(la, 0) + 1
        src = t.get("source_type", "manual")
        by_source[src] = by_source.get(src, 0) + 1
        if t.get("is_routine"):
            routine_count += 1

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_life_area": by_life_area,
        "by_source": by_source,
        "routine_count": routine_count,
        "one_time_count": total - routine_count,
    }


# ========================
# GEM (Goals Execution Manager)
# ========================

@router.post("/gem/goals")
async def create_gem_goal(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    goal_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "goal_id": goal_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "life_area": body.get("life_area", ""),
        "goal_type": body.get("goal_type", "aspiration"),
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "smart_goal": body.get("smart_goal", ""),
        "priority": body.get("priority", "medium"),
        "status": body.get("status", "active"),
        "target_date": body.get("target_date"),
        "linked_decisions": body.get("linked_decisions", []),
        "linked_solution_finders": body.get("linked_solution_finders", []),
        "linked_solution_matrices": body.get("linked_solution_matrices", []),
        "progress_percent": body.get("progress_percent", 0),
        "created_at": now,
        "updated_at": now,
    }
    await db.gem_goals.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/gem/goals")
async def list_gem_goals(request: Request, user: dict = Depends(get_current_user)):
    query: dict = {"user_id": user["user_id"]}
    params = request.query_params
    if params.get("life_area"):
        query["life_area"] = params["life_area"]
    if params.get("goal_type"):
        query["goal_type"] = params["goal_type"]
    if params.get("status"):
        query["status"] = params["status"]
    if params.get("priority"):
        query["priority"] = params["priority"]

    goals = await db.gem_goals.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return goals


@router.get("/gem/goals/{goal_id}")
async def get_gem_goal(goal_id: str, user: dict = Depends(get_current_user)):
    goal = await db.gem_goals.find_one(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.put("/gem/goals/{goal_id}")
async def update_gem_goal(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    goal = await db.gem_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    allowed = [
        "life_area", "goal_type", "title", "description", "smart_goal",
        "priority", "status", "target_date",
        "linked_decisions", "linked_solution_finders", "linked_solution_matrices",
        "progress_percent",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.gem_goals.update_one({"goal_id": goal_id}, {"$set": update})
    updated = await db.gem_goals.find_one({"goal_id": goal_id}, {"_id": 0})
    return updated


@router.delete("/gem/goals/{goal_id}")
async def delete_gem_goal(goal_id: str, user: dict = Depends(get_current_user)):
    result = await db.gem_goals.delete_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"message": "Goal deleted"}


@router.post("/gem/goals/{goal_id}/link")
async def link_goal(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Link a decision, solution finder, or solution matrix to a goal."""
    body = await request.json()
    goal = await db.gem_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    link_type = body.get("link_type")  # decision, solution_finder, solution_matrix
    link_id = body.get("link_id")
    if not link_type or not link_id:
        raise HTTPException(status_code=400, detail="link_type and link_id required")

    field_map = {
        "decision": "linked_decisions",
        "solution_finder": "linked_solution_finders",
        "solution_matrix": "linked_solution_matrices",
    }
    field = field_map.get(link_type)
    if not field:
        raise HTTPException(status_code=400, detail="Invalid link_type")

    current = goal.get(field, [])
    if link_id not in current:
        current.append(link_id)
        await db.gem_goals.update_one(
            {"goal_id": goal_id},
            {"$set": {field: current, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    return {"message": f"Linked {link_type} to goal"}


@router.get("/gem/dashboard")
async def gem_dashboard(user: dict = Depends(get_current_user)):
    """GEM overview: goals per life area, per type, with progress."""
    goals = await db.gem_goals.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(500)

    by_area = {}
    by_type = {"problem": 0, "need": 0, "aspiration": 0}
    by_status = {}
    total_progress = 0

    for g in goals:
        area = g.get("life_area", "other")
        by_area.setdefault(area, {"total": 0, "active": 0, "completed": 0})
        by_area[area]["total"] += 1
        if g.get("status") == "completed":
            by_area[area]["completed"] += 1
        elif g.get("status") == "active":
            by_area[area]["active"] += 1

        gt = g.get("goal_type", "aspiration")
        by_type[gt] = by_type.get(gt, 0) + 1

        s = g.get("status", "active")
        by_status[s] = by_status.get(s, 0) + 1

        total_progress += g.get("progress_percent", 0)

    return {
        "total_goals": len(goals),
        "avg_progress": round(total_progress / max(len(goals), 1), 1),
        "by_area": by_area,
        "by_type": by_type,
        "by_status": by_status,
    }


# ========================
# TEPFI RESOURCE MATRIX
# ========================

@router.post("/tepfi/entries")
async def create_tepfi_entry(request: Request, user: dict = Depends(get_current_user)):
    """Create a TEPFI resource entry. Tracks Time, Effort, People, Finance, Infrastructure across Self/Micro/Macro."""
    body = await request.json()
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build the matrix: { "time": { "self": ..., "micro": ..., "macro": ... }, ... }
    matrix = {}
    for dim in TEPFI_DIMENSIONS:
        matrix[dim] = {}
        for layer in TEPFI_LAYERS:
            key = f"{dim}_{layer}"
            matrix[dim][layer] = {
                "description": body.get(key, {}).get("description", "") if isinstance(body.get(key), dict) else body.get(f"{key}_description", ""),
                "score": body.get(key, {}).get("score", 0) if isinstance(body.get(key), dict) else body.get(f"{key}_score", 0),
                "notes": body.get(key, {}).get("notes", "") if isinstance(body.get(key), dict) else body.get(f"{key}_notes", ""),
            }

    # Also accept pre-built matrix object
    if "matrix" in body and isinstance(body["matrix"], dict):
        matrix = body["matrix"]

    doc = {
        "entry_id": entry_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": body.get("title", ""),
        "life_area": body.get("life_area", ""),
        "goal_id": body.get("goal_id"),
        "decision_type": body.get("decision_type", ""),
        "linked_solution_matrix_id": body.get("linked_solution_matrix_id"),
        "linked_goal_id": body.get("linked_goal_id"),
        "matrix": matrix,
        "overall_notes": body.get("overall_notes", ""),
        "status": body.get("status", "draft"),
        "created_at": now,
        "updated_at": now,
    }
    await db.tepfi_entries.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/tepfi/entries")
async def list_tepfi_entries(request: Request, user: dict = Depends(get_current_user)):
    query: dict = {"user_id": user["user_id"]}
    params = request.query_params
    if params.get("life_area"):
        query["life_area"] = params["life_area"]
    if params.get("goal_id"):
        query["goal_id"] = params["goal_id"]
    if params.get("status"):
        query["status"] = params["status"]

    entries = await db.tepfi_entries.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return entries


@router.get("/tepfi/entries/{entry_id}")
async def get_tepfi_entry(entry_id: str, user: dict = Depends(get_current_user)):
    entry = await db.tepfi_entries.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="TEPFI entry not found")
    return entry


@router.put("/tepfi/entries/{entry_id}")
async def update_tepfi_entry(entry_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    entry = await db.tepfi_entries.find_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if not entry:
        raise HTTPException(status_code=404, detail="TEPFI entry not found")

    allowed = [
        "title", "life_area", "goal_id", "decision_type",
        "linked_solution_matrix_id", "linked_goal_id",
        "matrix", "overall_notes", "status",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.tepfi_entries.update_one({"entry_id": entry_id}, {"$set": update})
    updated = await db.tepfi_entries.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated


@router.delete("/tepfi/entries/{entry_id}")
async def delete_tepfi_entry(entry_id: str, user: dict = Depends(get_current_user)):
    result = await db.tepfi_entries.delete_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="TEPFI entry not found")
    return {"message": "TEPFI entry deleted"}


@router.get("/tepfi/dashboard")
async def tepfi_dashboard(user: dict = Depends(get_current_user)):
    """TEPFI overview: aggregated scores across life areas."""
    entries = await db.tepfi_entries.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).to_list(200)

    by_area = {}
    overall_scores = {dim: {layer: [] for layer in TEPFI_LAYERS} for dim in TEPFI_DIMENSIONS}

    for e in entries:
        area = e.get("life_area", "other")
        by_area.setdefault(area, {"count": 0, "avg_scores": {}})
        by_area[area]["count"] += 1

        matrix = e.get("matrix", {})
        for dim in TEPFI_DIMENSIONS:
            dim_data = matrix.get(dim, {})
            for layer in TEPFI_LAYERS:
                layer_data = dim_data.get(layer, {})
                score = layer_data.get("score", 0)
                if score:
                    overall_scores[dim][layer].append(score)

    # Calculate averages
    avg_matrix = {}
    for dim in TEPFI_DIMENSIONS:
        avg_matrix[dim] = {}
        for layer in TEPFI_LAYERS:
            scores = overall_scores[dim][layer]
            avg_matrix[dim][layer] = round(sum(scores) / max(len(scores), 1), 1) if scores else 0

    return {
        "total_entries": len(entries),
        "by_area": by_area,
        "avg_matrix": avg_matrix,
    }


@router.post("/tepfi/import-from-matrix/{matrix_id}")
async def import_tepfi_from_solution_matrix(matrix_id: str, user: dict = Depends(get_current_user)):
    """Import TEPFI data from an existing Solution Matrix entry."""
    sm = await db.solution_matrices.find_one(
        {"entry_id": matrix_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not sm:
        raise HTTPException(status_code=404, detail="Solution Matrix not found")

    # Check if already imported
    existing = await db.tepfi_entries.find_one({
        "user_id": user["user_id"],
        "linked_solution_matrix_id": matrix_id,
    })
    if existing:
        raise HTTPException(status_code=400, detail="Already imported from this matrix")

    # Map solution matrix layers to TEPFI
    now = datetime.now(timezone.utc).isoformat()
    matrix = {}
    tepfi_map = {
        "time": "time",
        "people": "people",
        "finance": "finance",
        "infrastructure": "infrastructure",
        "capacity": "effort",
    }

    for dim in TEPFI_DIMENSIONS:
        matrix[dim] = {}
        for layer in TEPFI_LAYERS:
            sm_layer_key = layer
            sm_layer_data = sm.get("steps", {}).get("2", {}).get(sm_layer_key, {})
            # Try to find matching sub-area in solution matrix
            sm_dim_key = tepfi_map.get(dim, dim)
            sub_area_data = sm_layer_data.get(sm_dim_key, {})
            matrix[dim][layer] = {
                "description": sub_area_data.get("description", sub_area_data.get("notes", "")),
                "score": sub_area_data.get("score", 0),
                "notes": sub_area_data.get("analysis", ""),
            }

    doc = {
        "entry_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": f"From: {sm.get('smart_goal', sm.get('title', 'Solution Matrix'))}",
        "life_area": sm.get("area_of_life", ""),
        "decision_type": "",
        "linked_solution_matrix_id": matrix_id,
        "linked_goal_id": None,
        "goal_id": None,
        "matrix": matrix,
        "overall_notes": f"Imported from Solution Matrix: {sm.get('smart_goal', '')}",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    await db.tepfi_entries.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ========================
# GOOGLE CALENDAR SCHEDULING (Enhanced)
# ========================

@router.post("/calendar/batch-export")
async def batch_export_to_calendar(request: Request, user: dict = Depends(get_current_user)):
    """Generate Google Calendar URLs for multiple tasks at once."""
    body = await request.json()
    task_ids = body.get("task_ids", [])

    if not task_ids:
        # Export all non-done tasks with deadlines
        tasks = await db.ctt_tasks.find(
            {"user_id": user["user_id"], "current_status": {"$ne": "done"}, "deadline": {"$ne": None}},
            {"_id": 0}
        ).to_list(100)
    else:
        tasks = await db.ctt_tasks.find(
            {"user_id": user["user_id"], "task_id": {"$in": task_ids}},
            {"_id": 0}
        ).to_list(100)

    results = []
    for task in tasks:
        title = task.get("task", "Untitled Task")
        details_parts = []
        if task.get("project"):
            details_parts.append(f"Project: {task['project']}")
        if task.get("priority"):
            details_parts.append(f"Priority: {task['priority'].upper()}")
        if task.get("life_area"):
            details_parts.append(f"Life Area: {task['life_area'].replace('_', ' ').title()}")
        if task.get("remarks"):
            details_parts.append(f"Notes: {task['remarks']}")
        if task.get("sub_task"):
            details_parts.append(f"Sub-task: {task['sub_task']}")
        details = "\n".join(details_parts)

        deadline = task.get("deadline", "")
        from_time = task.get("from_time", "")
        to_time = task.get("to_time", "")

        base = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        params_str = f"&text={quote(title)}&details={quote(details)}"

        if from_time and to_time:
            # Try to format as Google Calendar expects: YYYYMMDDTHHmmssZ
            ft = _format_gcal_date(from_time)
            tt = _format_gcal_date(to_time)
            params_str += f"&dates={ft}/{tt}"
        elif deadline:
            dd = _format_gcal_date(deadline)
            params_str += f"&dates={dd}/{dd}"

        results.append({
            "task_id": task["task_id"],
            "task": title,
            "calendar_url": base + params_str,
        })

    return {"tasks": results, "count": len(results)}


@router.get("/calendar/upcoming")
async def get_upcoming_calendar_items(request: Request, user: dict = Depends(get_current_user)):
    """Get upcoming tasks with deadlines for calendar view."""
    params = request.query_params
    days_ahead = int(params.get("days", "30"))

    tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"], "current_status": {"$ne": "cancelled"}},
        {"_id": 0}
    ).sort("deadline", 1).to_list(500)

    # Filter tasks with valid deadlines
    upcoming = []
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    future_str = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    for t in tasks:
        deadline = t.get("deadline", "")
        if deadline and today_str <= deadline <= future_str:
            upcoming.append(t)

    # Also group by date
    by_date: dict = {}
    for t in upcoming:
        d = t.get("deadline", "")
        by_date.setdefault(d, [])
        by_date[d].append(t)

    return {"upcoming": upcoming, "by_date": by_date, "total": len(upcoming)}


def _format_gcal_date(date_str: str) -> str:
    """Try to format date string for Google Calendar (YYYYMMDDTHHmmssZ)."""
    if not date_str:
        return ""
    # Remove common separators and try to parse
    clean = date_str.strip()
    try:
        # Try ISO format: YYYY-MM-DD HH:MM
        if " " in clean and ":" in clean:
            dt = datetime.strptime(clean[:16], "%Y-%m-%d %H:%M")
            return dt.strftime("%Y%m%dT%H%M%S")
        # Try date only: YYYY-MM-DD
        if "-" in clean and len(clean) >= 10:
            dt = datetime.strptime(clean[:10], "%Y-%m-%d")
            return dt.strftime("%Y%m%d")
        # Try DD/MM/YYYY
        if "/" in clean:
            parts = clean.split("/")
            if len(parts) == 3:
                dt = datetime.strptime(clean[:10], "%d/%m/%Y")
                return dt.strftime("%Y%m%d")
    except (ValueError, IndexError):
        pass
    return quote(clean)
