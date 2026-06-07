"""Admin routes — setup, role promotion/demotion, admin user list, template
authorization (approve/revoke).
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import (
    get_current_user, require_admin, require_root_super_admin,
    get_user_role, get_role_level, ROOT_SUPER_ADMIN_EMAIL,
)
from models.decisions_models import PromoteUserRequest, DemoteUserRequest

router = APIRouter(tags=["Decisions"])


@router.post("/admin/setup")
async def admin_setup(user: dict = Depends(get_current_user)):
    # SECURITY: Only the designated root super-admin email may ever claim
    # super_admin via setup. This blocks self-elevation by any other user.
    email = (user.get("email") or "").strip().lower()
    if email != ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only the root super-admin may perform setup")
    existing_super = await db.users.find_one({"role": "super_admin"}, {"_id": 0})
    if existing_super and (existing_super.get("email") or "").strip().lower() != ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Super Admin already exists")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"role": "super_admin"}})
    return {"message": "You are now Super Admin", "role": "super_admin"}


@router.post("/admin/promote")
async def promote_user(data: PromoteUserRequest, user: dict = Depends(require_root_super_admin)):
    promoter_role = get_user_role(user)
    promoter_level = get_role_level(promoter_role)
    target_role = data.role
    target_level = get_role_level(target_role)
    if target_role not in ("admin", "co_admin"):
        raise HTTPException(status_code=400, detail="Can only promote to 'admin' or 'co_admin'")
    if target_role == "co_admin" and promoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can create Co-Admins")
    if target_role == "admin" and promoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can promote to Admin")
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    current_target_level = get_role_level(get_user_role(target_user))
    if current_target_level >= target_level:
        raise HTTPException(status_code=400, detail=f"User already has role '{get_user_role(target_user)}'")
    await db.users.update_one({"email": data.email.lower()}, {"$set": {"role": target_role}})
    return {"message": f"User {data.email} promoted to {target_role}"}


@router.post("/admin/demote")
async def demote_user(data: DemoteUserRequest, user: dict = Depends(require_root_super_admin)):
    demoter_role = get_user_role(user)
    demoter_level = get_role_level(demoter_role)
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    target_role = get_user_role(target_user)
    # The root super-admin can never be demoted via API (checked first).
    if (target_user.get("email") or "").strip().lower() == ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Root super-admin cannot be demoted")
    if target_user["user_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    if target_role == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin cannot be demoted")
    if target_role == "co_admin" and demoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can demote Co-Admins")
    if target_role == "admin" and demoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can demote Admins")
    await db.users.update_one({"email": data.email.lower()}, {"$set": {"role": "user"}})
    return {"message": f"User {data.email} demoted to regular user"}


@router.get("/admin/users")
async def get_admin_users(user: dict = Depends(require_admin)):
    admin_users = await db.users.find({"role": {"$in": ["super_admin", "co_admin", "admin"]}}, {"_id": 0, "password_hash": 0}).to_list(100)
    return admin_users


@router.post("/admin/templates/{template_id}/approve")
async def approve_admin_template(template_id: str, user: dict = Depends(require_admin)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("visibility") != "public":
        raise HTTPException(status_code=400, detail="Only public templates can be authorized")
    await db.templates.update_one({"id": template_id}, {"$set": {
        "authorized": True, "authorized_by": user["user_id"],
        "authorized_by_name": user.get("name", "Unknown"), "authorized_at": datetime.now(timezone.utc),
    }})
    return {"message": "Template authorized successfully"}


@router.post("/admin/templates/{template_id}/revoke")
async def revoke_admin_template(template_id: str, user: dict = Depends(require_admin)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.templates.update_one({"id": template_id}, {"$set": {
        "authorized": False, "authorized_by": None, "authorized_by_name": None, "authorized_at": None,
    }})
    return {"message": "Template authorization revoked"}
