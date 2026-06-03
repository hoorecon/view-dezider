"""
App appearance configuration — centrally-managed UI font family.

Stored as a single document in `app_settings` (_key='appearance'). The font
family is chosen by an admin and applied app-wide (web + native) by the
frontend FontFamilyProvider. Default is "Inter" (matches jelcos.ai).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger("appearance")
router = APIRouter(tags=["Appearance"])

APPEARANCE_KEY = "appearance"
DEFAULT_FONT = "Inter"
DEFAULT_COMPANY_NAME = "HOORECON IT-Sys Pvt Ltd"

# Allow-list of selectable fonts (Google Fonts + System). Keep in sync with the
# frontend FONT_OPTIONS list in src/constants/fonts.ts.
ALLOWED_FONTS = [
    "System",
    "Inter",
    "Roboto",
    "Poppins",
    "Plus Jakarta Sans",
    "Hind",
    "Noto Sans Devanagari",
    "JetBrains Mono",
]


class AppearanceUpdate(BaseModel):
    font_family: str = Field(..., min_length=1, max_length=60)


class CompanyNameUpdate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=120)


async def _get_doc() -> dict:
    # `key` (NOT `_key`) — the app_settings collection has a unique index on
    # `key:1` (see core/db_indices.py). Using `_key` would leave `key:null`
    # and collide with any other settings doc that also lacks `key` (e.g.
    # payments_global), surfacing as a 500 DuplicateKeyError on upsert.
    doc = await db.app_settings.find_one({"key": APPEARANCE_KEY}, {"_id": 0}) or {}
    return doc


@router.get("/appearance")
async def get_appearance():
    """Public: the current app-wide font family + company name + options."""
    doc = await _get_doc()
    font = doc.get("font_family") or DEFAULT_FONT
    if font not in ALLOWED_FONTS:
        font = DEFAULT_FONT
    return {
        "font_family": font,
        "font_options": ALLOWED_FONTS,
        "default_font": DEFAULT_FONT,
        "company_name": doc.get("company_name") or DEFAULT_COMPANY_NAME,
    }


@router.put("/admin/company-name")
async def update_company_name(body: CompanyNameUpdate, user: dict = Depends(get_current_user)):
    """Super-admin only: centrally update the legal company name used across
    legal pages, footer and the PII-access NDA."""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required.")
    name = body.company_name.strip()
    await db.app_settings.update_one(
        {"key": APPEARANCE_KEY},
        {"$set": {"key": APPEARANCE_KEY, "company_name": name}},
        upsert=True,
    )
    logger.info("Company name set to %r by %s", name, user.get("email"))
    return {"success": True, "company_name": name}


@router.put("/admin/appearance")
async def update_appearance(body: AppearanceUpdate, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    if body.font_family not in ALLOWED_FONTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported font. Choose one of: {', '.join(ALLOWED_FONTS)}",
        )
    await db.app_settings.update_one(
        {"key": APPEARANCE_KEY},
        {"$set": {"key": APPEARANCE_KEY, "font_family": body.font_family}},
        upsert=True,
    )
    logger.info("App font set to %s by %s", body.font_family, user.get("email"))
    return {"success": True, "font_family": body.font_family}
