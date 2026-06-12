"""
Payment Admin + Coupons + OrgType Master
=========================================
Single-file backend module that adds three coordinated capabilities:

1.  ORG TYPE MASTER  — central canonical list of org-type values used across
    Decision Flow, Contacts, Coupons, Reports etc. Seeded from the existing
    6-card Decision-Flow vocabulary on first boot.

2.  GLOBAL "SKIP PAYMENT" TOGGLE — admin can force-bypass Razorpay redirects
    for ALL paid flows (Decision Flow SKUs, Subscriptions, Top-ups) while
    Razorpay credentials are being procured for production testing.

3.  COUPONS (Admin-managed + public validate / redeem) — port of the legacy
    MySQL SP_GetDiscount with these enhancements:
      - Stored in Mongo (coupons collection).
      - Per-user usage tracked in `coupon_usages` so the per-user cap works.
      - NEW `applicable_org_types` filter (multi-select; empty = all).
      - Returns the resolved net payable amount and a structured `remarks`
        code (kept compatible with [ERR-#n] / [MSG-#n] tokens from the SP).
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Request
from dotenv import load_dotenv

from core.database import db
from core.auth import get_current_user

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# ORG TYPE MASTER
# =============================================================================
# Seeded from /app/frontend/app/tools/new-decision.tsx ACTING_AS array so the
# vocabulary stays identical to the 6 Decision-Flow cards. Admins can add more
# at runtime via /api/admin/org-types.
DEFAULT_ORG_TYPES: List[Dict[str, Any]] = [
    {"key": "INDIVIDUAL",    "label": "Individual",              "icon": "person",        "color": "#6366F1", "is_org": False, "active": True, "sort_order": 1, "description": "Self / personal"},
    {"key": "FAMILY",        "label": "Family",                  "icon": "people",        "color": "#EC4899", "is_org": False, "active": True, "sort_order": 2, "description": "Family / household"},
    {"key": "BUSINESS_ORG",  "label": "Business Organization",   "icon": "business",      "color": "#0EA5E9", "is_org": True,  "active": True, "sort_order": 3, "description": "Company / startup / SMB"},
    {"key": "ACADEMIC_ORG",  "label": "Academic Organization",   "icon": "school",        "color": "#F59E0B", "is_org": True,  "active": True, "sort_order": 4, "description": "School / college / research"},
    {"key": "NONPROFIT_ORG", "label": "Non-profit Organization", "icon": "heart",         "color": "#10B981", "is_org": True,  "active": True, "sort_order": 5, "description": "NGO / charity / foundation"},
    {"key": "ASSOCIATION",   "label": "Association",             "icon": "people-circle", "color": "#F43F5E", "is_org": True,  "active": True, "sort_order": 6, "description": "Society / club / housing"},
    {"key": "GOVERNMENT",    "label": "Government",              "icon": "globe",         "color": "#8B5CF6", "is_org": True,  "active": True, "sort_order": 7, "description": "Public / policy / civic"},
]


async def _ensure_org_types_seed() -> None:
    """Idempotent seeder — only inserts a key if it doesn't already exist.
    Also backfills `description` (and the seed `sort_order`) on legacy rows
    that pre-date those fields, without touching admin-edited values."""
    for item in DEFAULT_ORG_TYPES:
        await db.org_types_master.update_one(
            {"key": item["key"]},
            {"$setOnInsert": {**item, "created_at": datetime.now(timezone.utc).isoformat(), "is_system": True}},
            upsert=True,
        )
        await db.org_types_master.update_one(
            {"key": item["key"], "description": {"$exists": False}},
            {"$set": {"description": item["description"], "sort_order": item["sort_order"]}},
        )


@router.get("/org-types")
async def list_org_types_public(user: dict = Depends(get_current_user)):
    """Public (auth) endpoint — used by Contacts, Decision Flow, Coupon UI, etc."""
    await _ensure_org_types_seed()
    docs = await db.org_types_master.find(
        {"active": True}, {"_id": 0}
    ).sort([("sort_order", 1), ("label", 1)]).to_list(200)
    return docs


def _require_admin(user: dict) -> None:
    role = (user.get("role") or "").lower()
    if role not in {"admin", "superadmin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin privilege required")


@router.get("/admin/org-types")
async def list_org_types_admin(user: dict = Depends(get_current_user)):
    _require_admin(user)
    await _ensure_org_types_seed()
    docs = await db.org_types_master.find({}, {"_id": 0}).sort([("sort_order", 1)]).to_list(500)
    return docs


@router.post("/admin/org-types")
async def create_org_type(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    key = (body.get("key") or "").strip().upper().replace(" ", "_")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    existing = await db.org_types_master.find_one({"key": key})
    if existing:
        raise HTTPException(status_code=409, detail="Org type with this key already exists")
    doc = {
        "key": key,
        "label": body.get("label") or key.title().replace("_", " "),
        "icon": body.get("icon") or "ellipse",
        "color": body.get("color") or "#64748B",
        "description": (body.get("description") or "").strip(),
        "is_org": bool(body.get("is_org", True)),
        "active": True,
        "sort_order": int(body.get("sort_order") or 99),
        "is_system": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("user_id"),
    }
    await db.org_types_master.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/admin/org-types/{key}")
async def update_org_type(key: str, request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    allowed = ["label", "icon", "color", "description", "is_org", "active", "sort_order"]
    update = {k: body[k] for k in allowed if k in body}
    if not update:
        raise HTTPException(status_code=400, detail="No mutable fields supplied")
    res = await db.org_types_master.update_one({"key": key}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Org type not found")
    doc = await db.org_types_master.find_one({"key": key}, {"_id": 0})
    return doc


@router.delete("/admin/org-types/{key}")
async def delete_org_type(key: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    doc = await db.org_types_master.find_one({"key": key})
    if not doc:
        raise HTTPException(status_code=404, detail="Org type not found")
    if doc.get("is_system"):
        # System rows can only be soft-disabled
        await db.org_types_master.update_one({"key": key}, {"$set": {"active": False}})
        return {"status": "disabled", "key": key, "reason": "system org type cannot be hard-deleted"}
    await db.org_types_master.delete_one({"key": key})
    return {"status": "deleted", "key": key}


# =============================================================================
# GLOBAL PAYMENT-SKIP TOGGLE
# =============================================================================
# Stored as a single document in `app_settings` collection with _key='payments'.
# When `skip_payment_all_flows=True` the FE must treat any paid flow as
# auto-granted and call `/payments/skip-grant` instead of opening Razorpay.

PAYMENT_SETTING_KEY = "payments_global"


async def _get_payment_settings() -> Dict[str, Any]:
    doc = await db.app_settings.find_one({"_key": PAYMENT_SETTING_KEY}, {"_id": 0})
    if not doc:
        doc = {
            "_key": PAYMENT_SETTING_KEY,
            "skip_payment_all_flows": False,
            "skip_payment_reason": "",
            "skip_payment_enabled_at": None,
            "skip_payment_enabled_by": None,
        }
        await db.app_settings.insert_one({**doc, "_key": PAYMENT_SETTING_KEY})
    doc.pop("_key", None)
    return doc


@router.get("/admin/payment-settings")
async def admin_get_payment_settings(user: dict = Depends(get_current_user)):
    _require_admin(user)
    return await _get_payment_settings()


@router.put("/admin/payment-settings")
async def admin_update_payment_settings(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    update: Dict[str, Any] = {}
    if "skip_payment_all_flows" in body:
        flag = bool(body["skip_payment_all_flows"])
        update["skip_payment_all_flows"] = flag
        update["skip_payment_enabled_at"] = datetime.now(timezone.utc).isoformat() if flag else None
        update["skip_payment_enabled_by"] = user.get("user_id") if flag else None
    if "skip_payment_reason" in body:
        update["skip_payment_reason"] = str(body.get("skip_payment_reason") or "")[:500]
    if not update:
        raise HTTPException(status_code=400, detail="No payment settings supplied")
    await db.app_settings.update_one(
        {"_key": PAYMENT_SETTING_KEY},
        {"$set": update},
        upsert=True,
    )
    # Audit log
    await db.audit_log.insert_one({
        "actor_id": user.get("user_id"),
        "action": "payment_settings_update",
        "patch": update,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    return await _get_payment_settings()


@router.get("/payment-settings")
async def public_get_payment_settings(user: dict = Depends(get_current_user)):
    """
    Exposed to ALL authenticated users so the FE can decide whether to render
    the Razorpay button or a "Skip payment (Admin override)" CTA. Returns only
    a tiny slice — never the audit fields.
    """
    s = await _get_payment_settings()
    return {"skip_payment_all_flows": bool(s.get("skip_payment_all_flows", False))}


# =============================================================================
# COUPONS — Admin CRUD + Public validate / redeem
# =============================================================================

VALID_DISCOUNT_TYPES = {"Percentage", "Value", "NetValue"}
VALID_USER_TYPES = {"User", "Org", "Expert"}


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ----- Admin CRUD ------------------------------------------------------------

@router.get("/admin/coupons")
async def list_coupons(user: dict = Depends(get_current_user)):
    _require_admin(user)
    docs = await db.coupons.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@router.get("/admin/coupons/{code}")
async def get_coupon(code: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    doc = await db.coupons.find_one({"coupon_code": code.upper()}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return doc


@router.post("/admin/coupons")
async def create_coupon(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    code = (body.get("coupon_code") or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="coupon_code is required")
    if await db.coupons.find_one({"coupon_code": code}):
        raise HTTPException(status_code=409, detail=f"Coupon '{code}' already exists")

    discount_type = body.get("discount_type", "Percentage")
    if discount_type not in VALID_DISCOUNT_TYPES:
        raise HTTPException(status_code=400, detail=f"discount_type must be one of {sorted(VALID_DISCOUNT_TYPES)}")
    user_type = body.get("user_type") or None
    if user_type and user_type not in VALID_USER_TYPES:
        raise HTTPException(status_code=400, detail=f"user_type must be one of {sorted(VALID_USER_TYPES)}")

    doc = {
        "coupon_code": code,
        "coupon_desc": body.get("coupon_desc", ""),
        "user_type": user_type,
        "discount_type": discount_type,
        "discount_value": float(body.get("discount_value") or 0),
        "max_usage_limit": (int(body["max_usage_limit"]) if body.get("max_usage_limit") not in (None, "") else None),
        "current_usage_limit": 0,
        "max_usage_limit_per_user": (int(body["max_usage_limit_per_user"]) if body.get("max_usage_limit_per_user") not in (None, "") else None),
        "valid_from": body.get("valid_from") or _now().isoformat(),
        "valid_until": body.get("valid_until"),
        "is_active": body.get("is_active") or "Y",
        # NEW — multi-select of org_type keys from org_types_master; [] or None = applicable to all
        "applicable_org_types": [str(k).upper() for k in (body.get("applicable_org_types") or [])] or None,
        # NEW — restrict to specific flows: ['DECISION_FLOW','SUBSCRIPTION','TOPUP','SKU']; empty = any
        "applicable_flows": [str(f).upper() for f in (body.get("applicable_flows") or [])] or None,
        "created_at": _now().isoformat(),
        "created_by": user.get("user_id"),
        "updated_at": _now().isoformat(),
    }
    await db.coupons.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/admin/coupons/{code}")
async def update_coupon(code: str, request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    body = await request.json()
    code = code.upper()
    existing = await db.coupons.find_one({"coupon_code": code})
    if not existing:
        raise HTTPException(status_code=404, detail="Coupon not found")

    allowed = [
        "coupon_desc", "user_type", "discount_type", "discount_value",
        "max_usage_limit", "max_usage_limit_per_user",
        "valid_from", "valid_until", "is_active",
        "applicable_org_types", "applicable_flows",
    ]
    update: Dict[str, Any] = {}
    for k in allowed:
        if k in body:
            update[k] = body[k]
    if "discount_type" in update and update["discount_type"] not in VALID_DISCOUNT_TYPES:
        raise HTTPException(status_code=400, detail="invalid discount_type")
    if "user_type" in update and update["user_type"] and update["user_type"] not in VALID_USER_TYPES:
        raise HTTPException(status_code=400, detail="invalid user_type")
    if "applicable_org_types" in update:
        update["applicable_org_types"] = [str(k).upper() for k in (update["applicable_org_types"] or [])] or None
    if "applicable_flows" in update:
        update["applicable_flows"] = [str(f).upper() for f in (update["applicable_flows"] or [])] or None
    if "discount_value" in update:
        update["discount_value"] = float(update["discount_value"])
    if "max_usage_limit" in update and update["max_usage_limit"] in ("", None):
        update["max_usage_limit"] = None
    elif "max_usage_limit" in update:
        update["max_usage_limit"] = int(update["max_usage_limit"])
    if "max_usage_limit_per_user" in update and update["max_usage_limit_per_user"] in ("", None):
        update["max_usage_limit_per_user"] = None
    elif "max_usage_limit_per_user" in update:
        update["max_usage_limit_per_user"] = int(update["max_usage_limit_per_user"])

    update["updated_at"] = _now().isoformat()
    update["updated_by"] = user.get("user_id")
    await db.coupons.update_one({"coupon_code": code}, {"$set": update})
    doc = await db.coupons.find_one({"coupon_code": code}, {"_id": 0})
    return doc


@router.delete("/admin/coupons/{code}")
async def delete_coupon(code: str, user: dict = Depends(get_current_user)):
    _require_admin(user)
    # Soft-delete via is_active='N' (preserves usage history)
    res = await db.coupons.update_one(
        {"coupon_code": code.upper()},
        {"$set": {"is_active": "N", "updated_at": _now().isoformat(), "updated_by": user.get("user_id")}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"status": "deactivated", "coupon_code": code.upper()}


# ----- Public validate + redeem  --------------------------------------------

@router.post("/coupons/validate")
async def validate_coupon(request: Request, user: dict = Depends(get_current_user)):
    """Public (auth) coupon check. Thin wrapper over evaluate_coupon()."""
    body = await request.json()
    return await evaluate_coupon(
        code=(body.get("coupon_code") or "").strip().upper(),
        list_price=float(body.get("list_price") or 0),
        user_id=user.get("user_id"),
        org_type=(body.get("org_type") or "").upper() or None,
        flow=(body.get("flow") or "").upper() or None,
    )


async def evaluate_coupon(
    *,
    code: str,
    list_price: float,
    user_id: Optional[str],
    org_type: Optional[str] = None,
    flow: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Port of SP_GetDiscount with two enhancements:
      • per-user usage is read from `coupon_usages` (was an input arg in the SP).
      • `applicable_org_types` is honoured (new field).
    Reusable from both the public endpoint and the server-side checkout.
    Output: full SP-shape struct (see end of function).
    """
    code = (code or "").strip().upper()
    list_price = float(list_price or 0)
    org_type = (org_type or "").upper() or None
    flow = (flow or "").upper() or None

    out: Dict[str, Any] = {
        "coupon_code": code,
        "coupon_desc": None,
        "user_type": None,
        "discount_type": None,
        "discount_value": 0,
        "max_usage_limit": None,
        "current_usage": None,
        "max_usage_limit_per_user": None,
        "valid_from": None,
        "valid_until": None,
        "applicable_org_types": None,
        "applicable_flows": None,
        "net_payable_amount": list_price,
        "remarks": None,
        "remarks_code": None,
        "valid": False,
    }

    if not code or list_price <= 0:
        out["remarks"] = "[ERR-#0] coupon_code and positive list_price are required"
        out["remarks_code"] = "ERR-0"
        return out

    coupon = await db.coupons.find_one({"coupon_code": code}, {"_id": 0})

    if not coupon:
        out["remarks"] = "[ERR-#1] Invalid Coupon Code !"
        out["remarks_code"] = "ERR-1"
        return out

    # Fill descriptive fields regardless of validity (mirrors SP behaviour)
    out["coupon_desc"] = coupon.get("coupon_desc")
    out["user_type"] = coupon.get("user_type")
    out["discount_type"] = coupon.get("discount_type")
    out["discount_value"] = float(coupon.get("discount_value") or 0)
    out["max_usage_limit"] = coupon.get("max_usage_limit")
    out["current_usage"] = int(coupon.get("current_usage_limit") or 0)
    out["max_usage_limit_per_user"] = coupon.get("max_usage_limit_per_user")
    out["valid_from"] = coupon.get("valid_from")
    out["valid_until"] = coupon.get("valid_until")
    out["applicable_org_types"] = coupon.get("applicable_org_types")
    out["applicable_flows"] = coupon.get("applicable_flows")

    # --- 1. Active flag ------------------------------------------------------
    if (coupon.get("is_active") or "N") != "Y":
        out["remarks"] = "[ERR-#2] Valid, but Currently Inactive Coupon Code !"
        out["remarks_code"] = "ERR-2"
        return out

    today = _now()
    vf = _parse_dt(coupon.get("valid_from"))
    vu = _parse_dt(coupon.get("valid_until"))

    # --- 2. Not yet started --------------------------------------------------
    if vf and vf > today:
        out["remarks"] = "[ERR-#3] Valid, Currently Active - but Yet to be enabled Coupon Code !"
        out["remarks_code"] = "ERR-3"
        return out

    # --- 3. Expired ----------------------------------------------------------
    if vu and today > vu:
        out["remarks"] = "[ERR-#4] Valid, Currently Active - but Date-Expired Coupon Code !"
        out["remarks_code"] = "ERR-4"
        return out

    # --- 4. Global usage cap -------------------------------------------------
    mul = coupon.get("max_usage_limit")
    cul = int(coupon.get("current_usage_limit") or 0)
    if mul is not None and cul >= int(mul):
        out["remarks"] = "[ERR-#5] Valid, Currently Active, Sales-Enabled Coupon Code - but Max Usage Limit has reached !"
        out["remarks_code"] = "ERR-5"
        return out

    # --- 5. Per-user cap (DB-derived, replaces SP's p_usageCountForThisUser) -
    mupu = coupon.get("max_usage_limit_per_user")
    if mupu is not None:
        per_user_used = await db.coupon_usages.count_documents({
            "coupon_code": code,
            "user_id": user_id,
        })
        if per_user_used >= int(mupu):
            out["remarks"] = "[ERR-#6] Valid, Currently Active, Sales-Enabled Coupon Code - but Max Usage Limit Per User has reached !"
            out["remarks_code"] = "ERR-6"
            out["current_user_usage"] = per_user_used
            return out

    # --- 6. NEW: applicable_org_types filter --------------------------------
    apply_org_types = coupon.get("applicable_org_types")
    if apply_org_types:
        if not org_type:
            out["remarks"] = "[ERR-#8] Coupon restricted to certain Org Types; please supply org_type"
            out["remarks_code"] = "ERR-8"
            return out
        if org_type not in apply_org_types:
            out["remarks"] = f"[ERR-#9] Coupon not applicable to Org Type '{org_type}'"
            out["remarks_code"] = "ERR-9"
            return out

    # --- 7. NEW: applicable_flows filter ------------------------------------
    apply_flows = coupon.get("applicable_flows")
    if apply_flows and flow and flow not in apply_flows:
        out["remarks"] = f"[ERR-#10] Coupon not applicable to flow '{flow}'"
        out["remarks_code"] = "ERR-10"
        return out

    # --- 8. Compute net payable amount --------------------------------------
    dtype = coupon.get("discount_type")
    dval = float(coupon.get("discount_value") or 0)

    if dtype == "Percentage":
        if dval > 100:
            dval = 100.0
        net = list_price * (1 - (dval / 100.0))
        out["remarks"] = "[MSG-#1] Successfully Applied the Coupon Code of 'Discount Percentage' type"
        out["remarks_code"] = "MSG-1"
    elif dtype == "Value":
        net = list_price - dval
        if net < 0:
            net = 0.0
        out["remarks"] = "[MSG-#2] Successfully Applied the Coupon Code of 'Discount Value' type"
        out["remarks_code"] = "MSG-2"
    elif dtype == "NetValue":
        net = dval
        out["remarks"] = "[MSG-#3] Successfully Applied the Coupon Code of 'NetValue' type"
        out["remarks_code"] = "MSG-3"
    else:
        out["remarks"] = "[ERR-#7] Invalid Discount Type for the given Coupon Code !"
        out["remarks_code"] = "ERR-7"
        return out

    # Final shape — round to 2 decimal places to match Razorpay paise math
    out["net_payable_amount"] = round(float(net), 2)
    out["discount_value"] = dval
    out["valid"] = True
    return out


@router.post("/coupons/redeem")
async def redeem_coupon(request: Request, user: dict = Depends(get_current_user)):
    """
    Called AFTER a successful Razorpay capture (or skip-grant). Atomically
    increments `current_usage_limit` and records per-user usage. Thin wrapper
    over record_coupon_redemption().
    """
    body = await request.json()
    code = (body.get("coupon_code") or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="coupon_code is required")
    return await record_coupon_redemption(
        code=code,
        user_id=user.get("user_id"),
        org_id=user.get("org_id"),
        order_id=body.get("order_id"),
        flow=(body.get("flow") or "").upper() or None,
        list_price=float(body.get("list_price") or 0),
        net_payable_amount=float(body.get("net_payable_amount") or 0),
    )


async def record_coupon_redemption(
    *,
    code: str,
    user_id: Optional[str],
    org_id: Optional[str] = None,
    order_id: Optional[str] = None,
    flow: Optional[str] = None,
    list_price: float = 0,
    net_payable_amount: float = 0,
) -> Dict[str, Any]:
    """Increment global usage + record a per-user usage row. Reusable server-side."""
    code = (code or "").strip().upper()
    coupon = await db.coupons.find_one({"coupon_code": code})
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    await db.coupons.update_one(
        {"coupon_code": code},
        {"$inc": {"current_usage_limit": 1}, "$set": {"updated_at": _now().isoformat()}},
    )
    usage_doc = {
        "coupon_code": code,
        "user_id": user_id,
        "org_id": org_id,
        "order_id": order_id,
        "flow": (flow or "").upper() or None,
        "list_price": float(list_price or 0),
        "net_payable_amount": float(net_payable_amount or 0),
        "used_at": _now().isoformat(),
    }
    await db.coupon_usages.insert_one(usage_doc)
    usage_doc.pop("_id", None)
    return {"status": "redeemed", **usage_doc}


