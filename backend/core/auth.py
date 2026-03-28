"""Shared authentication utilities for modular routes."""
import os
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Depends
from jose import JWTError, jwt
from passlib.context import CryptContext
from .database import db

SECRET_KEY = os.environ.get("SECRET_KEY", "view-dezider-secret-key-venture-buddha-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_HIERARCHY = {"super_admin": 3, "co_admin": 2, "admin": 1, "user": 0}
ADMIN_ROLES = ["admin", "co_admin", "super_admin"]

ORG_ROLE_HIERARCHY = {"org_super_admin": 3, "org_co_admin": 2, "org_admin": 1, "org_member": 0}
ORG_ADMIN_ROLES = ["org_admin", "org_co_admin", "org_super_admin"]


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request) -> dict:
    """Extract and validate user from session token (cookie or header)."""
    session_token = None
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    return user_doc


def get_user_role(user: dict) -> str:
    return user.get("role", "user")


def get_role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)


def get_org_role_level(role: str) -> int:
    return ORG_ROLE_HIERARCHY.get(role, 0)


async def require_admin(user: dict = Depends(get_current_user)):
    """Require at least admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_co_admin(user: dict = Depends(get_current_user)):
    """Require at least co_admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 2:
        raise HTTPException(status_code=403, detail="Co-Admin access required")
    return user


async def require_super_admin(user: dict = Depends(get_current_user)):
    """Require super_admin role"""
    role = get_user_role(user)
    if get_role_level(role) < 3:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user
