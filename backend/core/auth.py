import os
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from .database import db

SECRET_KEY = os.environ.get("SECRET_KEY", "view-dezider-secret-key-venture-buddha-2025")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_HIERARCHY = {"super_admin": 3, "co_admin": 2, "admin": 1, "user": 0}
ADMIN_ROLES = ["admin", "co_admin", "super_admin"]


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request):
    """Dependency that extracts and validates the JWT token from the request."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "user"),
            "org_id": user.get("org_id")
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_user_role(user: dict) -> str:
    return user.get("role", "user")
