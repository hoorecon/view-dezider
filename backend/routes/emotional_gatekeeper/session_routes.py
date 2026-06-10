"""Emotional Gatekeeper — Session & Dashboard Routes"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core import ai_wallet
from routes.auth_routes import get_current_user

from .models import (
    CreateSessionRequest, UpdateSessionRequest,
    CommitmentRequest, JournalRequest,
)
from .constants import SESSION_TYPES, SESSION_STATUSES
from .ai_engine import generate_breakthrough_report

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ SESSIONS ============

@router.post("/sessions")
async def create_session(data: CreateSessionRequest, user: dict = Depends(get_current_user)):
    """Create a new breakthrough session."""
    if data.session_type not in SESSION_TYPES:
        raise HTTPException(400, f"Invalid session_type. Must be one of: {SESSION_TYPES}")

    session_id = f"EG-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    session = {
        "id": session_id,
        "user_id": user["user_id"],
        "session_type": data.session_type,
        "title": data.title or f"{data.session_type.title()} Session",
        "status": "draft",
        "intensity_before": None,
        "intensity_after": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.breakthrough_sessions.insert_one(session)
    session.pop("_id", None)
    return session


@router.get("/sessions")
async def list_sessions(
    session_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List user's breakthrough sessions."""
    query: dict = {"user_id": user["user_id"]}
    if session_type:
        query["session_type"] = session_type
    if status:
        query["status"] = status
    total = await db.breakthrough_sessions.count_documents(query)
    sessions = await db.breakthrough_sessions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"total": total, "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get a specific session with all related reflections."""
    session = await db.breakthrough_sessions.find_one(
        {"id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not session:
        raise HTTPException(404, "Session not found")

    # Attach related reflections
    trap = await db.trap_reflections.find_one({"session_id": session_id}, {"_id": 0})
    loop = await db.loop_reflections.find_one({"session_id": session_id}, {"_id": 0})
    limitation = await db.limitation_reflections.find_one({"session_id": session_id}, {"_id": 0})
    outlet = await db.outlet_reflections.find_one({"session_id": session_id}, {"_id": 0})
    aim = await db.aim_reflections.find_one({"session_id": session_id}, {"_id": 0})
    commitments = await db.breakthrough_commitments.find(
        {"session_id": session_id}, {"_id": 0}
    ).to_list(20)
    journal = await db.breakthrough_journal.find_one({"session_id": session_id}, {"_id": 0})
    report = await db.breakthrough_reports.find_one({"session_id": session_id}, {"_id": 0})

    session["trap_reflection"] = trap
    session["loop_reflection"] = loop
    session["limitation_reflection"] = limitation
    session["outlet_reflection"] = outlet
    session["aim_reflection"] = aim
    session["commitments"] = commitments
    session["journal"] = journal
    session["report"] = report
    # Per-session AI spend (credits + call count) for the "AI used this session" UI.
    session["ai_cost"] = await ai_wallet.session_cost(user["user_id"], session_id)

    return session


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, data: UpdateSessionRequest, user: dict = Depends(get_current_user)):
    """Update session status or intensity."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.title is not None:
        update["title"] = data.title
    if data.status is not None:
        if data.status not in SESSION_STATUSES:
            raise HTTPException(400, f"Invalid status. Must be one of: {SESSION_STATUSES}")
        update["status"] = data.status
    if data.intensity_before is not None:
        update["intensity_before"] = data.intensity_before
    if data.intensity_after is not None:
        update["intensity_after"] = data.intensity_after

    await db.breakthrough_sessions.update_one({"id": session_id}, {"$set": update})
    return {"id": session_id, **update}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a session and all related data."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    await db.breakthrough_sessions.delete_one({"id": session_id})
    await db.trap_reflections.delete_many({"session_id": session_id})
    await db.loop_reflections.delete_many({"session_id": session_id})
    await db.limitation_reflections.delete_many({"session_id": session_id})
    await db.outlet_reflections.delete_many({"session_id": session_id})
    await db.aim_reflections.delete_many({"session_id": session_id})
    await db.breakthrough_commitments.delete_many({"session_id": session_id})
    await db.breakthrough_journal.delete_many({"session_id": session_id})
    await db.breakthrough_reports.delete_many({"session_id": session_id})

    return {"message": "Session deleted", "id": session_id}


# ============ COMMITMENTS ============

@router.post("/sessions/{session_id}/commitments")
async def add_commitment(session_id: str, data: CommitmentRequest, user: dict = Depends(get_current_user)):
    """Add an action commitment to a session."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    commit_id = f"BC-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    commitment = {
        "id": commit_id,
        "session_id": session_id,
        "user_id": user["user_id"],
        "commitment_type": data.commitment_type,
        "commitment_text": data.commitment_text,
        "due_date": data.due_date,
        "status": "pending",
        "reminder_enabled": data.reminder_enabled,
        "created_at": now,
        "updated_at": now,
    }
    await db.breakthrough_commitments.insert_one(commitment)
    commitment.pop("_id", None)
    return commitment


@router.put("/commitments/{commitment_id}/complete")
async def complete_commitment(commitment_id: str, user: dict = Depends(get_current_user)):
    """Mark a commitment as completed."""
    result = await db.breakthrough_commitments.update_one(
        {"id": commitment_id, "user_id": user["user_id"]},
        {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Commitment not found")
    return {"id": commitment_id, "status": "completed"}


# ============ JOURNAL ============

@router.post("/sessions/{session_id}/journal")
async def save_journal(session_id: str, data: JournalRequest, user: dict = Depends(get_current_user)):
    """Save a journal entry for a session."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    journal_id = f"BJ-{uuid.uuid4().hex[:8].upper()}"
    journal = {
        "id": journal_id,
        "session_id": session_id,
        "user_id": user["user_id"],
        "journal_title": data.journal_title or session.get("title", "Breakthrough Journal"),
        "journal_content": data.journal_content or "",
        "tags": data.tags,
        "ai_report": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.breakthrough_journal.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": journal},
        upsert=True,
    )
    journal.pop("_id", None)
    return journal


# ============ REPORT ============

@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, user: dict = Depends(get_current_user)):
    """Generate the AI Breakthrough Report for a session."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(404, "Session not found")

    # Collect all session data
    session_data = {**session}
    trap = await db.trap_reflections.find_one({"session_id": session_id}, {"_id": 0})
    loop = await db.loop_reflections.find_one({"session_id": session_id}, {"_id": 0})
    limitation = await db.limitation_reflections.find_one({"session_id": session_id}, {"_id": 0})
    aim = await db.aim_reflections.find_one({"session_id": session_id}, {"_id": 0})
    outlet = await db.outlet_reflections.find_one({"session_id": session_id}, {"_id": 0})
    if trap:
        session_data["trap"] = trap
    if loop:
        session_data["loop"] = loop
    if limitation:
        session_data["limitation"] = limitation

    # Guard: don't generate a (generic) report when the user hasn't recorded anything yet.
    has_content = bool(
        (trap and (trap.get("situation") or trap.get("ai_summary"))) or
        (loop and (loop.get("repeated_thought") or loop.get("ai_reframe_full"))) or
        (limitation and (limitation.get("limitation_statement") or limitation.get("ai_summary"))) or
        (aim and (aim.get("addictions") or aim.get("irritations") or aim.get("ai_analysis"))) or
        (outlet and outlet.get("ai_analysis"))
    )
    if not has_content:
        raise HTTPException(status_code=400, detail={
            "code": "no_reflection_data",
            "message": "Complete at least one reflection (Trap, Loop, Limitation, or AIM) before generating a report.",
        })

    try:
        report = await generate_breakthrough_report(session_data, user_id=user["user_id"], session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(502, detail={"code": "ai_error", "message": "AI report generation failed. Please try again."})

    now = datetime.now(timezone.utc).isoformat()
    report_doc = {
        "id": f"BR-{uuid.uuid4().hex[:8].upper()}",
        "session_id": session_id,
        "user_id": user["user_id"],
        "report": report,
        "created_at": now,
    }
    await db.breakthrough_reports.update_one(
        {"session_id": session_id},
        {"$set": report_doc},
        upsert=True,
    )

    # Update session status
    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "completed", "updated_at": now}}
    )

    report_doc.pop("_id", None)
    return report_doc


# ============ DASHBOARD ============

@router.get("/dashboard")
async def get_dashboard(user: dict = Depends(get_current_user)):
    """Inner Breakthrough Tracker dashboard."""
    uid = user["user_id"]

    total_sessions = await db.breakthrough_sessions.count_documents({"user_id": uid})
    completed_sessions = await db.breakthrough_sessions.count_documents({"user_id": uid, "status": "completed"})
    traps_identified = await db.trap_reflections.count_documents({"user_id": uid})
    loops_broken = await db.loop_reflections.count_documents({"user_id": uid})
    limitations_identified = await db.limitation_reflections.count_documents({"user_id": uid})
    outlets_analyzed = await db.outlet_reflections.count_documents({"user_id": uid})
    aim_sessions = await db.aim_reflections.count_documents({"user_id": uid})

    commitments_total = await db.breakthrough_commitments.count_documents({"user_id": uid})
    commitments_completed = await db.breakthrough_commitments.count_documents({"user_id": uid, "status": "completed"})

    # Streak: consecutive days with completed sessions
    sessions = await db.breakthrough_sessions.find(
        {"user_id": uid, "status": "completed"}, {"_id": 0, "created_at": 1}
    ).sort("created_at", -1).limit(60).to_list(60)

    streak = 0
    if sessions:
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        current_date = today
        session_dates = set()
        for s in sessions:
            d = s.get("created_at", "")
            if isinstance(d, str) and d:
                session_dates.add(datetime.fromisoformat(d.replace("Z", "+00:00")).date())
        while current_date in session_dates:
            streak += 1
            current_date -= timedelta(days=1)

    # Recent sessions
    recent = await db.breakthrough_sessions.find(
        {"user_id": uid}, {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)

    # Pending commitments
    pending_actions = await db.breakthrough_commitments.find(
        {"user_id": uid, "status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).limit(10).to_list(10)

    return {
        "traps_identified": traps_identified,
        "loops_broken": loops_broken,
        "limitations_identified": limitations_identified,
        "outlets_analyzed": outlets_analyzed,
        "aim_sessions": aim_sessions,
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "commitments_total": commitments_total,
        "commitments_completed": commitments_completed,
        "breakthrough_streak": streak,
        "recent_sessions": recent,
        "pending_actions": pending_actions,
    }
