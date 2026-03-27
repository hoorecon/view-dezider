"""
Time Dezider + Time Store
- Daily schedule aggregation from CTT + Lifestyle + Unplanned
- AI-driven rescheduling with CLD + TEPFI analysis
- "Buy Time" analysis engine
"""

import uuid
import math
import json as json_module
import os
import logging
from datetime import datetime, timezone, timedelta, date as date_type
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter()

# Credit deduction helper
async def _deduct_ai_credits(user_id: str, action: str):
    try:
        from routes.payments import deduct_credits
        await deduct_credits(user_id, action)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Credit deduction skipped: {e}")

# ========================
# USER PREFERENCES
# ========================

@router.get("/time-dezider/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    """Get user's Time Dezider preferences (day boundaries, etc.)"""
    prefs = await db.time_preferences.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    if not prefs:
        prefs = {
            "user_id": user["user_id"],
            "day_start": "06:00",
            "day_end": "23:00",
            "default_task_duration": 60,
            "buffer_minutes": 15,
            "auto_save_schedule": True,
        }
        await db.time_preferences.insert_one(prefs)
        prefs.pop("_id", None)
    return prefs


@router.put("/time-dezider/preferences")
async def update_preferences(request: Request, user: dict = Depends(get_current_user)):
    """Update user's Time Dezider preferences"""
    body = await request.json()
    allowed = ["day_start", "day_end", "default_task_duration", "buffer_minutes", "auto_save_schedule"]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.time_preferences.update_one(
        {"user_id": user["user_id"]},
        {"$set": update},
        upsert=True
    )
    prefs = await db.time_preferences.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return prefs


# ========================
# DAILY SCHEDULE
# ========================

def _parse_time(t_str: str) -> Optional[int]:
    """Parse HH:MM to minutes since midnight. Returns None if invalid."""
    if not t_str or not isinstance(t_str, str):
        return None
    try:
        parts = t_str.strip().replace(".", ":").split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m
    except (ValueError, IndexError):
        return None


def _minutes_to_time(mins: int) -> str:
    """Convert minutes since midnight to HH:MM"""
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def _duration_to_minutes(dur_str: str) -> int:
    """Parse duration string like '1h', '30m', '1.5h', '90' to minutes."""
    if not dur_str:
        return 60
    dur_str = str(dur_str).strip().lower()
    try:
        if 'h' in dur_str:
            return int(float(dur_str.replace('h', '').strip()) * 60)
        elif 'm' in dur_str:
            return int(float(dur_str.replace('m', '').replace('min', '').strip()))
        else:
            val = float(dur_str)
            return int(val) if val > 10 else int(val * 60)
    except (ValueError, TypeError):
        return 60


@router.get("/time-dezider/daily")
async def get_daily_schedule(request: Request, user: dict = Depends(get_current_user)):
    """
    Aggregate CTT tasks + Lifestyle routines + Unplanned tasks into a unified daily timeline.
    Query params: date=YYYY-MM-DD (defaults to today)
    """
    params = request.query_params
    target_date = params.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # Get user preferences
    prefs = await db.time_preferences.find_one({"user_id": user["user_id"]}, {"_id": 0})
    day_start = prefs.get("day_start", "06:00") if prefs else "06:00"
    day_end = prefs.get("day_end", "23:00") if prefs else "23:00"

    time_blocks = []

    # 1. CTT Scheduled Tasks
    ctt_tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(500)

    for task in ctt_tasks:
        if task.get("current_status") in ["done", "cancelled"]:
            continue

        # Check if task applies to this date
        day_status = task.get("day_status", {})
        deadline = task.get("deadline", "")
        from_time = task.get("from_time", "")
        to_time = task.get("to_time", "")
        is_routine = task.get("is_routine", False)
        freq = task.get("frequency", "")

        applies = False
        # If it has a day_status entry for this date
        if target_date in day_status:
            applies = True
        # If deadline matches
        elif deadline and target_date in str(deadline):
            applies = True
        # If it's a routine with a time set (applies daily/weekly)
        elif is_routine and from_time:
            applies = True
        # If from_time contains the target date (e.g., "2026-03-27 09:00")
        elif from_time and target_date in str(from_time):
            applies = True
        # If from_time is just a time (HH:MM format, no date) - it's a recurring/undated task
        elif from_time and len(str(from_time).strip()) <= 5 and ":" in str(from_time):
            applies = True
        # If no date info but task is open, include it
        elif not deadline and task.get("current_status") == "open":
            applies = True

        if not applies:
            continue

        # Parse time
        start_mins = _parse_time(from_time)
        end_mins = _parse_time(to_time)
        duration = _duration_to_minutes(task.get("task_duration", ""))

        if start_mins is not None and end_mins is None:
            end_mins = start_mins + duration
        elif start_mins is None and end_mins is not None:
            start_mins = max(0, end_mins - duration)
        elif start_mins is None:
            start_mins = None
            end_mins = None

        block = {
            "id": f"ctt_{task['task_id']}",
            "source_type": "ctt",
            "source_id": task["task_id"],
            "title": task.get("task", "Untitled"),
            "description": task.get("sub_task", ""),
            "start_time": _minutes_to_time(start_mins) if start_mins is not None else None,
            "end_time": _minutes_to_time(end_mins) if end_mins is not None else None,
            "duration_minutes": duration,
            "priority": task.get("priority", "medium"),
            "life_area": task.get("life_area", ""),
            "is_flexible": task.get("priority") != "high",
            "is_delegatable": bool(task.get("task_owners") and len(task.get("task_owners", [])) > 0),
            "is_routine": is_routine,
            "status": day_status.get(target_date, task.get("current_status", "scheduled")),
            "project": task.get("project", ""),
        }
        time_blocks.append(block)

    # 2. Lifestyle Routines
    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0}
    ).to_list(200)

    # Check today's completions
    today_completions = await db.routine_completions.find(
        {"user_id": user["user_id"], "date": target_date},
        {"_id": 0}
    ).to_list(200)
    completed_routine_ids = {c["routine_id"] for c in today_completions}

    for routine in routines:
        freq = routine.get("frequency", "daily")
        # Simple frequency check
        if freq == "daily":
            applies = True
        elif freq == "weekly":
            try:
                d = datetime.strptime(target_date, "%Y-%m-%d")
                applies = d.weekday() < 5  # Mon-Fri for weekly
            except (ValueError, TypeError):
                applies = True
        else:
            applies = True

        if not applies:
            continue

        time_slot = routine.get("time_slot", "")
        start_mins = _parse_time(time_slot)
        duration = 30  # Default routine duration

        if start_mins is not None:
            end_mins = start_mins + duration
        else:
            start_mins = None
            end_mins = None

        block = {
            "id": f"routine_{routine['routine_id']}",
            "source_type": "lifestyle",
            "source_id": routine["routine_id"],
            "title": routine.get("name", "Routine"),
            "description": routine.get("description", ""),
            "start_time": _minutes_to_time(start_mins) if start_mins is not None else None,
            "end_time": _minutes_to_time(end_mins) if end_mins is not None else None,
            "duration_minutes": duration,
            "priority": routine.get("priority", "medium"),
            "life_area": routine.get("life_area", ""),
            "is_flexible": routine.get("priority") != "high",
            "is_delegatable": False,
            "is_routine": True,
            "status": "completed" if routine["routine_id"] in completed_routine_ids else "scheduled",
            "project": "",
        }
        time_blocks.append(block)

    # 3. Unplanned Tasks (stored separately)
    unplanned = await db.time_blocks_unplanned.find(
        {"user_id": user["user_id"], "date": target_date},
        {"_id": 0}
    ).to_list(50)

    for up in unplanned:
        block = {
            "id": up.get("block_id", f"unplanned_{up.get('_id', '')}"),
            "source_type": "unplanned",
            "source_id": up.get("block_id"),
            "title": up.get("title", "Unplanned Task"),
            "description": up.get("description", ""),
            "start_time": up.get("start_time"),
            "end_time": up.get("end_time"),
            "duration_minutes": up.get("duration_minutes", 60),
            "priority": up.get("priority", "high"),
            "life_area": up.get("life_area", ""),
            "is_flexible": False,
            "is_delegatable": up.get("is_delegatable", False),
            "is_routine": False,
            "status": up.get("status", "scheduled"),
            "project": "",
        }
        time_blocks.append(block)

    # Sort by start_time (None at end)
    def sort_key(b):
        st = _parse_time(b.get("start_time", "") or "")
        return st if st is not None else 9999
    time_blocks.sort(key=sort_key)

    # Calculate stats
    total_scheduled = sum(b["duration_minutes"] for b in time_blocks if b.get("start_time"))
    total_unscheduled = sum(b["duration_minutes"] for b in time_blocks if not b.get("start_time"))
    day_start_mins = _parse_time(day_start) or 360
    day_end_mins = _parse_time(day_end) or 1380
    available_minutes = day_end_mins - day_start_mins
    free_minutes = max(0, available_minutes - total_scheduled)

    return {
        "date": target_date,
        "day_start": day_start,
        "day_end": day_end,
        "blocks": time_blocks,
        "stats": {
            "total_blocks": len(time_blocks),
            "scheduled_minutes": total_scheduled,
            "unscheduled_minutes": total_unscheduled,
            "available_minutes": available_minutes,
            "free_minutes": free_minutes,
            "utilization_percent": round((total_scheduled / max(available_minutes, 1)) * 100, 1),
        }
    }


