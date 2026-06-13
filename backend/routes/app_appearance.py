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
# Loader music — kept small so it streams instantly even on slow links.
# Per-slot storage in a SEPARATE collection (`app_loader_music`) so multiple
# audio files don't blow past Mongo's 16 MB doc cap when stored on the
# shared `app_settings` doc.
MAX_MUSIC_BYTES = 30 * 1024 * 1024  # 30 MB
ALLOWED_MUSIC_MIME = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
                      "audio/ogg", "audio/webm", "audio/mp4", "audio/aac"}
# Recognised loader slots. `default` is the fallback every other slot falls
# back to when empty (unless the slot is explicitly silent). Keep this list
# in sync with the frontend constant (`src/constants/loaderMusicSlots.ts`).
LOADER_SLOTS = {
    "default": "Default (fallback for any loader)",
    "deep_import": "Deep Import (multi-page crawl)",
    "url_import": "URL Import (single-page)",
    "ai_assess_all": "AI Assess All (Step 7)",
    "top5_picker": "Top-5 fetch loader (Step 5 → Step 8)",
    "mpps_pdf": "MPPS PDF generation (Step 9)",
    "results_reveal": "Final Decision reveal (Step 8 / 10)",
}

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
        # Loader music — multi-slot map. `default` is the fallback for any
        # slot that has no audio uploaded AND is not explicitly silenced.
        # Backward-compat single-slot fields (`has_loader_music`,
        # `loader_music_url`, ...) still point at the `default` slot so older
        # clients keep working.
        "loader_music_slots": await _loader_music_slots_summary(),
        "loader_music_volume": await _loader_music_volume_map(),
        **(await _legacy_loader_music_compat()),
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


async def _loader_music_volume_map() -> dict:
    """Read per-platform default volume (0..1) from the AI Wallet config so
    admins can tune them without redeploying the app. Falls back to safe
    defaults when the key is missing."""
    try:
        from core import ai_wallet
        cfg = await ai_wallet.get_config()
    except Exception:
        cfg = {}
    def clamp(v, default):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, v))
    return {
        "web": clamp(cfg.get("loader_music_volume_web"), 0.55),
        "android": clamp(cfg.get("loader_music_volume_android"), 0.75),
        "ios": clamp(cfg.get("loader_music_volume_ios"), 0.65),
    }


async def _loader_music_slots_summary() -> dict:
    """Return a dict of slot_name → {has, url, filename, version, silent}.
    Always includes every key in LOADER_SLOTS so the client can render the
    full Admin UI even before any audio has been uploaded."""
    out: dict = {}
    docs = await db.app_loader_music.find({}, {"_id": 1, "filename": 1,
                                               "version": 1, "silent": 1}).to_list(50)
    by_slot = {d["_id"]: d for d in docs}
    for slot, label in LOADER_SLOTS.items():
        d = by_slot.get(slot) or {}
        # An "uploaded" doc exists when the slot has audio bytes; the row
        # might also exist with just `silent: true` and no audio.
        has_audio = bool(d) and not d.get("silent")
        out[slot] = {
            "label": label,
            "has": has_audio,
            "silent": bool(d.get("silent")),
            "url": f"/api/appearance/loader-music/{slot}" if has_audio else None,
            "filename": d.get("filename") if has_audio else None,
            "version": int(d.get("version") or 0),
        }
    return out


async def _legacy_loader_music_compat() -> dict:
    """Keep the older `has_loader_music` / `loader_music_url` fields working
    for callers that haven't been migrated to the slot-aware payload yet.
    Always points at the `default` slot."""
    default = await db.app_loader_music.find_one({"_id": "default"},
                                                  {"_id": 0, "filename": 1, "version": 1, "silent": 1}) or {}
    has = bool(default) and not default.get("silent")
    return {
        "has_loader_music": has,
        "loader_music_url": "/api/appearance/loader-music/default" if has else None,
        "loader_music_version": int(default.get("version") or 0),
        "loader_music_filename": default.get("filename") if has else None,
    }


