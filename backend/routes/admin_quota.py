"""
Admin "Edit User Report Allocation" — correct a user's remaining (LEFT) report
quota per SKU.

Why: an admin once mis-configured an SKU's per-purchase quota (e.g. 1,000,000)
and needs to revoke / correct the over-allocated reports already granted to a
specific user. Normal users can never edit their own balances; this is a
privileged, audited, OTP-gated tool.

Access policy:
  • Super Admin: always allowed; can grant/revoke `can_edit_quota` to admins.
  • Admin with `can_edit_quota == True`: allowed.
  • Everyone else: 403.

Flow:
  1. Locate the user by BOTH email AND mobile (stricter identity proof).
  2. Request a WhatsApp OTP — sent to the SUPER ADMIN's registered WhatsApp to
     authorize the change (default: OTP required).
  3. Apply the new LEFT value for a chosen SKU. The target user is notified
     (WhatsApp + email) with the stated reason. Every change is written to the
     immutable `quota_admin_log`.
"""
import hashlib
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger("admin_quota")
router = APIRouter(prefix="/admin/quota", tags=["Admin Quota"])

OTP_TTL_MIN = 10
OTP_MAX_ATTEMPTS = 5
# Mirror the WhatsApp-OTP behaviour: only expose the code in the API response
# when delivery fails OR a non-production flag is explicitly set. Prod = secure.
EXPOSE_DEV_CODE = os.getenv("WA_OTP_EXPOSE_DEV_CODE", "false").strip().lower() == "true"


# ───────────────────────── helpers ─────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _role(u: dict) -> str:
    return (u.get("role") or "").lower()


def _norm_phone(p: Optional[str]) -> str:
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def _mask_phone(p: Optional[str]) -> str:
    d = _norm_phone(p)
    if len(d) < 4:
        return "••••"
    return "+" + d[:2] + "•" * max(0, len(d) - 6) + d[-4:]


def _gen_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def _load_actor(user: dict) -> dict:
    """Re-fetch the full user doc so permission flags are always fresh."""
    u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return u or user


def _can_edit_quota(u: dict) -> bool:
    r = _role(u)
    if r == "super_admin":
        return True
    if r in ("admin", "co_admin") and bool(u.get("can_edit_quota")):
        return True
    return False


async def _require_quota(user: dict) -> dict:
    u = await _load_actor(user)
    if not _can_edit_quota(u):
        raise HTTPException(403, "You do not have report-allocation edit permission.")
    return u


async def _require_super(user: dict) -> dict:
    u = await _load_actor(user)
    if _role(u) != "super_admin":
        raise HTTPException(403, "Super-admin access required.")
    return u


async def _super_admin_recipient() -> Optional[Dict[str, Any]]:
    """First super-admin that has a usable WhatsApp number — the OTP goes here."""
    cur = db.users.find(
        {"role": "super_admin"},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1, "whatsapp_number": 1},
    )
    async for s in cur:
        n = _norm_phone(s.get("whatsapp_number"))
        if n:
            return {"phone": n, "email": s.get("email"), "name": s.get("name")}
    return None


async def _send_whatsapp_safe(to: str, body: str) -> bool:
    try:
        from routes.whatsapp_otp import _send_whatsapp
        await _send_whatsapp(to, body)
        return True
    except Exception as e:  # best-effort
        logger.warning("quota whatsapp send failed: %s", e)
        return False


async def _send_email_safe(to: str, subject: str, html: str) -> bool:
    try:
        from routes.report_shares import _send_email
        await _send_email(to, subject, html)
        return True
    except Exception as e:  # best-effort (Resend may be unconfigured in dev)
        logger.warning("quota email send failed: %s", e)
        return False


async def _user_sku_rollup(user_id: str) -> List[Dict[str, Any]]:
    skus = await db.sku_catalog.find({}, {"_id": 0, "code": 1, "name": 1}).to_list(50)
    name_by_code = {s["code"]: s.get("name", s["code"]) for s in skus}
    rows = await db.user_entitlements.find(
        {"user_id": user_id, "status": "active"}, {"_id": 0}
    ).to_list(200)
    roll: Dict[str, Dict[str, Any]] = {}
    for d in rows:
        c = d["sku_code"]
        r = roll.setdefault(c, {"sku_code": c, "name": name_by_code.get(c, c),
                                "granted": 0, "consumed": 0, "balance": 0})
        r["granted"] += int(d.get("granted_qty") or 0)
        r["consumed"] += int(d.get("consumed_qty") or 0)
        r["balance"] += int(d.get("balance") or 0)
    # include zero rows for active SKUs the user has never bought
    for code, nm in name_by_code.items():
        roll.setdefault(code, {"sku_code": code, "name": nm,
                               "granted": 0, "consumed": 0, "balance": 0})
    order = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
    return sorted(roll.values(), key=lambda x: order.get(x["sku_code"], 99))


