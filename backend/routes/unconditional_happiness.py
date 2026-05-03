"""
Unconditional Happiness Module
A guided practice to shift from conditional to unconditional happiness.
4 phases: Recollection → Reframing → Embodiment → Integration
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/unconditional-happiness", tags=["Unconditional Happiness"])

HAPPINESS_FRAMEWORK = {
    "title": "Unconditional Happiness",
    "tagline": "Let us celebrate the life of unconditional happiness from now on!",
    "audio_url": "https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/zcy23t73_Joy.mp3",
    "audio_title": "Joy — Guided Practice for Unconditional Happiness",
    "phases": [
        {
            "phase_number": 1,
            "name": "Recollection & Awareness",
            "icon": "time",
            "color": "#3B82F6",
            "prompt": "When you were a child, were you conditionally happy or unconditionally happy?",
            "instruction": "Recall a moment of pure, unadulterated joy from childhood. Feel that state again.",
            "reflection_question": "What is the earliest memory of pure happiness you can recall?",
        },
        {
            "phase_number": 2,
            "name": "Reframing & Decision",
            "icon": "bulb",
            "color": "#F59E0B",
            "prompt": "Most of us are in the illusion of 'waiting to start living syndrome' — waiting for some success to live happily.",
            "instruction": "Only if we are happy can we be successful. Happiness is the CAUSE, not the EFFECT of success.",
            "reflection_question": "What conditions have you been attaching to your happiness? List them and release them now.",
        },
        {
            "phase_number": 3,
            "name": "Embodiment & Celebration",
            "icon": "musical-notes",
            "color": "#10B981",
            "prompt": "Let us NOT attach any conditions or reasons to be happy. Let us celebrate the life of unconditional happiness from now on!",
            "instruction": "Hooray! It is time to listen to your favorite success song. You can even dance to the tunes if you wish.",
            "reflection_question": "What does unconditional happiness feel like in your body right now?",
        },
        {
            "phase_number": 4,
            "name": "Integration & Return",
            "icon": "heart",
            "color": "#EC4899",
            "prompt": "Now, imbibe these feelings of success and happiness in you.",
            "instruction": "Slowly bring back your attention to this room. Carry this unconditional happiness with you throughout the day.",
            "reflection_question": "What is one thing you will do differently today, knowing you are already happy?",
        },
    ],
}


@router.get("/framework")
async def get_happiness_framework():
    return HAPPINESS_FRAMEWORK


@router.post("/sessions")
async def log_session(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    session_id = f"UH-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "session_id": session_id,
        "user_id": user["user_id"],
        "reflections": body.get("reflections", {}),
        # { "1": "My childhood memory...", "2": "I was attaching...", ... }
        "listened_audio": body.get("listened_audio", False),
        "happiness_before": body.get("happiness_before", 0),
        "happiness_after": body.get("happiness_after", 0),
        "notes": body.get("notes", ""),
        "completed": body.get("completed", True),
        "created_at": now,
    }
    await db.happiness_sessions.insert_one(doc)
    doc.pop("_id", None)

    # Update streak
    await _update_streak(user["user_id"], now[:10])

    return doc


async def _update_streak(user_id: str, today: str):
    stats = await db.happiness_stats.find_one({"user_id": user_id})
    if not stats:
        await db.happiness_stats.insert_one({
            "user_id": user_id,
            "total_sessions": 1,
            "current_streak": 1,
            "best_streak": 1,
            "last_session_date": today,
        })
    else:
        total = stats.get("total_sessions", 0) + 1
        last_date = stats.get("last_session_date", "")
        streak = stats.get("current_streak", 0)
        best = stats.get("best_streak", 0)

        from datetime import timedelta
        try:
            last_dt = datetime.strptime(last_date, "%Y-%m-%d")
            today_dt = datetime.strptime(today, "%Y-%m-%d")
            diff = (today_dt - last_dt).days
            if diff == 1:
                streak += 1
            elif diff > 1:
                streak = 1
            # same day = no change
        except ValueError:
            streak = 1

        best = max(best, streak)
        await db.happiness_stats.update_one(
            {"user_id": user_id},
            {"$set": {
                "total_sessions": total,
                "current_streak": streak,
                "best_streak": best,
                "last_session_date": today,
            }}
        )


@router.get("/sessions")
async def list_sessions(request: Request, user: dict = Depends(get_current_user)):
    limit = int(request.query_params.get("limit", "20"))
    docs = await db.happiness_sessions.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return docs


@router.get("/dashboard")
async def happiness_dashboard(user: dict = Depends(get_current_user)):
    stats = await db.happiness_stats.find_one({"user_id": user["user_id"]}, {"_id": 0})
    recent = await db.happiness_sessions.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(5)

    if not stats:
        stats = {"total_sessions": 0, "current_streak": 0, "best_streak": 0}

    # Average happiness improvement
    improvements = []
    for s in recent:
        b = s.get("happiness_before", 0)
        a = s.get("happiness_after", 0)
        if b > 0:
            improvements.append(a - b)

    avg_improvement = round(sum(improvements) / max(len(improvements), 1), 1)

    return {
        **stats,
        "recent_sessions": recent,
        "avg_happiness_improvement": avg_improvement,
    }