# ========================
# UNPLANNED TASK
# ========================

@router.post("/time-dezider/unplanned-task")
async def add_unplanned_task(request: Request, user: dict = Depends(get_current_user)):
    """Add an unplanned task that needs to be accommodated in the daily schedule."""
    body = await request.json()
    block_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    target_date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    doc = {
        "block_id": block_id,
        "user_id": user["user_id"],
        "date": target_date,
        "title": body.get("title", ""),
        "description": body.get("description", ""),
        "duration_minutes": body.get("duration_minutes", 60),
        "priority": body.get("priority", "high"),
        "life_area": body.get("life_area", ""),
        "is_delegatable": body.get("is_delegatable", False),
        "start_time": body.get("start_time"),
        "end_time": body.get("end_time"),
        "status": "scheduled",
        "created_at": now,
    }
    await db.time_blocks_unplanned.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/time-dezider/unplanned-task/{block_id}")
async def remove_unplanned_task(block_id: str, user: dict = Depends(get_current_user)):
    result = await db.time_blocks_unplanned.delete_one({"block_id": block_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"message": "Unplanned task removed"}


# ========================
# AI RESCHEDULING
# ========================

@router.post("/time-dezider/reschedule")
async def ai_reschedule(request: Request, user: dict = Depends(get_current_user)):
    """
    AI-driven rescheduling when an unplanned task creates conflicts.
    Uses CLD relationships, TEPFI resources (all 5 dimensions), and priority analysis.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    body = await request.json()

    # Deduct credits
    await _deduct_ai_credits(user["user_id"], "time_dezider_reschedule")

    target_date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    unplanned_title = body.get("unplanned_title", "")
    unplanned_duration = body.get("unplanned_duration", 60)
    unplanned_priority = body.get("unplanned_priority", "high")

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Gather current schedule
    from starlette.datastructures import QueryParams
    # Manually fetch daily schedule
    prefs = await db.time_preferences.find_one({"user_id": user["user_id"]}, {"_id": 0})
    day_start = prefs.get("day_start", "06:00") if prefs else "06:00"
    day_end = prefs.get("day_end", "23:00") if prefs else "23:00"

    # Get all blocks
    ctt_tasks = await db.ctt_tasks.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)
    routines = await db.lifestyle_routines.find({"user_id": user["user_id"], "is_active": True}, {"_id": 0}).to_list(200)

    # Build schedule description
    schedule_items = []
    for task in ctt_tasks:
        ft = task.get("from_time", "")
        tt = task.get("to_time", "")
        dur = task.get("task_duration", "")
        if ft or task.get("current_status") == "open":
            schedule_items.append({
                "id": task["task_id"],
                "type": "ctt_task",
                "title": task.get("task", ""),
                "from_time": ft,
                "to_time": tt,
                "duration": dur or "60m",
                "priority": task.get("priority", "medium"),
                "life_area": task.get("life_area", ""),
                "is_routine": task.get("is_routine", False),
                "flexible": task.get("priority") != "high",
                "delegatable": bool(task.get("task_owners")),
                "owners": task.get("task_owners", []),
            })

    for r in routines:
        schedule_items.append({
            "id": r["routine_id"],
            "type": "routine",
            "title": r.get("name", ""),
            "from_time": r.get("time_slot", ""),
            "to_time": "",
            "duration": "30m",
            "priority": r.get("priority", "medium"),
            "life_area": r.get("life_area", ""),
            "is_routine": True,
            "flexible": r.get("priority") != "high",
            "delegatable": False,
        })

    # Get TEPFI data for delegation/automation analysis
    tepfi_entries = await db.tepfi_entries.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)
    tepfi_summary = []
    for entry in tepfi_entries:
        matrix = entry.get("matrix", {})
        tepfi_summary.append({
            "title": entry.get("title", ""),
            "life_area": entry.get("life_area", ""),
            "people_self": matrix.get("people", {}).get("self", {}),
            "people_micro": matrix.get("people", {}).get("micro", {}),
            "people_macro": matrix.get("people", {}).get("macro", {}),
            "effort_self": matrix.get("effort", {}).get("self", {}),
            "effort_micro": matrix.get("effort", {}).get("micro", {}),
            "finance_self": matrix.get("finance", {}).get("self", {}),
            "finance_micro": matrix.get("finance", {}).get("micro", {}),
            "infrastructure_self": matrix.get("infrastructure", {}).get("self", {}),
            "infrastructure_micro": matrix.get("infrastructure", {}).get("micro", {}),
        })

    # Get CLD data if exists for any recent decision
    cld_data = await db.cld_diagrams.find({"user_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(3)
    cld_context = ""
    if cld_data:
        cld = cld_data[0]
        nodes = [n.get("name", "") for n in cld.get("nodes", [])]
        loops = [lp.get("name", "") for lp in cld.get("loops", [])]
        cld_context = f"\nCLD Context: Factors={nodes}, Loops={loops}"

    schedule_json = json_module.dumps(schedule_items[:30], indent=1, default=str)
    tepfi_json = json_module.dumps(tepfi_summary[:10], indent=1, default=str)

    prompt = f"""You are a Time Management AI for the Dezider decision framework. 

CURRENT SCHEDULE for {target_date} (day: {day_start} to {day_end}):
{schedule_json}

UNPLANNED TASK TO ACCOMMODATE:
- Title: {unplanned_title}
- Duration: {unplanned_duration} minutes
- Priority: {unplanned_priority}

TEPFI RESOURCES (People, Effort, Finance, Infrastructure available for delegation/optimization):
{tepfi_json}
{cld_context}

TASK: Generate rescheduling suggestions to accommodate the unplanned task. For each suggestion:
1. Analyze conflicts and find optimal time slots
2. Consider TEPFI resources:
   - People layer: Who specifically (from micro/macro) can tasks be delegated to?
   - Effort layer: Can effort be reduced by simplifying the task?
   - Finance layer: Can money solve this (hire help, buy tools)?
   - Infrastructure layer: Can this be automated?
3. Use priority hierarchy: high > medium > low
4. Prefer moving flexible, low-priority tasks
5. Suggest specific time changes

Return ONLY valid JSON:
{{
  "suggestions": [
    {{
      "action": "move|compress|delegate|eliminate|split",
      "target_block_id": "id of the task/routine to modify",
      "target_title": "name of the task",
      "description": "Clear explanation of what to do",
      "new_start_time": "HH:MM or null",
      "new_end_time": "HH:MM or null",
      "new_duration_minutes": 60,
      "delegate_to": "specific person name or null",
      "tepfi_lever": "people|effort|finance|infrastructure|time",
      "tepfi_layer": "self|micro|macro",
      "impact_score": 1-10,
      "time_saved_minutes": 0,
      "reasoning": "brief reason"
    }}
  ],
  "recommended_slot": {{
    "start_time": "HH:MM",
    "end_time": "HH:MM"
  }},
  "overall_assessment": "brief summary of schedule health"
}}"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"td_resched_{user['user_id']}_{uuid.uuid4().hex[:6]}",
            system_message="You are an expert time management AI. Analyze schedules using TEPFI framework (Time, Effort, People, Finance, Infrastructure) across Self/Micro/Macro layers."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json_module.loads(text)
        return result
    except json_module.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid format")
    except Exception as e:
        logger.error(f"Reschedule failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rescheduling failed: {str(e)[:200]}")


# ========================
# APPROVE RESCHEDULING
# ========================

@router.post("/time-dezider/approve")
async def approve_reschedule(request: Request, user: dict = Depends(get_current_user)):
    """
    Apply approved rescheduling suggestions.
    Updates actual CTT tasks and Lifestyle routines.
    Body: { suggestions: [{ target_block_id, action, new_start_time, new_end_time, ... }] }
    """
    body = await request.json()
    suggestions = body.get("suggestions", [])
    applied = 0
    now = datetime.now(timezone.utc).isoformat()

    for sug in suggestions:
        block_id = sug.get("target_block_id", "")
        action = sug.get("action", "")
        new_start = sug.get("new_start_time")
        new_end = sug.get("new_end_time")
        new_duration = sug.get("new_duration_minutes")

        if block_id.startswith("ctt_") or (not block_id.startswith("routine_") and not block_id.startswith("unplanned_")):
            task_id = block_id.replace("ctt_", "")
            update = {"updated_at": now}
            if new_start:
                update["from_time"] = new_start
            if new_end:
                update["to_time"] = new_end
            if new_duration:
                update["task_duration"] = f"{new_duration}m"
            if action == "eliminate":
                update["current_status"] = "cancelled"
            elif action == "delegate":
                delegate_to = sug.get("delegate_to", "")
                if delegate_to:
                    update["task_owners"] = [delegate_to]
                    update["remarks"] = f"Delegated to {delegate_to} by Time Dezider"

            result = await db.ctt_tasks.update_one(
                {"task_id": task_id, "user_id": user["user_id"]},
                {"$set": update}
            )
            if result.modified_count > 0:
                applied += 1

        elif block_id.startswith("routine_"):
            routine_id = block_id.replace("routine_", "")
            update = {"updated_at": now}
            if new_start:
                update["time_slot"] = new_start
            if action == "eliminate":
                update["is_active"] = False

            result = await db.lifestyle_routines.update_one(
                {"routine_id": routine_id, "user_id": user["user_id"]},
                {"$set": update}
            )
            if result.modified_count > 0:
                applied += 1

    return {"message": f"Applied {applied} rescheduling changes", "applied": applied}


# ========================
# TIME STORE - BUY TIME
# ========================

@router.get("/time-store/budget")
async def get_time_budget(request: Request, user: dict = Depends(get_current_user)):
    """
    Calculate current time allocation across all commitments.
    Query: period=daily|weekly (default: daily)
    """
    params = request.query_params
    period = params.get("period", "daily")

    prefs = await db.time_preferences.find_one({"user_id": user["user_id"]}, {"_id": 0})
    day_start = prefs.get("day_start", "06:00") if prefs else "06:00"
    day_end = prefs.get("day_end", "23:00") if prefs else "23:00"
    day_start_mins = _parse_time(day_start) or 360
    day_end_mins = _parse_time(day_end) or 1380
    available_per_day = day_end_mins - day_start_mins

    ctt_tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"], "current_status": {"$nin": ["done", "cancelled"]}},
        {"_id": 0}
    ).to_list(500)

    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0}
    ).to_list(200)

    # Build allocation by life area
    by_area = {}
    by_type = {"ctt_routine": 0, "ctt_onetime": 0, "lifestyle": 0}
    all_items = []

    for task in ctt_tasks:
        dur = _duration_to_minutes(task.get("task_duration", "60"))
        is_routine = task.get("is_routine", False)
        freq = task.get("frequency", "")

        # Calculate daily equivalent
        if is_routine:
            if freq == "weekly":
                daily_mins = dur / 7
            elif freq == "monthly":
                daily_mins = dur / 30
            else:
                daily_mins = dur
            by_type["ctt_routine"] += daily_mins
        else:
            daily_mins = dur  # one-time tasks count for their day
            by_type["ctt_onetime"] += daily_mins

        area = task.get("life_area", "other") or "other"
        by_area.setdefault(area, 0)
        by_area[area] += daily_mins

        all_items.append({
            "id": task["task_id"],
            "type": "ctt",
            "title": task.get("task", ""),
            "daily_minutes": round(daily_mins, 1),
            "priority": task.get("priority", "medium"),
            "life_area": area,
            "is_routine": is_routine,
            "is_delegatable": bool(task.get("task_owners")),
        })

    for routine in routines:
        dur = 30  # default routine duration
        freq = routine.get("frequency", "daily")
        if freq == "weekly":
            daily_mins = dur / 7
        elif freq == "monthly":
            daily_mins = dur / 30
        else:
            daily_mins = dur

        by_type["lifestyle"] += daily_mins
        area = routine.get("life_area", "other") or "other"
        by_area.setdefault(area, 0)
        by_area[area] += daily_mins

        all_items.append({
            "id": routine["routine_id"],
            "type": "lifestyle",
            "title": routine.get("name", ""),
            "daily_minutes": round(daily_mins, 1),
            "priority": routine.get("priority", "medium"),
            "life_area": area,
            "is_routine": True,
            "is_delegatable": False,
        })

    total_committed = sum(by_area.values())
    multiplier = 7 if period == "weekly" else 1
    available = available_per_day * multiplier

    return {
        "period": period,
        "available_minutes": round(available, 1),
        "committed_minutes": round(total_committed * multiplier, 1),
        "free_minutes": round((available_per_day - total_committed) * multiplier, 1),
        "utilization_percent": round((total_committed / max(available_per_day, 1)) * 100, 1),
        "by_area": {k: round(v * multiplier, 1) for k, v in by_area.items()},
        "by_type": {k: round(v * multiplier, 1) for k, v in by_type.items()},
        "items": sorted(all_items, key=lambda x: x["daily_minutes"], reverse=True),
        "day_start": day_start,
        "day_end": day_end,
    }


