"""Emotional Gatekeeper — Generic voice transcription endpoint.

A session-less Whisper endpoint usable across ALL Emotional Gatekeeper
sub-modules whenever the input is free-form emotional text and the user
may want to dictate instead of typing slowly while emotionally activated.

Unlike `/trap/{session_id}/voice` (which requires an existing
`breakthrough_sessions` row), this endpoint only needs an authenticated user
and an audio blob. It is used by inputs that are NOT bound to a session
(e.g. Gratitude Journal entries in the Advisor card).

Returns: { field, transcribed_text }
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/voice/transcribe")
async def generic_voice_transcribe(
    audio: UploadFile = File(...),
    field: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Session-less voice → English text. Used by Gratitude entries and
    any other EG input that is not tied to a `breakthrough_sessions` row.
    """
    # Imports are deferred so the test harness can stub the STT engine
    # without dragging the social_learning module on every boot.
    from routes.social_learning.stt_engine import stt_engine
    from routes.social_learning.constants import ALLOWED_AUDIO_TYPES

    # MediaRecorder sends e.g. "audio/webm;codecs=opus" — strip the params.
    content_type = (audio.content_type or "").split(";")[0].strip()
    audio_format = ALLOWED_AUDIO_TYPES.get(content_type)
    if not audio_format:
        ext = (audio.filename or "").rsplit(".", 1)[-1].lower()
        ext_map = {"wav": "wav", "mp3": "mp3", "ogg": "ogg", "webm": "webm", "m4a": "m4a"}
        audio_format = ext_map.get(ext)
    if not audio_format:
        audio_format = "webm"  # safest default for browser MediaRecorder

    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "Audio file too large (max 10MB)")

    try:
        text = stt_engine.transcribe(audio_bytes, audio_format=audio_format, language="en-US")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("EG generic voice transcribe failed: %s", e)
        raise HTTPException(500, "Transcription failed. Please try again.")

    return {"field": field, "transcribed_text": text or ""}
