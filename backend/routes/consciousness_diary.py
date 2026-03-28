"""
Consciousness Diary — Inner Self-Awareness Tracking
- Daily diary entries with 8 emotional/behavioral metrics
- 6-level Self-Awareness progressive scale (Thought → Intense Action)
- Emotional Wellness aggregate scoring
- Auto-calculation of Level 4 (Individual Action) from 8 metrics
- Links to daily CTT tasks, Lifestyle routines & unplanned events
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta, date as date_type
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/consciousness-diary", tags=["Consciousness Diary"])

# ========================
# 6 SELF-AWARENESS LEVELS
# ========================
AWARENESS_LEVELS = [
    {"level": 1, "name": "Thought Level", "desc": "Awareness of your own thoughts and mental patterns", "icon": "bulb", "color": "#818CF8"},
    {"level": 2, "name": "Breath Level", "desc": "Awareness of your breathing and its connection to emotions", "icon": "leaf", "color": "#3B82F6"},
    {"level": 3, "name": "Bodily Sensations Level", "desc": "Awareness of physical sensations and body signals", "icon": "body", "color": "#10B981"},
    {"level": 4, "name": "Individual Action Level", "desc": "Awareness of your actions and their emotional triggers (auto-calculated from diary)", "icon": "flash", "color": "#F59E0B"},
    {"level": 5, "name": "Interaction Level", "desc": "Awareness of how you interact with others and social dynamics", "icon": "people", "color": "#EC4899"},
    {"level": 6, "name": "Intense Action Level", "desc": "Awareness during high-pressure situations and crisis moments", "icon": "flame", "color": "#EF4444"},
]

# 8 METRICS SCHEMA
METRICS_SCHEMA = [
    {"key": "anger", "name": "Incidents of Anger", "period": "daily",
     "fields": ["count", "avg_duration_mins", "avg_intensity"]},
    {"key": "sadness", "name": "Incidents of Sadness", "period": "daily",
     "fields": ["count", "avg_duration_mins", "avg_intensity"]},
    {"key": "fear", "name": "Incidents of Fear", "period": "daily",
     "fields": ["count", "avg_duration_mins", "avg_intensity"]},
    {"key": "emotional_outlets", "name": "Negative Impact of Emotional Outlets", "period": "daily",
     "fields": ["time_impact_pct", "money_impact_pct", "health_impact_pct", "relationships_impact_pct"]},
    {"key": "ads", "name": "Attention Deficiency Syndrome Impact", "period": "weekly",
     "fields": ["time_impact_pct", "money_impact_pct", "health_impact_pct", "relationships_impact_pct"]},
    {"key": "sit_still", "name": "Ability to Sit Still (15 min)", "period": "daily",
     "fields": ["achieved", "comfort_score"]},
    {"key": "peacefulness", "name": "Ability to be Peaceful", "period": "daily",
     "fields": ["peaceful_hours", "depth_score"]},
    {"key": "solution_leadership", "name": "Solution-Oriented Leadership", "period": "weekly",
     "fields": ["problems_with_solutions", "problems_without_solutions"]},
]


# ========================
# CONFIGURATION
# ========================

@router.get("/config")
async def get_diary_config():
    """Get consciousness diary configuration (levels, metrics schema)"""
    return {
        "awareness_levels": AWARENESS_LEVELS,
        "metrics_schema": METRICS_SCHEMA,
    }


# ========================
# DIARY ENTRY CRUD
# ========================

@router.post("/entries")
async def create_diary_entry(request: Request, user: dict = Depends(get_current_user)):
    """Create or update a daily consciousness diary entry with 8 metrics"""
    body = await request.json()
    uid = user["user_id"]
    entry_date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # Check if entry already exists for this date
    existing = await db.consciousness_diary.find_one(
        {"user_id": uid, "date": entry_date}, {"_id": 0}
    )
    if existing:
        # Update existing entry
        return await _update_entry(existing["entry_id"], body, uid)

    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build metrics from body
    metrics = _build_metrics(body)

    # Fetch daily context (CTT + Routines + Unplanned)
    daily_context = await _fetch_daily_context(uid, entry_date)

    # Life areas reflection
    life_areas_notes = body.get("life_areas_notes", {})
    overall_reflection = body.get("overall_reflection", "")

    entry = {
        "entry_id": entry_id,
        "user_id": uid,
        "date": entry_date,
        "metrics": metrics,
        "life_areas_notes": life_areas_notes,
        "overall_reflection": overall_reflection,
        "daily_context_snapshot": {
            "tasks_count": daily_context["tasks_count"],
            "routines_count": daily_context["routines_count"],
            "unplanned_count": daily_context["unplanned_count"],
        },
        "created_at": now,
        "updated_at": now,
    }

    await db.consciousness_diary.insert_one(entry)
    entry.pop("_id", None)

    # Auto-update Level 4 score
    await _auto_compute_level4(uid)

    return entry


@router.get("/entries")
async def get_diary_entry(
    user: dict = Depends(get_current_user),
    date: Optional[str] = None,
):
    """Get diary entry for a specific date (defaults to today)"""
    uid = user["user_id"]
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = await db.consciousness_diary.find_one(
        {"user_id": uid, "date": date}, {"_id": 0}
    )

    # Also fetch daily context for display
    daily_context = await _fetch_daily_context(uid, date)

    return {
        "entry": entry,
        "daily_context": daily_context,
        "date": date,
    }


@router.put("/entries/{entry_id}")
async def update_diary_entry(entry_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update an existing diary entry"""
    body = await request.json()
    return await _update_entry(entry_id, body, user["user_id"])


