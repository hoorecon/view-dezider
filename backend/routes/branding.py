"""
Branding routes — exposes the active edition's brand surface to the frontend.

Endpoints:
  GET /api/branding/current      — public; called by frontend on app boot
  GET /api/branding/editions     — super-admin only; lists all known editions
  POST /api/branding/me/edition  — set current user's home edition (auth required)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.branding import (
    get_active_edition, get_brand_config, list_editions, EDITIONS,
    MASTER_BRAND_NAME, MASTER_BRAND_TAGLINE, LEGAL_ENTITY,
)
from core.database import db
from core.auth import get_current_user, require_admin

router = APIRouter(prefix="/branding", tags=["Branding"])


@router.get("/current")
async def current_branding():
    """Public endpoint — frontend hydrates the active edition's brand surface on boot.
    No auth required so the splash / login screen can render before user signs in.
    """
    cfg = get_brand_config()
    return {
        "ok": True,
        "active_edition": get_active_edition(),
        "branding": cfg.as_dict(),
        "master": {
            "name": MASTER_BRAND_NAME,
            "tagline": MASTER_BRAND_TAGLINE,
        },
        "legal_entity": LEGAL_ENTITY,
    }


@router.get("/editions")
async def all_editions(user: dict = Depends(require_admin)):
    """Super-admin only — list every registered edition."""
    return {"editions": list_editions(), "active": get_active_edition()}


class SetEditionBody(BaseModel):
    edition: str


@router.post("/me/edition")
async def set_my_home_edition(body: SetEditionBody, user: dict = Depends(get_current_user)):
    """User picks/changes their home edition. Stored on the user record so
    Super Admin can filter views per edition.
    """
    edition = (body.edition or "").lower()
    if edition not in EDITIONS:
        raise HTTPException(400, f"unknown edition '{edition}'. valid: {list(EDITIONS.keys())}")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"product_edition": edition}},
    )
    return {"ok": True, "product_edition": edition}