# ───────────────────────── Loader music (Deep Import & long crawls) ─────
class LoaderMusicUpdate(BaseModel):
    music_base64: str = Field(..., min_length=10)
    filename: Optional[str] = Field(None, max_length=120)


class LoaderMusicSilent(BaseModel):
    silent: bool = True


def _parse_music(data_url: str):
    """Return (raw_bytes, mime) from an audio data URL or raise HTTPException."""
    s = (data_url or "").strip()
    mime = "audio/mpeg"
    if s.startswith("data:"):
        try:
            header, b64 = s.split(",", 1)
            mime = header.split(";")[0].replace("data:", "").lower() or "audio/mpeg"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid audio data.")
    else:
        b64 = s
    if mime == "audio/mp3":
        mime = "audio/mpeg"
    if mime not in ALLOWED_MUSIC_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Audio must be MP3 / WAV / OGG / M4A. Got {mime}.",
        )
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid audio encoding.")
    if len(raw) > MAX_MUSIC_BYTES:
        raise HTTPException(status_code=400,
                            detail=f"Audio must be {MAX_MUSIC_BYTES // (1024 * 1024)} MB or smaller.")
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="Audio file is empty or corrupt.")
    return raw, mime


def _check_slot(slot: str) -> str:
    if slot not in LOADER_SLOTS:
        raise HTTPException(status_code=404, detail=f"Unknown loader slot '{slot}'.")
    return slot


@router.put("/admin/loader-music/{slot}")
async def update_loader_music(slot: str, body: LoaderMusicUpdate,
                              user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    raw, mime = _parse_music(body.music_base64)
    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    await db.app_loader_music.update_one(
        {"_id": slot},
        {"$set": {
            "base64": data_url, "mime": mime,
            "filename": (body.filename or f"{slot}-music").strip()[:120],
            "version": int(time.time()),
            "silent": False,
        }},
        upsert=True,
    )
    logger.info("Loader music updated [%s] (%d bytes, %s) by %s",
                slot, len(raw), mime, user.get("email"))
    return {"success": True, "slot": slot, "has": True,
            "url": f"/api/appearance/loader-music/{slot}",
            "filename": body.filename}


@router.delete("/admin/loader-music/{slot}")
async def delete_loader_music(slot: str, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    await db.app_loader_music.delete_one({"_id": slot})
    return {"success": True, "slot": slot, "has": False}


@router.put("/admin/loader-music/{slot}/silent")
async def set_loader_music_silent(slot: str, body: LoaderMusicSilent,
                                  user: dict = Depends(get_current_user)):
    """Mark a slot as EXPLICITLY silent — no fallback to `default`. Useful
    when the user wants Deep Import muted but other loaders to keep using
    the default soundtrack."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    await db.app_loader_music.update_one(
        {"_id": slot},
        {"$set": {"silent": bool(body.silent), "version": int(time.time())}},
        upsert=True,
    )
    return {"success": True, "slot": slot, "silent": bool(body.silent)}


@router.get("/appearance/loader-music/{slot}")
async def serve_loader_music(slot: str):
    """Stream a slot's audio with auto-fallback to `default` when empty.
    A slot flagged `silent:true` returns 404 INSTEAD of falling back so the
    admin can explicitly mute one workflow."""
    _check_slot(slot)
    doc = await db.app_loader_music.find_one({"_id": slot})
    if doc and doc.get("silent"):
        return Response(status_code=404)
    if not doc or not doc.get("base64"):
        if slot == "default":
            return Response(status_code=404)
        # Fall back to default audio.
        doc = await db.app_loader_music.find_one({"_id": "default"})
        if not doc or doc.get("silent") or not doc.get("base64"):
            return Response(status_code=404)
    mime = doc.get("mime") or "audio/mpeg"
    try:
        data_url = doc["base64"]
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        raw = base64.b64decode(b64)
    except Exception:
        return Response(status_code=404)
    return StreamingResponse(
        BytesIO(raw),
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=300",
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(raw)),
        },
    )
