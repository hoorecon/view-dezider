"""SuperAdmin security settings (stored in db.app_settings key='security_config').

Currently exposes `skip_whatsapp_otp_for_admins` (default TRUE): when on, users
with an admin role are treated as WhatsApp-verified so they bypass the post-login
WhatsApp OTP gate. This does NOT change OTP sending/verification for regular users.
"""
from __future__ import annotations

from typing import Any, Dict

from core.database import db

SECURITY_KEY = "security_config"
ADMIN_ROLES = {"admin", "super_admin", "co_admin"}
DEFAULTS = {"skip_whatsapp_otp_for_admins": True}


async def get_security_config() -> Dict[str, Any]:
    doc = await db.app_settings.find_one({"key": SECURITY_KEY}) or {}
    return {
        "skip_whatsapp_otp_for_admins": bool(
            doc.get("skip_whatsapp_otp_for_admins", DEFAULTS["skip_whatsapp_otp_for_admins"])
        ),
    }


async def set_security_config(patch: Dict[str, Any], by: str) -> Dict[str, Any]:
    update: Dict[str, Any] = {}
    if "skip_whatsapp_otp_for_admins" in patch:
        update["skip_whatsapp_otp_for_admins"] = bool(patch["skip_whatsapp_otp_for_admins"])
    if update:
        from datetime import datetime, timezone
        update["updated_by"] = by
        update["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.app_settings.update_one(
            {"key": SECURITY_KEY}, {"$set": {"key": SECURITY_KEY, **update}}, upsert=True
        )
    return await get_security_config()


async def effective_whatsapp_verified(user_doc: Dict[str, Any]) -> bool:
    """True if the user is already verified OR is an admin and the skip flag is on."""
    if bool(user_doc.get("whatsapp_verified")):
        return True
    role = (user_doc.get("role") or "user")
    if role in ADMIN_ROLES:
        cfg = await get_security_config()
        if cfg["skip_whatsapp_otp_for_admins"]:
            return True
    return False
