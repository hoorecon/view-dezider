"""
Masters API — reference data for religions, castes, languages, occupations,
skills, drives and traits.

Public (authenticated) endpoints power the Contacts autocomplete/dropdowns.
Admin endpoints (require_admin) allow add / edit / delete of any master row,
including the bundled seed rows.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.auth import get_current_user, require_admin
from core.database import db
from core.masters_seed import MASTER_TYPES

router = APIRouter(prefix="/masters", tags=["masters"])


def _now():
    return datetime.now(timezone.utc).isoformat()


def _public(doc: dict) -> dict:
    return {
        "master_id": doc.get("master_id"),
        "type": doc.get("type"),
        "value": doc.get("value"),
        "parent": doc.get("parent"),
        "active": doc.get("active", True),
        "is_seed": doc.get("is_seed", False),
    }


@router.get("/types")
async def list_master_types(user: dict = Depends(get_current_user)):
    return {"types": MASTER_TYPES}


@router.get("/{mtype}")
async def list_masters(
    mtype: str,
    search: Optional[str] = Query(None),
    parent: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(500, le=2000),
    user: dict = Depends(get_current_user),
):
    if mtype not in MASTER_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown master type '{mtype}'")
    query: dict = {"type": mtype}
    if not include_inactive:
        query["active"] = True
    if parent:
        query["parent_lower"] = parent.strip().lower()
    if search:
        query["value_lower"] = {"$regex": _escape(search.strip().lower())}
    docs = (
        await db.masters.find(query, {"_id": 0})
        .sort([("order", 1), ("value_lower", 1)])
        .to_list(limit)
    )
    return {"items": [_public(d) for d in docs], "count": len(docs)}


def _escape(s: str) -> str:
    import re
    return re.escape(s)


@router.post("")
async def create_master(request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    mtype = (body.get("type") or "").strip().lower()
    value = (body.get("value") or "").strip()
    parent = (body.get("parent") or None)
    if mtype not in MASTER_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown master type '{mtype}'")
    if not value:
        raise HTTPException(status_code=400, detail="value is required")

    dup = await db.masters.find_one({
        "type": mtype,
        "value_lower": value.lower(),
        "parent_lower": (parent or "").lower(),
    })
    if dup:
        raise HTTPException(status_code=409, detail="This value already exists")

    last = await db.masters.find({"type": mtype}, {"order": 1}).sort("order", -1).to_list(1)
    next_order = (last[0]["order"] + 1) if last else 0

    doc = {
        "master_id": str(uuid.uuid4()),
        "type": mtype,
        "value": value,
        "value_lower": value.lower(),
        "parent": parent,
        "parent_lower": (parent or "").lower(),
        "order": next_order,
        "active": True,
        "is_seed": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.masters.insert_one(doc)
    return _public(doc)


@router.put("/{master_id}")
async def update_master(master_id: str, request: Request, admin: dict = Depends(require_admin)):
    body = await request.json()
    doc = await db.masters.find_one({"master_id": master_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Master not found")
    updates: dict = {"updated_at": _now()}
    if "value" in body:
        v = (body.get("value") or "").strip()
        if not v:
            raise HTTPException(status_code=400, detail="value cannot be empty")
        updates["value"] = v
        updates["value_lower"] = v.lower()
    if "parent" in body:
        p = body.get("parent") or None
        updates["parent"] = p
        updates["parent_lower"] = (p or "").lower()
    if "active" in body:
        updates["active"] = bool(body.get("active"))
    if "order" in body:
        try:
            updates["order"] = int(body.get("order"))
        except Exception:
            pass
    await db.masters.update_one({"master_id": master_id}, {"$set": updates})
    out = await db.masters.find_one({"master_id": master_id}, {"_id": 0})
    return _public(out)


@router.delete("/{master_id}")
async def delete_master(master_id: str, admin: dict = Depends(require_admin)):
    res = await db.masters.delete_one({"master_id": master_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Master not found")
    return {"deleted": True, "master_id": master_id}
