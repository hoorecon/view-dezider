"""Organization routes — Multi-tenant SaaS: create, get, update, members, roles"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import (
    get_current_user, get_user_role, get_role_level,
    get_org_role_level, ORG_ROLE_HIERARCHY, ORG_ADMIN_ROLES,
)

router = APIRouter(tags=["Organizations"])


@router.post("/organizations")
async def create_organization(request: Request, user: dict = Depends(get_current_user)):
    """Create a new organization"""
    body = await request.json()
    name = body.get("name", "").strip()
    slug = body.get("slug", "").strip().lower().replace(" ", "-")
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Name and slug are required")
    existing = await db.organizations.find_one({"slug": slug})
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already taken")
    org_doc = {
        "id": str(uuid.uuid4()),
        "name": name,
        "slug": slug,
        "org_type": body.get("org_type", "BUSINESS").upper(),
        "logo_url": body.get("logo_url", ""),
        "primary_color": body.get("primary_color", "#6C63FF"),
        "accent_color": body.get("accent_color", "#FF6584"),
        "tagline": body.get("tagline", ""),
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.organizations.insert_one(org_doc)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"org_id": org_doc["id"], "org_role": "org_super_admin"}}
    )
    return {"id": org_doc["id"], "slug": slug, "message": "Organization created"}


@router.get("/organizations/{slug}")
async def get_organization_by_slug(slug: str):
    """Get organization branding by slug (public endpoint)"""
    org = await db.organizations.find_one({"slug": slug}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "id": org["id"], "name": org["name"], "slug": org["slug"],
        "org_type": org.get("org_type", "BUSINESS"),
        "logo_url": org.get("logo_url", ""),
        "primary_color": org.get("primary_color", "#6C63FF"),
        "accent_color": org.get("accent_color", "#FF6584"),
        "tagline": org.get("tagline", ""),
    }


@router.put("/organizations/{org_id}")
async def update_organization(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update organization branding (org_admin+ or global admin)"""
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if user_doc.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    org_role = user_doc.get("org_role", "org_member")
    global_role = get_user_role(user_doc)
    if get_org_role_level(org_role) < 1 and get_role_level(global_role) < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")
    body = await request.json()
    update_fields = {k: v for k, v in body.items() if k in ["name", "logo_url", "primary_color", "accent_color", "tagline"]}
    if update_fields:
        await db.organizations.update_one({"id": org_id}, {"$set": update_fields})
    return {"message": "Organization updated"}


@router.get("/organizations/{org_id}/members")
async def get_org_members(org_id: str, user: dict = Depends(get_current_user)):
    """Get members of an organization with org roles"""
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if user_doc.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    members = await db.users.find({"org_id": org_id}, {"_id": 0, "password_hash": 0}).to_list(200)
    for m in members:
        if not m.get("org_role"):
            org = await db.organizations.find_one({"id": org_id})
            if org and m.get("user_id") == org.get("created_by"):
                m["org_role"] = "org_super_admin"
                await db.users.update_one({"user_id": m["user_id"]}, {"$set": {"org_role": "org_super_admin"}})
            else:
                m["org_role"] = "org_member"
    return members


@router.put("/organizations/{org_id}/members/{target_user_id}/role")
async def update_org_member_role(org_id: str, target_user_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Promote/demote org member role"""
    promoter = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if promoter.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    promoter_org_role = promoter.get("org_role", "org_member")
    promoter_level = get_org_role_level(promoter_org_role)
    if promoter_level < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")
    target = await db.users.find_one({"user_id": target_user_id, "org_id": org_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this organization")
    body = await request.json()
    new_role = body.get("org_role", "").strip()
    if new_role not in ORG_ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid org role. Must be one of: {list(ORG_ROLE_HIERARCHY.keys())}")
    new_role_level = get_org_role_level(new_role)
    target_current_level = get_org_role_level(target.get("org_role", "org_member"))
    if target_user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own org role")
    if new_role_level >= promoter_level:
        raise HTTPException(status_code=403, detail="Cannot promote to a role equal or higher than your own")
    if target_current_level >= promoter_level:
        raise HTTPException(status_code=403, detail="Cannot modify a user with equal or higher org role")
    if new_role == "org_co_admin" and promoter_org_role != "org_super_admin":
        raise HTTPException(status_code=403, detail="Only Org Super Admin can assign Org Co-Admin role")
    await db.users.update_one({"user_id": target_user_id}, {"$set": {"org_role": new_role}})
    return {"message": f"User org role updated to {new_role}"}


@router.delete("/organizations/{org_id}/members/{target_user_id}")
async def remove_org_member(org_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    """Remove a member from the organization"""
    remover = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if remover.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    remover_level = get_org_role_level(remover.get("org_role", "org_member"))
    if remover_level < 1:
        raise HTTPException(status_code=403, detail="Org Admin access required")
    target = await db.users.find_one({"user_id": target_user_id, "org_id": org_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this organization")
    if target_user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself from the organization")
    target_level = get_org_role_level(target.get("org_role", "org_member"))
    if target_level >= remover_level:
        raise HTTPException(status_code=403, detail="Cannot remove a user with equal or higher org role")
    await db.users.update_one(
        {"user_id": target_user_id},
        {"$set": {"org_id": None, "org_role": None}}
    )
    return {"message": "Member removed from organization"}