@router.post("/time-store/analyze")
async def analyze_time_store(request: Request, user: dict = Depends(get_current_user)):
    """
    AI-powered analysis to find where to free up desired time.
    Uses ALL 5 TEPFI dimensions × 3 layers + CLD analysis.
    Body: { desired_free_hours: float, period: 'daily'|'weekly' }
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    body = await request.json()

    # Deduct credits
    await _deduct_ai_credits(user["user_id"], "time_store_analyze")

    desired_hours = body.get("desired_free_hours", 2)
    period = body.get("period", "daily")
    desired_minutes = desired_hours * 60

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Gather ALL data
    ctt_tasks = await db.ctt_tasks.find(
        {"user_id": user["user_id"], "current_status": {"$nin": ["done", "cancelled"]}},
        {"_id": 0}
    ).to_list(500)

    routines = await db.lifestyle_routines.find(
        {"user_id": user["user_id"], "is_active": True},
        {"_id": 0}
    ).to_list(200)

    tepfi_entries = await db.tepfi_entries.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(50)

    goals = await db.gem_goals.find(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0}
    ).to_list(100)

    cld_data = await db.cld_diagrams.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(3)

    # Build comprehensive context
    activities = []
    for task in ctt_tasks:
        dur = _duration_to_minutes(task.get("task_duration", "60"))
        activities.append({
            "id": task["task_id"],
            "type": "ctt_task",
            "title": task.get("task", ""),
            "duration_minutes": dur,
            "is_routine": task.get("is_routine", False),
            "frequency": task.get("frequency", "once"),
            "priority": task.get("priority", "medium"),
            "life_area": task.get("life_area", ""),
            "owners": task.get("task_owners", []),
            "project": task.get("project", ""),
        })

    for r in routines:
        activities.append({
            "id": r["routine_id"],
            "type": "routine",
            "title": r.get("name", ""),
            "duration_minutes": 30,
            "is_routine": True,
            "frequency": r.get("frequency", "daily"),
            "priority": r.get("priority", "medium"),
            "life_area": r.get("life_area", ""),
        })

    # Full TEPFI summary with all 5 dimensions × 3 layers
    tepfi_full = []
    for entry in tepfi_entries:
        m = entry.get("matrix", {})
        tepfi_full.append({
            "title": entry.get("title", ""),
            "life_area": entry.get("life_area", ""),
            "time": {"self": m.get("time", {}).get("self", {}), "micro": m.get("time", {}).get("micro", {}), "macro": m.get("time", {}).get("macro", {})},
            "effort": {"self": m.get("effort", {}).get("self", {}), "micro": m.get("effort", {}).get("micro", {}), "macro": m.get("effort", {}).get("macro", {})},
            "people": {"self": m.get("people", {}).get("self", {}), "micro": m.get("people", {}).get("micro", {}), "macro": m.get("people", {}).get("macro", {})},
            "finance": {"self": m.get("finance", {}).get("self", {}), "micro": m.get("finance", {}).get("micro", {}), "macro": m.get("finance", {}).get("macro", {})},
            "infrastructure": {"self": m.get("infrastructure", {}).get("self", {}), "micro": m.get("infrastructure", {}).get("micro", {}), "macro": m.get("infrastructure", {}).get("macro", {})},
        })

    # CLD context
    cld_context = ""
    if cld_data:
        cld = cld_data[0]
        cld_nodes = [{"name": n.get("name", ""), "centrality": n.get("centrality", 0.5), "classification": n.get("classification", "")} for n in cld.get("nodes", [])]
        cld_links = [{"from": lk.get("from_id", ""), "to": lk.get("to_id", ""), "type": lk.get("link_type", ""), "strength": lk.get("strength", 5)} for lk in cld.get("links", [])]
        cld_context = f"\nCLD Analysis:\n  Nodes: {json_module.dumps(cld_nodes, default=str)}\n  Links: {json_module.dumps(cld_links[:15], default=str)}"

    goals_context = json_module.dumps([{"title": g.get("title", ""), "life_area": g.get("life_area", ""), "priority": g.get("priority", "")} for g in goals[:15]], default=str)

    prompt = f"""You are a Time Store AI for the Dezider framework. The user wants to FREE UP {desired_hours} hours {period}.

