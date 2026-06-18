"""Auth routes — register, login, logout, forgot/reset password, Google session, push token, user search"""

import uuid
import os
import random
import logging
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from core.database import db
from core.auth import (
    get_current_user, get_password_hash, verify_password,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context,
)
from core.helpers import generate_user_id
from core.rate_limiting import limiter, AUTH_LIMIT
from core.security_config import effective_whatsapp_verified

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])


# ========================
# MODELS
# ========================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    org_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    org_id: Optional[str] = None

class SessionRequest(BaseModel):
    session_id: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class SetPasswordRequest(BaseModel):
    new_password: str


# ========================
# ROUTES
# ========================

@router.post("/auth/register")
@limiter.limit(AUTH_LIMIT)
async def register(request: Request, user_data: UserCreate, response: Response):
    """Register a new user with email/password"""
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = generate_user_id()
    hashed_password = get_password_hash(user_data.password)

    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": hashed_password,
        "picture": None,
        "auth_method": "email",
        "org_id": user_data.org_id,
        "org_role": "org_member" if user_data.org_id else None,
        "created_at": datetime.now(timezone.utc)
    }

    await db.users.insert_one(user_doc)

    # Auto-create the idempotent 'Self' contact so every new profile has a
    # selectable "Self" in Contacts (used in Solution Finder Q3). Non-fatal.
    try:
        from routes.contacts import ensure_self_contact_for_user
        await ensure_self_contact_for_user(user_doc)
    except Exception as _e:
        logging.warning(f"ensure-self on register failed (non-fatal): {_e}")

    # Create session
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)

    response.set_cookie(
        key="session_token", value=session_token,
        httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
    )

    from core.posthog_client import track as ph_track
    ph_track(user_id, "signup", {"method": "email", "has_org": bool(user_data.org_id)})

    return {
        "user_id": user_id, "email": user_data.email, "name": user_data.name,
        "picture": None, "auth_method": "email",
        "whatsapp_number": None, "whatsapp_verified": False,
        "session_token": session_token
    }


@router.post("/auth/login")
@limiter.limit(AUTH_LIMIT)
async def login(request: Request, user_data: UserLogin, response: Response):
    """Login with email/password"""
    user_doc = await db.users.find_one({"email": user_data.email}, {"_id": 0})

    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user_doc.get("auth_method") == "google" and not user_doc.get("password_hash"):
        raise HTTPException(status_code=400, detail="This account uses Google Sign-In. Please login with Google.")

    if not verify_password(user_data.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_doc["user_id"],
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)

    response.set_cookie(
        key="session_token", value=session_token,
        httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
    )

    return {
        "user_id": user_doc["user_id"], "email": user_doc["email"], "name": user_doc["name"],
        "picture": user_doc.get("picture"), "auth_method": user_doc["auth_method"],
        "org_id": user_doc.get("org_id"),
        "role": user_doc.get("role", "user"),
        "user_type": user_doc.get("user_type"),
        "is_admin": user_doc.get("role", "user") in ("admin", "super_admin", "co_admin"),
        "whatsapp_number": user_doc.get("whatsapp_number"),
        "whatsapp_verified": await effective_whatsapp_verified(user_doc),
        "session_token": session_token
    }


