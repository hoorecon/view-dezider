"""Emotional Gatekeeper — Breaking the Trap Routes"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from core.database import db
from routes.auth_routes import get_current_user

from .models import TrapCaptureRequest, TrapLandscapingRequest, TrapLinkingRequest, TrapLoopingRequest
from .ai_engine import analyze_trap, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trap/{session_id}/capture")
async def trap_capture(session_id: str, data: TrapCaptureRequest, user: dict = Depends(get_current_user)):
    """Screen 2: Capture the trap situation."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    trap_id = f"TR-{uuid.uuid4().hex[:8].upper()}"

    doc = {
        "id": trap_id,
        "session_id": session_id,
        "user_id": user["user_id"],
        "situation": data.situation,
        "category": data.category,
        "start_period": data.start_period,
        "intensity": data.intensity,
        # Will be filled in subsequent steps
        "landscaping_pattern": None,
        "trigger_type": None,
        "external_trigger": None,
        "internal_trigger": None,
        "linking_meaning": None,
        "looping_thought": None,
        "emotional_intensity": data.intensity,
        "ai_summary": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.trap_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc}, upsert=True,
    )

    # Update session
    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "in_progress", "intensity_before": data.intensity, "updated_at": now}}
    )

    doc.pop("_id", None)
    return doc


@router.put("/trap/{session_id}/landscaping")
async def trap_landscaping(session_id: str, data: TrapLandscapingRequest, user: dict = Depends(get_current_user)):
    """Screen 3: Landscaping detection."""
    trap = await db.trap_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]})
    if not trap:
        raise HTTPException(404, "Trap reflection not found. Complete capture first.")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "scanning_for": data.scanning_for,
        "scanning_patterns": data.scanning_patterns,
        "scanning_without_urgency": data.scanning_without_urgency,
        "repeated_concern": data.repeated_concern,
        "updated_at": now,
    }
    await db.trap_reflections.update_one({"session_id": session_id, "user_id": user["user_id"]}, {"$set": update})
    return {"session_id": session_id, "step": "landscaping", **update}


@router.put("/trap/{session_id}/linking")
async def trap_linking(session_id: str, data: TrapLinkingRequest, user: dict = Depends(get_current_user)):
    """Screen 4: Linking detection."""
    trap = await db.trap_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]})
    if not trap:
        raise HTTPException(404, "Trap reflection not found.")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "trigger_description": data.trigger_description,
        "trigger_type": data.trigger_type,
        "external_trigger": data.external_trigger,
        "internal_trigger": data.internal_trigger,
        "linking_meaning": data.linking_meaning,
        "updated_at": now,
    }
    await db.trap_reflections.update_one({"session_id": session_id, "user_id": user["user_id"]}, {"$set": update})
    return {"session_id": session_id, "step": "linking", **update}


@router.put("/trap/{session_id}/looping")
async def trap_looping(session_id: str, data: TrapLoopingRequest, user: dict = Depends(get_current_user)):
    """Screen 5: Looping detection."""
    trap = await db.trap_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]})
    if not trap:
        raise HTTPException(404, "Trap reflection not found.")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "looping_thought": data.repeating_thought,
        "repeating_question": data.repeating_question,
        "getting_new_solution": data.getting_new_solution,
        "emotion_increasing": data.emotion_increasing,
        "intensity_before_loop": data.intensity_before,
        "intensity_after_loop": data.intensity_after,
        "updated_at": now,
    }
    await db.trap_reflections.update_one({"session_id": session_id, "user_id": user["user_id"]}, {"$set": update})
    return {"session_id": session_id, "step": "looping", **update}


@router.post("/trap/{session_id}/analyze")
async def trap_analyze(session_id: str, user: dict = Depends(get_current_user)):
    """Screen 6: AI Trap Awareness Summary."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    trap = await db.trap_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not trap:
        raise HTTPException(404, "Trap reflection not found.")

    try:
        analysis = await analyze_trap(trap)
    except Exception as e:
        logger.error(f"Trap analysis failed: {e}")
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    await db.trap_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {"ai_summary": analysis, "updated_at": now}}
    )

    return {"session_id": session_id, "analysis": analysis}


@router.post("/trap/{session_id}/voice")
async def trap_voice_input(
    session_id: str,
    audio: UploadFile = File(...),
    field: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Transcribe voice input for any trap field (English only)."""
    from routes.social_learning.stt_engine import stt_engine
    from routes.social_learning.constants import ALLOWED_AUDIO_TYPES

    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    content_type = audio.content_type or ""
    audio_format = ALLOWED_AUDIO_TYPES.get(content_type)
    if not audio_format:
        ext = (audio.filename or "").rsplit(".", 1)[-1].lower()
        ext_map = {"wav": "wav", "mp3": "mp3", "ogg": "ogg", "webm": "webm", "m4a": "m4a"}
        audio_format = ext_map.get(ext)
    if not audio_format:
        raise HTTPException(400, "Unsupported audio format. Use WAV, MP3, OGG, or WEBM.")

    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Audio file too large (max 10MB)")

    try:
        text = stt_engine.transcribe(audio_bytes, audio_format=audio_format, language="en-US")
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"field": field, "transcribed_text": text}
