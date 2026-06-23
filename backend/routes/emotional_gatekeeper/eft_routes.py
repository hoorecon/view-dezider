"""
Emotional Gatekeeper — EFT Tapping for Stress Relief

A gentle, deterministic (no-AI) guided EFT tapping flow. Stores per-session
reflections in db.eft_reflections and exposes an admin-configurable content
config (title, affirmation templates, tapping points, diagram/video media,
disclaimer, safety keywords) stored in app_config {key: "eft_config"}.
"""

import os
import uuid
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response

from core.database import db
from core.auth import require_admin
from routes.auth_routes import get_current_user

from .models import EFTSaveRequest, EFTConfigRequest
from .constants import EFT_DEFAULTS

logger = logging.getLogger(__name__)
router = APIRouter()

# Persistent static media directory (served at /api/static/eft/<file>).
_STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "eft"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_VIDEO = {"video/mp4", "video/webm", "video/quicktime", "video/ogg"}
_MAX_UPLOAD_MB = 50


async def _load_config() -> dict:
    """Merge stored admin overrides over the built-in defaults."""
    cfg = dict(EFT_DEFAULTS)
    stored = await db.app_config.find_one({"key": "eft_config"}, {"_id": 0})
    if stored and isinstance(stored.get("value"), dict):
        for k, v in stored["value"].items():
            if v is not None:
                cfg[k] = v
    # Auto-heal legacy diagram images that were written to ephemeral disk
    # (static/eft/<file>) and lost on redeploy → fall back to the default
    # diagram so the screen is never blank. New uploads use DB-backed
    # /api/emotional-gatekeeper/eft/media/<id> which always persists.
    diag = str(cfg.get("diagram_image_url") or "")
    if diag.startswith("/api/static/eft/"):
        fname = diag.rsplit("/", 1)[-1]
        if not (_STATIC_DIR / fname).exists():
            cfg["diagram_image_url"] = EFT_DEFAULTS["diagram_image_url"]
    return cfg


# ============ CONFIG (user-facing) ============

@router.get("/eft/config")
async def get_eft_config(user: dict = Depends(get_current_user)):
    """Public-to-authenticated config used by the EFT tapping screen."""
    return await _load_config()


# ============ SAVE SESSION ============

@router.post("/eft/{session_id}/save")
async def save_eft_session(session_id: str, data: EFTSaveRequest, user: dict = Depends(get_current_user)):
    """Persist an EFT tapping session/round and mark the session completed."""
    session = await db.breakthrough_sessions.find_one(
        {"id": session_id, "user_id": user["user_id"]}
    )
    if not session:
        raise HTTPException(404, "Session not found")

    if data.selected_type not in ("emotion", "problem"):
        raise HTTPException(400, "selected_type must be 'emotion' or 'problem'")
    if not (data.subject_text or "").strip():
        raise HTTPException(400, "Please enter the emotion or problem.")
    if data.initial_intensity_score is None or not (0 <= data.initial_intensity_score <= 10):
        raise HTTPException(400, "initial_intensity_score must be between 0 and 10.")
    if data.final_intensity_score is not None and not (0 <= data.final_intensity_score <= 10):
        raise HTTPException(400, "final_intensity_score must be between 0 and 10.")

    reduction = None
    if data.final_intensity_score is not None:
        reduction = data.initial_intensity_score - data.final_intensity_score

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": f"EFT-{uuid.uuid4().hex[:8].upper()}",
        "session_id": session_id,
        "user_id": user["user_id"],
        "selected_type": data.selected_type,
        "subject_text": data.subject_text.strip()[:300],
        "affirmation": (data.affirmation or "").strip(),
        "initial_intensity_score": data.initial_intensity_score,
        "final_intensity_score": data.final_intensity_score,
        "intensity_reduction": reduction,
        "rounds_completed": max(1, data.rounds_completed or 1),
        "user_reflection": (data.user_reflection or "").strip()[:500] or None,
        "safety_flagged": bool(data.safety_flagged),
        "created_at": now,
        "updated_at": now,
    }
    await db.eft_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc},
        upsert=True,
    )

    # Mirror intensity onto the session + mark completed once a round is done.
    session_update = {
        "intensity_before": data.initial_intensity_score,
        "updated_at": now,
    }
    if data.final_intensity_score is not None:
        session_update["intensity_after"] = data.final_intensity_score
        session_update["status"] = "completed"
    else:
        session_update["status"] = "in_progress"
    # Give the session a meaningful title from the subject.
    session_update["title"] = f"EFT — {doc['subject_text'][:40]}"
    await db.breakthrough_sessions.update_one({"id": session_id}, {"$set": session_update})

    doc.pop("_id", None)
    return doc


