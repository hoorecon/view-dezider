"""
Meditation Settings — User-level customizable meditation URLs & file uploads
Supports 3 meditation slots: guru_invocation, stillness_meditation, goal_manifestation
Each slot can be: default URL, custom URL, or uploaded MP3 file.
"""
import os
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/meditation-settings", tags=["Meditation Settings"])

# Persistent upload directory
UPLOAD_DIR = "/app/backend/uploads/meditations"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# DEFAULT MEDITATION URLS
# ═══════════════════════════════════════════════════════════════

MEDITATION_DEFAULTS = {
    "guru_invocation": {
        "id": "guru_invocation",
        "name": "Guru Invocation",
        "description": "Invoke the blessings of all your Gurus — Guru Paduka Stotram",
        "default_url": "https://isha.sadhguru.org/in/en/blog/article/mystic-chants-guru-paduka-stotram",
        "default_type": "link",
        "icon": "musical-notes",
        "color": "#7C3AED",
    },
    "stillness_meditation": {
        "id": "stillness_meditation",
        "name": "Stillness Meditation",
        "description": "Connect to Absolute Stillness — deep meditation practice",
        "default_url": "https://www.youtube.com/watch?v=hs0rnDhOU-I",
        "default_type": "link",
        "icon": "leaf",
        "color": "#3B82F6",
    },
    "goal_manifestation": {
        "id": "goal_manifestation",
        "name": "KalphaVriksha Meditation",
        "description": "Feeling as if Already Achieved — manifestation meditation",
        "default_url": "https://customer-assets.emergentagent.com/job_a7a2d7ec-9ce2-470b-8ff8-d26638aa4277/artifacts/4evzh8fa_KalphaVriksha%20Meditation.mp3",
        "default_type": "audio",
        "icon": "heart",
        "color": "#10B981",
    },
}


# ═══════════════════════════════════════════════════════════════
# GET DEFAULTS
# ═══════════════════════════════════════════════════════════════

@router.get("/defaults")
async def get_defaults():
    """Return the 3 meditation slot definitions with their default URLs."""
    return {"meditations": list(MEDITATION_DEFAULTS.values())}


# ═══════════════════════════════════════════════════════════════
# GET USER PREFERENCES (with resolved URLs)
# ═══════════════════════════════════════════════════════════════

@router.get("/preferences")
async def get_preferences(request: Request, user: dict = Depends(get_current_user)):
    """Return user's meditation preferences — custom URL/upload if set, otherwise defaults."""
    prefs = await db.meditation_preferences.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    base_url = str(request.base_url).rstrip("/")

    result = {}
    for med_id, defaults in MEDITATION_DEFAULTS.items():
        custom = {}
        if prefs and med_id in prefs.get("meditations", {}):
            custom = prefs["meditations"][med_id]

        source_type = custom.get("source_type", "default")
        if source_type == "custom_url":
            resolved_url = custom.get("custom_url", defaults["default_url"])
        elif source_type == "uploaded":
            filename = custom.get("filename", "")
            resolved_url = f"{base_url}/api/meditation-settings/files/{user['user_id']}/{filename}" if filename else defaults["default_url"]
        else:
            resolved_url = defaults["default_url"]

        result[med_id] = {
            **defaults,
            "source_type": source_type,
            "resolved_url": resolved_url,
            "custom_url": custom.get("custom_url", ""),
            "filename": custom.get("filename", ""),
            "original_name": custom.get("original_name", ""),
        }

    return {"meditations": result}


# ═══════════════════════════════════════════════════════════════
# UPDATE PREFERENCES (URL-based)
# ═══════════════════════════════════════════════════════════════

@router.put("/preferences")
async def update_preferences(request: Request, user: dict = Depends(get_current_user)):
    """
    Update meditation preference for a slot.
    Body: { meditation_id, source_type: "default"|"custom_url", custom_url?: str }
    """
    body = await request.json()
    med_id = body.get("meditation_id")
    if med_id not in MEDITATION_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid meditation_id: {med_id}")

    source_type = body.get("source_type", "default")
    now = datetime.now(timezone.utc).isoformat()

    update_data = {
        "source_type": source_type,
        "custom_url": body.get("custom_url", ""),
        "updated_at": now,
    }

    await db.meditation_preferences.update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {
                f"meditations.{med_id}": update_data,
                "updated_at": now,
            },
            "$setOnInsert": {"user_id": user["user_id"], "created_at": now},
        },
        upsert=True,
    )

    return {"updated": True, "meditation_id": med_id, "source_type": source_type}


# ═══════════════════════════════════════════════════════════════
# UPLOAD MP3 FILE
# ═══════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_meditation(
    meditation_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a custom MP3 file for a meditation slot."""
    if meditation_id not in MEDITATION_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid meditation_id: {meditation_id}")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(('.mp3', '.m4a', '.wav', '.ogg', '.aac')):
        raise HTTPException(status_code=400, detail="Only audio files (mp3, m4a, wav, ogg, aac) are allowed")

    # Check file size (max 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Save file
    user_dir = os.path.join(UPLOAD_DIR, user["user_id"])
    os.makedirs(user_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{meditation_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(user_dir, filename)

    # Remove old upload for this slot if exists
    prefs = await db.meditation_preferences.find_one({"user_id": user["user_id"]})
    if prefs and meditation_id in prefs.get("meditations", {}):
        old_file = prefs["meditations"][meditation_id].get("filename", "")
        if old_file:
            old_path = os.path.join(user_dir, old_file)
            if os.path.exists(old_path):
                os.remove(old_path)

    with open(filepath, "wb") as f:
        f.write(content)

    now = datetime.now(timezone.utc).isoformat()

    await db.meditation_preferences.update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {
                f"meditations.{meditation_id}": {
                    "source_type": "uploaded",
                    "filename": filename,
                    "original_name": file.filename,
                    "file_size": len(content),
                    "updated_at": now,
                },
                "updated_at": now,
            },
            "$setOnInsert": {"user_id": user["user_id"], "created_at": now},
        },
        upsert=True,
    )

    return {
        "uploaded": True,
        "meditation_id": meditation_id,
        "filename": filename,
        "original_name": file.filename,
        "file_size": len(content),
    }


# ═══════════════════════════════════════════════════════════════
# SERVE UPLOADED FILES
# ═══════════════════════════════════════════════════════════════

@router.get("/files/{user_id}/{filename}")
async def serve_meditation_file(user_id: str, filename: str):
    """Serve an uploaded meditation file."""
    filepath = os.path.join(UPLOAD_DIR, user_id, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="audio/mpeg")


# ═══════════════════════════════════════════════════════════════
# RESET TO DEFAULT
# ═══════════════════════════════════════════════════════════════

@router.delete("/preferences/{meditation_id}")
async def reset_to_default(meditation_id: str, user: dict = Depends(get_current_user)):
    """Reset a meditation slot back to its default."""
    if meditation_id not in MEDITATION_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Invalid meditation_id: {meditation_id}")

    # Remove uploaded file if exists
    prefs = await db.meditation_preferences.find_one({"user_id": user["user_id"]})
    if prefs and meditation_id in prefs.get("meditations", {}):
        old_file = prefs["meditations"][meditation_id].get("filename", "")
        if old_file:
            old_path = os.path.join(UPLOAD_DIR, user["user_id"], old_file)
            if os.path.exists(old_path):
                os.remove(old_path)

    await db.meditation_preferences.update_one(
        {"user_id": user["user_id"]},
        {"$unset": {f"meditations.{meditation_id}": ""}},
    )

    return {"reset": True, "meditation_id": meditation_id}
