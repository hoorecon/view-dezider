"""Test123 quick-decision session routes."""

from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import Test123Session, Test123Create, Test123Update

router = APIRouter(tags=["Decisions"])


@router.post("/test123", response_model=dict)
async def create_test123(test_data: Test123Create, user: dict = Depends(get_current_user)):
    session = Test123Session(user_id=user["user_id"], situation=test_data.situation)
    await db.test123_sessions.insert_one(session.dict())
    return {"id": session.id, "message": "Test123 session created"}


@router.get("/test123", response_model=List[dict])
async def get_test123_sessions(user: dict = Depends(get_current_user)):
    sessions = await db.test123_sessions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions


@router.get("/test123/{session_id}")
async def get_test123_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.test123_sessions.find_one({"id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/test123/{session_id}")
async def update_test123_session(session_id: str, update_data: Test123Update, user: dict = Depends(get_current_user)):
    existing = await db.test123_sessions.find_one({"id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.test123_sessions.update_one({"id": session_id}, {"$set": update_dict})
    return {"message": "Session updated successfully"}


@router.delete("/test123/{session_id}")
async def delete_test123_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a Test123 quick-decision session owned by the caller."""
    res = await db.test123_sessions.delete_one(
        {"id": session_id, "user_id": user["user_id"]}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id, "message": "Session deleted."}
