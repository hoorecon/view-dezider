"""
GEM Flight Model for Success
- 7-Step Process (SMART iPod Celebrations)
- Flight Model visual (12 secrets mapped to flight parts)
- GIS Model (Grace, Involvement, Support)
- iGIS Model (inner awareness, Grace, Involvement, Support)
- Orchestrates ALL modules: CTT, Lifestyle, TEPFI, CLD, Solutions, PRR
"""

import uuid
import os
import math
import json as json_module
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gem-flight", tags=["GEM Flight Model"])


# ========================
# 12 SECRETS CONFIGURATION
# ========================

SECRETS_CONFIG = [
    {"key": "vision", "num": "A", "name": "Vision", "flight_part": "Skyway / Flight Path", "icon": "navigate", "color": "#818CF8"},
    {"key": "goal_clarity", "num": "1", "name": "Goal Clarity", "flight_part": "Cockpit", "icon": "compass", "color": "#3B82F6"},
    {"key": "practicality", "num": "2", "name": "Practicality", "flight_part": "Left Wing", "icon": "analytics", "color": "#10B981"},
    {"key": "creativity", "num": "3", "name": "Creativity", "flight_part": "Right Wing", "icon": "color-palette", "color": "#F59E0B"},
    {"key": "intensity", "num": "4", "name": "Intensity", "flight_part": "Engine", "icon": "flash", "color": "#EF4444"},
    {"key": "objectivity", "num": "5", "name": "Objectivity", "flight_part": "Brakes & Wheels", "icon": "scale", "color": "#8B5CF6"},
    {"key": "physical_health", "num": "6", "name": "Physical Health", "flight_part": "Flight Body", "icon": "fitness", "color": "#EC4899"},
    {"key": "mental_strength", "num": "7", "name": "Mental Strength", "flight_part": "Engine Condition", "icon": "bulb", "color": "#14B8A6"},
    {"key": "emotional_balance", "num": "8", "name": "Emotional Balance", "flight_part": "Passenger Area", "icon": "heart", "color": "#F43F5E"},
    {"key": "energy_levels", "num": "9", "name": "Energy Levels", "flight_part": "Fuel", "icon": "battery-charging", "color": "#22C55E"},
    {"key": "capability", "num": "10", "name": "Capability", "flight_part": "Tail", "icon": "build", "color": "#6366F1"},
    {"key": "external_image", "num": "B", "name": "External Image", "flight_part": "Canvas / Brand", "icon": "megaphone", "color": "#D946EF"},
]

SEVEN_STEPS = [
    {"step": 1, "name": "Vision & Goal Clarity", "mnemonic": "SMART", "desc": "Define your SMART goal and vision. Where do you want to go?", "icon": "flag"},
    {"step": 2, "name": "Practicality", "mnemonic": "I", "desc": "Honestly assess where you are right now. Current reality check.", "icon": "location"},
    {"step": 3, "name": "Plan Your Mission", "mnemonic": "P", "desc": "Identify milestones, obstacles, solutions. Create the roadmap.", "icon": "map"},
    {"step": 4, "name": "Test Drive", "mnemonic": "P", "desc": "Validate your plan in a simulated or safe environment.", "icon": "speedometer"},
    {"step": 5, "name": "Organize Resources", "mnemonic": "O", "desc": "Organize all TEPFI resources (Time, Effort, People, Finance, Infra).", "icon": "grid"},
    {"step": 6, "name": "Initiate & Drive", "mnemonic": "D", "desc": "Execute dynamically through 4 gears: Protect → Inspire → Integrate → Expand.", "icon": "rocket"},
    {"step": 7, "name": "Celebrate & Restore", "mnemonic": "Celebration", "desc": "Celebrate success and restore balance across all life areas.", "icon": "trophy"},
]

GEARS = [
    {"gear": 1, "name": "Protect Yourself", "desc": "Ensure your own safety and stability first", "icon": "shield-checkmark"},
    {"gear": 2, "name": "Inspire Others", "desc": "Emerge as an example and inspire your team", "icon": "star"},
    {"gear": 3, "name": "Integrate & Regulate", "desc": "Integrate resources and regulate synergy", "icon": "git-merge"},
    {"gear": 4, "name": "Expand & Scale", "desc": "Scale the mission beyond initial scope", "icon": "expand"},
]


# ========================
# FLIGHT PROJECT CRUD
# ========================

