"""Emotional Gatekeeper — Breaking the Limitations Routes"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from routes.auth_routes import get_current_user

from .models import LimitationCaptureRequest, LimitationFlowRequest
from .ai_engine import classify_limitation, generate_limitation_reframe, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/limitation/{session_id}/capture")
async def limitation_capture(session_id: str, data: LimitationCaptureRequest, user: dict = Depends(get_current_user)):
    """Screen 2: Capture the limitation."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    lim_id = f"LM-{uuid.uuid4().hex[:8].upper()}"
    doc = {
        "id": lim_id,
        "session_id": session_id,
        "user_id": user["user_id"],
        "limitation_statement": data.limitation_statement,
        "why_limited": data.why_limited,
        "origin": data.origin,
        "limitation_category": data.limitation_category,
        "belief_duration": data.belief_duration,
        "cost_of_limitation": data.cost_of_limitation,
        "ai_classification": None,
        "flow_answers": {},
        "reframe": None,
        "ai_summary": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.limitation_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc}, upsert=True,
    )

    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "in_progress", "updated_at": now}}
    )

    doc.pop("_id", None)
    return doc


@router.post("/limitation/{session_id}/classify")
async def limitation_classify(session_id: str, user: dict = Depends(get_current_user)):
    """Screen 3: AI classifies the limitation category."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    lim = await db.limitation_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not lim:
        raise HTTPException(404, "Limitation reflection not found.")

    try:
        classification = await classify_limitation(lim)
    except Exception as e:
        logger.error(f"Limitation classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    # Update category if AI classified and user didn't already set one
    update = {"ai_classification": classification, "updated_at": now}
    if not lim.get("limitation_category"):
        update["limitation_category"] = classification.get("category", "past_self")

    await db.limitation_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": update}
    )

    return {"session_id": session_id, "classification": classification}


@router.put("/limitation/{session_id}/flow")
async def limitation_flow(session_id: str, data: LimitationFlowRequest, user: dict = Depends(get_current_user)):
    """Flow 3A-3D: Save flow-specific answers."""
    lim = await db.limitation_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]})
    if not lim:
        raise HTTPException(404, "Limitation reflection not found.")

    now = datetime.now(timezone.utc).isoformat()
    await db.limitation_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {"flow_answers": data.answers, "updated_at": now}}
    )

    return {"session_id": session_id, "answers_saved": True}


@router.post("/limitation/{session_id}/reframe")
async def limitation_reframe(session_id: str, user: dict = Depends(get_current_user)):
    """Generate the limitation reframe and breakthrough."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    lim = await db.limitation_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not lim:
        raise HTTPException(404, "Limitation reflection not found.")

    category = lim.get("limitation_category", "past_self")
    flow_answers = lim.get("flow_answers", {})

    try:
        reframe = await generate_limitation_reframe(lim, category, flow_answers)
    except Exception as e:
        logger.error(f"Limitation reframe failed: {e}")
        raise HTTPException(500, f"AI reframe failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    await db.limitation_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {"reframe": reframe, "ai_summary": reframe, "updated_at": now}}
    )

    return {"session_id": session_id, "reframe": reframe}
