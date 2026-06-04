"""
App appearance configuration — centrally-managed UI font family.

Stored as a single document in `app_settings` (_key='appearance'). The font
family is chosen by an admin and applied app-wide (web + native) by the
frontend FontFamilyProvider. Default is "Inter" (matches jelcos.ai).
"""
import logging
import base64
import binascii
import time
from io import BytesIO
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger("appearance")
router = APIRouter(tags=["Appearance"])

APPEARANCE_KEY = "appearance"
DEFAULT_FONT = "Inter"
DEFAULT_BRAND_NAME = "JELCOS AI"
DEFAULT_TAGLINE = "Joyful Executive's Life Choices Operating System — Powered by AI"
DEFAULT_COMPANY_NAME = "HOORECON IT-Sys Pvt Ltd"  # legal entity name
DEFAULT_ADDRESS = (
    "Innov8 Millenia, 2nd Floor, East Wing, RMZ,\n"
    "Millennia Business Park, Campus 1A, No. 143,\n"
    "MGR Road (North Veeranam Salai), Perungudi,\n"
    "Sholinganallur, Chennai-600096, Tamil Nadu, India."
)
DEFAULT_PHONE = "+(91)-(0)44-46972104"
DEFAULT_EMAIL = "admin@hoorecon.com"
DEFAULT_WEBSITE = "www.hoorecon.com"
DEFAULT_SUPPORT_HOURS = "Monday–Friday, 10:00 AM – 6:00 PM IST"
MAX_LOGO_BYTES = 1024 * 1024  # 1 MB
ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/jpg"}

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
        # Company / contact profile (Admin-configurable)
        "brand_name": doc.get("brand_name") or DEFAULT_BRAND_NAME,
        "tagline": doc.get("tagline") or DEFAULT_TAGLINE,
        "legal_name": doc.get("company_name") or DEFAULT_COMPANY_NAME,
        "address": doc.get("address") or DEFAULT_ADDRESS,
        "phone": doc.get("phone") or DEFAULT_PHONE,
        "email": doc.get("email") or DEFAULT_EMAIL,
        "website": doc.get("website") or DEFAULT_WEBSITE,
        "support_hours": doc.get("support_hours") or DEFAULT_SUPPORT_HOURS,
        "has_logo": bool(doc.get("logo_base64")),
        "logo_url": "/api/appearance/logo" if doc.get("logo_base64") else None,
        "logo_version": int(doc.get("logo_version") or 0),
    }


class CompanyInfoUpdate(BaseModel):
    brand_name: Optional[str] = Field(default=None, max_length=120)
    tagline: Optional[str] = Field(default=None, max_length=240)
    legal_name: Optional[str] = Field(default=None, max_length=160)
    address: Optional[str] = Field(default=None, max_length=600)
    phone: Optional[str] = Field(default=None, max_length=60)
    email: Optional[str] = Field(default=None, max_length=120)
    website: Optional[str] = Field(default=None, max_length=160)
    support_hours: Optional[str] = Field(default=None, max_length=160)


@router.put("/admin/company-info")
async def update_company_info(body: CompanyInfoUpdate, user: dict = Depends(get_current_user)):
    """Super-admin only: update the company/contact profile shown on the
    Contact page, all legal/policy pages, footer and PII-access NDA."""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required.")
    set_doc: dict = {"key": APPEARANCE_KEY}
    # `legal_name` is stored under the legacy `company_name` field so existing
    # consumers (footer, NDA) keep working without migration.
    if body.legal_name is not None:
        set_doc["company_name"] = body.legal_name.strip()
    for field in ("brand_name", "tagline", "address", "phone", "email", "website", "support_hours"):
        val = getattr(body, field)
        if val is not None:
            set_doc[field] = val.strip()
    await db.app_settings.update_one(
        {"key": APPEARANCE_KEY}, {"$set": set_doc}, upsert=True
    )
    logger.info("Company info updated (%s) by %s", list(set_doc.keys()), user.get("email"))
    return {"success": True, "updated": [k for k in set_doc if k != "key"]}


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


# ───────────────────────── Logo ─────────────────────────
class LogoUpdate(BaseModel):
    logo_base64: str = Field(..., min_length=10)


def _parse_logo(data_url: str):
    """Return (raw_bytes, mime) from a data URL or raise HTTPException."""
    s = (data_url or "").strip()
    mime = "image/png"
    if s.startswith("data:"):
        try:
            header, b64 = s.split(",", 1)
            mime = header.split(";")[0].replace("data:", "").lower() or "image/png"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid image data.")
    else:
        b64 = s
    if mime not in ALLOWED_LOGO_MIME:
        raise HTTPException(status_code=400, detail="Logo must be a PNG or JPG image.")
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image encoding.")
    if len(raw) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo must be 1 MB or smaller.")
    if len(raw) < 50:
        raise HTTPException(status_code=400, detail="Image is empty or corrupt.")
    return raw, ("image/jpeg" if mime == "image/jpg" else mime)


async def get_app_logo() -> Optional[str]:
    """Return the stored logo as a data URL, or None. Used by PDF rendering."""
    doc = await _get_doc()
    return doc.get("logo_base64")


@router.put("/admin/logo")
async def update_logo(body: LogoUpdate, user: dict = Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required.")
    raw, mime = _parse_logo(body.logo_base64)
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    await db.app_settings.update_one(
        {"key": APPEARANCE_KEY},
        {"$set": {
            "key": APPEARANCE_KEY,
            "logo_base64": data_url,
            "logo_mime": mime,
            "logo_version": int(time.time()),
        }},
        upsert=True,
    )
    logger.info("Logo updated (%d bytes, %s) by %s", len(raw), mime, user.get("email"))
    return {"success": True, "has_logo": True, "logo_url": "/api/appearance/logo"}


@router.delete("/admin/logo")
async def delete_logo(user: dict = Depends(get_current_user)):
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required.")
    await db.app_settings.update_one(
        {"key": APPEARANCE_KEY},
        {"$unset": {"logo_base64": "", "logo_mime": ""}, "$set": {"logo_version": int(time.time())}},
        upsert=True,
    )
    return {"success": True, "has_logo": False}


@router.get("/appearance/logo")
async def serve_logo():
    """Serve the raw logo image (cacheable). 404 when no logo is configured."""
    doc = await _get_doc()
    data_url = doc.get("logo_base64")
    if not data_url:
        return Response(status_code=404)
    mime = doc.get("logo_mime") or "image/png"
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(b64)
    except Exception:
        return Response(status_code=404)
    return StreamingResponse(
        BytesIO(raw),
        media_type=mime,
        headers={"Cache-Control": "public, max-age=300"},
    )
