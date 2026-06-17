"""Referral Bonus Designer — SuperAdmin configurable + per-user payouts.

Math (from Virality Algo.xlsx):
  K = referral_rate × avg_refs × conversion_rate
  Reward modes: cash | coupon | karma_points | special_access

Defaults:
  L1=20%, L2=10%, L3=5% commission on first purchase.
  After first purchase, all halve (10/5/2.5%) until ALOS expires (default 365 days).
  100 KP = ₹10
  Coupon: 10–50% range, default 20%, validity 3 months
  Special Access: most attractive module of next-higher tier (ACM-driven)
  Auto-suggested split: 40% Cash + 30% Coupon + 20% KP + 10% Special-Access.
  AI re-balances per-user every 30 days based on redemption history.
  Cash payout requires UPI / bank details + 7-day refund window.
"""
import hashlib
import hmac
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user, ADMIN_ROLES, get_user_role


# Iter 129 — HMAC secret used to sign webhook → /credit calls.
# Set REFERRAL_WEBHOOK_SECRET in backend/.env for production.
REFERRAL_WEBHOOK_SECRET = os.getenv("REFERRAL_WEBHOOK_SECRET", "").strip()
HMAC_SKEW_SECONDS = 300  # 5-minute clock skew tolerance

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/referral", tags=["Referral Bonus"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_CONFIG: Dict[str, Any] = {
    "_id": "global",
    # Commissions (percent of paid amount)
    "l1_pct_first": 20.0,
    "l2_pct_first": 10.0,
    "l3_pct_first": 5.0,
    "subsequent_multiplier": 0.5,  # halves the rate
    "alos_days": 365,  # estimated avg lifespan after which subsequent multiplier no longer applies
    # Karma Points
    "karma_inr_value": 10.0,  # 100 KP = ₹10
    "karma_points_per_unit": 100,
    # Coupons
    "coupon_min_pct": 10.0,
    "coupon_max_pct": 50.0,
    "coupon_default_pct": 20.0,
    "coupon_validity_days": 90,  # 3 months
    # Special Access
    "special_access_strategy": "next_higher_tier_top_module",  # | fallback_2x_karma if already on top
    # AI Mode-Mix split (auto-suggested defaults)
    "split_cash": 40.0,
    "split_coupon": 30.0,
    "split_karma": 20.0,
    "split_special": 10.0,
    "ai_rebalance_days": 30,
    # Cash payout
    "cash_refund_window_days": 7,
    "updated_at": None,
}


async def _ensure_config():
    cfg = await db.referral_config.find_one({"_id": "global"})
    if not cfg:
        d = {**DEFAULT_CONFIG, "updated_at": _now()}
        await db.referral_config.insert_one(d)


# ─── Config (SuperAdmin) ─────────────────────────────────────────────
@router.get("/config")
async def get_config(user: dict = Depends(get_current_user)):
    await _ensure_config()
    cfg = await db.referral_config.find_one({"_id": "global"}, {"_id": 0})
    return cfg


@router.put("/config")
async def update_config(payload: Dict[str, Any], user: dict = Depends(get_current_user)):
    # Iter 129 — tightened to super_admin role only
    if get_user_role(user) != "super_admin":
        raise HTTPException(403, "Super-admin only")
    await _ensure_config()
    payload = {k: v for k, v in payload.items() if k in DEFAULT_CONFIG and k != "_id"}
    payload["updated_at"] = _now()
    await db.referral_config.update_one({"_id": "global"}, {"$set": payload})
    return {"ok": True, "config": await db.referral_config.find_one({"_id": "global"}, {"_id": 0})}


# ─── User Referral Profile (UPI/Bank details for cash opt-in) ────────
class BankDetailsIn(BaseModel):
    opt_in_cash: bool = False
    upi_id: Optional[str] = ""
    bank_acct_name: Optional[str] = ""
    bank_acct_number: Optional[str] = ""
    bank_acct_type: Optional[str] = "Savings"  # default
    bank_name: Optional[str] = ""
    bank_branch: Optional[str] = ""
    ifsc_code: Optional[str] = ""
    swift_code: Optional[str] = ""


@router.get("/me/profile")
async def get_my_profile(user: dict = Depends(get_current_user)):
    p = await db.referral_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {
        "user_id": user["user_id"],
        "referral_code": user.get("referral_code") or user["user_id"][:8].upper(),
        "opt_in_cash": False,
    }
    p.setdefault("karma_balance", 0)
    p.setdefault("cash_balance_inr", 0.0)
    return p