CURRENT ACTIVITIES ({len(activities)} total):
{json_module.dumps(activities[:40], indent=1, default=str)}

TEPFI RESOURCES (5 dimensions × 3 layers):
{json_module.dumps(tepfi_full[:10], indent=1, default=str)}

ACTIVE GOALS:
{goals_context}
{cld_context}

ANALYSIS TASK: For each activity, evaluate using ALL 5 TEPFI dimensions:
1. **TIME** (Self/Micro/Macro): Can the time allocation be reduced?
2. **EFFORT** (8 sub-dimensions × 3 layers): Attitude, Knowledge, Skills, Physical Health, Mental State, Emotional Wellness, Energy Level, Action - Can effort be optimized through any of these components?
3. **PEOPLE** (Self/Micro/Macro): Can someone else do it? Name specific people from TEPFI micro/macro data if available
4. **FINANCE** (Self/Micro/Macro): Can money solve this? (Hire help, buy automation tools, outsource)
5. **INFRASTRUCTURE** (Self/Micro/Macro): Can tools/systems automate this?

For each suggestion, specify one of these actions:
- ELIMINATE: Remove entirely (low CLD centrality, low goal alignment)
- REDUCE: Cut duration (over-allocated based on actual need)
- DELEGATE: Give to specific person (from TEPFI People layer)
- BATCH: Combine with similar tasks
- AUTOMATE: Use tools/systems (from TEPFI Infrastructure)

