"""
Faculty Module — vetted faculty directory with comprehensive CRUD operations.

A Faculty profile includes:
  • Personal / Contact Info: name, email, phone, whatsapp, address, photo_url
  • Academic Profile: department, designation, institution, qualification, experience_years
  • Expertise: specializations, subjects, languages, bio
  • Availability & Organization associations
  • Status: is_active, is_verified

Endpoints:
  • GET    /api/faculty                   — list faculty profiles (filterable by search, department, designation, institution, include_inactive)
  • GET    /api/faculty/{faculty_id}      — retrieve single faculty profile
  • POST   /api/faculty                   — create new faculty profile (authenticated / admin)
  • PUT    /api/faculty/{faculty_id}      — update existing faculty profile (authenticated / admin)
  • DELETE /api/faculty/{faculty_id}      — delete faculty profile (authenticated / admin)
  • POST   /api/faculty/bulk              — bulk upload multiple faculty profiles (authenticated / admin)
  • GET    /api/faculty/meta/departments  — list available departments and designations
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import ADMIN_ROLES, get_current_user, require_admin
from core.database import db

router = APIRouter(prefix="/faculty", tags=["Facilitators"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class FacultyOrg(BaseModel):
    org_id: Optional[str] = None
    org_name: str = Field(..., min_length=1, max_length=160)
    role: Optional[str] = Field(None, max_length=120)            # e.g. "Visiting Professor", "Head of Dept"
    contact_email: Optional[str] = Field(None, max_length=160)
    phone: Optional[str] = Field(None, max_length=40)
    department: Optional[str] = Field(None, max_length=120)
    country: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    city: Optional[str] = Field(None, max_length=80)


class FacultyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    email: str = Field(..., min_length=3, max_length=160)
    photo_url: Optional[str] = None
    department: Optional[str] = Field(None, max_length=120)      # e.g. "Computer Science", "Management"
    designation: Optional[str] = Field(None, max_length=120)    # e.g. "Professor", "Associate Professor", "Dean"
    institution: Optional[str] = Field(None, max_length=180)    # e.g. "Indian Institute of Technology", "Harvard"
    qualification: Optional[str] = Field(None, max_length=120)  # e.g. "Ph.D in AI", "M.Tech"
    experience_years: Optional[str] = Field(None, max_length=60) # e.g. "12 years", "15+"
    bio: Optional[str] = Field(None, max_length=4000)
    headline: Optional[str] = Field(None, max_length=240)
    languages: List[str] = Field(default_factory=list)
    specializations: List[str] = Field(default_factory=list)    # e.g. ["Machine Learning", "Strategic Management"]
    subjects: List[str] = Field(default_factory=list)            # e.g. ["Data Structures", "Decision Systems"]
    phone: Optional[str] = Field(None, max_length=40)
    whatsapp: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = Field(None, max_length=400)
    country: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    city: Optional[str] = Field(None, max_length=80)
    available_timings: List[str] = Field(default_factory=list)
    fees_per_min_inr: Optional[int] = Field(None, ge=0)
    organizations: List[FacultyOrg] = Field(default_factory=list)
    is_active: bool = True
    is_verified: bool = True


class FacultyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    institution: Optional[str] = None
    qualification: Optional[str] = None
    experience_years: Optional[str] = None
    bio: Optional[str] = None
    headline: Optional[str] = None
    languages: Optional[List[str]] = None
    specializations: Optional[List[str]] = None
    subjects: Optional[List[str]] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    available_timings: Optional[List[str]] = None
    fees_per_min_inr: Optional[int] = None
    organizations: Optional[List[FacultyOrg]] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class FacultyBulkUpload(BaseModel):
    faculty_list: List[FacultyCreate]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_admin(user: dict) -> bool:
    return (user.get("role") or "user").lower() in [r.lower() for r in ADMIN_ROLES] + ["admin", "super_admin", "co_admin"]


def _public(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc.pop("_id", None)
    return doc


def _build_doc(body: FacultyCreate, user: dict) -> dict:
    faculty_id = f"fac_{uuid.uuid4().hex[:12]}"
    return {
        "faculty_id": faculty_id,
        "name": body.name.strip(),
        "email": body.email.strip().lower(),
        "photo_url": body.photo_url,
        "department": body.department.strip() if body.department else None,
        "designation": body.designation.strip() if body.designation else None,
        "institution": body.institution.strip() if body.institution else None,
        "qualification": body.qualification.strip() if body.qualification else None,
        "experience_years": body.experience_years,
        "bio": body.bio,
        "headline": body.headline,
        "languages": body.languages,
        "specializations": body.specializations,
        "subjects": body.subjects,
        "phone": body.phone,
        "whatsapp": body.whatsapp,
        "address": body.address,
        "country": body.country,
        "state": body.state,
        "city": body.city,
        "available_timings": body.available_timings,
        "fees_per_min_inr": body.fees_per_min_inr,
        "organizations": [o.model_dump() for o in body.organizations],
        "rating_avg": None,
        "rating_count": 0,
        "is_active": body.is_active,
        "is_verified": body.is_verified,
        "source": "manual",
        "created_by": user.get("user_id", "admin"),
        "created_at": _now(),
        "updated_at": _now(),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def list_faculty(
    department: Optional[str] = Query(None),
    designation: Optional[str] = Query(None),
    institution: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(200, le=1000),
    user: dict = Depends(get_current_user),
):
    """List faculty profiles with optional filtering and search."""
    q: Dict[str, Any] = {}
    if not (include_inactive and _is_admin(user)):
        q["is_active"] = True

    if department:
        q["department"] = {"$regex": f"^{re.escape(department.strip())}$", "$options": "i"}
    if designation:
        q["designation"] = {"$regex": f"^{re.escape(designation.strip())}$", "$options": "i"}
    if institution:
        q["institution"] = {"$regex": re.escape(institution.strip()), "$options": "i"}

    if search:
        rx = re.escape(search.strip())
        q["$or"] = [
            {"name": {"$regex": rx, "$options": "i"}},
            {"email": {"$regex": rx, "$options": "i"}},
            {"department": {"$regex": rx, "$options": "i"}},
            {"designation": {"$regex": rx, "$options": "i"}},
            {"institution": {"$regex": rx, "$options": "i"}},
            {"specializations": {"$regex": rx, "$options": "i"}},
            {"subjects": {"$regex": rx, "$options": "i"}},
        ]

    cur = db.faculty.find(q, {"_id": 0}).sort([("name", 1)])
    items = [_public(d) for d in await cur.to_list(limit)]
    return {"items": items, "count": len(items)}


@router.get("/meta/departments")
async def list_faculty_metadata(user: dict = Depends(get_current_user)):
    """Retrieve distinct departments and designations for filter dropdowns."""
    depts = await db.faculty.distinct("department", {"is_active": True})
    desigs = await db.faculty.distinct("designation", {"is_active": True})
    institutions = await db.faculty.distinct("institution", {"is_active": True})
    return {
        "departments": [d for d in depts if d],
        "designations": [d for d in desigs if d],
        "institutions": [i for i in institutions if i],
    }


@router.get("/{faculty_id}")
async def get_faculty_detail(faculty_id: str, user: dict = Depends(get_current_user)):
    """Retrieve details of a single faculty member."""
    doc = await db.faculty.find_one({"faculty_id": faculty_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Faculty member not found")
    return _public(doc)


@router.post("")
async def create_faculty(body: FacultyCreate, user: dict = Depends(get_current_user)):
    """Create a new faculty profile (Admin or authorized user)."""
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Valid email is required")

    dup = await db.faculty.find_one({"email": email}, {"_id": 1})
    if dup:
        raise HTTPException(409, "A faculty member with this email already exists")

    doc = _build_doc(body, user)
    await db.faculty.insert_one(doc)
    return _public(doc)


@router.put("/{faculty_id}")
async def update_faculty(faculty_id: str, body: FacultyUpdate, user: dict = Depends(get_current_user)):
    """Update an existing faculty profile."""
    existing = await db.faculty.find_one({"faculty_id": faculty_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Faculty member not found")

    updates: Dict[str, Any] = {"updated_at": _now()}
    data = body.model_dump(exclude_unset=True)

    if "email" in data and data["email"]:
        new_email = data["email"].strip().lower()
        if "@" not in new_email:
            raise HTTPException(400, "Valid email is required")
        clash = await db.faculty.find_one(
            {"email": new_email, "faculty_id": {"$ne": faculty_id}}, {"_id": 1}
        )
        if clash:
            raise HTTPException(409, "Another faculty member already uses this email")
        updates["email"] = new_email
        data.pop("email")

    if "organizations" in data and data["organizations"] is not None:
        updates["organizations"] = [
            o.model_dump() if hasattr(o, "model_dump") else o for o in body.organizations
        ]
        data.pop("organizations")

    for k, v in data.items():
        updates[k] = v

    await db.faculty.update_one({"faculty_id": faculty_id}, {"$set": updates})
    updated = await db.faculty.find_one({"faculty_id": faculty_id}, {"_id": 0})
    return _public(updated)


@router.delete("/{faculty_id}")
async def delete_faculty(faculty_id: str, user: dict = Depends(get_current_user)):
    """Delete a faculty profile."""
    res = await db.faculty.delete_one({"faculty_id": faculty_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Faculty member not found")
    return {"deleted": True, "faculty_id": faculty_id}


@router.post("/bulk")
async def bulk_upload_faculty(body: FacultyBulkUpload, user: dict = Depends(get_current_user)):
    """Bulk create faculty members from list."""
    created: List[dict] = []
    errors: List[dict] = []
    seen_emails: set[str] = set()

    for idx, item in enumerate(body.faculty_list):
        email = (item.email or "").strip().lower()
        if "@" not in email:
            errors.append({"index": idx, "email": item.email, "error": "Invalid email format"})
            continue
        if email in seen_emails:
            errors.append({"index": idx, "email": email, "error": "Duplicate email within bulk batch"})
            continue

        dup = await db.faculty.find_one({"email": email}, {"_id": 1})
        if dup:
            errors.append({"index": idx, "email": email, "error": "Email already exists in directory"})
            continue

        doc = _build_doc(item, user)
        doc["source"] = "bulk"
        await db.faculty.insert_one(doc)
        seen_emails.add(email)
        created.append({"faculty_id": doc["faculty_id"], "name": doc["name"], "email": email})

    return {
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors,
    }
