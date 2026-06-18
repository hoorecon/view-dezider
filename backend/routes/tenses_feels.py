"""Tenses & Feels + Goals & Feels — EG sub-modules.

Provides session storage for the 12-emotion coaching framework and the
10-life-area Goals-&-Feels exercise. Optional AI-personalized guidance via
Emergent LLM.

Schema:
  tenses_feels_sessions: per-emotion reflection rows
  goals_feels_rows: per-life-area goal+emotion+healing rows
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenses-feels", tags=["Tenses & Feels"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Valid emotion codes (mirrors the 12-emotion framework) ──────────
EMOTION_CODES = {
    # Past
    "clinging", "longing",
    # Future
    "fear", "anxiety",
    # Present · Self · Emotional
    "anger", "sadness",
    # Present · Self · Mental
    "over_cautious", "over_careless",
    # Present · Others · Your side
    "jealousy", "disgraceful",
    # Present · Others · Their side
    "aggression", "heartbroken",
}
HEALING_FEELINGS = {"gratefulness", "faith", "happily_active"}


# ─── Tenses & Feels: per-emotion reflection ───────────────────────
class ReflectionIn(BaseModel):
    emotion_code: str            # one of EMOTION_CODES
    user_situation: str          # free-text recall of the specific incident
    intensity: int = 5           # 1..10
    life_lesson: Optional[str] = ""
    healing_feeling: Optional[str] = ""  # one of HEALING_FEELINGS
    constructive_action: Optional[str] = ""
    notes: Optional[str] = ""


@router.post("/reflect")
async def submit_reflection(p: ReflectionIn, user: dict = Depends(get_current_user)):
    if p.emotion_code not in EMOTION_CODES:
        raise HTTPException(400, f"emotion_code must be one of {sorted(EMOTION_CODES)}")
    if p.healing_feeling and p.healing_feeling not in HEALING_FEELINGS:
        raise HTTPException(400, f"healing_feeling must be one of {sorted(HEALING_FEELINGS)}")
    if not (1 <= int(p.intensity) <= 10):
        raise HTTPException(400, "intensity must be between 1 and 10")
    if not (p.user_situation or "").strip():
        raise HTTPException(400, "user_situation is required")

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        **p.model_dump(),
        "created_at": _now(),
    }
    await db.tenses_feels_sessions.insert_one(doc)
    doc.pop("_id", None)
    return {"reflection": doc}


@router.get("/reflections")
async def list_reflections(
    emotion_code: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {"user_id": user["user_id"]}
    if emotion_code:
        q["emotion_code"] = emotion_code
    rows = await db.tenses_feels_sessions.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"reflections": rows, "count": len(rows)}


@router.get("/summary")
async def my_summary(user: dict = Depends(get_current_user)):
    """Per-emotion counts + last reflection date."""
    pipeline = [
        {"$match": {"user_id": user["user_id"]}},
        {"$group": {"_id": "$emotion_code", "count": {"$sum": 1}, "last": {"$max": "$created_at"}, "avg_intensity": {"$avg": "$intensity"}}},
        {"$sort": {"count": -1}},
    ]
    rows = await db.tenses_feels_sessions.aggregate(pipeline).to_list(50)
    return {"summary": [{"emotion_code": r["_id"], **{k: v for k, v in r.items() if k != "_id"}} for r in rows]}


class AIGuidanceIn(BaseModel):
    emotion_code: str
    user_situation: str
    intensity: int = 5


@router.post("/ai-guidance")
async def ai_guidance(p: AIGuidanceIn, user: dict = Depends(get_current_user)):
    """AI-personalized coaching prompt for the user's specific situation.

    Stays grounded in the 12-emotion framework. Falls back to a generic
    response when LLM is unavailable so the UI never gets stuck.
    """
    if p.emotion_code not in EMOTION_CODES:
        raise HTTPException(400, f"emotion_code must be one of {sorted(EMOTION_CODES)}")
    if not p.user_situation.strip():
        raise HTTPException(400, "user_situation is required")

    code = p.emotion_code
    healing_map = {
        "clinging": "gratefulness", "longing": "gratefulness",
        "fear": "faith", "anxiety": "faith",
        "anger": "happily_active", "sadness": "happily_active",
        "over_cautious": "happily_active", "over_careless": "happily_active",
        "jealousy": "happily_active", "disgraceful": "happily_active",
        "aggression": "happily_active", "heartbroken": "happily_active",
    }
    healing = healing_map.get(code, "happily_active")

    prompt = (
        "You are a compassionate coach grounded in the 12-emotion 'Tenses & Feels' framework "
        "(Past: Clinging/Longing; Future: Fear/Anxiety; Present-Self-Emotional: Anger/Sadness; "
        "Present-Self-Mental: Over-Cautious/Over-Careless; Present-Others-YourSide: Jealousy/Disgraceful; "
        "Present-Others-TheirSide: Aggression/Heartbroken). The 3 healing feelings are Gratefulness, "
        "Faith, and Happily Active.\n\n"
        f"The user is processing the '{code}' emotion. Their situation:\n\"{p.user_situation}\"\n"
        f"Intensity: {p.intensity}/10. Suggested healing feeling: '{healing}'.\n\n"
        "Respond ONLY in strict JSON with these keys:\n"
        "{\n  acknowledgement: 1-2 sentences validating their feelings,\n"
        "  reframe: 1-2 sentences offering perspective grounded in the framework,\n"
        "  power_statement: a short first-person affirmation,\n"
        "  constructive_action: ONE concrete next step (CCCC: Consistently Constructive with Complete Conviction),\n"
        "  life_lesson_question: a question the user can sit with to extract a lesson\n}"
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY") or "",
            session_id=f"tf-ai-{user['user_id']}-{code}",
            system_message="Return ONLY strict JSON. No markdown fences. No commentary.",
        ).with_model("anthropic", "claude-haiku-4-5")
        reply = await chat.send_message(UserMessage(text=prompt))
        import json, re
        m = re.search(r"\{.*\}", (reply or "").strip(), re.DOTALL)
        data = json.loads(m.group(0) if m else "{}")
        data.setdefault("healing_feeling", healing)
        return data
    except Exception as e:
        logger.warning("tenses-feels AI fallback: %s", e)
        # Deterministic fallback
        fallback = {
            "acknowledgement": "It's natural to feel this. Bringing it into the light is the first step.",
            "reframe": (
                "Past is unchangeable; future is uncertain. Both pull energy away from the present — "
                "where your power actually lives."
            ),
            "power_statement": "I acknowledge this feeling and choose the response most appropriate to the situation.",
            "constructive_action": "Write down one specific precautionary step you'll take this week (CCCC).",
            "life_lesson_question": "What lesson can I carry forward so this pattern doesn't repeat?",
            "healing_feeling": healing,
        }
        return fallback


# ─── Goals & Feels: 10-area-of-life rows ──────────────────────────
class AssociatedEmotion(BaseModel):
    emotion_code: str
    healing_feeling: Optional[str] = ""
    degree: Optional[int] = 5  # 1..10

class GoalFeelRow(BaseModel):
    area_of_life: str             # e.g. "holistic_health"
    sub_area: Optional[str] = ""  # e.g. "physical", "mental", "emotional"
    # ── New schema (June 2026): typed goal + multi-emotion ──
    goal_type: Optional[str] = ""     # problem | need | risk | aspiration
    goal_title: Optional[str] = ""    # picked/autosuggested from goal-setter
    goal_setter_id: Optional[str] = None  # back-link to /goal-setter
    associated_emotions: List[AssociatedEmotion] = Field(default_factory=list)
    # ── Legacy fields kept for backwards compatibility with old sheets ──
    problem: Optional[str] = ""
    need: Optional[str] = ""
    aspiration: Optional[str] = ""
    source_tense: str = "present"  # past | present | future
    primary_emotion: Optional[str] = ""  # one of EMOTION_CODES or healing
    degree: int = 5                # 1..10
    healing_feeling: Optional[str] = ""


class GoalFeelsSheetIn(BaseModel):
    sheet_name: str = "My Goals & Feels"
    rows: List[GoalFeelRow] = Field(default_factory=list)


@router.post("/goals-feels")
async def save_goals_feels(p: GoalFeelsSheetIn, user: dict = Depends(get_current_user)):
    if not (1 <= len(p.rows) <= 100):
        raise HTTPException(400, "rows must be 1–100")
    # Validate enums best-effort
    valid_tenses = {"past", "present", "future"}
    for r in p.rows:
        if r.source_tense not in valid_tenses:
            raise HTTPException(400, f"source_tense must be one of {sorted(valid_tenses)}")
        if not (1 <= int(r.degree) <= 10):
            raise HTTPException(400, "degree must be 1–10")

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "sheet_name": p.sheet_name,
        "rows": [r.model_dump() for r in p.rows],
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.goals_feels_sheets.insert_one(doc)
    doc.pop("_id", None)
    return {"sheet": doc}


@router.get("/goals-feels/latest")
async def latest_sheet(user: dict = Depends(get_current_user)):
    row = await db.goals_feels_sheets.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {"sheet": row}


@router.put("/goals-feels/{sheet_id}")
async def update_sheet(sheet_id: str, p: GoalFeelsSheetIn, user: dict = Depends(get_current_user)):
    existing = await db.goals_feels_sheets.find_one({"id": sheet_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Not found")
    await db.goals_feels_sheets.update_one(
        {"id": sheet_id},
        {"$set": {"sheet_name": p.sheet_name, "rows": [r.model_dump() for r in p.rows], "updated_at": _now()}},
    )
    return {"ok": True}


@router.get("/goals-feels")
async def list_sheets(limit: int = 20, user: dict = Depends(get_current_user)):
    rows = await db.goals_feels_sheets.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"sheets": rows}