Target: Find enough activities to free {desired_minutes} minutes {period}.

Return ONLY valid JSON:
{{
  "current_total_minutes_{period}": 0,
  "target_free_minutes": {desired_minutes},
  "suggestions": [
    {{
      "activity_id": "id",
      "activity_title": "name",
      "activity_type": "ctt_task|routine",
      "action": "eliminate|reduce|delegate|batch|automate",
      "description": "Clear actionable description",
      "current_minutes_{period}": 60,
      "suggested_minutes_{period}": 30,
      "time_saved_minutes": 30,
      "tepfi_dimension": "time|effort|people|finance|infrastructure",
      "tepfi_layer": "self|micro|macro",
      "delegate_to": "specific person name or null",
      "tool_suggestion": "specific tool/system or null",
      "cost_estimate": "monetary cost if applicable or null",
      "impact_risk": 1-10,
      "goal_alignment_score": 1-10,
      "cld_centrality": 0.0-1.0,
      "reasoning": "brief explanation referencing TEPFI and CLD data"
    }}
  ],
  "total_time_recoverable": 0,
  "feasibility": "achievable|partial|difficult",
  "overall_recommendation": "summary of the best strategy"
}}"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ts_analyze_{user['user_id']}_{uuid.uuid4().hex[:6]}",
            system_message="You are an expert time optimization AI using the TEPFI framework (Time, Effort, People, Finance, Infrastructure) across Self/Micro/Macro layers with Causal Loop Diagram awareness."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json_module.loads(text)
        return result
    except json_module.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid format")
    except Exception as e:
        logger.error(f"Time Store analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)[:200]}")


