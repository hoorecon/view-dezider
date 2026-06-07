"""Dashboard stats + folder reference routes."""

from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import DECISION_FOLDERS

router = APIRouter(tags=["Decisions"])


@router.get("/stats")
async def get_user_stats(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    total_decisions = await db.decisions.count_documents({"user_id": user_id})
    completed_decisions = await db.decisions.count_documents({"user_id": user_id, "status": "completed"})
    total_test123 = await db.test123_sessions.count_documents({"user_id": user_id})
    total_journal = await db.journal.count_documents({"user_id": user_id})
    completed_journal = await db.journal.count_documents({"user_id": user_id, "status": "completed"})
    latest_assessment = await db.assessments.find_one({"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)])
    return {
        "decisions": {"total": total_decisions, "completed": completed_decisions},
        "test123": {"total": total_test123},
        "journal": {"total": total_journal, "completed": completed_journal},
        "latest_assessment": latest_assessment,
    }


@router.get("/folders")
async def get_folders():
    return DECISION_FOLDERS
