"""Video Call Sessions routes (Expert Consultation)"""

import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, ADMIN_ROLES
from core.helpers import create_notification

DEFAULT_CALL_DURATION = 30
MIN_CALL_DURATION = 5
MAX_CALL_DURATION = 120

router = APIRouter(tags=["Video Calls"])


@router.get("/call-config")
async def get_call_config():
    """Get admin-configured call settings"""
    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    if not config:
        return {
            "min_duration": MIN_CALL_DURATION, "max_duration": MAX_CALL_DURATION,
            "default_duration": DEFAULT_CALL_DURATION, "provider": "jitsi",
            "jitsi_domain": "meet.jit.si",
        }
    return config.get("value", {})


@router.put("/call-config")
async def update_call_config(request: Request, user: dict = Depends(get_current_user)):
    """Update call configuration (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    config_value = {
        "min_duration": max(5, min(body.get("min_duration", MIN_CALL_DURATION), 60)),
        "max_duration": max(15, min(body.get("max_duration", MAX_CALL_DURATION), 180)),
        "default_duration": body.get("default_duration", DEFAULT_CALL_DURATION),
        "provider": body.get("provider", "jitsi"),
        "jitsi_domain": body.get("jitsi_domain", "meet.jit.si"),
    }
    await db.app_config.update_one(
        {"key": "call_settings"},
        {"$set": {"key": "call_settings", "value": config_value}},
        upsert=True
    )
    return {"message": "Call config updated", "config": config_value}


@router.post("/call-sessions")
async def create_call_session(request: Request, user: dict = Depends(get_current_user)):
    """Create a new video call session with an expert."""
    body = await request.json()
    expert_id = body.get("expert_id")
    decision_id = body.get("decision_id")
    step_number = body.get("step_number", 0)
    duration_minutes = body.get("duration_minutes", DEFAULT_CALL_DURATION)

    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    config_val = config.get("value", {}) if config else {}
    max_dur = config_val.get("max_duration", MAX_CALL_DURATION)
    min_dur = config_val.get("min_duration", MIN_CALL_DURATION)
    provider = config_val.get("provider", "jitsi")
    jitsi_domain = config_val.get("jitsi_domain", "meet.jit.si")

    duration_minutes = max(min_dur, min(duration_minutes, max_dur))

    if expert_id:
        expert = await db.experts.find_one({"id": expert_id, "is_active": True}, {"_id": 0})
        if not expert:
            raise HTTPException(status_code=404, detail="Expert not found or inactive")

    room_id = f"prr-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration_minutes)

    room_url = f"https://{jitsi_domain}/{room_id}"

    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})

    session_doc = {
        "id": str(uuid.uuid4()), "room_id": room_id, "room_url": room_url,
        "provider": provider, "created_by": user["user_id"],
        "creator_name": user_doc.get("name", "User") if user_doc else "User",
        "expert_id": expert_id, "decision_id": decision_id,
        "step_number": step_number,
        "step_name": body.get("step_name", f"Step {step_number}"),
        "duration_minutes": duration_minutes, "status": "active",
        "created_at": now, "expires_at": expires_at, "ended_at": None,
        "share_context": {
            "decision_title": body.get("decision_title", ""),
            "step_data": body.get("step_data"),
        },
    }

    await db.call_sessions.insert_one(session_doc)

    if expert_id:
        expert = await db.experts.find_one({"id": expert_id}, {"_id": 0})
        if expert and expert.get("email"):
            notif = {
                "id": str(uuid.uuid4()),
                "user_email": expert["email"],
                "type": "call_invitation",
                "title": f"Call Request from {session_doc['creator_name']}",
                "body": f"Step {step_number}: {body.get('step_name', '')} - {body.get('decision_title', '')}",
                "data": {
                    "room_url": room_url, "session_id": session_doc["id"],
                    "duration_minutes": duration_minutes, "expires_at": expires_at.isoformat(),
                },
                "read": False, "created_at": now,
            }
            await db.notifications.insert_one(notif)

    return {
        "session_id": session_doc["id"], "room_id": room_id, "room_url": room_url,
        "provider": provider, "duration_minutes": duration_minutes,
        "expires_at": expires_at.isoformat(),
    }


@router.get("/call-sessions/{session_id}")
async def get_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get call session details"""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("expires_at"):
        expires_at = session["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        elif expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            if session["status"] == "active":
                await db.call_sessions.update_one({"id": session_id}, {"$set": {"status": "expired"}})
                session["status"] = "expired"
    return session


@router.put("/call-sessions/{session_id}/end")
async def end_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """End a call session"""
    result = await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Call session ended"}


@router.get("/call-sessions")
async def list_call_sessions(user: dict = Depends(get_current_user), decision_id: str = None):
    """List call sessions for the current user"""
    query = {"created_by": user["user_id"]}
    if decision_id:
        query["decision_id"] = decision_id
    sessions = await db.call_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions
