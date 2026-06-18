"""WOWO ACM v2 — Unified administration endpoints.

Bundles four small concerns introduced in the v2 architecture sweep so they
stay together and load on boot via a single import line in server.py:

  /api/acm-v2/resolver-config         Admin GET/PUT of the resolver tuning knobs
                                       (trial days, fallback chain, plan rename map)
  /api/acm-v2/trial-payments          Admin list of trial_payment_instruments
                                       (saved cards/UPI captured at trial opt-in)
  /api/acm-v2/tier-segment-mapping    Admin CRUD: which Customer Segments are
                                       reachable from each 7-Chakra Tier
  /api/geo/countries                  Public list (idempotently seeded)
  /api/geo/states/{country_code}      Public per-country state list
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user, get_user_role, ADMIN_ROLES

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ACM v2 — Resolver, Trials, Geography"])


def _require_admin(user: dict):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")


# ============================================================
# 1. ACM RESOLVER CONFIG (admin-tunable)
# ============================================================
DEFAULT_RESOLVER_CONFIG = {
    "trial_days": {"starter_trial": 1, "pro_trial": 3, "premium_trial": 7},
    "plan_alias": {
        "basic": "starter", "enterprise": "premium",  # legacy → ACM
    },
    "auto_convert_default": False,
    "require_payment_for_trial": True,
    "on_demand_thresholds": {"retail_min_inr": 0, "bulk_min_inr": 5000},
    "fallback_to_free_on_expiry": True,
}


@router.get("/acm-v2/resolver-config")
async def get_resolver_config(user: dict = Depends(get_current_user)):
    """Admin — return the live resolver config (with defaults filled in)."""
    _require_admin(user)
    row = await db.acm_meta.find_one({"key": "resolver_config"}, {"_id": 0}) or {}
    merged = {**DEFAULT_RESOLVER_CONFIG, **(row.get("config") or {})}
    return {"config": merged, "updated_at": row.get("updated_at")}


@router.put("/acm-v2/resolver-config")
async def update_resolver_config(request: Request, user: dict = Depends(get_current_user)):
    """Admin — persist resolver tuning knobs. Validates basic shape."""
    _require_admin(user)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Body must be a JSON object")
    cfg = {**DEFAULT_RESOLVER_CONFIG, **(body.get("config") or {})}
    # Coerce trial_days to ints
    td = cfg.get("trial_days") or {}
    if not isinstance(td, dict):
        raise HTTPException(400, "trial_days must be a dict")
    for k, v in list(td.items()):
        try:
            td[k] = max(0, int(v))
        except (TypeError, ValueError):
            raise HTTPException(400, f"trial_days.{k} must be an integer")
    cfg["trial_days"] = td

    await db.acm_meta.update_one(
        {"key": "resolver_config"},
        {"$set": {
            "key": "resolver_config",
            "config": cfg,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": user.get("email") or user["user_id"],
        }},
        upsert=True,
    )
    return {"ok": True, "config": cfg}


# ============================================================
# 2. TRIAL PAYMENT INSTRUMENTS
# ============================================================
@router.get("/acm-v2/trial-payments")
async def list_trial_payment_instruments(
    user: dict = Depends(get_current_user),
    limit: int = 100, status: Optional[str] = None,
):
    """Admin — list saved payment instruments captured during trial opt-in."""
    _require_admin(user)
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    rows = await db.trial_payment_instruments.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(max(1, min(limit, 500))).to_list(500)
    return {"items": rows, "count": len(rows)}


@router.post("/acm-v2/trial-payments")
async def create_trial_payment_instrument(request: Request, user: dict = Depends(get_current_user)):
    """User-initiated — register a saved payment method when starting a trial
    with auto_convert=ON. The token is provided by Razorpay tokens API (PCI safe).
    Body: { trial_type, razorpay_token, razorpay_customer_id, method, last4? }
    """
    body = await request.json()
    trial_type = body.get("trial_type")
    if trial_type not in {"starter_trial", "pro_trial", "premium_trial"}:
        raise HTTPException(400, "Invalid trial_type")

    cfg_row = await db.acm_meta.find_one({"key": "resolver_config"}, {"_id": 0}) or {}
    cfg = {**DEFAULT_RESOLVER_CONFIG, **(cfg_row.get("config") or {})}
    if cfg.get("require_payment_for_trial") and not body.get("razorpay_token"):
        raise HTTPException(400, "razorpay_token required for trial opt-in (auto-convert ON)")

    doc = {
        "user_id": user["user_id"],
        "email": user.get("email"),
        "trial_type": trial_type,
        "razorpay_token": body.get("razorpay_token"),
        "razorpay_customer_id": body.get("razorpay_customer_id"),
        "method": body.get("method", "card"),
        "last4": body.get("last4"),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
    }
    await db.trial_payment_instruments.insert_one(doc.copy())

    # Stamp the user with trial_type + expiry so the resolver picks it up
    days = (cfg.get("trial_days") or {}).get(trial_type, 7)
    from datetime import timedelta
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "trial_type": trial_type,
            "trial_started_at": datetime.now(timezone.utc),
            "trial_expires_at": expires,
            "trial_auto_convert": True,
        }},
    )
    # Drop _id for JSON
    doc.pop("_id", None)
    return {"ok": True, "trial_expires_at": expires.isoformat(), "instrument": doc}


# ============================================================
# 3. TIER ↔ SEGMENT MAPPING
# ============================================================
@router.get("/acm-v2/tier-segment-mapping")
async def list_tier_segment_mapping(user: dict = Depends(get_current_user)):
    """Admin — list every tier→segments mapping."""
    _require_admin(user)
    rows = await db.tier_segment_mapping.find({}, {"_id": 0}).to_list(200)
    return {"mappings": rows, "count": len(rows)}


@router.put("/acm-v2/tier-segment-mapping/{tier_id}")
async def set_tier_segment_mapping(
    tier_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Admin — set the list of segment_ids reachable from a tier."""
    _require_admin(user)
    body = await request.json()
    segment_ids = body.get("segment_ids") or []
    if not isinstance(segment_ids, list):
        raise HTTPException(400, "segment_ids must be a list")
    await db.tier_segment_mapping.update_one(
        {"tier_id": tier_id},
        {"$set": {
            "tier_id": tier_id,
            "segment_ids": segment_ids,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": user.get("email") or user["user_id"],
        }},
        upsert=True,
    )
    return {"ok": True, "tier_id": tier_id, "segment_ids": segment_ids}


