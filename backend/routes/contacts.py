"""Contact List Management with rich metadata, filters, and import capabilities."""

import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/contacts", tags=["Contact List"])

FILTERABLE_FIELDS = [
    "gender", "country", "language", "profession", "skills",
    "social_status", "relationship_status", "caste", "religion",
    "age_group", "political_party", "business_network", "organization",
]

GENDER_OPTIONS = ["male", "female", "non_binary", "prefer_not_to_say"]
AGE_GROUPS = ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"]
SOCIAL_STATUS_OPTIONS = ["student", "employed", "self_employed", "business_owner", "retired", "homemaker", "unemployed"]
RELATIONSHIP_OPTIONS = ["single", "married", "divorced", "widowed", "in_relationship", "prefer_not_to_say"]
IMPORT_SOURCES = ["manual", "email", "mobile", "whatsapp", "linkedin"]


@router.post("")
async def create_contact(request: Request, user: dict = Depends(get_current_user)):
    """Create a new contact with rich metadata."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Contact name is required")

    contact_id = f"contact_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "id": contact_id,
        "user_id": user["user_id"],
        "name": name,
        "email": body.get("email", "").strip().lower(),
        "phone": body.get("phone", "").strip(),
        "whatsapp": body.get("whatsapp", "").strip(),
        "linkedin_url": body.get("linkedin_url", "").strip(),
        # Demographics
        "gender": body.get("gender", ""),
        "age_group": body.get("age_group", ""),
        "country": body.get("country", ""),
        "state": body.get("state", ""),
        "city": body.get("city", ""),
        "language": body.get("language", ""),
        # Professional
        "profession": body.get("profession", ""),
        "skills": body.get("skills", []),  # list of strings
        "organization": body.get("organization", ""),
        "designation": body.get("designation", ""),
        "business_network": body.get("business_network", ""),
        # Social
        "social_status": body.get("social_status", ""),
        "relationship_status": body.get("relationship_status", ""),
        "caste": body.get("caste", ""),
        "religion": body.get("religion", ""),
        "political_party": body.get("political_party", ""),
        # Meta
        "tags": body.get("tags", []),  # custom user tags
        "notes": body.get("notes", ""),
        "is_sme": body.get("is_sme", False),  # Subject Matter Expert flag
        "sme_domains": body.get("sme_domains", []),
        "import_source": body.get("import_source", "manual"),
        "linked_user_id": None,  # Will be set if contact matches a platform user
        "profile_image": body.get("profile_image", ""),
        "verified": False,
        "created_at": now,
        "updated_at": now,
    }

    # Try to link to existing platform user
    if doc["email"]:
        platform_user = await db.users.find_one({"email": doc["email"]}, {"_id": 0, "user_id": 1, "name": 1})
        if platform_user:
            doc["linked_user_id"] = platform_user["user_id"]

    await db.contacts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_contacts(
    request: Request,
    user: dict = Depends(get_current_user),
    search: Optional[str] = None,
    gender: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = None,
    profession: Optional[str] = None,
    skill: Optional[str] = None,
    social_status: Optional[str] = None,
    relationship_status: Optional[str] = None,
    caste: Optional[str] = None,
    religion: Optional[str] = None,
    age_group: Optional[str] = None,
    political_party: Optional[str] = None,
    business_network: Optional[str] = None,
    organization: Optional[str] = None,
    is_sme: Optional[bool] = None,
    tag: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    """List contacts with rich filtering capabilities."""
    query = {"user_id": user["user_id"]}

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"organization": {"$regex": search, "$options": "i"}},
        ]

    if gender:
        query["gender"] = gender
    if country:
        query["country"] = {"$regex": country, "$options": "i"}
    if language:
        query["language"] = {"$regex": language, "$options": "i"}
    if profession:
        query["profession"] = {"$regex": profession, "$options": "i"}
    if skill:
        query["skills"] = {"$in": [skill]}
    if social_status:
        query["social_status"] = social_status
    if relationship_status:
        query["relationship_status"] = relationship_status
    if caste:
        query["caste"] = {"$regex": caste, "$options": "i"}
    if religion:
        query["religion"] = {"$regex": religion, "$options": "i"}
    if age_group:
        query["age_group"] = age_group
    if political_party:
        query["political_party"] = {"$regex": political_party, "$options": "i"}
    if business_network:
        query["business_network"] = {"$regex": business_network, "$options": "i"}
    if organization:
        query["organization"] = {"$regex": organization, "$options": "i"}
    if is_sme is not None:
        query["is_sme"] = is_sme
    if tag:
        query["tags"] = {"$in": [tag]}

    total = await db.contacts.count_documents(query)
    contacts = await db.contacts.find(query, {"_id": 0}).sort("name", 1).skip(skip).limit(limit).to_list(limit)

    return {"contacts": contacts, "total": total, "limit": limit, "skip": skip}


@router.get("/filter-options")
async def get_filter_options(user: dict = Depends(get_current_user)):
    """Get distinct values for all filterable fields (for populating filter dropdowns)."""
    options = {}
    for field in FILTERABLE_FIELDS:
        if field == "skills":
            pipeline = [
                {"$match": {"user_id": user["user_id"]}},
                {"$unwind": "$skills"},
                {"$group": {"_id": "$skills"}},
                {"$sort": {"_id": 1}},
                {"$limit": 100},
            ]
            result = await db.contacts.aggregate(pipeline).to_list(100)
            options[field] = [r["_id"] for r in result if r["_id"]]
        else:
            values = await db.contacts.distinct(field, {"user_id": user["user_id"]})
            options[field] = [v for v in sorted(values) if v]

    options["tags"] = await db.contacts.distinct("tags", {"user_id": user["user_id"]})
    options["tags"] = [t for t in sorted(options["tags"]) if t]

    return options


@router.get("/{contact_id}")
async def get_contact(contact_id: str, user: dict = Depends(get_current_user)):
    contact = await db.contacts.find_one({"id": contact_id, "user_id": user["user_id"]}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.put("/{contact_id}")
async def update_contact(contact_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    contact = await db.contacts.find_one({"id": contact_id, "user_id": user["user_id"]})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    allowed = [
        "name", "email", "phone", "whatsapp", "linkedin_url",
        "gender", "age_group", "country", "state", "city", "language",
        "profession", "skills", "organization", "designation", "business_network",
        "social_status", "relationship_status", "caste", "religion", "political_party",
        "tags", "notes", "is_sme", "sme_domains", "profile_image",
    ]
    update = {}
    for field in allowed:
        if field in body:
            update[field] = body[field]
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Re-check platform link if email changed
    if "email" in update and update["email"]:
        platform_user = await db.users.find_one({"email": update["email"].strip().lower()}, {"_id": 0, "user_id": 1})
        if platform_user:
            update["linked_user_id"] = platform_user["user_id"]

    await db.contacts.update_one({"id": contact_id}, {"$set": update})
    updated = await db.contacts.find_one({"id": contact_id}, {"_id": 0})
    return updated


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, user: dict = Depends(get_current_user)):
    result = await db.contacts.delete_one({"id": contact_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact deleted"}


@router.post("/import-bulk")
async def import_contacts_bulk(request: Request, user: dict = Depends(get_current_user)):
    """Bulk import contacts from various sources."""
    body = await request.json()
    contacts_data = body.get("contacts", [])
    source = body.get("source", "manual")  # email, mobile, whatsapp, linkedin, manual

    if not contacts_data:
        raise HTTPException(status_code=400, detail="No contacts to import")

    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0
    results = []

    for c in contacts_data:
        name = c.get("name", "").strip()
        email = c.get("email", "").strip().lower()
        phone = c.get("phone", "").strip()

        if not name and not email and not phone:
            skipped += 1
            continue

        # Check for duplicates
        dup_query = {"user_id": user["user_id"]}
        if email:
            dup_query["email"] = email
        elif phone:
            dup_query["phone"] = phone
        else:
            dup_query["name"] = name

        existing = await db.contacts.find_one(dup_query)
        if existing:
            skipped += 1
            continue

        contact_id = f"contact_{uuid.uuid4().hex[:12]}"
        doc = {
            "id": contact_id,
            "user_id": user["user_id"],
            "name": name or email or phone,
            "email": email,
            "phone": phone,
            "whatsapp": c.get("whatsapp", phone),
            "linkedin_url": c.get("linkedin_url", ""),
            "gender": c.get("gender", ""),
            "age_group": c.get("age_group", ""),
            "country": c.get("country", ""),
            "state": c.get("state", ""),
            "city": c.get("city", ""),
            "language": c.get("language", ""),
            "profession": c.get("profession", ""),
            "skills": c.get("skills", []),
            "organization": c.get("organization", ""),
            "designation": c.get("designation", ""),
            "business_network": c.get("business_network", ""),
            "social_status": c.get("social_status", ""),
            "relationship_status": c.get("relationship_status", ""),
            "caste": c.get("caste", ""),
            "religion": c.get("religion", ""),
            "political_party": c.get("political_party", ""),
            "tags": c.get("tags", []),
            "notes": c.get("notes", ""),
            "is_sme": c.get("is_sme", False),
            "sme_domains": c.get("sme_domains", []),
            "import_source": source,
            "linked_user_id": None,
            "profile_image": "",
            "verified": False,
            "created_at": now,
            "updated_at": now,
        }

        # Try to link
        if email:
            pu = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
            if pu:
                doc["linked_user_id"] = pu["user_id"]

        await db.contacts.insert_one(doc)
        imported += 1

    return {"imported": imported, "skipped": skipped, "total_processed": len(contacts_data)}
