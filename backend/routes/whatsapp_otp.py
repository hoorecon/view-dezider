"""
WhatsApp OTP verification (UltraMsg).

Sends a 6-digit OTP to a user's WhatsApp number and verifies it, marking the
user's WhatsApp number as verified. UltraMsg credentials resolve from the Admin
UI (db.integrations) first, then fall back to .env (see
core.integrations.resolve_ultramsg_creds).

Abuse protection:
  • resend cooldown (default 60s)
  • max sends per day (default 5)
  • max verify attempts per OTP (default 5)

OTP codes are stored hashed (SHA-256 + pepper), never plaintext. A TTL index on
`expires_at` auto-purges stale OTPs.

NOTE: `dev_code` is echoed in the send response so the flow is testable in
environments where a real WhatsApp message cannot be received (mirrors the
existing forgot-password convention in auth_routes.py).
"""
import os
import re
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta, date

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from core.database import db
from core.auth import get_current_user, SECRET_KEY
from core.integrations import resolve_ultramsg_creds

load_dotenv()
logger = logging.getLogger("whatsapp_otp")

router = APIRouter(prefix="/auth/whatsapp", tags=["WhatsApp OTP"])

# Tunables (env-overridable)
RESEND_COOLDOWN_SECONDS = int(os.getenv("WA_OTP_RESEND_COOLDOWN_SECONDS", "60"))
MAX_SEND_PER_DAY = int(os.getenv("WA_OTP_MAX_SEND_PER_DAY", "5"))
CODE_TTL_MINUTES = int(os.getenv("WA_OTP_CODE_TTL_MINUTES", "10"))
MAX_VERIFY_ATTEMPTS = int(os.getenv("WA_OTP_MAX_VERIFY_ATTEMPTS", "5"))
# Debug-only: expose the OTP in the API response even when WhatsApp delivered it.
# MUST remain false/unset in production (the code is always sent via WhatsApp).
EXPOSE_DEV_CODE = os.getenv("WA_OTP_EXPOSE_DEV_CODE", "false").strip().lower() == "true"
_PEPPER = os.getenv("WA_OTP_PEPPER") or (SECRET_KEY or "jelcos-wa-otp")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_phone(p: Optional[str]) -> Optional[str]:
    """Return a digits-only WhatsApp number in international format.

    A bare 10-digit Indian number gets an implicit '91' country code.
    """
    digits = re.sub(r"\D", "", p or "")
    if not digits:
        return None
    if len(digits) == 10:  # assume India
        digits = "91" + digits
    return digits


def _gen_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(f"{code}{_PEPPER}".encode("utf-8")).hexdigest()


async def _send_whatsapp(to: str, body: str) -> None:
    instance_id, token, source = await resolve_ultramsg_creds()
    if not (instance_id and token):
        raise RuntimeError("UltraMsg not configured")
    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data={"token": token, "to": to, "body": body})
    if r.status_code >= 300:
        raise RuntimeError(f"UltraMsg error {r.status_code}: {r.text[:200]}")
    try:
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"UltraMsg error: {data.get('error')}")
    except ValueError:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────
class SendOtpRequest(BaseModel):
    phone_number: Optional[str] = None  # required if user has none on file


class VerifyOtpRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=8)


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/status")
async def whatsapp_status(user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    return {
        "whatsapp_number": u.get("whatsapp_number"),
        "whatsapp_verified": bool(u.get("whatsapp_verified")),
    }


@router.post("/send-otp")
async def send_otp(body: SendOtpRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0}) or {}

    phone = _norm_phone(body.phone_number) or _norm_phone(u.get("whatsapp_number"))
    if not phone:
        raise HTTPException(status_code=400, detail="A WhatsApp number is required.")

    # Already-verified short-circuit applies only when NOT changing the number.
    if u.get("whatsapp_verified") and phone == _norm_phone(u.get("whatsapp_number")):
        return {"success": True, "already_verified": True}

    now = _now()
    today = date.today().isoformat()
    existing = await db.whatsapp_otps.find_one({"user_id": user_id, "verified": False})

    send_count_today = 0
    if existing:
        last_sent = existing.get("last_sent_at")
        if last_sent and isinstance(last_sent, datetime):
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            elapsed = (now - last_sent).total_seconds()
            if elapsed < RESEND_COOLDOWN_SECONDS:
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {int(RESEND_COOLDOWN_SECONDS - elapsed)}s before requesting another code.",
                )
        if existing.get("day_bucket") == today:
            send_count_today = int(existing.get("send_count_today") or 0)
            if send_count_today >= MAX_SEND_PER_DAY:
                raise HTTPException(
                    status_code=429,
                    detail="You've requested the maximum number of codes for today. Please try again tomorrow.",
                )

    code = _gen_code()
    code_hash = _hash_code(code)
    expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)

    await db.whatsapp_otps.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "phone_number": phone,
                "code_hash": code_hash,
                "created_at": now,
                "expires_at": expires_at,
                "last_sent_at": now,
                "day_bucket": today,
                "send_count_today": send_count_today + 1,
                "verify_attempts": 0,
                "verified": False,
            }
        },
        upsert=True,
    )

    # Persist the pending number on the user record so it survives reloads.
    await db.users.update_one({"user_id": user_id}, {"$set": {"whatsapp_number": phone}})

    body_text = (
        f"Your JELCOS AI verification code is {code}. "
        f"It expires in {CODE_TTL_MINUTES} minutes. Do not share this code."
    )
    delivered = False
    send_error = None
    try:
        await _send_whatsapp(phone, body_text)
        delivered = True
    except Exception as e:  # noqa: BLE001
        send_error = str(e)[:200]
        logger.warning("UltraMsg OTP send failed for user=%s: %s", user_id, send_error)

    resp = {
        "success": True,
        "delivered": delivered,
        "phone_number": phone,
        "cooldown_seconds": RESEND_COOLDOWN_SECONDS,
    }
    # Security: never expose the OTP over the wire when WhatsApp delivered it.
    # Only surface it as a fallback when delivery failed, or when the debug
    # flag WA_OTP_EXPOSE_DEV_CODE=true is explicitly set (non-production only).
    if not delivered or EXPOSE_DEV_CODE:
        resp["dev_code"] = code
    if not delivered:
        resp["delivery_error"] = send_error
    return resp


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    now = _now()
    otp = await db.whatsapp_otps.find_one({"user_id": user_id, "verified": False})

    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    exp = otp.get("expires_at")
    if isinstance(exp, datetime) and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < now:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    attempts = int(otp.get("verify_attempts") or 0)
    if attempts >= MAX_VERIFY_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    if _hash_code(body.code.strip()) != otp.get("code_hash"):
        await db.whatsapp_otps.update_one({"_id": otp["_id"]}, {"$inc": {"verify_attempts": 1}})
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    await db.whatsapp_otps.update_one(
        {"_id": otp["_id"]}, {"$set": {"verified": True, "verified_at": now}}
    )
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "whatsapp_verified": True,
            "whatsapp_number": otp.get("phone_number"),
            "whatsapp_verified_at": now,
        }},
    )
    return {"success": True, "whatsapp_verified": True, "whatsapp_number": otp.get("phone_number")}
