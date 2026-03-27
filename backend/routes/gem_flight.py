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
from datetime import datetime, timezone
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

    result = await db.flight_projects.update_one(
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

    result = await db.flight_projects.update_one(
        {"project_id": project_id, "user_id": user["user_id"]},
        {"$addToSet": {"linked_routines": routine_id},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Routine linked"}
