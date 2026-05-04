"""Auth routes — register, login, logout, forgot/reset password, Google session, push token, user search"""

import uuid
import os
import random
import logging
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from core.database import db
from core.auth import (
    get_current_user, get_password_hash, verify_password,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_DAYS, pwd_context,
)
from core.helpers import generate_user_id
from core.rate_limiting import limiter, AUTH_LIMIT

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

    return {
        "user_id": user_id, "email": user_data.email, "name": user_data.name,
        "picture": None, "auth_method": "email", "session_token": session_token
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
        "org_id": user_doc.get("org_id"), "session_token": session_token
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
        "picture": picture, "auth_method": "google", "session_token": session_token
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    return {
        "user_id": user["user_id"], "email": user["email"], "name": user["name"],
        "picture": user.get("picture"), "auth_method": user.get("auth_method", "email"),
        "has_password": bool(user.get("password_hash")),
        "role": user.get("role", "user"),
        "org_id": user.get("org_id"), "org_role": user.get("org_role"),
    }


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