async def _update_entry(entry_id: str, body: dict, uid: str):
    metrics = _build_metrics(body)
    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if metrics:
        update_fields["metrics"] = metrics
    if "life_areas_notes" in body:
        update_fields["life_areas_notes"] = body["life_areas_notes"]
    if "overall_reflection" in body:
        update_fields["overall_reflection"] = body["overall_reflection"]

    result = await db.consciousness_diary.update_one(
        {"entry_id": entry_id, "user_id": uid},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")

    entry = await db.consciousness_diary.find_one(
        {"entry_id": entry_id, "user_id": uid}, {"_id": 0}
    )
    await _auto_compute_level4(uid)
    return entry


@router.get("/history")
async def get_diary_history(
    user: dict = Depends(get_current_user),
    days: int = 30,
):
    """Get diary entry history for trend analysis"""
    uid = user["user_id"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    entries = await db.consciousness_diary.find(
        {"user_id": uid, "date": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("date", -1).to_list(days)

    return {"entries": entries, "total": len(entries), "days_range": days}


@router.delete("/entries/{entry_id}")
async def delete_diary_entry(entry_id: str, user: dict = Depends(get_current_user)):
    result = await db.consciousness_diary.delete_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"message": "Entry deleted"}


# ========================
# SELF-AWARENESS LEVELS
# ========================

@router.get("/self-awareness")
async def get_self_awareness(user: dict = Depends(get_current_user)):
    """Get self-awareness levels (6 levels). Level 4 is auto-calculated."""
    uid = user["user_id"]

    sa = await db.self_awareness.find_one({"user_id": uid}, {"_id": 0})
    if not sa:
        # Initialize with defaults
        sa = {
            "user_id": uid,
            "levels": {
                "1": {"score": 5, "source": "self_rated", "notes": ""},
                "2": {"score": 5, "source": "self_rated", "notes": ""},
                "3": {"score": 5, "source": "self_rated", "notes": ""},
                "4": {"score": 5, "source": "auto_calculated", "notes": "Based on 8 diary metrics"},
                "5": {"score": 5, "source": "self_rated", "notes": ""},
                "6": {"score": 5, "source": "self_rated", "notes": ""},
            },
            "overall_level": 5.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.self_awareness.insert_one({**sa})
        sa.pop("_id", None)

    return {
        "levels": sa.get("levels", {}),
        "overall_level": sa.get("overall_level", 5.0),
        "config": AWARENESS_LEVELS,
        "updated_at": sa.get("updated_at"),
    }


@router.put("/self-awareness")
async def update_self_awareness(request: Request, user: dict = Depends(get_current_user)):
    """Update self-rated awareness levels (1,2,3,5,6). Level 4 is auto-calculated."""
    body = await request.json()
    uid = user["user_id"]
    levels_input = body.get("levels", {})

    sa = await db.self_awareness.find_one({"user_id": uid})
    if not sa:
        sa = {"user_id": uid, "levels": {}}
        await db.self_awareness.insert_one(sa)

    current_levels = sa.get("levels", {})

    # Update self-rated levels (1,2,3,5,6) — NOT level 4
    for level_key in ["1", "2", "3", "5", "6"]:
        if level_key in levels_input:
            level_data = levels_input[level_key]
            current_levels[level_key] = {
                "score": max(0, min(10, level_data.get("score", 5))),
                "source": "self_rated",
                "notes": level_data.get("notes", current_levels.get(level_key, {}).get("notes", "")),
            }

    # Ensure level 4 exists
    if "4" not in current_levels:
        current_levels["4"] = {"score": 5, "source": "auto_calculated", "notes": "Based on 8 diary metrics"}

    # Compute overall
    all_scores = [current_levels.get(str(i), {}).get("score", 5) for i in range(1, 7)]
    overall = round(sum(all_scores) / 6, 1)

    now = datetime.now(timezone.utc).isoformat()
    await db.self_awareness.update_one(
        {"user_id": uid},
        {"$set": {"levels": current_levels, "overall_level": overall, "updated_at": now}}
    )

    return {
        "levels": current_levels,
        "overall_level": overall,
        "config": AWARENESS_LEVELS,
        "updated_at": now,
    }


# ========================
# EMOTIONAL WELLNESS SUMMARY
# ========================

@router.get("/emotional-wellness")
async def get_emotional_wellness(
    user: dict = Depends(get_current_user),
    days: int = 7,
):
    """
    Aggregate emotional wellness score from recent diary entries.
    Computes trends for all 8 metrics.
    """
    uid = user["user_id"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    entries = await db.consciousness_diary.find(
        {"user_id": uid, "date": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("date", -1).to_list(days)

    if not entries:
        return {
            "status": "no_data",
            "message": "No diary entries found. Start logging your consciousness diary to see emotional wellness insights.",
            "entries_count": 0,
            "wellness_score": 0,
            "metrics_summary": {},
        }

    # Aggregate metrics
    anger_counts, anger_durations, anger_intensities = [], [], []
    sadness_counts, sadness_durations, sadness_intensities = [], [], []
    fear_counts, fear_durations, fear_intensities = [], [], []
    emotional_outlet_impacts = []
    ads_impacts = []
    sit_still_achieved = []
    sit_still_comfort = []
    peaceful_hours_list = []
    peaceful_depth_list = []
    sol_with = []
    sol_without = []

    for entry in entries:
        m = entry.get("metrics", {})

        anger = m.get("anger", {})
        if anger.get("count") is not None:
            anger_counts.append(anger["count"])
        if anger.get("avg_duration_mins") is not None:
            anger_durations.append(anger["avg_duration_mins"])
        if anger.get("avg_intensity") is not None:
            anger_intensities.append(anger["avg_intensity"])

        sadness = m.get("sadness", {})
        if sadness.get("count") is not None:
            sadness_counts.append(sadness["count"])
        if sadness.get("avg_duration_mins") is not None:
            sadness_durations.append(sadness["avg_duration_mins"])
        if sadness.get("avg_intensity") is not None:
            sadness_intensities.append(sadness["avg_intensity"])

        fear = m.get("fear", {})
        if fear.get("count") is not None:
            fear_counts.append(fear["count"])
        if fear.get("avg_duration_mins") is not None:
            fear_durations.append(fear["avg_duration_mins"])
        if fear.get("avg_intensity") is not None:
            fear_intensities.append(fear["avg_intensity"])

        eo = m.get("emotional_outlets", {})
        impact_vals = [eo.get("time_impact_pct", 0), eo.get("money_impact_pct", 0),
                       eo.get("health_impact_pct", 0), eo.get("relationships_impact_pct", 0)]
        emotional_outlet_impacts.append(sum(impact_vals) / max(len([v for v in impact_vals if v > 0]), 1))

        ads = m.get("ads", {})
        ads_vals = [ads.get("time_impact_pct", 0), ads.get("money_impact_pct", 0),
                    ads.get("health_impact_pct", 0), ads.get("relationships_impact_pct", 0)]
        ads_impacts.append(sum(ads_vals) / max(len([v for v in ads_vals if v > 0]), 1))

        ss = m.get("sit_still", {})
        if ss.get("achieved") is not None:
            sit_still_achieved.append(1 if ss["achieved"] else 0)
        if ss.get("comfort_score") is not None:
            sit_still_comfort.append(ss["comfort_score"])

        peace = m.get("peacefulness", {})
        if peace.get("peaceful_hours") is not None:
            peaceful_hours_list.append(peace["peaceful_hours"])
        if peace.get("depth_score") is not None:
            peaceful_depth_list.append(peace["depth_score"])

        sl = m.get("solution_leadership", {})
        if sl.get("problems_with_solutions") is not None:
            sol_with.append(sl["problems_with_solutions"])
        if sl.get("problems_without_solutions") is not None:
            sol_without.append(sl["problems_without_solutions"])

    def safe_avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 0

    metrics_summary = {
        "anger": {
            "avg_count": safe_avg(anger_counts),
            "avg_duration_mins": safe_avg(anger_durations),
            "avg_intensity": safe_avg(anger_intensities),
        },
        "sadness": {
            "avg_count": safe_avg(sadness_counts),
            "avg_duration_mins": safe_avg(sadness_durations),
            "avg_intensity": safe_avg(sadness_intensities),
        },
        "fear": {
            "avg_count": safe_avg(fear_counts),
            "avg_duration_mins": safe_avg(fear_durations),
            "avg_intensity": safe_avg(fear_intensities),
        },
        "emotional_outlets": {
            "avg_negative_impact_pct": safe_avg(emotional_outlet_impacts),
        },
        "ads": {
            "avg_negative_impact_pct": safe_avg(ads_impacts),
        },
        "sit_still": {
            "achievement_rate_pct": round((safe_avg(sit_still_achieved)) * 100, 1) if sit_still_achieved else 0,
            "avg_comfort": safe_avg(sit_still_comfort),
        },
        "peacefulness": {
            "avg_peaceful_hours": safe_avg(peaceful_hours_list),
            "avg_depth": safe_avg(peaceful_depth_list),
        },
        "solution_leadership": {
            "avg_with_solutions": safe_avg(sol_with),
            "avg_without_solutions": safe_avg(sol_without),
            "solution_ratio": round(safe_avg(sol_with) / max(safe_avg(sol_with) + safe_avg(sol_without), 1) * 100, 1),
        },
    }

    # Compute overall wellness score (0-10)
    # Lower anger/sadness/fear = better; higher peace/stillness = better
    negative_score = (
        min(10, safe_avg(anger_intensities)) +
        min(10, safe_avg(sadness_intensities)) +
        min(10, safe_avg(fear_intensities)) +
        min(10, safe_avg(emotional_outlet_impacts) / 10) +
        min(10, safe_avg(ads_impacts) / 10)
    ) / 5  # Average negative (0-10)

    positive_score = (
        min(10, safe_avg(sit_still_comfort)) +
        min(10, safe_avg(peaceful_depth_list)) +
        min(10, (metrics_summary["solution_leadership"]["solution_ratio"] / 10))
    ) / 3  # Average positive (0-10)

    wellness_score = round(max(0, min(10, (10 - negative_score + positive_score) / 2)), 1)

    return {
        "status": "ok",
        "entries_count": len(entries),
        "days_range": days,
        "wellness_score": wellness_score,
        "metrics_summary": metrics_summary,
        "trend_direction": "improving" if len(entries) > 1 and entries[0].get("metrics", {}).get("peacefulness", {}).get("depth_score", 0) > entries[-1].get("metrics", {}).get("peacefulness", {}).get("depth_score", 0) else "stable",
    }


# ========================
# DAILY CONTEXT (CTT + Routines + Unplanned)
# ========================

@router.get("/daily-context")
async def get_daily_context(
    user: dict = Depends(get_current_user),
    date: Optional[str] = None,
):
    """Get CTT tasks, Lifestyle routines & unplanned events for a specific date"""
    uid = user["user_id"]
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return await _fetch_daily_context(uid, date)


# ========================
# HELPER FUNCTIONS
# ========================

def _build_metrics(body: dict) -> dict:
    """Build structured metrics from request body"""
    metrics = {}

    # 1. Anger
    anger = body.get("anger", {})
    if anger:
        metrics["anger"] = {
            "count": anger.get("count", 0),
            "avg_duration_mins": anger.get("avg_duration_mins", 0),
            "avg_intensity": max(0, min(10, anger.get("avg_intensity", 0))),
        }

    # 2. Sadness
    sadness = body.get("sadness", {})
    if sadness:
        metrics["sadness"] = {
            "count": sadness.get("count", 0),
            "avg_duration_mins": sadness.get("avg_duration_mins", 0),
            "avg_intensity": max(0, min(10, sadness.get("avg_intensity", 0))),
        }

    # 3. Fear
    fear = body.get("fear", {})
    if fear:
        metrics["fear"] = {
            "count": fear.get("count", 0),
            "avg_duration_mins": fear.get("avg_duration_mins", 0),
            "avg_intensity": max(0, min(10, fear.get("avg_intensity", 0))),
        }

    # 4. Emotional Outlets
    eo = body.get("emotional_outlets", {})
    if eo:
        metrics["emotional_outlets"] = {
            "time_impact_pct": max(0, min(100, eo.get("time_impact_pct", 0))),
            "money_impact_pct": max(0, min(100, eo.get("money_impact_pct", 0))),
            "health_impact_pct": max(0, min(100, eo.get("health_impact_pct", 0))),
            "relationships_impact_pct": max(0, min(100, eo.get("relationships_impact_pct", 0))),
        }

    # 5. ADS (weekly)
    ads = body.get("ads", {})
    if ads:
        metrics["ads"] = {
            "time_impact_pct": max(0, min(100, ads.get("time_impact_pct", 0))),
            "money_impact_pct": max(0, min(100, ads.get("money_impact_pct", 0))),
            "health_impact_pct": max(0, min(100, ads.get("health_impact_pct", 0))),
            "relationships_impact_pct": max(0, min(100, ads.get("relationships_impact_pct", 0))),
        }

    # 6. Sit Still
    ss = body.get("sit_still", {})
    if ss:
        metrics["sit_still"] = {
            "achieved": bool(ss.get("achieved", False)),
            "comfort_score": max(0, min(10, ss.get("comfort_score", 0))),
        }

    # 7. Peacefulness
    peace = body.get("peacefulness", {})
    if peace:
        metrics["peacefulness"] = {
            "peaceful_hours": max(0, min(24, peace.get("peaceful_hours", 0))),
            "depth_score": max(0, min(10, peace.get("depth_score", 0))),
        }

    # 8. Solution-Oriented Leadership (weekly)
    sl = body.get("solution_leadership", {})
    if sl:
        metrics["solution_leadership"] = {
            "problems_with_solutions": max(0, sl.get("problems_with_solutions", 0)),
            "problems_without_solutions": max(0, sl.get("problems_without_solutions", 0)),
        }

    return metrics


async def _fetch_daily_context(uid: str, date_str: str) -> dict:
    """Fetch CTT tasks, routines, and unplanned tasks for a given date"""
    # CTT Tasks for the date
    tasks = await db.ctt_tasks.find(
        {"user_id": uid},
        {"_id": 0, "task_id": 1, "title": 1, "status": 1, "priority": 1,
         "from_time": 1, "to_time": 1, "life_area": 1}
    ).to_list(200)

    # Filter tasks that match the date (by from_time or created_at)
    day_tasks = []
    for t in tasks:
        ft = t.get("from_time", "")
        if ft and ft.startswith(date_str):
            day_tasks.append(t)

    # Lifestyle routines (active)
    routines = await db.lifestyle_routines.find(
        {"user_id": uid, "is_active": True},
        {"_id": 0, "routine_id": 1, "name": 1, "time_slot": 1,
         "frequency": 1, "life_area": 1, "streak": 1}
    ).to_list(100)

    # Unplanned tasks for the date
    unplanned = await db.unplanned_tasks.find(
        {"user_id": uid, "date": date_str},
        {"_id": 0, "task_id": 1, "title": 1, "duration_mins": 1,
         "priority": 1, "life_area": 1}
    ).to_list(50)

    return {
        "date": date_str,
        "tasks": day_tasks,
        "tasks_count": len(day_tasks),
        "routines": routines,
        "routines_count": len(routines),
        "unplanned": unplanned,
        "unplanned_count": len(unplanned),
    }


async def _auto_compute_level4(uid: str):
    """
    Auto-compute Level 4 (Individual Action) from the 8 diary metrics.
    Uses last 7 days of diary data to calculate a score.
    Lower negative emotions + higher positive traits = higher score.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    entries = await db.consciousness_diary.find(
        {"user_id": uid, "date": {"$gte": cutoff}},
        {"_id": 0, "metrics": 1}
    ).to_list(7)

    if not entries:
        return

    # Aggregate scores
    neg_scores = []
    pos_scores = []

    for entry in entries:
        m = entry.get("metrics", {})

        # Negative factors (lower = better)
        for emotion_key in ["anger", "sadness", "fear"]:
            emotion = m.get(emotion_key, {})
            intensity = emotion.get("avg_intensity", 0)
            count = emotion.get("count", 0)
            neg_scores.append(min(10, (intensity * count) / max(count, 1)))

        # Emotional outlets & ADS impact
        for impact_key in ["emotional_outlets", "ads"]:
            imp = m.get(impact_key, {})
            vals = [imp.get("time_impact_pct", 0), imp.get("money_impact_pct", 0),
                    imp.get("health_impact_pct", 0), imp.get("relationships_impact_pct", 0)]
            avg_impact = sum(vals) / max(len([v for v in vals if v > 0]), 1)
            neg_scores.append(min(10, avg_impact / 10))

        # Positive factors (higher = better)
        ss = m.get("sit_still", {})
        if ss:
            pos_scores.append(ss.get("comfort_score", 0))

        peace = m.get("peacefulness", {})
        if peace:
            pos_scores.append(peace.get("depth_score", 0))

        sl = m.get("solution_leadership", {})
        if sl:
            total = sl.get("problems_with_solutions", 0) + sl.get("problems_without_solutions", 0)
            if total > 0:
                ratio = sl["problems_with_solutions"] / total
                pos_scores.append(min(10, ratio * 10))

    avg_neg = sum(neg_scores) / max(len(neg_scores), 1)
    avg_pos = sum(pos_scores) / max(len(pos_scores), 1)

    # Level 4 score: combination of low negative and high positive
    level4_score = round(max(0, min(10, (10 - avg_neg + avg_pos) / 2)), 1)

    # Update self-awareness Level 4
    sa = await db.self_awareness.find_one({"user_id": uid})
    if sa:
        levels = sa.get("levels", {})
        levels["4"] = {
            "score": level4_score,
            "source": "auto_calculated",
            "notes": f"Based on {len(entries)} diary entries (last 7 days)",
        }
        all_scores = [levels.get(str(i), {}).get("score", 5) for i in range(1, 7)]
        overall = round(sum(all_scores) / 6, 1)

        await db.self_awareness.update_one(
            {"user_id": uid},
            {"$set": {
                "levels": levels,
                "overall_level": overall,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
    else:
        # Create initial self-awareness record
        levels = {
            "1": {"score": 5, "source": "self_rated", "notes": ""},
            "2": {"score": 5, "source": "self_rated", "notes": ""},
            "3": {"score": 5, "source": "self_rated", "notes": ""},
            "4": {"score": level4_score, "source": "auto_calculated",
                  "notes": f"Based on {len(entries)} diary entries"},
            "5": {"score": 5, "source": "self_rated", "notes": ""},
            "6": {"score": 5, "source": "self_rated", "notes": ""},
        }
        all_scores = [levels[str(i)]["score"] for i in range(1, 7)]
        overall = round(sum(all_scores) / 6, 1)

        await db.self_awareness.insert_one({
            "user_id": uid,
            "levels": levels,
            "overall_level": overall,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
