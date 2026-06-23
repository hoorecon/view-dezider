"""
Platform Experts — vetted, admin-managed expert directory (Collaboration Epic Phase B2).

A Platform Expert is a comprehensive, masters-driven profile that users can
share decision-steps with (via the Share modal's "Experts" tab). Unlike the
legacy `db.experts` "authorized experts" (simple name/email) and the
self-onboarded ExpertNet profiles, a Platform Expert is:

  • masters-driven   — Expert Type, Languages, Experience Range, Fees/min,
                       Available Timings all come from the Masters catalog.
  • catalog-linked   — pinned to one or more Central Catalog node-ids so the
                       Share modal can surface "experts for THIS topic".
  • multi-org        — the same person (e.g. a surgeon) can be associated with
                       many organisations; each association carries its own
                       Role, Fees/min, Contact Email, WhatsApp, Mobile,
                       Physical Address, Available Timings and Country/State/City.

Stored in its own `platform_experts` collection so it never collides with the
two pre-existing expert schemas.

Admin endpoints (require_admin): create / update / delete / bulk-upload.
Read endpoints (authenticated): list (filterable) + detail — power the Share
modal's Experts tab and any topic-scoped discovery.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import ADMIN_ROLES, get_current_user, require_admin
from core.database import db

router = APIRouter(prefix="/platform-experts", tags=["Platform Experts"])


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class ExpertOrg(BaseModel):
    org_id: Optional[str] = None
    org_name: str = Field(..., min_length=1, max_length=160)
    role: Optional[str] = Field(None, max_length=120)            # e.g. "Senior Surgeon"
    fees_per_min_inr: Optional[int] = Field(None, ge=0)
    contact_email: Optional[str] = Field(None, max_length=160)
    whatsapp: Optional[str] = Field(None, max_length=40)
    mobile: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = Field(None, max_length=400)
    available_timings: List[str] = Field(default_factory=list)
    country: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    city: Optional[str] = Field(None, max_length=80)


class PlatformExpertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    email: str = Field(..., min_length=3, max_length=160)
    photo_url: Optional[str] = None
    headline: Optional[str] = Field(None, max_length=240)
    bio: Optional[str] = Field(None, max_length=4000)
    expert_type: Optional[str] = Field(None, max_length=120)     # master value
    languages: List[str] = Field(default_factory=list)           # master values
    experience_range: Optional[str] = Field(None, max_length=80)  # master value
    fees_per_min_inr: Optional[int] = Field(None, ge=0)
    available_timings: List[str] = Field(default_factory=list)   # master values
    specializations: List[str] = Field(default_factory=list)
    catalog_node_ids: List[str] = Field(default_factory=list)
    organizations: List[ExpertOrg] = Field(default_factory=list)
    is_active: bool = True
    is_verified: bool = True


class PlatformExpertUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    expert_type: Optional[str] = None
    languages: Optional[List[str]] = None
    experience_range: Optional[str] = None
    fees_per_min_inr: Optional[int] = None
    available_timings: Optional[List[str]] = None
    specializations: Optional[List[str]] = None
    catalog_node_ids: Optional[List[str]] = None
    organizations: Optional[List[ExpertOrg]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class BulkUpload(BaseModel):
    experts: List[PlatformExpertCreate]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_admin(user: dict) -> bool:
    return (user.get("role") or "user") in ADMIN_ROLES


def _public(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc.pop("_id", None)
    return doc


async def _build_doc(body: PlatformExpertCreate, user: dict) -> dict:
    expert_id = f"pex_{uuid.uuid4().hex[:12]}"
    return {
        "expert_id": expert_id,
        "name": body.name.strip(),
        "email": body.email.strip().lower(),
        "photo_url": body.photo_url,
        "headline": body.headline,
        "bio": body.bio,
        "expert_type": body.expert_type,
        "languages": body.languages,
        "experience_range": body.experience_range,
        "fees_per_min_inr": body.fees_per_min_inr,
        "available_timings": body.available_timings,
        "specializations": body.specializations,
        "catalog_node_ids": body.catalog_node_ids,
        "organizations": [o.model_dump() for o in body.organizations],
        "rating_avg": None,
        "rating_count": 0,
        "karma_points": 0,
        "is_active": body.is_active,
        "is_verified": body.is_verified,
        "source": "manual",
        "created_by": user["user_id"],
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------------------
# read (authenticated)
# ---------------------------------------------------------------------------
@router.get("")
async def list_platform_experts(
    catalog_node_id: Optional[str] = Query(None),
    expert_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(200, le=1000),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    # only admins may list inactive
    if not (include_inactive and _is_admin(user)):
        q["is_active"] = True
    if catalog_node_id:
        q["catalog_node_ids"] = catalog_node_id
    if expert_type:
        q["expert_type"] = expert_type
    if language:
        q["languages"] = language
    if search:
        import re
        rx = re.escape(search.strip())
        q["$or"] = [
            {"name": {"$regex": rx, "$options": "i"}},
            {"email": {"$regex": rx, "$options": "i"}},
            {"expert_type": {"$regex": rx, "$options": "i"}},
            {"specializations": {"$regex": rx, "$options": "i"}},
        ]
    cur = db.platform_experts.find(q, {"_id": 0}).sort([("name", 1)])
    items = [_public(d) for d in await cur.to_list(limit)]
    return {"items": items, "count": len(items)}


@router.get("/{expert_id}")
async def get_platform_expert(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.platform_experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "platform expert not found")
    return _public(e)


# ---------------------------------------------------------------------------
# admin mutators
# ---------------------------------------------------------------------------
@router.post("")
async def create_platform_expert(body: PlatformExpertCreate, admin: dict = Depends(require_admin)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "valid email is required")
    dup = await db.platform_experts.find_one({"email": email}, {"_id": 1})
    if dup:
        raise HTTPException(409, "a platform expert with this email already exists")
    doc = await _build_doc(body, admin)
    await db.platform_experts.insert_one(doc)
    return _public(doc)


@router.put("/{expert_id}")
async def update_platform_expert(expert_id: str, body: PlatformExpertUpdate, admin: dict = Depends(require_admin)):
    existing = await db.platform_experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "platform expert not found")
    updates: Dict[str, Any] = {"updated_at": _now()}
    data = body.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        new_email = data["email"].strip().lower()
        if "@" not in new_email:
            raise HTTPException(400, "valid email is required")
        clash = await db.platform_experts.find_one(
            {"email": new_email, "expert_id": {"$ne": expert_id}}, {"_id": 1}
        )
        if clash:
            raise HTTPException(409, "another platform expert already uses this email")
        updates["email"] = new_email
        data.pop("email")
    if "organizations" in data and data["organizations"] is not None:
        updates["organizations"] = [
            o.model_dump() if hasattr(o, "model_dump") else o for o in body.organizations
        ]
        data.pop("organizations")
    for k, v in data.items():
        updates[k] = v
    await db.platform_experts.update_one({"expert_id": expert_id}, {"$set": updates})
    return _public(await db.platform_experts.find_one({"expert_id": expert_id}, {"_id": 0}))


@router.delete("/{expert_id}")
async def delete_platform_expert(expert_id: str, admin: dict = Depends(require_admin)):
    res = await db.platform_experts.delete_one({"expert_id": expert_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "platform expert not found")
    return {"deleted": True, "expert_id": expert_id}


@router.post("/bulk")
async def bulk_upload_platform_experts(body: BulkUpload, admin: dict = Depends(require_admin)):
    """Bulk-create platform experts. Each item is validated independently;
    rows that clash on email (or are otherwise invalid) are reported but do not
    abort the batch."""
    created: List[dict] = []
    errors: List[dict] = []
    seen_emails: set[str] = set()
    for idx, item in enumerate(body.experts):
        email = (item.email or "").strip().lower()
        if "@" not in email:
            errors.append({"index": idx, "email": item.email, "error": "invalid email"})
            continue
        if email in seen_emails:
            errors.append({"index": idx, "email": email, "error": "duplicate email within batch"})
            continue
        dup = await db.platform_experts.find_one({"email": email}, {"_id": 1})
        if dup:
            errors.append({"index": idx, "email": email, "error": "email already exists"})
            continue
        doc = await _build_doc(item, admin)
        doc["source"] = "bulk"
        await db.platform_experts.insert_one(doc)
        seen_emails.add(email)
        created.append({"expert_id": doc["expert_id"], "name": doc["name"], "email": email})
    return {"created_count": len(created), "error_count": len(errors), "created": created, "errors": errors}