# ============ ADMIN CONFIG ============

@router.get("/eft/admin/config")
async def admin_get_eft_config(user: dict = Depends(require_admin)):
    """Full effective config + defaults (for reset)."""
    cfg = await _load_config()
    return {"config": cfg, "defaults": EFT_DEFAULTS}


@router.put("/eft/admin/config")
async def admin_put_eft_config(data: EFTConfigRequest, user: dict = Depends(require_admin)):
    """Upsert admin overrides. Only provided (non-null) fields are stored."""
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields provided to update.")

    now = datetime.now(timezone.utc).isoformat()
    existing = await db.app_config.find_one({"key": "eft_config"}, {"_id": 0})
    merged = dict(existing.get("value", {})) if existing else {}
    merged.update(payload)

    await db.app_config.update_one(
        {"key": "eft_config"},
        {"$set": {"key": "eft_config", "value": merged, "updated_at": now,
                  "updated_by": user["user_id"]}},
        upsert=True,
    )
    return await _load_config()


@router.post("/eft/admin/upload-media")
async def admin_upload_eft_media(
    media_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload a diagram image or instruction video; returns its served URL.

    media_type: "image" | "video". The returned URL can be saved into the
    config (diagram_image_url / video_url) via PUT /eft/admin/config.
    """
    if media_type not in ("image", "video"):
        raise HTTPException(400, "media_type must be 'image' or 'video'")

    content_type = (file.content_type or "").lower()
    allowed = _ALLOWED_IMAGE if media_type == "image" else _ALLOWED_VIDEO
    if content_type not in allowed:
        raise HTTPException(400, f"Unsupported {media_type} type: {content_type or 'unknown'}. Allowed: {sorted(allowed)}")

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > _MAX_UPLOAD_MB:
        raise HTTPException(400, f"File too large ({size_mb:.1f} MB). Max {_MAX_UPLOAD_MB} MB.")

    ext = os.path.splitext(file.filename or "")[1].lower() or (
        ".jpg" if media_type == "image" else ".mp4"
    )
    media_id = f"{media_type}_{uuid.uuid4().hex[:12]}"

    # Persist in MongoDB (survives redeploys / multi-replica scaling) instead of
    # writing to ephemeral container disk under static/eft/ which gets wiped.
    await db.eft_media.update_one(
        {"id": media_id},
        {"$set": {
            "id": media_id,
            "media_type": media_type,
            "content_type": content_type,
            "ext": ext,
            "data_b64": base64.b64encode(data).decode("ascii"),
            "size_bytes": len(data),
            "uploaded_by": user["user_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    url = f"/api/emotional-gatekeeper/eft/media/{media_id}"
    return {"url": url, "media_type": media_type, "size_mb": round(size_mb, 2)}


@router.get("/eft/media/{media_id}")
async def get_eft_media(media_id: str):
    """Serve an uploaded EFT image/video from MongoDB (persistent across deploys)."""
    doc = await db.eft_media.find_one({"id": media_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Media not found")
    try:
        raw = base64.b64decode(doc["data_b64"])
    except Exception:
        raise HTTPException(500, "Corrupt media")
    return Response(
        content=raw,
        media_type=doc.get("content_type") or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )
