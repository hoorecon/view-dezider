"""
Admin "User View" — read-only PII lookup with consent + immutable audit.

Access policy:
  • Super Admin: always allowed; can grant/revoke `can_view_pii` to admins.
  • Admin with `can_view_pii == True`: allowed.
  • Everyone else: 403.

A lookup requires BOTH the user's email AND WhatsApp number to match the same
account (stricter identity proof), a stated purpose, and an explicit NDA
acknowledgement. Every access is written to `pii_access_log` (immutable — no
update/delete endpoints). Admins see their own log; Super Admin sees all.
"""
import logging
import uuid
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger("pii_admin")
router = APIRouter(prefix="/admin/pii", tags=["PII Admin"])

PURPOSES = ["Support service", "Data Analytics", "Training Support", "Other"]


def _now():
    return datetime.now(timezone.utc)


def _norm_phone(p: Optional[str]) -> str:
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 10:
        digits = "91" + digits
    return digits


def _can_view_pii(user: dict) -> bool:
    role = user.get("role")
    if role == "super_admin":
        return True
    if role == "admin" and bool(user.get("can_view_pii")):
        return True
    return False


async def _require_pii(user: dict) -> dict:
    if not _can_view_pii(user):
        raise HTTPException(status_code=403, detail="You do not have PII-access permission.")
    return user


async def _require_super(user: dict) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super-admin access required.")
    return user


# ───────────────────────── Models ─────────────────────────
class GrantRequest(BaseModel):
    email: str
    grant: bool = True


class LookupRequest(BaseModel):
    email: str = Field(..., min_length=3)
    whatsapp_number: str = Field(..., min_length=6)
    purpose: str = Field(..., min_length=2)
    purpose_note: Optional[str] = Field(default=None, max_length=300)
    nda_ack: bool = False


# ───────────────────────── Permission management ─────────────────────────
@router.get("/permission")
async def my_pii_permission(user: dict = Depends(get_current_user)):
    """Whether the current admin can use the PII lookup."""
    return {"can_view_pii": _can_view_pii(user), "role": user.get("role")}


@router.get("/grants")
async def list_grants(user: dict = Depends(get_current_user)):
    await _require_super(user)
    cursor = db.users.find(
        {"role": "admin"},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1, "can_view_pii": 1},
    )
    admins = await cursor.to_list(length=500)
    for a in admins:
        a["can_view_pii"] = bool(a.get("can_view_pii"))
    return {"admins": admins, "purposes": PURPOSES}


@router.post("/grant")
async def set_grant(body: GrantRequest, user: dict = Depends(get_current_user)):
    await _require_super(user)
    target = await db.users.find_one({"email": body.email.lower().strip()}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=400, detail="PII access can only be granted to admins.")
    await db.users.update_one(
        {"user_id": target["user_id"]},
        {"$set": {"can_view_pii": bool(body.grant)}},
    )
    logger.info("can_view_pii=%s for %s by %s", body.grant, target["email"], user.get("email"))
    return {"success": True, "email": target["email"], "can_view_pii": bool(body.grant)}


# ───────────────────────── NDA text ─────────────────────────
@router.get("/nda")
async def get_nda(user: dict = Depends(get_current_user)):
    appearance = await db.app_settings.find_one({"key": "appearance"}, {"_id": 0}) or {}
    company = appearance.get("company_name") or "HOORECON IT-Sys Pvt Ltd"
    return {
        "company_name": company,
        "title": "PII Access — Confidentiality & NDA Acknowledgement",
        "body": [
            f"By proceeding, you confirm you are an authorised representative of {company} "
            "and have signed a Non-Disclosure Agreement (NDA) governing access to personal "
            "and sensitive user data (PII).",
            "You will access this information strictly for the stated business purpose "
            "(e.g., support, analytics or training) and for no other reason.",
            "You will not copy, export, share, or retain this data beyond what is necessary "
            "for the stated purpose, and you will comply with all applicable data-protection "
            "laws (including India's DPDP Act).",
            "Every access is logged with your identity, the user accessed, the purpose, and a "
            "timestamp. Misuse may lead to disciplinary, civil and/or criminal action.",
        ],
        "acknowledgement": "I have signed the NDA and accept these conditions.",
    }


# ───────────────────────── Lookup (read-only) ─────────────────────────
@router.post("/lookup")
async def lookup(body: LookupRequest, user: dict = Depends(get_current_user)):
    await _require_pii(user)
    if not body.nda_ack:
        raise HTTPException(status_code=400, detail="You must acknowledge the NDA to proceed.")
    if body.purpose not in PURPOSES:
        raise HTTPException(status_code=400, detail="Invalid purpose.")
    if body.purpose == "Other" and not (body.purpose_note or "").strip():
        raise HTTPException(status_code=400, detail="Please describe the purpose for 'Other'.")

    email = body.email.lower().strip()
    wa = _norm_phone(body.whatsapp_number)

    target = await db.users.find_one({"email": email}, {"_id": 0})
    matched = bool(target) and _norm_phone(target.get("whatsapp_number")) == wa and wa != ""

    # Audit EVERY attempt (success or failure) — immutable.
    audit = {
        "id": str(uuid.uuid4()),
        "viewer_id": user["user_id"],
        "viewer_email": user.get("email"),
        "viewer_role": user.get("role"),
        "lookup_email": email,
        "lookup_whatsapp": wa,
        "purpose": body.purpose,
        "purpose_note": (body.purpose_note or "").strip() or None,
        "matched": matched,
        "target_user_id": target.get("user_id") if matched else None,
        "created_at": _now(),
    }
    await db.pii_access_log.insert_one(dict(audit))

    if not matched:
        raise HTTPException(
            status_code=404,
            detail="No account matches that email AND WhatsApp number together.",
        )

    uid = target["user_id"]

    # Entitlements (Bought/Used/Left per SKU)
    ent_cursor = db.user_entitlements.find({"user_id": uid}, {"_id": 0})
    ents = await ent_cursor.to_list(length=100)
    entitlements = [
        {
            "sku_code": e.get("sku_code"),
            "bought": int(e.get("granted_qty") or 0),
            "used": int(e.get("consumed_qty") or 0),
            "left": int(e.get("balance") or 0),
        }
        for e in ents
    ]

    # Decisions (titles only — no full content)
    dec_cursor = db.decisions.find(
        {"user_id": uid}, {"_id": 0, "title": 1, "created_at": 1}
    ).sort("created_at", -1).limit(50)
    decisions = await dec_cursor.to_list(length=50)
    decision_titles = [
        {"title": d.get("title") or "(untitled)", "created_at": d.get("created_at")}
        for d in decisions
    ]
    decisions_count = await db.decisions.count_documents({"user_id": uid})

    return {
        "matched": True,
        "audit_id": audit["id"],
        "profile": {
            "user_id": uid,
            "name": target.get("name"),
            "email": target.get("email"),
            "whatsapp_number": target.get("whatsapp_number"),
            "whatsapp_verified": bool(target.get("whatsapp_verified")),
            "role": target.get("role", "user"),
            "user_type": target.get("user_type") or "free",
            "effective_user_type": target.get("effective_user_type"),
            "org_id": target.get("org_id"),
            "auth_method": target.get("auth_method", "email"),
            "created_at": target.get("created_at"),
        },
        "entitlements": entitlements,
        "decisions_count": decisions_count,
        "recent_decisions": decision_titles,
    }


# ───────────────────────── Access logs ─────────────────────────
def _serialize_log(rows):
    out = []
    for r in rows:
        r.pop("_id", None)
        out.append(r)
    return out


@router.get("/my-access-log")
async def my_access_log(user: dict = Depends(get_current_user)):
    await _require_pii(user)
    cursor = db.pii_access_log.find(
        {"viewer_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(200)
    rows = await cursor.to_list(length=200)
    return {"entries": rows}


@router.get("/access-log")
async def all_access_log(user: dict = Depends(get_current_user)):
    await _require_super(user)
    cursor = db.pii_access_log.find({}, {"_id": 0}).sort("created_at", -1).limit(500)
    rows = await cursor.to_list(length=500)
    return {"entries": rows}
