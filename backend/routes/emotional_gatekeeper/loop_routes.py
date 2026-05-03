"""Emotional Gatekeeper — Breaking the Loop Routes"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from routes.auth_routes import get_current_user

from .models import LoopCaptureRequest, LoopMethodRequest
from .ai_engine import recommend_loop_method, generate_loop_reframe, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/loop/{session_id}/capture")
async def loop_capture(session_id: str, data: LoopCaptureRequest, user: dict = Depends(get_current_user)):
    """Screen 2: Capture the loop."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    loop_id = f"LO-{uuid.uuid4().hex[:8].upper()}"
    doc = {
        "id": loop_id,
        "session_id": session_id,
        "user_id": user["user_id"],
        "repeated_thought": data.repeated_thought,
        "emotion": data.emotion,
        "repeat_count_today": data.repeat_count_today,
        "fear": data.fear,
        "trying_to_solve": data.trying_to_solve,
        "selected_method": None,
        "ai_recommended_method": None,
        "method_answers": {},
        "reframe": None,
        "calming_statement": None,
        "immediate_action": None,
        "affirmation": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.loop_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc}, upsert=True,
    )

    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "in_progress", "updated_at": now}}
    )

    doc.pop("_id", None)
    return doc


@router.post("/loop/{session_id}/recommend")
async def loop_recommend(session_id: str, user: dict = Depends(get_current_user)):
    """Screen 3: AI recommends the best loop-breaking method."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    loop = await db.loop_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not loop:
        raise HTTPException(404, "Loop reflection not found. Complete capture first.")

    try:
        recommendation = await recommend_loop_method(loop)
    except Exception as e:
        logger.error(f"Loop recommendation failed: {e}")
        raise HTTPException(500, f"AI recommendation failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    await db.loop_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {"ai_recommended_method": recommendation, "updated_at": now}}
    )

    return {"session_id": session_id, "recommendation": recommendation}


@router.put("/loop/{session_id}/method")
async def loop_apply_method(session_id: str, data: LoopMethodRequest, user: dict = Depends(get_current_user)):
    """Screen 4A-4D: Apply the selected method with answers."""
    loop = await db.loop_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]})
    if not loop:
        raise HTTPException(404, "Loop reflection not found.")

    valid_methods = ["i_dont_know", "all_is_well", "both_good_bad", "this_too_shall_pass"]
    if data.selected_method not in valid_methods:
        raise HTTPException(400, f"Invalid method. Must be one of: {valid_methods}")

    now = datetime.now(timezone.utc).isoformat()
    await db.loop_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {
            "selected_method": data.selected_method,
            "method_answers": data.method_answers,
            "updated_at": now,
        }}
    )

    return {"session_id": session_id, "method": data.selected_method, "answers_saved": True}


@router.post("/loop/{session_id}/reframe")
async def loop_reframe(session_id: str, user: dict = Depends(get_current_user)):
    """Screen 5: Generate the loop reframe summary."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    loop = await db.loop_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not loop:
        raise HTTPException(404, "Loop reflection not found.")

    if not loop.get("selected_method"):
        raise HTTPException(400, "Please select and complete a loop-breaking method first.")

    try:
        reframe = await generate_loop_reframe(loop, loop)
    except Exception as e:
        logger.error(f"Loop reframe failed: {e}")
        raise HTTPException(500, f"AI reframe generation failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    await db.loop_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {
            "reframe": reframe.get("new_perspective", ""),
            "calming_statement": reframe.get("calming_statement", ""),
            "immediate_action": reframe.get("immediate_action", ""),
            "affirmation": reframe.get("reflection_affirmation", ""),
            "ai_reframe_full": reframe,
            "updated_at": now,
        }}
    )

    return {"session_id": session_id, "reframe": reframe}