@router.get("/config")
async def get_config():
    """Get the Flight Model configuration (secrets, steps, gears)"""
    return {
        "secrets": SECRETS_CONFIG,
        "seven_steps": SEVEN_STEPS,
        "gears": GEARS,
    }


@router.post("/projects")
async def create_flight_project(request: Request, user: dict = Depends(get_current_user)):
    """Create a new Flight Model project (goal journey from Point A to Point B)"""
    body = await request.json()
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    project = {
        "project_id": project_id,
        "user_id": user["user_id"],
        "title": body.get("title", ""),
        "vision": body.get("vision", ""),
        "goal": body.get("goal", ""),
        "goal_smart": {
            "specific": body.get("specific", ""),
            "measurable": body.get("measurable", ""),
            "achievable": body.get("achievable", ""),
            "realistic": body.get("realistic", ""),
            "time_bound": body.get("time_bound", ""),
        },
        "point_a": body.get("point_a", ""),  # Where I am now
        "point_b": body.get("point_b", ""),  # Where I want to be
        "life_area": body.get("life_area", ""),
        "current_step": 1,
        "current_gear": 0,  # 0 = not in drive phase yet
        "progress_percent": 0,
        "status": "active",  # active, paused, completed, abandoned

        # 7-step data
        "steps": {str(i): {
            "status": "pending",  # pending, in_progress, completed
            "milestones": [],
            "obstacles": [],
            "solutions": [],
            "notes": "",
            "started_at": None,
            "completed_at": None,
        } for i in range(1, 8)},

        # 12 secrets scores (auto-computed + manual override)
        "secrets_scores": {s["key"]: {"auto_score": 0, "manual_score": None, "notes": ""} for s in SECRETS_CONFIG},

        # GIS Model scores
        "gis": {
            "grace": {"score": 0, "notes": "", "source": "astrology"},
            "involvement": {"score": 0, "notes": "", "auto_computed": True},
            "support_micro": {"score": 0, "notes": ""},
            "support_macro": {"score": 0, "notes": ""},
        },

        # iGIS Model
        "igis": {
            "inner_awareness": {"score": 0, "notes": "", "sources": ["introspection", "energy_healing", "manifestation"]},
            "grace": {"score": 0, "notes": ""},
            "involvement": {"score": 0, "notes": ""},
            "support": {"score": 0, "notes": ""},
        },

        # Linked modules
        "linked_gem_goals": body.get("linked_gem_goals", []),
        "linked_decisions": body.get("linked_decisions", []),
        "linked_ctt_tasks": [],
        "linked_routines": [],

        "created_at": now,
        "updated_at": now,
    }

    await db.flight_projects.insert_one(project)
    project.pop("_id", None)
    return project


@router.get("/projects")
async def list_flight_projects(user: dict = Depends(get_current_user)):
    """List all flight projects for the user"""
    projects = await db.flight_projects.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return {"projects": projects}


@router.get("/projects/{project_id}")
async def get_flight_project(project_id: str, user: dict = Depends(get_current_user)):
    """Get a specific flight project with auto-computed scores"""
    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Flight project not found")
    return project


@router.put("/projects/{project_id}")
async def update_flight_project(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update flight project fields"""
    body = await request.json()
    allowed = [
        "title", "vision", "goal", "goal_smart", "point_a", "point_b",
        "life_area", "current_step", "current_gear", "progress_percent",
        "status", "steps", "secrets_scores", "gis", "igis",
        "linked_gem_goals", "linked_decisions", "linked_ctt_tasks", "linked_routines",
    ]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Flight project not found")

    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    return project


@router.delete("/projects/{project_id}")
async def delete_flight_project(project_id: str, user: dict = Depends(get_current_user)):
    result = await db.flight_projects.delete_one(
        {"project_id": project_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Flight project deleted"}


# ========================
# STEP MANAGEMENT
# ========================

@router.put("/projects/{project_id}/step/{step_num}")
async def update_step(project_id: str, step_num: int, request: Request, user: dict = Depends(get_current_user)):
    """Update a specific step's data (milestones, obstacles, solutions, status)"""
    if step_num < 1 or step_num > 7:
        raise HTTPException(status_code=400, detail="Step must be 1-7")

    body = await request.json()
    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    steps = project.get("steps", {})
    step_key = str(step_num)
    step_data = steps.get(step_key, {})

    # Update step fields
    for field in ["status", "milestones", "obstacles", "solutions", "notes"]:
        if field in body:
            step_data[field] = body[field]

    now = datetime.now(timezone.utc).isoformat()
    if body.get("status") == "in_progress" and not step_data.get("started_at"):
        step_data["started_at"] = now
    if body.get("status") == "completed":
        step_data["completed_at"] = now

    steps[step_key] = step_data

    # Auto-update current_step and progress
    completed_steps = sum(1 for s in steps.values() if s.get("status") == "completed")
    progress = round((completed_steps / 7) * 100)
    current_step = step_num
    if body.get("status") == "completed" and step_num < 7:
        current_step = step_num + 1

    # Auto-set gear if entering step 6
    current_gear = project.get("current_gear", 0)
    if step_num == 6 and body.get("status") == "in_progress" and current_gear == 0:
        current_gear = 1

    await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$set": {
            f"steps.{step_key}": step_data,
            "current_step": current_step,
            "progress_percent": progress,
            "current_gear": current_gear,
            "updated_at": now,
            "status": "completed" if completed_steps == 7 else "active",
        }}
    )

    return {"step": step_data, "current_step": current_step, "progress_percent": progress}


