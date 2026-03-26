"""
Org Auth Routes — Org Login Refinement with WhatsApp OTP (UltraMsg)
- Org login credential validation
- Conditional WhatsApp OTP for Business & Government orgs (not NonProfit)
- UltraMsg integration for sending OTP via WhatsApp
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import random
import os
import httpx
import logging

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

from core.database import db
from passlib.context import CryptContext

router = APIRouter(prefix="/org-auth", tags=["Org Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# ========================
# CONSTANTS
# ========================
ORG_TYPES = ["BUSINESS", "NONPROFIT", "GOVERNMENT"]
OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS = 3

# UltraMsg Config
ULTRAMSG_INSTANCE_ID = os.environ.get("ULTRAMSG_INSTANCE_ID", "")
ULTRAMSG_API_TOKEN = os.environ.get("ULTRAMSG_API_TOKEN", "")
ULTRAMSG_BASE_URL = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}"

# ========================
# MODELS
# ========================

class OrgLoginRequest(BaseModel):
    org_slug: str
    email: str
    password: str

class OTPVerifyRequest(BaseModel):
    verification_id: str
    otp: str

class OrgUserCreateRequest(BaseModel):
    org_id: str
    name: str
    email: str
    password: str
    whatsapp_number: Optional[str] = None
    role: str = "member"

# ========================
# ULTRAMSG WHATSAPP SERVICE
# ========================

async def send_whatsapp_otp(phone_number: str, otp_code: str) -> dict:
    """Send OTP via WhatsApp using UltraMsg API"""
    if not ULTRAMSG_INSTANCE_ID or not ULTRAMSG_API_TOKEN:
        logger.warning("UltraMsg credentials not configured. OTP not sent.")
        return {"success": False, "error": "WhatsApp OTP service not configured", "mock": True}

    try:
        url = f"{ULTRAMSG_BASE_URL}/messages/chat"
        payload = {
            "token": ULTRAMSG_API_TOKEN,
            "to": phone_number,
            "body": f"Your View Dezider verification code is: *{otp_code}*\n\nThis code expires in {OTP_EXPIRY_MINUTES} minutes. Do not share it with anyone.",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, data=payload)
            result = response.json()
            if response.status_code == 200 and result.get("sent") == "true":
                return {"success": True, "message_id": result.get("id")}
            else:
                logger.error(f"UltraMsg API error: {result}")
                return {"success": False, "error": str(result)}
    except Exception as e:
        logger.error(f"WhatsApp OTP send failed: {e}")
        return {"success": False, "error": str(e)}

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def hash_otp(otp: str) -> str:
    """Hash OTP for secure storage"""
    return hashlib.sha256(otp.encode()).hexdigest()

# ========================
# ENDPOINTS
# ========================

@router.post("/login")
async def org_login(payload: OrgLoginRequest):
    """
    Step 1: Validate org credentials.
    If org type is Business or Government → require WhatsApp OTP (returns verification_id).
    If org type is NonProfit → login immediately.
    """
    # Find org by slug
    org = await db.organizations.find_one({"slug": payload.org_slug.strip().lower()})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org_type = org.get("org_type", "BUSINESS").upper()

    # Find user in this org
    user = await db.users.find_one({
        "email": payload.email.strip().lower(),
        "org_id": org["id"],
    })
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not pwd_context.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if OTP required based on org type
    requires_otp = org_type in ["BUSINESS", "GOVERNMENT"]

    if not requires_otp:
        # NonProfit — login immediately, generate session token
        session_token = str(uuid.uuid4())
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"session_token": session_token, "last_login": datetime.now(timezone.utc)}}
        )
        return {
            "status": "authenticated",
            "requires_otp": False,
            "session_token": session_token,
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user.get("name", ""),
                "org_id": org["id"],
                "org_name": org.get("name", ""),
                "org_type": org_type,
                "org_role": user.get("org_role", "org_member"),
            },
        }

    # Business or Government — send OTP
    whatsapp_number = user.get("whatsapp_number")
    if not whatsapp_number:
        raise HTTPException(
            status_code=400,
            detail="No WhatsApp number registered for this user. Contact your org admin."
        )

    otp_code = generate_otp()
    verification_id = str(uuid.uuid4())

    # Store OTP verification record
    otp_record = {
        "id": verification_id,
        "org_user_id": user["user_id"],
        "org_id": org["id"],
        "org_type": org_type,
        "otp_hash": hash_otp(otp_code),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        "attempt_count": 0,
        "verified": False,
        "created_at": datetime.now(timezone.utc),
        "provider_response": None,
    }
    await db.whatsapp_otp_verifications.insert_one(otp_record)

    # Send OTP via WhatsApp
    send_result = await send_whatsapp_otp(whatsapp_number, otp_code)
    await db.whatsapp_otp_verifications.update_one(
        {"id": verification_id},
        {"$set": {"provider_response": send_result}}
    )

    # Mask phone number for display
    masked_phone = whatsapp_number[:4] + "****" + whatsapp_number[-3:] if len(whatsapp_number) > 7 else "****"

    return {
        "status": "otp_required",
        "requires_otp": True,
        "verification_id": verification_id,
        "masked_phone": masked_phone,
        "org_type": org_type,
        "otp_sent": send_result.get("success", False),
        "message": f"OTP sent to WhatsApp {masked_phone}",
    }


@router.post("/verify-otp")
async def verify_otp(payload: OTPVerifyRequest):
    """
    Step 2: Verify the WhatsApp OTP and complete login.
    """
    record = await db.whatsapp_otp_verifications.find_one({"id": payload.verification_id})
    if not record:
        raise HTTPException(status_code=404, detail="Verification session not found")

    if record.get("verified"):
        raise HTTPException(status_code=400, detail="OTP already verified")

    # Check expiry
    if datetime.now(timezone.utc) > record["expires_at"]:
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one.")

    # Check attempts
    if record.get("attempt_count", 0) >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="Too many failed attempts. Please request a new OTP.")

    # Increment attempt count
    await db.whatsapp_otp_verifications.update_one(
        {"id": payload.verification_id},
        {"$inc": {"attempt_count": 1}}
    )

    # Verify OTP hash
    if hash_otp(payload.otp) != record["otp_hash"]:
        remaining = OTP_MAX_ATTEMPTS - record.get("attempt_count", 0) - 1
        raise HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempts remaining.")

    # Mark as verified
    await db.whatsapp_otp_verifications.update_one(
        {"id": payload.verification_id},
        {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc)}}
    )

    # Generate session token for the user
    user = await db.users.find_one({"user_id": record["org_user_id"]})
    org = await db.organizations.find_one({"id": record["org_id"]})

    session_token = str(uuid.uuid4())
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"session_token": session_token, "last_login": datetime.now(timezone.utc)}}
    )

    return {
        "status": "authenticated",
        "session_token": session_token,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "org_id": record["org_id"],
            "org_name": org.get("name", "") if org else "",
            "org_type": record["org_type"],
            "org_role": user.get("org_role", "org_member"),
        },
    }


@router.post("/resend-otp")
async def resend_otp(verification_id: str):
    """Resend OTP for an existing verification session"""
    record = await db.whatsapp_otp_verifications.find_one({"id": verification_id})
    if not record:
        raise HTTPException(status_code=404, detail="Verification session not found")

    if record.get("verified"):
        raise HTTPException(status_code=400, detail="Already verified")

    user = await db.users.find_one({"user_id": record["org_user_id"]})
    if not user or not user.get("whatsapp_number"):
        raise HTTPException(status_code=400, detail="No WhatsApp number found")

    # Generate new OTP
    otp_code = generate_otp()
    await db.whatsapp_otp_verifications.update_one(
        {"id": verification_id},
        {"$set": {
            "otp_hash": hash_otp(otp_code),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
            "attempt_count": 0,
        }}
    )

    send_result = await send_whatsapp_otp(user["whatsapp_number"], otp_code)
    return {
        "message": "OTP resent",
        "otp_sent": send_result.get("success", False),
    }
