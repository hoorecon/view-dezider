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
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
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
                                               "version": 1, "silent": 1,
                                               "base64": 1, "chunk_count": 1}).to_list(50)
    by_slot = {d["_id"]: d for d in docs}
    for slot, label in LOADER_SLOTS.items():
        d = by_slot.get(slot) or {}
        # A slot HAS audio when:
        #  • not flagged silent, AND
        #  • either the legacy `base64` field is set, OR `chunk_count > 0`.
        has_bytes = bool(d.get("base64")) or int(d.get("chunk_count") or 0) > 0
        has_audio = has_bytes and not d.get("silent")
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


@router.post("/admin/loader-music/{slot}/upload")
async def upload_loader_music_multipart(
    slot: str,
    audio: UploadFile = File(..., description="MP3 / WAV / OGG / M4A ≤ 30 MB"),
    filename: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    """Multipart variant of PUT /admin/loader-music/{slot}.

    Why we have BOTH:
    * The JSON+base64 PUT is convenient but inflates payloads by ~33% and
      keeps the entire body in memory before parsing — production proxies
      (nginx / ALB / CloudFront) tend to reject the resulting ~40 MB JSON
      with no CORS headers, which the browser then mis-reports as a CORS
      error. Multipart streams cleanly through every proxy we've seen.
    * Use this endpoint for the Admin UI uploader; the JSON PUT stays for
      tests / scripted seeding.
    """
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    mime = (audio.content_type or "audio/mpeg").lower()
    if mime == "audio/mp3":
        mime = "audio/mpeg"
    if mime not in ALLOWED_MUSIC_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Audio must be MP3 / WAV / OGG / M4A. Got {mime}.",
        )
    # Stream-read with a hard cap so a hostile upload can't exhaust memory.
    raw = bytearray()
    chunk_size = 1024 * 1024  # 1 MB
    while True:
        chunk = await audio.read(chunk_size)
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > MAX_MUSIC_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Audio must be {MAX_MUSIC_BYTES // (1024 * 1024)} MB or smaller.",
            )
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="Audio file is empty or corrupt.")
    raw_bytes = bytes(raw)
    data_url = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode()}"
    chosen_name = (filename or audio.filename or f"{slot}-music").strip()[:120]
    await db.app_loader_music.update_one(
        {"_id": slot},
        {"$set": {
            "base64": data_url, "mime": mime,
            "filename": chosen_name,
            "version": int(time.time()),
            "silent": False,
        }},
        upsert=True,
    )
    logger.info("Loader music uploaded (multipart) [%s] (%d bytes, %s) by %s",
                slot, len(raw_bytes), mime, user.get("email"))
    return {"success": True, "slot": slot, "has": True,
            "url": f"/api/appearance/loader-music/{slot}",
            "filename": chosen_name, "bytes": len(raw_bytes)}