@router.get("/coupons/my-usage/{code}")
async def my_coupon_usage(code: str, user: dict = Depends(get_current_user)):
    """How many times the current user has used this coupon (for FE preview)."""
    code = code.upper()
    n = await db.coupon_usages.count_documents({"coupon_code": code, "user_id": user.get("user_id")})
    return {"coupon_code": code, "user_id": user.get("user_id"), "usage_count": n}


# =============================================================================
# SKIP-GRANT ENDPOINT — used when skip_payment_all_flows == True
# =============================================================================

@router.post("/payments/skip-grant")
async def payments_skip_grant(request: Request, user: dict = Depends(get_current_user)):
    """
    Server-side enforced bypass — must verify the toggle is ON. Records a
    pseudo-order so downstream features (credits, SKU unlocks) behave the same
    as a normal Razorpay capture. NEVER trust an FE-supplied flag alone.

    Body: {
      flow: 'DECISION_FLOW' | 'SUBSCRIPTION' | 'TOPUP' | 'SKU',
      sku_id?: str, plan_id?: str, amount: number (rupees),
      coupon_code?: str, net_payable_amount?: number, list_price?: number,
      metadata?: dict
    }
    """
    s = await _get_payment_settings()
    if not s.get("skip_payment_all_flows"):
        raise HTTPException(status_code=403, detail="Payment skip is currently disabled by Admin")

    body = await request.json()
    flow = (body.get("flow") or "DECISION_FLOW").upper()
    pseudo_order_id = f"SKIP-{_now().strftime('%Y%m%d%H%M%S')}-{(user.get('user_id') or 'anon')[:8]}"
    grant = {
        "order_id": pseudo_order_id,
        "user_id": user.get("user_id"),
        "org_id": user.get("org_id"),
        "flow": flow,
        "sku_id": body.get("sku_id"),
        "plan_id": body.get("plan_id"),
        "list_price": float(body.get("list_price") or body.get("amount") or 0),
        "net_payable_amount": float(body.get("net_payable_amount") or body.get("amount") or 0),
        "amount_charged": 0.0,
        "currency": "INR",
        "payment_method": "ADMIN_SKIP",
        "coupon_code": (body.get("coupon_code") or "").upper() or None,
        "skip_reason": s.get("skip_payment_reason") or "Admin payment skip enabled",
        "metadata": body.get("metadata") or {},
        "status": "granted",
        "created_at": _now().isoformat(),
    }
    await db.payment_grants.insert_one(grant)

    # If a coupon was supplied, redeem it server-side too so usage counters stay consistent
    if grant["coupon_code"]:
        try:
            await db.coupons.update_one(
                {"coupon_code": grant["coupon_code"]},
                {"$inc": {"current_usage_limit": 1}, "$set": {"updated_at": _now().isoformat()}},
            )
            await db.coupon_usages.insert_one({
                "coupon_code": grant["coupon_code"],
                "user_id": user.get("user_id"),
                "org_id": user.get("org_id"),
                "order_id": pseudo_order_id,
                "flow": flow,
                "list_price": grant["list_price"],
                "net_payable_amount": grant["net_payable_amount"],
                "used_at": _now().isoformat(),
                "via": "skip_grant",
            })
        except Exception as e:
            logger.warning("skip-grant coupon redeem failed: %s", e)

    grant.pop("_id", None)
    return grant


@router.get("/payments/skip-grant/history")
async def payments_skip_history(user: dict = Depends(get_current_user)):
    """Current user's own skip-grant orders (e.g. for receipt list)."""
    docs = await db.payment_grants.find(
        {"user_id": user.get("user_id")}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return docs