@router.post("/auth/google/session")
async def google_session(session_data: SessionRequest, response: Response):
    """
    Exchange Google OAuth session_id for user data and create session.
    REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    """
    try:
        async with httpx.AsyncClient() as client_http:
            res = await client_http.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_data.session_id}
            )
            if res.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session ID")
            google_data = res.json()
    except Exception as e:
        logging.error(f"Error fetching Google session: {e}")
        raise HTTPException(status_code=401, detail="Failed to validate Google session")

    email = google_data.get("email")
    name = google_data.get("name")
    picture = google_data.get("picture")

    existing_user = await db.users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        user_id = existing_user["user_id"]
        await db.users.update_one({"email": email}, {"$set": {"name": name, "picture": picture}})
    else:
        user_id = generate_user_id()
        user_doc = {
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "auth_method": "google", "created_at": datetime.now(timezone.utc)
        }
        await db.users.insert_one(user_doc)
        # Auto-create the idempotent 'Self' contact for brand-new Google users.
        try:
            from routes.contacts import ensure_self_contact_for_user
            await ensure_self_contact_for_user(user_doc)
        except Exception as _e:
            logging.warning(f"ensure-self on google register failed (non-fatal): {_e}")

    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.user_sessions.insert_one(session_doc)

    response.set_cookie(
        key="session_token", value=session_token,
        httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
    )

    return {
        "user_id": user_id, "email": email, "name": name,
        "picture": picture, "auth_method": "google",
        "whatsapp_number": (existing_user or {}).get("whatsapp_number"),
        "whatsapp_verified": bool((existing_user or {}).get("whatsapp_verified")),
        "session_token": session_token
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user (with ACM v2 effective access key)."""
    custom_pic = user.get("profile_picture")

    # Resolve effective access key on every /me call (cheap; cached on user doc)
    eff_key = user.get("effective_access_key")
    eff_user_type = user.get("effective_user_type") or user.get("user_type", "free")
    eff_plan = user.get("effective_plan") or user.get("subscription_plan", "none")
    try:
        from core.acm_engine import resolve_user_acm_profile
        prof = await resolve_user_acm_profile(user)
        eff_key = prof.get("access_key", eff_key)
        eff_user_type = prof.get("user_type", eff_user_type)
        eff_plan = prof.get("subscription_plan", eff_plan)
    except Exception:
        pass

    return {
        "user_id": user["user_id"], "email": user["email"], "name": user["name"],
        "picture": custom_pic or user.get("picture"),
        "has_custom_picture": bool(custom_pic),
        "gender": user.get("gender"),
        "auth_method": user.get("auth_method", "email"),
        "has_password": bool(user.get("password_hash")),
        "role": user.get("role", "user"),
        "org_id": user.get("org_id"), "org_role": user.get("org_role"),
        "whatsapp_number": user.get("whatsapp_number"),
        "whatsapp_verified": await effective_whatsapp_verified(user),
        "can_view_pii": bool(user.get("can_view_pii")),
        # ACM v2 fields
        "user_type": eff_user_type,
        "subscription_plan": eff_plan,
        "effective_access_key": eff_key,
    }


ALLOWED_GENDERS = {"Male", "Female", "Other", "Prefer not to say"}


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    gender: Optional[str] = None  # one of ALLOWED_GENDERS, or "" to clear
    profile_picture: Optional[str] = None  # data URL, or "" to remove


@router.patch("/auth/profile")
async def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    """Update editable profile fields: name, gender, profile picture.
    Email is never editable here."""
    updates = {}
    unsets = {}

    if body.name is not None:
        n = body.name.strip()
        if len(n) < 1:
            raise HTTPException(status_code=400, detail="Name cannot be empty.")
        updates["name"] = n

    if body.gender is not None:
        g = body.gender.strip()
        if g == "":
            unsets["gender"] = ""
        elif g in ALLOWED_GENDERS:
            updates["gender"] = g
        else:
            raise HTTPException(status_code=400, detail="Invalid gender.")

    if body.profile_picture is not None:
        pic = body.profile_picture.strip()
        if pic == "":
            unsets["profile_picture"] = ""
        else:
            _validate_profile_picture(pic)
            updates["profile_picture"] = pic

    if not updates and not unsets:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    op = {}
    if updates:
        op["$set"] = updates
    if unsets:
        op["$unset"] = unsets
    await db.users.update_one({"user_id": user["user_id"]}, op)

    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    custom_pic = fresh.get("profile_picture")
    return {
        "success": True,
        "name": fresh.get("name"),
        "gender": fresh.get("gender"),
        "picture": custom_pic or fresh.get("picture"),
        "has_custom_picture": bool(custom_pic),
    }


def _validate_profile_picture(data_url: str):
    import base64 as _b64
    import binascii as _bin
    mime = "image/png"
    b64 = data_url
    if data_url.startswith("data:"):
        try:
            header, b64 = data_url.split(",", 1)
            mime = header.split(";")[0].replace("data:", "").lower()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid image data.")
    if mime not in {"image/png", "image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Picture must be PNG or JPG.")
    try:
        raw = _b64.b64decode(b64, validate=True)
    except (_bin.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image encoding.")
    if len(raw) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="Picture must be 1 MB or smaller.")


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user and clear session"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}


@router.post("/auth/forgot-password")
@limiter.limit(AUTH_LIMIT)
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """Generate OTP for password reset"""
    user_doc = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if user_doc.get("auth_method") == "google" and not user_doc.get("password_hash"):
        raise HTTPException(status_code=400, detail="This account uses Google Sign-In. Please login with Google or set a password from your profile.")

    otp = str(random.randint(100000, 999999))
    await db.password_resets.delete_many({"email": data.email})
    await db.password_resets.insert_one({
        "email": data.email, "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "created_at": datetime.now(timezone.utc),
    })
    return {"message": "OTP generated successfully", "otp": otp, "expires_in_minutes": 10}


@router.post("/auth/reset-password")
@limiter.limit(AUTH_LIMIT)
async def reset_password(request: Request, data: ResetPasswordRequest):
    """Reset password using OTP"""
    reset_doc = await db.password_resets.find_one({"email": data.email, "otp": data.otp})
    if not reset_doc:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
    expires_at = reset_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"_id": reset_doc["_id"]})
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    hashed_password = get_password_hash(data.new_password)
    await db.users.update_one({"email": data.email}, {"$set": {"password_hash": hashed_password}})
    await db.password_resets.delete_many({"email": data.email})
    return {"message": "Password reset successfully. You can now login with your new password."}


@router.post("/auth/set-password")
async def set_password(data: SetPasswordRequest, user: dict = Depends(get_current_user)):
    """Set password for Google-authenticated users"""
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    hashed_password = get_password_hash(data.new_password)
    update_fields = {"password_hash": hashed_password}
    if user.get("auth_method") == "google":
        update_fields["auth_method"] = "google_and_email"
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": update_fields})
    return {"message": "Password set successfully. You can now also login with email and password."}


@router.post("/auth/push-token")
async def register_push_token(request: Request, user: dict = Depends(get_current_user)):
    """Register Expo push token for the current user"""
    body = await request.json()
    token = body.get("push_token", "")
    if token:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"push_token": token}})
    return {"message": "Push token registered"}


@router.get("/users/search")
async def search_users(q: str = "", user: dict = Depends(get_current_user)):
    """Search users by name or email for sharing"""
    if not q or len(q) < 2:
        return []
    query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ],
        "user_id": {"$ne": user["user_id"]},
    }
    users = await db.users.find(query, {"_id": 0, "password_hash": 0, "push_token": 0}).to_list(20)
    return [{"user_id": u["user_id"], "name": u.get("name", ""), "email": u["email"]} for u in users]