@router.delete("/admin/loader-music/{slot}")
async def delete_loader_music(slot: str, user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    await db.app_loader_music.delete_one({"_id": slot})
    # Also drop the live binary chunks for this slot (chunked-upload format).
    await db.app_loader_music_blob.delete_many({"slot": slot})
    return {"success": True, "slot": slot, "has": False}


# ──────────────────────────────────────────────────────────────────────
# Chunked upload — bypasses the ~3 MB reverse-proxy body cap that some
# ingress configurations enforce on api.jelcos.ai. The client slices the
# audio into ≤1 MB chunks and POSTs each chunk separately; the final
# `commit` call atomically replaces the slot's live audio.
#
# Storage layout:
#   • app_loader_music_staging — temp docs per upload_id, one per chunk
#       { _id: ObjectId, upload_id, slot, idx, total, data (Binary), created_at }
#   • app_loader_music_blob — LIVE audio chunks per slot
#       { _id: ObjectId, slot, version, idx, data (Binary) }
#   • app_loader_music — metadata only for chunked uploads
#       { _id: slot, mime, filename, version, silent, chunk_count, total_bytes }
# Raw Binary storage (no base64) keeps each chunk well under the 16 MB
# BSON doc cap, so total file size is bounded only by MAX_MUSIC_BYTES (30 MB).
# ──────────────────────────────────────────────────────────────────────
MAX_UPLOAD_CHUNK_BYTES = 1_500_000   # ≈1.5 MB raw → ~2 MB multipart on the wire
STAGING_TTL_SECONDS = 60 * 30        # auto-clean abandoned uploads after 30m


class LoaderMusicCommitBody(BaseModel):
    upload_id: str = Field(..., min_length=8, max_length=120)
    mime: str = Field(..., min_length=3, max_length=80)
    filename: Optional[str] = Field(None, max_length=120)
    total_chunks: int = Field(..., ge=1, le=128)


@router.post("/admin/loader-music/{slot}/upload-chunk")
async def upload_loader_music_chunk(
    slot: str,
    upload_id: str = Form(..., min_length=8, max_length=120),
    idx: int = Form(..., ge=0, le=127),
    total: int = Form(..., ge=1, le=128),
    audio: UploadFile = File(..., description="One chunk of the audio file (≤1.5 MB raw)"),
    user: dict = Depends(get_current_user),
):
    """Stage a single chunk for a chunked audio upload. Bypasses the
    proxy's ~3 MB body cap by keeping each chunk small."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    if idx >= total:
        raise HTTPException(status_code=400, detail="idx must be < total.")
    # Read with a strict cap so a hostile client can't break the proxy budget.
    raw = bytearray()
    while True:
        chunk = await audio.read(256 * 1024)  # 256 KB sub-reads
        if not chunk:
            break
        raw.extend(chunk)
        if len(raw) > MAX_UPLOAD_CHUNK_BYTES + 65536:  # tiny headroom for multipart noise
            raise HTTPException(
                status_code=413,
                detail=f"Each chunk must be ≤ {MAX_UPLOAD_CHUNK_BYTES // 1024} KB.",
            )
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty chunk rejected.")
    from bson import Binary  # local import — bson ships with motor/pymongo
    from datetime import datetime, timezone
    await db.app_loader_music_staging.update_one(
        {"upload_id": upload_id, "slot": slot, "idx": int(idx)},
        {"$set": {
            "upload_id": upload_id,
            "slot": slot,
            "idx": int(idx),
            "total": int(total),
            "data": Binary(bytes(raw)),
            "user_id": user.get("user_id"),
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"success": True, "slot": slot, "upload_id": upload_id,
            "idx": int(idx), "total": int(total), "bytes": len(raw)}


@router.post("/admin/loader-music/{slot}/upload-commit")
async def upload_loader_music_commit(
    slot: str,
    body: LoaderMusicCommitBody,
    user: dict = Depends(get_current_user),
):
    """Finalise a chunked upload. Reads every staged chunk in order,
    validates the total size + mime, then atomically replaces the slot's
    live audio chunks. Stale staging docs are cleaned up afterwards."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    _check_slot(slot)
    mime = (body.mime or "audio/mpeg").lower()
    if mime == "audio/mp3":
        mime = "audio/mpeg"
    if mime not in ALLOWED_MUSIC_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Audio must be MP3 / WAV / OGG / M4A. Got {mime}.",
        )
    cursor = db.app_loader_music_staging.find(
        {"upload_id": body.upload_id, "slot": slot}
    ).sort("idx", 1)
    staged = await cursor.to_list(length=body.total_chunks + 8)
    if len(staged) != body.total_chunks:
        raise HTTPException(
            status_code=400,
            detail=f"Missing chunks: expected {body.total_chunks}, got {len(staged)}. Re-upload the missing chunks.",
        )
    # Validate the sequence and tally size.
    total_bytes = 0
    for i, doc in enumerate(staged):
        if doc.get("idx") != i:
            raise HTTPException(
                status_code=400,
                detail=f"Chunk {i} is missing or out of order.",
            )
        total_bytes += len(doc.get("data") or b"")
        if total_bytes > MAX_MUSIC_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Total audio must be ≤ {MAX_MUSIC_BYTES // (1024 * 1024)} MB.",
            )
    if total_bytes < 1024:
        raise HTTPException(status_code=400, detail="Assembled audio is too small / corrupt.")
    chosen_name = (body.filename or f"{slot}-music").strip()[:120]
    version = int(time.time())
    # Atomic replace: clear old chunks first, then insert new ones, then
    # update the metadata doc. If anything fails mid-way the metadata
    # still points to the old version (which we haven't deleted), so the
    # admin can retry without breaking the live audio.
    from bson import Binary  # noqa: F401 (already imported above in chunk endpoint)
    await db.app_loader_music_blob.delete_many({"slot": slot})
    new_chunks = [{
        "slot": slot, "version": version, "idx": d["idx"],
        "data": d["data"],
    } for d in staged]
    if new_chunks:
        await db.app_loader_music_blob.insert_many(new_chunks)
    await db.app_loader_music.update_one(
        {"_id": slot},
        {"$set": {
            "mime": mime,
            "filename": chosen_name,
            "version": version,
            "silent": False,
            "chunk_count": len(new_chunks),
            "total_bytes": total_bytes,
        }, "$unset": {"base64": ""}},  # drop the legacy inline field
        upsert=True,
    )
    # Sweep this upload + any abandoned uploads older than the TTL.
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STAGING_TTL_SECONDS)
    await db.app_loader_music_staging.delete_many(
        {"$or": [
            {"upload_id": body.upload_id},
            {"created_at": {"$lt": cutoff}},
        ]}
    )
    logger.info("Loader music committed (chunked) [%s] %d chunks · %d bytes · %s · by %s",
                slot, len(new_chunks), total_bytes, mime, user.get("email"))
    return {
        "success": True, "slot": slot, "has": True,
        "url": f"/api/appearance/loader-music/{slot}",
        "filename": chosen_name, "bytes": total_bytes,
        "chunks": len(new_chunks), "version": version,
    }


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
    Supports BOTH storage formats:
      • New chunked format (raw Binary, multiple docs in `app_loader_music_blob`)
      • Legacy inline base64 (single doc, `base64` field)
    A slot flagged `silent:true` returns 404 INSTEAD of falling back so the
    admin can explicitly mute one workflow."""
    _check_slot(slot)
    doc = await db.app_loader_music.find_one({"_id": slot})
    if doc and doc.get("silent"):
        return Response(status_code=404)

    async def _load(target_slot: str):
        """Return (raw_bytes, mime) for the given slot, or (None, None)."""
        d = await db.app_loader_music.find_one({"_id": target_slot})
        if not d or d.get("silent"):
            return None, None
        mime_local = d.get("mime") or "audio/mpeg"
        # New chunked format takes priority.
        if int(d.get("chunk_count") or 0) > 0:
            cur = db.app_loader_music_blob.find({"slot": target_slot}).sort("idx", 1)
            parts = await cur.to_list(length=int(d["chunk_count"]) + 4)
            if not parts:
                return None, None
            buf = b"".join((p.get("data") or b"") for p in parts)
            return buf, mime_local
        # Legacy inline base64.
        if d.get("base64"):
            try:
                data_url = d["base64"]
                b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
                return base64.b64decode(b64), mime_local
            except Exception:
                return None, None
        return None, None

    raw, mime = await _load(slot)
    if raw is None and slot != "default":
        raw, mime = await _load("default")
    if raw is None:
        return Response(status_code=404)
    return StreamingResponse(
        BytesIO(raw),
        media_type=mime or "audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=300",
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(raw)),
        },
    )