# ============================================================
# 4. GEOGRAPHY (idempotent seed on first request)
# ============================================================
_GEO_SEEDED = {"countries": False, "states": False}

# Trimmed shortlist (top 50). For prod, replace with ISO-3166 dump.
COUNTRIES = [
    ("IN", "India"), ("US", "United States"), ("GB", "United Kingdom"),
    ("CA", "Canada"), ("AU", "Australia"), ("DE", "Germany"), ("FR", "France"),
    ("JP", "Japan"), ("CN", "China"), ("BR", "Brazil"), ("ZA", "South Africa"),
    ("AE", "United Arab Emirates"), ("SG", "Singapore"), ("NL", "Netherlands"),
    ("IT", "Italy"), ("ES", "Spain"), ("MX", "Mexico"), ("RU", "Russia"),
    ("ID", "Indonesia"), ("KR", "South Korea"), ("TR", "Turkey"), ("SE", "Sweden"),
    ("CH", "Switzerland"), ("NO", "Norway"), ("DK", "Denmark"), ("FI", "Finland"),
    ("BE", "Belgium"), ("IE", "Ireland"), ("AT", "Austria"), ("PL", "Poland"),
    ("PT", "Portugal"), ("GR", "Greece"), ("CZ", "Czechia"), ("HU", "Hungary"),
    ("RO", "Romania"), ("NZ", "New Zealand"), ("MY", "Malaysia"), ("TH", "Thailand"),
    ("PH", "Philippines"), ("VN", "Vietnam"), ("PK", "Pakistan"), ("BD", "Bangladesh"),
    ("LK", "Sri Lanka"), ("NP", "Nepal"), ("BT", "Bhutan"), ("MM", "Myanmar"),
    ("EG", "Egypt"), ("KE", "Kenya"), ("NG", "Nigeria"), ("AR", "Argentina"),
]

INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]
INDIA_UTS = [
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
]


async def _ensure_geo_seeded():
    if not _GEO_SEEDED["countries"]:
        count = await db.geo_countries.count_documents({})
        if count < 30:
            for code, name in COUNTRIES:
                await db.geo_countries.update_one(
                    {"code": code},
                    {"$set": {"code": code, "name": name}},
                    upsert=True,
                )
            logger.info(f"geo_countries seeded: {len(COUNTRIES)} entries")
        _GEO_SEEDED["countries"] = True
    if not _GEO_SEEDED["states"]:
        count = await db.geo_states.count_documents({"country_code": "IN"})
        if count < 28:
            for s in INDIA_STATES:
                await db.geo_states.update_one(
                    {"country_code": "IN", "name": s},
                    {"$set": {"country_code": "IN", "name": s, "type": "state"}},
                    upsert=True,
                )
            for u in INDIA_UTS:
                await db.geo_states.update_one(
                    {"country_code": "IN", "name": u},
                    {"$set": {"country_code": "IN", "name": u, "type": "ut"}},
                    upsert=True,
                )
            logger.info(f"geo_states (IN) seeded: {len(INDIA_STATES)+len(INDIA_UTS)} entries")
        _GEO_SEEDED["states"] = True


@router.get("/geo/countries")
async def list_countries():
    """Public — list all countries (auto-seeds on first call)."""
    await _ensure_geo_seeded()
    rows = await db.geo_countries.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    return {"countries": rows, "count": len(rows)}


@router.get("/geo/states/{country_code}")
async def list_states(country_code: str):
    """Public — list states/UTs for a given country."""
    await _ensure_geo_seeded()
    rows = await db.geo_states.find(
        {"country_code": country_code.upper()}, {"_id": 0}
    ).sort("name", 1).to_list(500)
    return {"country_code": country_code.upper(), "states": rows, "count": len(rows)}


# ============================================================
# 5. INDEXES (called by server.py at boot)
# ============================================================
async def ensure_indexes():
    """Create the indexes the v2 collections rely on."""
    try:
        await db.trial_payment_instruments.create_index([("user_id", 1)])
        await db.trial_payment_instruments.create_index([("status", 1)])
        await db.tier_segment_mapping.create_index([("tier_id", 1)], unique=True)
        await db.geo_countries.create_index([("code", 1)], unique=True)
        await db.geo_states.create_index([("country_code", 1), ("name", 1)], unique=True)
        await db.sku_entitlements.create_index([("user_id", 1), ("kind", 1)])
        await db.razorpay_subscriptions.create_index([("user_id", 1), ("status", 1)])
        await db.users.create_index([("effective_access_key", 1)])
        logger.info("ACM v2 indexes ensured")
    except Exception as e:
        logger.warning(f"ACM v2 index creation skipped: {e}")