@router.post("/time-store/apply")
async def apply_time_store_suggestions(request: Request, user: dict = Depends(get_current_user)):
    """
    Apply selected Time Store suggestions.
    Updates CTT tasks and Lifestyle routines based on approved optimization actions.
    Body: { suggestions: [{ activity_id, activity_type, action, suggested_minutes, delegate_to, ... }] }
    """
    body = await request.json()
    suggestions = body.get("suggestions", [])
    applied = 0
    now = datetime.now(timezone.utc).isoformat()

    for sug in suggestions:
        activity_id = sug.get("activity_id", "")
        activity_type = sug.get("activity_type", "")
        action = sug.get("action", "")
        new_mins = sug.get("suggested_minutes", None)
        delegate_to = sug.get("delegate_to")

        if activity_type == "ctt_task":
            update = {"updated_at": now}
            if action == "eliminate":
                update["current_status"] = "cancelled"
                update["remarks"] = "Cancelled by Time Store optimization"
            elif action == "reduce" and new_mins is not None:
                update["task_duration"] = f"{new_mins}m"
                update["remarks"] = "Duration reduced by Time Store"
            elif action == "delegate" and delegate_to:
                update["task_owners"] = [delegate_to]
                update["remarks"] = f"Delegated to {delegate_to} by Time Store"
            elif action == "automate":
                update["remarks"] = f"Flagged for automation: {sug.get('tool_suggestion', '')}"

            result = await db.ctt_tasks.update_one(
                {"task_id": activity_id, "user_id": user["user_id"]},
                {"$set": update}
            )
            if result.modified_count > 0:
                applied += 1

        elif activity_type == "routine":
            update = {"updated_at": now}
            if action == "eliminate":
                update["is_active"] = False
            elif action == "reduce":
                update["expected_value"] = f"Reduced to {new_mins}m"

            result = await db.lifestyle_routines.update_one(
                {"routine_id": activity_id, "user_id": user["user_id"]},
                {"$set": update}
            )
            if result.modified_count > 0:
                applied += 1

    return {"message": f"Applied {applied} Time Store optimizations", "applied": applied}
