"""Auth routes — register, login, logout, forgot/reset password, session management"""

import uuid
import os
import random
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user
from models.schemas import (
    UserCreate, UserLogin, SessionRequest, ForgotPasswordRequest,
    ResetPasswordRequest, SetPasswordRequest,
    generate_user_id, hash_password, verify_password, create_access_token,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_DAYS,
)
from jose import JWTError, jwt
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])


@router.post("/auth/register", response_model=dict)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = generate_user_id()
    now = datetime.now(timezone.utc)
    user_doc = {
        "user_id": user_id,
        "email": user_data.email.lower(),
        "name": user_data.name,
        "password_hash": hash_password(user_data.password),
        "role": "user",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if user_data.org_id:
        org = await db.organizations.find_one({"id": user_data.org_id})
        if org:
            user_doc["org_id"] = user_data.org_id
            user_doc["org_role"] = "org_member"
    await db.users.insert_one(user_doc)
    token = create_access_token({"sub": user_id, "email": user_data.email.lower(), "name": user_data.name})
    return {"token": token, "user_id": user_id, "email": user_data.email.lower(), "name": user_data.name, "role": "user"}


@router.post("/auth/login", response_model=dict)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email.lower()})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Please set a password first or login via your original method")
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({
        "sub": user["user_id"], "email": user["email"], "name": user.get("name", ""),
        "role": user.get("role", "user"),
    })
    return {
        "token": token, "user_id": user["user_id"], "email": user["email"],
        "name": user.get("name", ""), "role": user.get("role", "user"),
        "org_id": user.get("org_id"), "org_role": user.get("org_role"),
    }


@router.post("/auth/google-session", response_model=dict)
async def google_session(request: SessionRequest):
    session = await db.google_sessions.find_one({"session_id": request.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("used"):
        raise HTTPException(status_code=400, detail="Session already used")
    await db.google_sessions.update_one({"session_id": request.session_id}, {"$set": {"used": True}})
    email = session.get("email", "").lower()
    name = session.get("name", email.split("@")[0])
    user = await db.users.find_one({"email": email})
    if not user:
        user_id = generate_user_id()
        now = datetime.now(timezone.utc)
        user_doc = {
            "user_id": user_id, "email": email, "name": name,
            "password_hash": None, "role": "user", "is_active": True,
            "auth_provider": "google", "google_id": session.get("google_id"),
            "avatar_url": session.get("avatar_url", ""),
            "created_at": now, "updated_at": now,
        }
        await db.users.insert_one(user_doc)
        user = user_doc
    else:
        user_id = user["user_id"]
        update_fields = {"updated_at": datetime.now(timezone.utc)}
        if session.get("avatar_url"):
            update_fields["avatar_url"] = session["avatar_url"]
        if not user.get("name") and name:
            update_fields["name"] = name
        await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
    token = create_access_token({
        "sub": user["user_id"], "email": email, "name": user.get("name", name),
        "role": user.get("role", "user"),
    })
    return {
        "token": token, "user_id": user["user_id"], "email": email,
        "name": user.get("name", name), "role": user.get("role", "user"),
        "org_id": user.get("org_id"), "org_role": user.get("org_role"),
    }


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    return user_doc


@router.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}


@router.post("/auth/forgot-password", response_model=dict)
async def forgot_password(request: ForgotPasswordRequest):
    user = await db.users.find_one({"email": request.email.lower()})
    if not user:
        return {"message": "If an account exists with this email, an OTP has been sent"}
    otp = str(random.randint(100000, 999999))
    await db.password_resets.insert_one({
        "email": request.email.lower(), "otp": otp,
        "created_at": datetime.now(timezone.utc), "used": False,
    })
    ultramsg_instance = os.environ.get("ULTRAMSG_INSTANCE")
    ultramsg_token = os.environ.get("ULTRAMSG_TOKEN")
    user_phone = user.get("phone", user.get("mobile", ""))
    if ultramsg_instance and ultramsg_token and user_phone:
        try:
            url = f"https://api.ultramsg.com/{ultramsg_instance}/messages/chat"
            payload = {"token": ultramsg_token, "to": user_phone, "body": f"Your View Dezider OTP is: {otp}. Valid for 10 minutes."}
            async with httpx.AsyncClient() as client_http:
                await client_http.post(url, data=payload, timeout=10)
        except Exception as e:
            logger.error(f"WhatsApp OTP error: {e}")
    return {"message": "If an account exists with this email, an OTP has been sent", "otp_for_dev": otp}


@router.post("/auth/reset-password", response_model=dict)
async def reset_password(request: ResetPasswordRequest):
    reset = await db.password_resets.find_one(
        {"email": request.email.lower(), "otp": request.otp, "used": False},
        sort=[("created_at", -1)]
    )
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    created_at = reset["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    elif created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - created_at).total_seconds() > 600:
        raise HTTPException(status_code=400, detail="OTP has expired")
    await db.password_resets.update_one({"_id": reset["_id"]}, {"$set": {"used": True}})
    new_hash = hash_password(request.new_password)
    await db.users.update_one({"email": request.email.lower()}, {"$set": {"password_hash": new_hash}})
    return {"message": "Password reset successfully"}


@router.post("/auth/set-password")
async def set_password(request: SetPasswordRequest, user: dict = Depends(get_current_user)):
    new_hash = hash_password(request.new_password)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"message": "Password set successfully"}


@router.post("/auth/push-token")
async def register_push_token(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    token = body.get("push_token", "")
    if token:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"push_token": token}})
    return {"message": "Push token registered"}


@router.get("/users/search")
async def search_users(q: str = "", user: dict = Depends(get_current_user)):
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