@router.put("/projects/{project_id}/gear/{gear_num}")
async def update_gear(project_id: str, gear_num: int, request: Request, user: dict = Depends(get_current_user)):
    """Update current gear in the Drive phase (Step 6)"""
    if gear_num < 1 or gear_num > 4:
        raise HTTPException(status_code=400, detail="Gear must be 1-4")

    result = await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$set": {"current_gear": gear_num, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"current_gear": gear_num}


# ========================
# AUTO-COMPUTE FLIGHT SCORES
# ========================

@router.get("/projects/{project_id}/flight-score")
async def compute_flight_scores(project_id: str, user: dict = Depends(get_current_user)):
    """
    Auto-compute the 12 secrets scores by pulling data from ALL linked modules:
    - Goal Clarity → GEM goals completion
    - Practicality → CTT tasks with from/to times set
    - Creativity → Solutions Store solutions count
    - Intensity → Lifestyle streaks / daily completion rate
    - Objectivity → CLD analysis (balance of reinforcing/balancing loops)
    - Physical Health → TEPFI Effort: Physical Health
    - Mental Strength → TEPFI Effort: Mental State + Attitude
    - Emotional Balance → TEPFI Effort: Emotional Wellness
    - Energy Levels → TEPFI Effort: Energy Level
    - Capability → TEPFI Effort: Knowledge + Skills + Action
    - Vision → Project vision clarity score
    - External Image → Solutions reviews / external feedback
    """
    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    uid = user["user_id"]
    scores = {}

    # --- Vision: Based on whether vision text is set and detailed
    vision_text = project.get("vision", "")
    scores["vision"] = min(10, max(1, len(vision_text) // 20 + (5 if vision_text else 0)))

    # --- Goal Clarity: SMART completeness
    smart = project.get("goal_smart", {})
    smart_filled = sum(1 for v in smart.values() if v and str(v).strip())
    scores["goal_clarity"] = min(10, smart_filled * 2)

    # --- Practicality: CTT tasks that have from_time/to_time set
    ctt_tasks = await db.ctt_tasks.find({"user_id": uid}, {"_id": 0}).to_list(200)
    tasks_with_time = sum(1 for t in ctt_tasks if t.get("from_time") and t.get("to_time"))
    total_tasks = max(len(ctt_tasks), 1)
    scores["practicality"] = min(10, round((tasks_with_time / total_tasks) * 10))

    # --- Creativity: Solutions in Solutions Store
    solutions = await db.solutions_store.find({"user_id": uid}, {"_id": 0}).to_list(100)
    scores["creativity"] = min(10, max(1, len(solutions) * 2))

    # --- Intensity: Lifestyle routine completion rate (streaks)
    routines = await db.lifestyle_routines.find({"user_id": uid, "is_active": True}, {"_id": 0}).to_list(100)
    total_streak = sum(r.get("streak", 0) for r in routines)
    scores["intensity"] = min(10, max(1, total_streak // max(len(routines), 1) + 1))

    # --- Objectivity: CLD balance (reinforcing vs balancing links)
    clds = await db.cld_diagrams.find({"user_id": uid}, {"_id": 0}).to_list(10)
    if clds:
        total_links = sum(len(c.get("links", [])) for c in clds)
        bal_links = sum(1 for c in clds for lk in c.get("links", []) if lk.get("link_type") == "balancing")
        ratio = bal_links / max(total_links, 1)
        scores["objectivity"] = min(10, max(1, round(ratio * 10) + 3))
    else:
        scores["objectivity"] = 3

    # --- TEPFI-based scores
    tepfi_entries = await db.tepfi_entries.find({"user_id": uid}, {"_id": 0}).to_list(50)

    def get_tepfi_effort_score(sub_keys):
        total = 0
        count = 0
        for entry in tepfi_entries:
            matrix = entry.get("matrix", {})
            effort = matrix.get("effort", {})
            for sk in sub_keys:
                for layer in ["self", "micro", "macro"]:
                    key = f"{sk}_{layer}"
                    cell = effort.get(key, effort.get(layer, {}))
                    if isinstance(cell, dict) and "score" in cell:
                        total += cell["score"]
                        count += 1
        return min(10, max(1, round(total / max(count, 1))))

    scores["physical_health"] = get_tepfi_effort_score(["physical_health"])
    scores["mental_strength"] = get_tepfi_effort_score(["mental_state", "attitude"])
    scores["emotional_balance"] = get_tepfi_effort_score(["emotional_wellness"])
    scores["energy_levels"] = get_tepfi_effort_score(["energy_level"])
    scores["capability"] = get_tepfi_effort_score(["knowledge", "skills", "action"])

    # --- External Image: Reviews count from ReviewNet
    reviews = await db.solution_reviews.find({"user_id": uid}, {"_id": 0}).to_list(50)
    scores["external_image"] = min(10, max(1, len(reviews) + 2))

    # Calculate overall flight health
    overall = round(sum(scores.values()) / max(len(scores), 1), 1)

    # GIS auto-compute
    gis = {
        "grace": project.get("gis", {}).get("grace", {}).get("score", 0),
        "involvement": round(sum(scores.get(k, 0) for k in ["goal_clarity", "practicality", "intensity", "capability"]) / 4, 1),
        "support_micro": 0,
        "support_macro": 0,
    }
    # Support from TEPFI People layer
    for entry in tepfi_entries:
        m = entry.get("matrix", {}).get("people", {})
        micro = m.get("micro", {})
        macro = m.get("macro", {})
        if isinstance(micro, dict) and "score" in micro:
            gis["support_micro"] = max(gis["support_micro"], micro["score"])
        if isinstance(macro, dict) and "score" in macro:
            gis["support_macro"] = max(gis["support_macro"], macro["score"])

    # iGIS
    igis = {
        "inner_awareness": project.get("igis", {}).get("inner_awareness", {}).get("score", 0),
        "grace": gis["grace"],
        "involvement": gis["involvement"],
        "support": round((gis["support_micro"] + gis["support_macro"]) / 2, 1),
    }

    # Save auto-scores
    secrets_update = {}
    for key, score in scores.items():
        secrets_update[f"secrets_scores.{key}.auto_score"] = score

    await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$set": {
            **secrets_update,
            "gis.involvement.score": gis["involvement"],
            "gis.support_micro.score": gis["support_micro"],
            "gis.support_macro.score": gis["support_macro"],
            "igis.involvement.score": igis["involvement"],
            "igis.support.score": igis["support"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    return {
        "scores": scores,
        "overall_health": overall,
        "gis": gis,
        "igis": igis,
        "max_possible": 10,
    }


# ========================
# LINK MODULES TO PROJECT
# ========================

@router.post("/projects/{project_id}/link-task")
async def link_ctt_task(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Link a CTT task to a flight project step"""
    body = await request.json()
    task_id = body.get("task_id")
    step_num = body.get("step_num", 6)

    await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$addToSet": {"linked_ctt_tasks": {"task_id": task_id, "step": step_num}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Task linked"}


@router.post("/projects/{project_id}/link-routine")
async def link_routine(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Link a Lifestyle routine to a flight project"""
    body = await request.json()
    routine_id = body.get("routine_id")

    await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$addToSet": {"linked_routines": routine_id},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Routine linked"}


# ========================
# FLIGHT DYNAMICS ENGINE
# ========================

@router.get("/projects/{project_id}/flight-dynamics")
async def get_flight_dynamics(project_id: str, user: dict = Depends(get_current_user)):
    """
    Compute real-time flight dynamics based on all linked module data.
    Returns altitude, speed, turbulence, ETA, heading, fuel, and crash risk.
    This powers the animated airplane visualization.
    """
    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    uid = user["user_id"]
    now = datetime.now(timezone.utc)

    # --- 1. ALTITUDE: Overall project health (0-40000 ft)
    # Based on step completion, secrets scores, and task progress
    steps = project.get("steps", {})
    completed_steps = sum(1 for s in steps.values() if s.get("status") == "completed")
    in_progress_steps = sum(1 for s in steps.values() if s.get("status") == "in_progress")
    step_score = (completed_steps * 14) + (in_progress_steps * 5)  # max ~100

    secrets_scores = project.get("secrets_scores", {})
    avg_secret = 0
    if secrets_scores:
        scores = [v.get("manual_score") or v.get("auto_score", 0) for v in secrets_scores.values()]
        avg_secret = sum(scores) / max(len(scores), 1)  # 0-10

    base_altitude = (step_score * 200) + (avg_secret * 1000)  # max ~30000
    altitude = min(40000, max(1000, int(base_altitude)))

    # --- 2. SPEED: Task completion velocity (0-900 knots)
    ctt_tasks = await db.ctt_tasks.find({"user_id": uid}, {"_id": 0}).to_list(200)
    total_tasks = len(ctt_tasks)
    done_tasks = sum(1 for t in ctt_tasks if t.get("status") == "done")
    in_progress_tasks = sum(1 for t in ctt_tasks if t.get("status") == "in_progress")
    blocked_tasks = sum(1 for t in ctt_tasks if t.get("status") == "blocked")

    velocity = 0
    if total_tasks > 0:
        velocity = ((done_tasks * 100 + in_progress_tasks * 40) / total_tasks)
    speed = min(900, max(100, int(velocity * 9)))  # knots

    # --- 3. TURBULENCE: Risk and instability indicators (0-10, 10=severe)
    turbulence_factors = []

    # Blocked tasks increase turbulence
    if total_tasks > 0:
        block_ratio = blocked_tasks / total_tasks
        turbulence_factors.append(block_ratio * 10)

    # Low TEPFI scores = turbulence
    tepfi_entries = await db.tepfi_entries.find({"user_id": uid}, {"_id": 0}).to_list(50)
    if tepfi_entries:
        all_scores = []
        for entry in tepfi_entries:
            matrix = entry.get("matrix", {})
            for dim_key, dim_val in matrix.items():
                if isinstance(dim_val, dict):
                    for layer_key, layer_val in dim_val.items():
                        if isinstance(layer_val, dict) and "score" in layer_val:
                            all_scores.append(layer_val["score"])
        if all_scores:
            avg_tepfi = sum(all_scores) / len(all_scores)
            turbulence_factors.append(max(0, (5 - avg_tepfi)))  # Low scores = high turbulence

    # CLD imbalance = turbulence
    clds = await db.cld_diagrams.find({"user_id": uid}, {"_id": 0}).to_list(10)
    if clds:
        total_links = sum(len(c.get("links", [])) for c in clds)
        reinforcing = sum(1 for c in clds for lk in c.get("links", []) if lk.get("link_type") == "reinforcing")
        if total_links > 0:
            imbalance = abs(0.5 - reinforcing / total_links) * 10
            turbulence_factors.append(imbalance)

    # Overdue or stale steps
    for step_key, step_data in steps.items():
        if step_data.get("status") == "in_progress" and step_data.get("started_at"):
            try:
                started = datetime.fromisoformat(step_data["started_at"].replace("Z", "+00:00"))
                days_stuck = (now - started).days
                if days_stuck > 14:
                    turbulence_factors.append(min(3, days_stuck / 10))
            except (ValueError, TypeError):
                pass

    turbulence = min(10, round(sum(turbulence_factors) / max(len(turbulence_factors), 1), 1))

    # --- 4. FUEL: Energy / resource levels from TEPFI (0-100%)
    fuel = 50  # default
    if tepfi_entries:
        energy_scores = []
        for entry in tepfi_entries:
            effort = entry.get("matrix", {}).get("effort", {})
            for key in ["energy_level_self", "energy_level_micro", "energy_level_macro"]:
                cell = effort.get(key, {})
                if isinstance(cell, dict) and "score" in cell:
                    energy_scores.append(cell["score"])
        if energy_scores:
            fuel = min(100, int((sum(energy_scores) / len(energy_scores)) * 10))

    # --- 5. ETA: Projected completion based on velocity
    progress = project.get("progress_percent", 0)
    remaining = 100 - progress
    if speed > 200:
        eta_days = max(1, int(remaining / (speed / 90)))
    elif speed > 0:
        eta_days = max(1, int(remaining / (speed / 45)))
    else:
        eta_days = 999  # stalled

    # Check time_bound from SMART goal
    time_bound = project.get("goal_smart", {}).get("time_bound", "")
    deadline_str = None
    days_to_deadline = None
    on_time = True
    if time_bound:
        try:
            deadline = datetime.fromisoformat(time_bound.replace("Z", "+00:00"))
            days_to_deadline = (deadline - now).days
            deadline_str = time_bound
            on_time = eta_days <= days_to_deadline if days_to_deadline > 0 else False
        except (ValueError, TypeError):
            pass

    # --- 6. CRASH RISK: Extreme danger indicator (0-100%)
    crash_factors = []
    if fuel < 20:
        crash_factors.append(30)
    if turbulence > 7:
        crash_factors.append(25)
    if blocked_tasks > total_tasks * 0.5 and total_tasks > 3:
        crash_factors.append(25)
    if days_to_deadline is not None and days_to_deadline < 0:
        crash_factors.append(40)  # past deadline
    if project.get("status") == "paused":
        crash_factors.append(15)
    crash_risk = min(100, sum(crash_factors))

    # --- 7. HEADING: Current direction / phase label
    current_step = project.get("current_step", 1)
    current_gear = project.get("current_gear", 0)
    if current_step <= 2:
        phase = "pre_flight"
        heading_label = "Pre-Flight Check"
    elif current_step <= 4:
        phase = "takeoff"
        heading_label = "Takeoff & Climb"
    elif current_step == 5:
        phase = "climbing"
        heading_label = "Climbing to Cruise"
    elif current_step == 6:
        phase = "cruise"
        heading_label = f"Cruising — Gear {current_gear}"
    elif current_step == 7 and project.get("status") == "completed":
        phase = "landed"
        heading_label = "Landed Successfully!"
    elif current_step == 7:
        phase = "descent"
        heading_label = "Final Descent & Landing"
    else:
        phase = "taxiing"
        heading_label = "Taxiing"

    # --- 8. WEATHER: Based on routine adherence
    routines = await db.lifestyle_routines.find({"user_id": uid, "is_active": True}, {"_id": 0}).to_list(100)
    total_streaks = sum(r.get("streak", 0) for r in routines)
    avg_streak = total_streaks / max(len(routines), 1)
    if avg_streak >= 7:
        weather = "clear"
        weather_label = "Clear Skies"
    elif avg_streak >= 3:
        weather = "partly_cloudy"
        weather_label = "Partly Cloudy"
    elif avg_streak >= 1:
        weather = "overcast"
        weather_label = "Overcast"
    else:
        weather = "stormy"
        weather_label = "Stormy"

    # Log flight event
    event = {
        "event_id": str(uuid.uuid4()),
        "project_id": project_id,
        "user_id": uid,
        "timestamp": now.isoformat(),
        "altitude": altitude,
        "speed": speed,
        "turbulence": turbulence,
        "fuel": fuel,
        "crash_risk": crash_risk,
        "phase": phase,
    }
    await db.flight_events.insert_one(event)

    return {
        "altitude": altitude,
        "altitude_label": f"{altitude:,} ft",
        "max_altitude": 40000,
        "speed": speed,
        "speed_label": f"{speed} knots",
        "max_speed": 900,
        "turbulence": turbulence,
        "turbulence_label": "Severe" if turbulence > 7 else "Moderate" if turbulence > 4 else "Light" if turbulence > 1 else "Smooth",
        "fuel": fuel,
        "fuel_label": f"{fuel}%",
        "eta_days": eta_days,
        "deadline": deadline_str,
        "days_to_deadline": days_to_deadline,
        "on_time": on_time,
        "crash_risk": crash_risk,
        "crash_label": "Critical" if crash_risk > 70 else "Warning" if crash_risk > 40 else "Caution" if crash_risk > 15 else "Safe",
        "phase": phase,
        "heading": heading_label,
        "weather": weather,
        "weather_label": weather_label,
        "current_step": current_step,
        "current_gear": current_gear,
        "progress_percent": progress,
        "tasks_summary": {
            "total": total_tasks,
            "done": done_tasks,
            "in_progress": in_progress_tasks,
            "blocked": blocked_tasks,
        },
        "routines_summary": {
            "total": len(routines),
            "avg_streak": round(avg_streak, 1),
        },
    }


# ========================
# FLIGHT EVENT LOG
# ========================

@router.get("/projects/{project_id}/flight-log")
async def get_flight_log(project_id: str, user: dict = Depends(get_current_user), limit: int = 20):
    """Get recent flight events for trend visualization"""
    events = await db.flight_events.find(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"events": list(reversed(events))}


# ========================
# iGIS MODULES
# Astrology, Energy Healing, Manifestation = STUBS
# Emotional Wellness, Self Awareness = LIVE (from Consciousness Diary)
# ========================

@router.get("/projects/{project_id}/igis/emotional-wellness")
async def igis_emotional_wellness(project_id: str, user: dict = Depends(get_current_user)):
    """[LIVE] Emotional Wellness from Consciousness Diary data"""
    uid = user["user_id"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    entries = await db.consciousness_diary.find(
        {"user_id": uid, "date": {"$gte": cutoff}},
        {"_id": 0}
    ).to_list(7)

    if not entries:
        return {
            "status": "no_data",
            "module": "emotional_wellness",
            "message": "No diary entries found. Start your Consciousness Diary to track emotional wellness.",
            "wellness_score": 0,
            "metrics_summary": {},
        }

    # Aggregate recent metrics
    anger_int, sadness_int, fear_int = [], [], []
    sit_comfort, peace_depth = [], []
    sol_ratio_vals = []

    for entry in entries:
        m = entry.get("metrics", {})
        if m.get("anger", {}).get("avg_intensity") is not None:
            anger_int.append(m["anger"]["avg_intensity"])
        if m.get("sadness", {}).get("avg_intensity") is not None:
            sadness_int.append(m["sadness"]["avg_intensity"])
        if m.get("fear", {}).get("avg_intensity") is not None:
            fear_int.append(m["fear"]["avg_intensity"])
        if m.get("sit_still", {}).get("comfort_score") is not None:
            sit_comfort.append(m["sit_still"]["comfort_score"])
        if m.get("peacefulness", {}).get("depth_score") is not None:
            peace_depth.append(m["peacefulness"]["depth_score"])
        sl = m.get("solution_leadership", {})
        total_sl = (sl.get("problems_with_solutions", 0) + sl.get("problems_without_solutions", 0))
        if total_sl > 0:
            sol_ratio_vals.append(sl["problems_with_solutions"] / total_sl * 10)

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    neg = (avg(anger_int) + avg(sadness_int) + avg(fear_int)) / 3
    pos = (avg(sit_comfort) + avg(peace_depth) + avg(sol_ratio_vals)) / 3
    wellness = round(max(0, min(10, (10 - neg + pos) / 2)), 1)

    return {
        "status": "ok",
        "module": "emotional_wellness",
        "wellness_score": wellness,
        "entries_count": len(entries),
        "avg_anger_intensity": avg(anger_int),
        "avg_sadness_intensity": avg(sadness_int),
        "avg_fear_intensity": avg(fear_int),
        "avg_peacefulness": avg(peace_depth),
        "avg_stillness_comfort": avg(sit_comfort),
        "solution_orientation": avg(sol_ratio_vals),
    }


@router.get("/projects/{project_id}/igis/self-awareness")
async def igis_self_awareness(project_id: str, user: dict = Depends(get_current_user)):
    """[LIVE] Self-Awareness Levels from Consciousness Diary"""
    uid = user["user_id"]

    sa = await db.self_awareness.find_one({"user_id": uid}, {"_id": 0})
    if not sa:
        return {
            "status": "no_data",
            "module": "self_awareness",
            "message": "No self-awareness data. Rate your levels in the Consciousness Diary to begin tracking.",
            "levels": {},
            "overall_level": 0,
        }

    return {
        "status": "ok",
        "module": "self_awareness",
        "levels": sa.get("levels", {}),
        "overall_level": sa.get("overall_level", 0),
        "level_names": {str(l["level"]): l["name"] for l in [
            {"level": 1, "name": "Thought Level"},
            {"level": 2, "name": "Breath Level"},
            {"level": 3, "name": "Bodily Sensations Level"},
            {"level": 4, "name": "Individual Action Level"},
            {"level": 5, "name": "Interaction Level"},
            {"level": 6, "name": "Intense Action Level"},
        ]},
        "updated_at": sa.get("updated_at"),
    }

@router.get("/projects/{project_id}/igis/astrology")
async def igis_astrology_stub(project_id: str, user: dict = Depends(get_current_user)):
    """[STUB] Astrology-based grace and timing insights"""
    return {
        "status": "stub",
        "module": "astrology",
        "message": "Astrology integration coming soon. This module will analyze planetary alignments for optimal decision timing.",
        "placeholder_data": {
            "favorable_periods": [
                {"label": "Career moves", "timing": "Next 2 weeks", "confidence": "N/A"},
                {"label": "Financial decisions", "timing": "After 15th", "confidence": "N/A"},
            ],
            "current_energy": "Neutral",
            "grace_score": 5,
        }
    }


@router.get("/projects/{project_id}/igis/energy-healing")
async def igis_energy_healing_stub(project_id: str, user: dict = Depends(get_current_user)):
    """[STUB] Energy healing and chakra balance insights"""
    return {
        "status": "stub",
        "module": "energy_healing",
        "message": "Energy Healing integration coming soon. This module will map your TEPFI energy patterns to chakra alignment.",
        "placeholder_data": {
            "chakras": [
                {"name": "Root", "area": "Security & Finance", "balance": "N/A"},
                {"name": "Sacral", "area": "Creativity & Relationships", "balance": "N/A"},
                {"name": "Solar Plexus", "area": "Willpower & Career", "balance": "N/A"},
                {"name": "Heart", "area": "Love & Emotional Health", "balance": "N/A"},
                {"name": "Throat", "area": "Communication & Social", "balance": "N/A"},
                {"name": "Third Eye", "area": "Intuition & Knowledge", "balance": "N/A"},
                {"name": "Crown", "area": "Spirituality & Purpose", "balance": "N/A"},
            ],
            "overall_energy": "Balanced",
            "recommended_practice": "Meditation & Breathwork",
        }
    }


@router.get("/projects/{project_id}/igis/manifestation")
async def igis_manifestation_stub(project_id: str, user: dict = Depends(get_current_user)):
    """[STUB] Manifestation tracking and visualization"""
    return {
        "status": "stub",
        "module": "manifestation",
        "message": "Manifestation integration coming soon. This module will help track visualization exercises and affirmation alignment.",
        "placeholder_data": {
            "affirmations": [
                "I am making consistent progress toward my goals",
                "I attract the resources and people I need",
                "I trust the process and stay committed",
            ],
            "visualization_score": "N/A",
            "alignment_level": "N/A",
        }
    }


# ========================
# FLIGHT SUMMARY / DASHBOARD
# ========================

@router.get("/projects/{project_id}/dashboard")
async def get_flight_dashboard(project_id: str, user: dict = Depends(get_current_user)):
    """
    Comprehensive flight dashboard combining project data, scores, dynamics,
    and linked module summaries. Single endpoint for the frontend.
    """
    project = await db.flight_projects.find_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    uid = user["user_id"]

    # Get linked tasks summary
    linked_task_ids = [lt.get("task_id") for lt in project.get("linked_ctt_tasks", [])]
    linked_tasks = []
    if linked_task_ids:
        linked_tasks = await db.ctt_tasks.find(
            {"task_id": {"$in": linked_task_ids}, "user_id": uid},
            {"_id": 0, "task_id": 1, "title": 1, "status": 1, "priority": 1}
        ).to_list(50)

    # Get linked routines summary
    linked_routine_ids = project.get("linked_routines", [])
    linked_routines = []
    if linked_routine_ids:
        linked_routines = await db.lifestyle_routines.find(
            {"routine_id": {"$in": linked_routine_ids}, "user_id": uid},
            {"_id": 0, "routine_id": 1, "title": 1, "streak": 1, "frequency": 1}
        ).to_list(50)

    # Get linked decisions summary
    linked_decision_ids = project.get("linked_decisions", [])
    linked_decisions = []
    if linked_decision_ids:
        linked_decisions = await db.decisions.find(
            {"decision_id": {"$in": linked_decision_ids}, "user_id": uid},
            {"_id": 0, "decision_id": 1, "title": 1, "status": 1, "decision_type": 1}
        ).to_list(20)

    return {
        "project": project,
        "linked_tasks": linked_tasks,
        "linked_routines": linked_routines,
        "linked_decisions": linked_decisions,
        "config": {
            "secrets": SECRETS_CONFIG,
            "seven_steps": SEVEN_STEPS,
            "gears": GEARS,
        }
    }