@router.put("/me/profile")
async def update_my_profile(p: BankDetailsIn, user: dict = Depends(get_current_user)):
    # Validate when opting-in for cash
    if p.opt_in_cash:
        missing = [k for k, v in {
            "upi_id (OR full bank details)": p.upi_id or (p.bank_acct_number and p.ifsc_code),
            "bank_acct_name": p.bank_acct_name if not p.upi_id else "ok",
        }.items() if not v]
        # Allow either UPI alone OR full bank details
        if not (p.upi_id or (p.bank_acct_number and p.ifsc_code and p.bank_acct_name)):
            raise HTTPException(400, "Provide UPI ID OR (Acct Name + Acct Number + IFSC) for cash opt-in")
    doc = {
        "user_id": user["user_id"],
        "referral_code": user.get("referral_code") or user["user_id"][:8].upper(),
        **p.model_dump(),
        "updated_at": _now(),
    }
    await db.referral_profiles.update_one({"user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    return {"ok": True}


# ─── Simulate / Preview Payout ───────────────────────────────────────
class SimulateIn(BaseModel):
    purchase_amount_inr: float
    level: int = 1  # 1|2|3
    is_first_purchase: bool = True
    referrer_since_days: int = 0  # for ALOS check
    mode_split: Optional[Dict[str, float]] = None  # override split if provided
    referee_tier_rank: Optional[int] = None  # for special access fallback logic (1=lowest..7=highest)
    user_on_highest_tier: bool = False


@router.post("/simulate")
async def simulate(payload: SimulateIn, user: dict = Depends(get_current_user)):
    await _ensure_config()
    cfg = await db.referral_config.find_one({"_id": "global"}, {"_id": 0})

    base_pct = {1: cfg["l1_pct_first"], 2: cfg["l2_pct_first"], 3: cfg["l3_pct_first"]}.get(payload.level, 0.0)
    # Multi-purchase rule: halve until ALOS expires
    if not payload.is_first_purchase and payload.referrer_since_days <= cfg["alos_days"]:
        base_pct *= cfg["subsequent_multiplier"]

    total_reward_inr = round(payload.purchase_amount_inr * base_pct / 100.0, 2)

    # Split into 4 modes
    split = payload.mode_split or {
        "cash": cfg["split_cash"], "coupon": cfg["split_coupon"],
        "karma": cfg["split_karma"], "special": cfg["split_special"],
    }
    s_sum = sum(split.values()) or 100.0
    split = {k: round(v * 100.0 / s_sum, 2) for k, v in split.items()}  # normalize to 100

    cash_inr = round(total_reward_inr * split["cash"] / 100.0, 2)
    coupon_value_inr = round(total_reward_inr * split["coupon"] / 100.0, 2)
    karma_value_inr = round(total_reward_inr * split["karma"] / 100.0, 2)
    karma_points = int(karma_value_inr * cfg["karma_points_per_unit"] / cfg["karma_inr_value"])
    special_value_inr = round(total_reward_inr * split["special"] / 100.0, 2)

    # Special access fallback when user is on highest tier already
    special_resolution = {"strategy": cfg["special_access_strategy"], "value_inr": special_value_inr}
    if payload.user_on_highest_tier:
        # Convert to 2x karma instead
        extra_kp = int((special_value_inr * 2) * cfg["karma_points_per_unit"] / cfg["karma_inr_value"])
        karma_points += extra_kp
        karma_value_inr = round(karma_value_inr + (special_value_inr * 2), 2)
        special_value_inr = 0.0
        special_resolution = {"strategy": "fallback_2x_karma", "added_karma_points": extra_kp}

    payout = {
        "applied_pct": base_pct,
        "total_reward_inr": total_reward_inr,
        "split_pct": split,
        "breakdown": {
            "cash_inr": cash_inr,
            "coupon_value_inr": coupon_value_inr,
            "coupon_default_pct": cfg["coupon_default_pct"],
            "coupon_validity_days": cfg["coupon_validity_days"],
            "karma_points": karma_points,
            "karma_value_inr": karma_value_inr,
            "special_access_value_inr": special_value_inr,
            "special_access_resolution": special_resolution,
        },
        "cash_refund_window_days": cfg["cash_refund_window_days"],
    }
    return payout


# ─── Credit Reward (called on successful purchase by referrer's referee) ─
class CreditIn(BaseModel):
    referrer_user_id: str
    referee_user_id: str
    purchase_amount_inr: float
    level: int = 1
    is_first_purchase: bool = True
    purchase_ref: Optional[str] = None
    user_on_highest_tier: bool = False


def _verify_hmac(raw_body: bytes, sig_header: Optional[str], ts_header: Optional[str]) -> Optional[str]:
    """Verify ed `X-Referral-Timestamp` and `X-Referral-Signature` headers.

    Returns None on success, error reason str on failure. The signature is
    `hex(hmac_sha256(secret, f"{ts}.{raw_body}"))`. Skew tolerance: 5 min.
    """
    if not REFERRAL_WEBHOOK_SECRET:
        return "REFERRAL_WEBHOOK_SECRET not configured"
    if not sig_header or not ts_header:
        return "Missing X-Referral-Timestamp / X-Referral-Signature headers"
    try:
        ts = int(ts_header)
    except ValueError:
        return "Bad timestamp"
    if abs(int(time.time()) - ts) > HMAC_SKEW_SECONDS:
        return "Timestamp skew exceeded"
    mac = hmac.new(
        REFERRAL_WEBHOOK_SECRET.encode("utf-8"),
        f"{ts}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(mac, sig_header):
        return "Signature mismatch"
    return None


@router.post("/credit")
async def credit(
    payload: CreditIn,
    request: Request,
    user: dict = Depends(get_current_user),
    x_referral_signature: Optional[str] = Header(default=None),
    x_referral_timestamp: Optional[str] = Header(default=None),
):
    """Credit a referral payout.

    Authorization paths (either is sufficient):
      1. SUPER_ADMIN role (manual/admin trigger) — for ops/CRM workflows
      2. Valid HMAC signature header (X-Referral-Signature + X-Referral-Timestamp)
         — for production payment-gateway webhook deliveries.
    """
    is_admin_path = get_user_role(user) == "super_admin"
    hmac_err: Optional[str] = None
    if not is_admin_path:
        raw = await request.body()
        hmac_err = _verify_hmac(raw, x_referral_signature, x_referral_timestamp)
        if hmac_err is not None:
            raise HTTPException(403, f"HMAC verification failed: {hmac_err}")

    sim = await simulate(SimulateIn(
        purchase_amount_inr=payload.purchase_amount_inr,
        level=payload.level,
        is_first_purchase=payload.is_first_purchase,
        user_on_highest_tier=payload.user_on_highest_tier,
    ), user)
    cfg = await db.referral_config.find_one({"_id": "global"}, {"_id": 0})

    # Karma + coupons + special are immediate; cash holds until refund-window passes.
    now = _now()
    credit_id = str(uuid.uuid4())
    # Karma credit
    await db.referral_profiles.update_one(
        {"user_id": payload.referrer_user_id},
        {"$inc": {"karma_balance": sim["breakdown"]["karma_points"]}},
        upsert=True,
    )
    # Coupon
    if sim["breakdown"]["coupon_value_inr"] > 0:
        await db.referral_coupons.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": payload.referrer_user_id,
            "value_inr": sim["breakdown"]["coupon_value_inr"],
            "pct_off": cfg["coupon_default_pct"],
            "expires_at": now + timedelta(days=cfg["coupon_validity_days"]),
            "used": False,
            "source_credit_id": credit_id,
            "created_at": now,
        })
    # Special Access entitlement
    if sim["breakdown"]["special_access_value_inr"] > 0:
        await db.referral_entitlements.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": payload.referrer_user_id,
            "strategy": sim["breakdown"]["special_access_resolution"]["strategy"],
            "value_inr": sim["breakdown"]["special_access_value_inr"],
            "source_credit_id": credit_id,
            "used": False,
            "created_at": now,
        })
    # Cash — held
    cash_avail_at = now + timedelta(days=cfg["cash_refund_window_days"])
    if sim["breakdown"]["cash_inr"] > 0:
        await db.referral_cash_ledger.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": payload.referrer_user_id,
            "amount_inr": sim["breakdown"]["cash_inr"],
            "status": "held",
            "hold_until": cash_avail_at,
            "source_credit_id": credit_id,
            "purchase_ref": payload.purchase_ref,
            "created_at": now,
        })

    await db.referral_credits.insert_one({
        "id": credit_id,
        "referrer_user_id": payload.referrer_user_id,
        "referee_user_id": payload.referee_user_id,
        "purchase_amount_inr": payload.purchase_amount_inr,
        "level": payload.level,
        "is_first_purchase": payload.is_first_purchase,
        "breakdown": sim["breakdown"],
        "created_at": now,
    })
    return {"ok": True, "credit_id": credit_id, "breakdown": sim["breakdown"]}


@router.get("/me/ledger")
async def my_ledger(user: dict = Depends(get_current_user)):
    karma = (await db.referral_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}).get("karma_balance", 0)
    coupons = await db.referral_coupons.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    entitlements = await db.referral_entitlements.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    cash = await db.referral_cash_ledger.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    credits = await db.referral_credits.find({"referrer_user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {
        "karma_balance": karma,
        "coupons": coupons,
        "special_access_entitlements": entitlements,
        "cash_ledger": cash,
        "credits": credits,
    }
