"""Homepage variant selector.

Admin picks which hero design renders at jelcos.ai (guest home). Two variants
ship today: 'classic' (dark purple gradient with stock image) and 'modern'
(fwdslash.ai-inspired light theme with grid + rotating headline + chat input).

Endpoints:
  GET  /api/home-variant                        PUBLIC — current variant slug
  GET  /api/admin/home-variant                  admin — full config incl. options
  PUT  /api/admin/home-variant                  admin — set active variant
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import db
from core.auth import require_super_admin

router = APIRouter(tags=["Home Variant"])

_KEY = "homepage_variant"
_DEFAULT = "modern"
_VARIANTS: List[Dict[str, str]] = [
    {"slug": "classic", "label": "Classic Purple",
     "description": "Original dark purple gradient hero with stock image + Get started free CTA."},
    {"slug": "modern", "label": "Modern Grid (fwdslash-inspired)",
     "description": "Light graph-paper background · rotating headline word · hero chat input · trusted-by strip."},
]
_ALLOWED = {v["slug"] for v in _VARIANTS}


class VariantSet(BaseModel):
    variant: str


async def _get_active() -> str:
    row = await db.settings.find_one({"key": _KEY}, {"_id": 0, "value": 1})
    v = (row or {}).get("value") or _DEFAULT
    return v if v in _ALLOWED else _DEFAULT


@router.get("/home-variant")
async def public_active_variant():
    """Public — the guest homepage fetches this on mount to decide which hero to render."""
    return {"variant": await _get_active()}


@router.get("/admin/home-variant")
async def admin_get_variant(user: dict = Depends(require_super_admin)):
    return {"active": await _get_active(), "options": _VARIANTS}


@router.put("/admin/home-variant")
async def admin_set_variant(body: VariantSet, user: dict = Depends(require_super_admin)):
    if body.variant not in _ALLOWED:
        raise HTTPException(400, f"Unknown variant. Choose one of {sorted(_ALLOWED)}")
    await db.settings.update_one(
        {"key": _KEY},
        {"$set": {"key": _KEY, "value": body.variant,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": user.get("user_id")}},
        upsert=True,
    )
    return {"message": f"Homepage variant set to '{body.variant}'.", "active": body.variant}
