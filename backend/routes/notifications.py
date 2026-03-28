"""Notifications + Experts routes"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, ADMIN_ROLES

router = APIRouter(tags=["Notifications"])


# ========================
# EXPERTS (admin-managed)
# ========================

@router.get("/experts")
async def get_experts(include_inactive: bool = False):
    """Get list of authorized experts"""
    query = {} if include_inactive else {"is_active": True}
    experts = await db.experts.find(query, {"_id": 0}).sort("name", 1).to_list(100)
    return experts


@router.post("/experts")
async def create_expert(request: Request, user: dict = Depends(get_current_user)):
    """Create an authorized expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    expert = {
        "id": str(uuid.uuid4()),
        "name": body.get("name", ""),
        "email": body.get("email", ""),
        "specialization": body.get("specialization", ""),
        "bio": body.get("bio", ""),
        "is_active": True,
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.experts.insert_one(expert)
    return {"id": expert["id"], "message": "Expert created"}


@router.put("/experts/{expert_id}")
async def update_expert(expert_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update an expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    update_fields = {k: v for k, v in body.items() if k in ["name", "email", "specialization", "bio", "is_active"]}
    result = await db.experts.update_one({"id": expert_id}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"message": "Expert updated"}


@router.delete("/experts/{expert_id}")
async def delete_expert(expert_id: str, user: dict = Depends(get_current_user)):
    """Delete an expert (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.experts.delete_one({"id": expert_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expert not found")
    return {"message": "Expert deleted"}


# ========================
# NOTIFICATIONS
# ========================

@router.get("/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    """Get all notifications for the current user"""
    notifications = await db.notifications.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifications


@router.get("/notifications/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents(
        {"user_id": user["user_id"], "read": False}
    )
    return {"count": count}


@router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: str, user: dict = Depends(get_current_user)):
    """Mark a specific notification as read"""
    result = await db.notifications.update_one(
        {"id": notif_id, "user_id": user["user_id"]},
        {"$set": {"read": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read"""
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "All notifications marked as read"}


@router.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: str, user: dict = Depends(get_current_user)):
    """Delete a notification"""
    await db.notifications.delete_one({"id": notif_id, "user_id": user["user_id"]})
    return {"message": "Notification deleted"}