# ───────────────────────── models ─────────────────────────
class GrantRequest(BaseModel):
    email: str
    grant: bool = True


class LookupRequest(BaseModel):
    email: str = Field(..., min_length=3)
    mobile: str = Field(..., min_length=6)


class OtpRequest(BaseModel):
    target_user_id: str


class ApplyRequest(BaseModel):
    target_user_id: str
    sku_code: str
    new_left: int = Field(..., ge=0, le=1_000_000)
    reason: str = Field(..., min_length=3, max_length=400)
    otp: Optional[str] = None


# ───────────────────────── permission management ─────────────────────────
@router.get("/permission")
async def my_permission(user: dict = Depends(get_current_user)):
    u = await _load_actor(user)
    return {"can_edit_quota": _can_edit_quota(u), "role": _role(u)}


@router.get("/grants")
async def list_grants(user: dict = Depends(get_current_user)):
    await _require_super(user)
    cur = db.users.find(
        {"role": {"$in": ["admin", "co_admin"]}},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1, "can_edit_quota": 1},
    )
    admins = await cur.to_list(500)
    for a in admins:
        a["can_edit_quota"] = bool(a.get("can_edit_quota"))
    return {"admins": admins}


@router.post("/grant")
async def set_grant(body: GrantRequest, user: dict = Depends(get_current_user)):
    await _require_super(user)
    res = await db.users.update_one(
        {"email": body.email.strip().lower()},
        {"$set": {"can_edit_quota": bool(body.grant)}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "No user with that email.")
    return {"success": True, "email": body.email.strip().lower(), "can_edit_quota": bool(body.grant)}


# ───────────────────────── lookup ─────────────────────────
@router.post("/lookup")
async def lookup_user(body: LookupRequest, user: dict = Depends(get_current_user)):
    await _require_quota(user)
    email = body.email.strip().lower()
    mobile = _norm_phone(body.mobile)
    u = await db.users.find_one({"email": email}, {"_id": 0})
    if not u:
        raise HTTPException(404, "No user matches that email.")
    # mobile must match the same account (check whatsapp_number / phone / mobile)
    on_file = {
        _norm_phone(u.get("whatsapp_number")),
        _norm_phone(u.get("phone")),
        _norm_phone(u.get("mobile")),
    }
    on_file.discard("")
    if mobile not in on_file:
        raise HTTPException(404, "Email and mobile do not match the same account.")
    skus = await _user_sku_rollup(u["user_id"])
    return {
        "user": {
            "user_id": u["user_id"],
            "name": u.get("name"),
            "email": u.get("email"),
            "mobile_masked": _mask_phone(next(iter(on_file))),
            "whatsapp_verified": bool(u.get("whatsapp_verified")),
        },
        "skus": skus,
    }


# ───────────────────────── OTP (sent to Super Admin) ─────────────────────────
@router.post("/request-otp")
async def request_otp(body: OtpRequest, user: dict = Depends(get_current_user)):
    actor = await _require_quota(user)
    target = await db.users.find_one({"user_id": body.target_user_id}, {"_id": 0, "email": 1})
    if not target:
        raise HTTPException(404, "Target user not found.")
    recipient = await _super_admin_recipient()
    if not recipient:
        raise HTTPException(
            400,
            "No Super Admin WhatsApp number is configured to authorize this change. "
            "Ask a Super Admin to verify their WhatsApp number first.",
        )
    code = _gen_code()
    await db.admin_quota_otps.update_one(
        {"actor_user_id": actor["user_id"]},
        {"$set": {
            "actor_user_id": actor["user_id"],
            "target_user_id": body.target_user_id,
            "code_hash": _hash_code(code),
            "expires_at": _now() + timedelta(minutes=OTP_TTL_MIN),
            "attempts": 0,
            "created_at": _now(),
        }},
        upsert=True,
    )
    sent = await _send_whatsapp_safe(
        recipient["phone"],
        f"JELCOS AI — Authorization code {code}. Approves editing report allocation "
        f"for {target.get('email')} (requested by {actor.get('email')}). "
        f"Valid {OTP_TTL_MIN} min. Do not share if you did not expect this.",
    )
    return {
        "otp_required": True,
        "sent": sent,
        "sent_to_masked": _mask_phone(recipient["phone"]),
        "ttl_minutes": OTP_TTL_MIN,
        **({"dev_code": code} if (not sent or EXPOSE_DEV_CODE) else {}),
    }


# ───────────────────────── apply ─────────────────────────
@router.post("/apply")
async def apply_edit(body: ApplyRequest, user: dict = Depends(get_current_user)):
    actor = await _require_quota(user)
    sku_code = body.sku_code.upper().strip()
    sku = await db.sku_catalog.find_one({"code": sku_code}, {"_id": 0, "name": 1})
    if not sku:
        raise HTTPException(404, f"Unknown SKU {sku_code}.")
    target = await db.users.find_one({"user_id": body.target_user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Target user not found.")

    # OTP verification (default: required)
    otp_doc = await db.admin_quota_otps.find_one({"actor_user_id": actor["user_id"]})
    if not otp_doc:
        raise HTTPException(400, "Request an authorization OTP first.")
    if otp_doc.get("target_user_id") != body.target_user_id:
        raise HTTPException(400, "OTP was issued for a different user. Re-request.")
    exp = otp_doc.get("expires_at")
    if isinstance(exp, datetime) and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < _now():
        raise HTTPException(400, "Authorization code expired. Request a new one.")
    if int(otp_doc.get("attempts") or 0) >= OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many incorrect attempts. Request a new code.")
    if _hash_code((body.otp or "").strip()) != otp_doc.get("code_hash"):
        await db.admin_quota_otps.update_one(
            {"_id": otp_doc["_id"]}, {"$inc": {"attempts": 1}}
        )
        raise HTTPException(401, "Incorrect authorization code.")

    # ── apply: collapse active rows into one canonical row at new_left ──
    tuid = body.target_user_id
    rows = await db.user_entitlements.find(
        {"user_id": tuid, "sku_code": sku_code, "status": "active"}, {"_id": 0}
    ).to_list(200)
    consumed = sum(int(r.get("consumed_qty") or 0) for r in rows)
    old_left = sum(int(r.get("balance") or 0) for r in rows)
    old_granted = sum(int(r.get("granted_qty") or 0) for r in rows)
    new_left = int(body.new_left)
    new_granted = consumed + new_left

    if not rows:
        await db.user_entitlements.insert_one({
            "id": str(uuid.uuid4()), "user_id": tuid, "sku_code": sku_code,
            "balance": new_left, "granted_qty": new_left, "consumed_qty": 0,
            "source_order_id": "admin_edit", "granted_at": _now().isoformat(),
            "last_topup_at": _now().isoformat(), "last_used_at": None, "status": "active",
        })
    else:
        keep = rows[0]
        await db.user_entitlements.update_one(
            {"id": keep["id"]},
            {"$set": {"balance": new_left, "granted_qty": new_granted,
                      "consumed_qty": consumed, "last_topup_at": _now().isoformat()}},
        )
        for extra in rows[1:]:
            await db.user_entitlements.update_one(
                {"id": extra["id"]},
                {"$set": {"status": "archived_admin_edit", "balance": 0}},
            )

    # ── immutable audit ──
    await db.quota_admin_log.insert_one({
        "id": str(uuid.uuid4()),
        "actor_user_id": actor["user_id"], "actor_email": actor.get("email"),
        "target_user_id": tuid, "target_email": target.get("email"),
        "sku_code": sku_code, "sku_name": sku.get("name"),
        "old_left": old_left, "new_left": new_left,
        "old_granted": old_granted, "new_granted": new_granted,
        "reason": body.reason.strip(),
        "otp_verified": True,
        "at": _now().isoformat(),
    })

    # consume the OTP (one-time)
    await db.admin_quota_otps.delete_one({"actor_user_id": actor["user_id"]})

    # ── notify the target user (info-only, best-effort) ──
    sku_name = sku.get("name", sku_code)
    notify_text = (
        f"JELCOS AI: Your '{sku_name}' report allocation was updated by our team. "
        f"Remaining now: {new_left}. Reason: {body.reason.strip()}. "
        f"Contact support if you have questions."
    )
    wa_to = _norm_phone(target.get("whatsapp_number"))
    notified_wa = await _send_whatsapp_safe(wa_to, notify_text) if wa_to else False
    notified_email = False
    if target.get("email"):
        notified_email = await _send_email_safe(
            target["email"],
            "Your JELCOS AI report allocation was updated",
            f"<p>Hello {target.get('name') or ''},</p>"
            f"<p>Your <b>{sku_name}</b> report allocation was updated by our team.</p>"
            f"<p><b>Remaining now:</b> {new_left}<br/><b>Reason:</b> {body.reason.strip()}</p>"
            f"<p>If you have any questions, please contact support.</p>",
        )

    return {
        "success": True,
        "sku_code": sku_code,
        "old_left": old_left, "new_left": new_left,
        "notified": {"whatsapp": notified_wa, "email": notified_email},
        "skus": await _user_sku_rollup(tuid),
    }


# ───────────────────────── audit log (read) ─────────────────────────
@router.get("/log")
async def quota_log(user: dict = Depends(get_current_user)):
    actor = await _require_quota(user)
    q: Dict[str, Any] = {}
    if _role(actor) != "super_admin":
        q["actor_user_id"] = actor["user_id"]
    logs = await db.quota_admin_log.find(q, {"_id": 0}).sort("at", -1).to_list(200)
    return {"logs": logs}
