"""AI credits wallet routes — user balance/ledger + Super-Admin configuration & grants."""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core import ai_wallet
from core.auth import get_current_user, require_admin, require_super_admin
from core.database import db

router = APIRouter()
log = logging.getLogger("ai_wallet_routes")


# ─────────────────────────── user ───────────────────────────
@router.get("/ai-wallet")
async def my_wallet(user: dict = Depends(get_current_user)):
    return await ai_wallet.get_balance(user["user_id"])


@router.get("/ai-wallet/ledger")
async def my_wallet_ledger(limit: int = 30, user: dict = Depends(get_current_user)):
    return {"items": await ai_wallet.get_ledger(user["user_id"], min(max(limit, 1), 100))}


# ───────────────────────── admin ─────────────────────────
@router.get("/admin/ai-wallet/config")
async def get_wallet_config(user: dict = Depends(require_super_admin)):
    return await ai_wallet.get_config()


@router.put("/admin/ai-wallet/config")
async def update_wallet_config(body: Dict[str, Any], user: dict = Depends(require_super_admin)):
    try:
        return await ai_wallet.update_config(body, by=user.get("email") or user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _resolve_user_id(body: Dict[str, Any]) -> str:
    uid = body.get("user_id")
    if uid:
        return uid
    email = (body.get("email") or "").strip().lower()
    if email:
        u = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        if u:
            return u["user_id"]
    raise HTTPException(status_code=404, detail="User not found (provide a valid user_id or email).")


@router.post("/admin/ai-wallet/grant")
async def grant_credits(body: Dict[str, Any], user: dict = Depends(require_admin)):
    """Add or set a user's AI credits. body: {user_id|email, credits, mode:'add'|'set'}."""
    target = await _resolve_user_id(body)
    try:
        credits = float(body.get("credits"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="`credits` must be a number.")
    mode = body.get("mode", "add")
    kind = "set" if mode == "set" else "grant"
    res = await ai_wallet.grant(
        target, credits, by=user.get("email") or user["user_id"],
        note=body.get("note") or ("Set by admin" if kind == "set" else "Granted by admin"),
        kind=kind,
    )
    return {"user_id": target, **res}


@router.get("/admin/ai-wallet/users")
async def list_wallets(limit: int = 100, user: dict = Depends(require_admin)):
    wallets = await db.ai_wallets.find({}, {"_id": 0}).sort("updated_at", -1).limit(min(max(limit, 1), 500)).to_list(500)
    # attach email/name
    ids = [w["user_id"] for w in wallets]
    users = {}
    if ids:
        async for u in db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "user_id": 1, "email": 1, "name": 1}):
            users[u["user_id"]] = u
    for w in wallets:
        u = users.get(w["user_id"], {})
        w["email"] = u.get("email", "")
        w["name"] = u.get("name", "")
        w["balance"] = round(float(w.get("balance", 0)), 2)
    return {"items": wallets}
