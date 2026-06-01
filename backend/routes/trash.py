"""Trash API — list, restore, and permanently delete soft-deleted items."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import db
from core.trash import TRASH_RETENTION_DAYS, purge_expired

router = APIRouter(tags=["trash"])


@router.get("/trash")
async def list_trash(user: dict = Depends(get_current_user)):
    await purge_expired()  # opportunistic 7-day auto-purge
    items = []
    cur = db.trash.find({"user_id": user["user_id"]}, {"_id": 0, "document": 0}).sort("deleted_at", -1)
    async for t in cur:
        deleted_at = t.get("deleted_at")
        if isinstance(deleted_at, datetime):
            da = deleted_at if deleted_at.tzinfo else deleted_at.replace(tzinfo=timezone.utc)
            expires = da + timedelta(days=TRASH_RETENTION_DAYS)
            days_left = max(0, (expires - datetime.now(timezone.utc)).days)
            deleted_iso = da.isoformat()
        else:
            days_left = TRASH_RETENTION_DAYS
            deleted_iso = str(deleted_at)
        items.append({
            "trash_id": t.get("trash_id"),
            "module": t.get("module"),
            "label": t.get("label"),
            "title": t.get("title"),
            "route": t.get("route"),
            "deleted_at": deleted_iso,
            "days_left": days_left,
        })
    return {"items": items, "retention_days": TRASH_RETENTION_DAYS}


@router.post("/trash/{trash_id}/restore")
async def restore_trash(trash_id: str, user: dict = Depends(get_current_user)):
    t = await db.trash.find_one({"trash_id": trash_id, "user_id": user["user_id"]})
    if not t:
        raise HTTPException(status_code=404, detail="Trash item not found")
    doc = t.get("document") or {}
    doc.pop("_id", None)
    coll = t["collection"]
    idf = t["id_field"]
    existing = await db[coll].find_one({idf: t["original_id"]}, {"_id": 1})
    if not existing:
        await db[coll].insert_one(doc)
    await db.trash.delete_one({"trash_id": trash_id, "user_id": user["user_id"]})
    return {"message": "Restored", "module": t.get("module"), "route": t.get("route"), "id": t.get("original_id")}


@router.delete("/trash/{trash_id}")
async def purge_one(trash_id: str, user: dict = Depends(get_current_user)):
    res = await db.trash.delete_one({"trash_id": trash_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Trash item not found")
    return {"message": "Permanently deleted"}


@router.delete("/trash")
async def empty_trash(user: dict = Depends(get_current_user)):
    res = await db.trash.delete_many({"user_id": user["user_id"]})
    return {"message": "Trash emptied", "count": res.deleted_count}
