"""
SKU Store — On-demand payment packages for Dezider decision modules.

Sells 4 layered SKUs (L1–L4) that grant entitlements to use the 3 decision
modules (MyDezider / Pros & Cons / SWOT). Each entitlement is consumed on
specific actions:

    L1 (DIY Decision Report,      ₹199)  — 1 report unlock + PDF for a decision
    L2 (10-Decision Family Bundle,₹999)  — 10 decisions across the 3 modules
    L3 (Professional Guided Sess.,₹1,999) — 1 expert booking (deep-link to expert-net)
    L4 (Expert Review,            ₹2,800) — 1 expert review delivery (manual fulfillment)

Prices are stored in the `sku_catalog` Mongo collection and editable via the
Admin UI — never hardcoded on the frontend. The collection auto-seeds with
the defaults below on first boot if missing.
"""

import uuid
import hmac
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/store", tags=["SKU Store"])


# ────────────────────────────────────────────────────────────────────────────
# Razorpay client (lazy import, reused from payments.py env)
# ────────────────────────────────────────────────────────────────────────────
try:
    import razorpay as _razorpay
except Exception:  # pragma: no cover
    _razorpay = None

RZP_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
_rzp_client = None
if _razorpay and RZP_KEY_ID and RZP_KEY_SECRET:
    try:
        _rzp_client = _razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))
    except Exception as e:  # pragma: no cover
        logger.warning("Razorpay client init failed: %s", e)


# ────────────────────────────────────────────────────────────────────────────
# DEFAULT SKU CATALOG (seed source-of-truth, mutable in DB)
# ────────────────────────────────────────────────────────────────────────────
# `quota` = how many decisions/sessions a single purchase unlocks.
# `applies_to_modules` mirrors the SWOT-template vocabulary so the catalog
# stays compatible with future per-module SKUs.
DEFAULT_SKUS: List[Dict[str, Any]] = [
    {
        "code": "L1",
        "layer": "L1",
        "name": "DIY Decision Report",
        "tagline": "Mass entry",
        "description": "Unlock the in-app decision summary plus a polished PDF report you can download or email yourself.",
        "price_paise": 19900,        # ₹199 excl. GST
        "quota": 1,
        "kind": "report",            # report | bundle | session | review
        "applies_to_modules": ["dezider", "pros_cons", "swot"],
        "fulfilment": "auto",
        "active": True,
        "display_order": 1,
        "badge_color": "#3B82F6",
        "icon": "document-text",
    },
    {
        "code": "L2",
        "layer": "L2",
        "name": "10-Decision Family Bundle",
        "tagline": "Main scalable product",
        "description": "10 decisions you can spend freely across My Dezider, Pros & Cons and SWOT — share with family.",
        "price_paise": 99900,        # ₹999
        "quota": 10,
        "kind": "bundle",
        "applies_to_modules": ["dezider", "pros_cons", "swot"],
        "fulfilment": "auto",
        "active": True,
        "display_order": 2,
        "badge_color": "#7C3AED",
        "icon": "people",
    },
    {
        "code": "L3",
        "layer": "L3",
        "name": "Professional Guided Session",
        "tagline": "Main assisted revenue",
        "description": "Book a 1-on-1 expert call with screen-share inside your decision flow. Filter by life-area & sub-area.",
        "price_paise": 199900,       # ₹1,999
        "quota": 1,
        "kind": "session",
        "applies_to_modules": ["dezider", "pros_cons", "swot"],
        "fulfilment": "booking",      # opens expert-net booking flow
        "active": True,
        "display_order": 3,
        "badge_color": "#059669",
        "icon": "videocam",
    },
    {
        "code": "L4",
        "layer": "L4",
        "name": "Expert Review",
        "tagline": "Scarce premium escalation",
        "description": "Have a domain expert review your completed decision and send written recommendations within 48 hours.",
        "price_paise": 280000,       # ₹2,800
        "quota": 1,
        "kind": "review",
        "applies_to_modules": ["dezider", "pros_cons", "swot"],
        "fulfilment": "manual",      # admin assigns expert delivery
        "active": True,
        "display_order": 4,
        "badge_color": "#DC2626",
        "icon": "ribbon",
    },
]

VALID_SKU_CODES = {s["code"] for s in DEFAULT_SKUS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_admin(user: dict) -> bool:
    role = (user or {}).get("role", "")
    org_role = (user or {}).get("org_role", "")
    return role in ("super_admin", "co_admin", "admin") or org_role in (
        "org_super_admin", "org_co_admin"
    )


# ────────────────────────────────────────────────────────────────────────────
# SEEDING
# ────────────────────────────────────────────────────────────────────────────
async def ensure_sku_catalog_seeded():
    """Idempotent seed — inserts any missing SKU with default values.

    Existing SKUs (already edited by admin) are NEVER overwritten — only
    missing rows are added. Safe to call on every boot.
    """
    for sku in DEFAULT_SKUS:
        existing = await db.sku_catalog.find_one({"code": sku["code"]})
        if not existing:
            doc = {**sku, "id": str(uuid.uuid4()), "created_at": _now(), "updated_at": _now()}
            await db.sku_catalog.insert_one(doc)
            logger.info("sku_catalog seeded: %s @ ₹%d", sku["code"], sku["price_paise"] / 100)


async def ensure_in_house_solutions_seeded():
    """Insert MyDezider / Pros&Cons / SWOT into solutions_store with org_id=0.

    Per user request: these three modules should appear as in-house Solution
    Store rows (Associated Org ID = 0). They link to the four payment SKUs via
    `linked_sku_codes` (reserved for the future SKU↔Solution mapping
    enhancement).
    """
    in_house_solutions = [
        {
            "slug": "module_dezider",
            "name": "My Dezider",
            "description": "Multi-factor decision wizard — score options across factors with expected vs. actual values.",
            "module": "dezider",
            "tags": ["decision", "framework", "factors"],
        },
        {
            "slug": "module_pros_cons",
            "name": "Pros & Cons",
            "description": "Classic side-by-side advantages / disadvantages comparison across multiple options.",
            "module": "pros_cons",
            "tags": ["decision", "compare", "tradeoff"],
        },
        {
            "slug": "module_swot",
            "name": "SWOT Analysis",
            "description": "Strengths, Weaknesses, Opportunities & Threats — convert any SWOT into a decision.",
            "module": "swot",
            "tags": ["decision", "swot", "analysis"],
        },
    ]
    for s in in_house_solutions:
        existing = await db.solutions_store.find_one({"slug": s["slug"]})
        if existing:
            continue
        await db.solutions_store.insert_one({
            "solution_id": str(uuid.uuid4()),
            "slug": s["slug"],
            "type": "SERVICE",
            "name": s["name"],
            "description": s["description"],
            "life_area_id": None,
            "sub_area_id": None,
            "category_id": None,
            "org_types": [],
            "decision_types": [],
            "scenario_ids": [],
            "visibility": "PUBLIC",
            "approval_status": "approved",
            "is_authorized": True,
            "created_by": "system",
            "created_by_name": "JELCOS (in-house)",
            "org_id": 0,                       # in-house marker
            "country": "IN",
            "state": "",
            "city": "",
            "language": "en",
            "provider": "JELCOS",
            "url": f"/tools/{s['module']}",
            "image_url": "",
            "tags": s["tags"],
            "price_range": "free-paid",
            "currency": "INR",
            "type_specific": {"module": s["module"]},
            "quantitative_factors": [],
            "linked_sku_codes": list(VALID_SKU_CODES),   # reserved for future
            "status": "active",
            "created_at": _now(),
            "updated_at": _now(),
        })
        logger.info("In-house Solution Store row seeded: %s", s["slug"])


# ────────────────────────────────────────────────────────────────────────────
# CATALOG ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────
@router.get("/skus")
async def list_skus(active_only: bool = True):
    """Public price list. Returns the 4 on-demand SKUs in display order."""
    await ensure_sku_catalog_seeded()
    q: Dict[str, Any] = {}
    if active_only:
        q["active"] = True
    items = await db.sku_catalog.find(q, {"_id": 0}).sort("display_order", 1).to_list(50)
    return {"skus": items}


@router.get("/skus/{code}")
async def get_sku(code: str):
    await ensure_sku_catalog_seeded()
    sku = await db.sku_catalog.find_one({"code": code.upper()}, {"_id": 0})
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return sku


class SkuPriceUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    price_paise: Optional[int] = Field(default=None, ge=0)
    quota: Optional[int] = Field(default=None, ge=1)
    active: Optional[bool] = None
    display_order: Optional[int] = None
    badge_color: Optional[str] = None


@router.put("/admin/skus/{code}")
async def admin_update_sku(
    code: str,
    body: SkuPriceUpdate,
    user: dict = Depends(get_current_user),
):
    """Admin-only: update SKU price/metadata. Never edits `code`/`kind`/`fulfilment`."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")

    await ensure_sku_catalog_seeded()
    code_uc = code.upper()
    sku = await db.sku_catalog.find_one({"code": code_uc}, {"_id": 0})
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    updates = {k: v for k, v in body.dict(exclude_none=True).items()}
    if not updates:
        return sku
    updates["updated_at"] = _now()
    await db.sku_catalog.update_one({"code": code_uc}, {"$set": updates})

    # Audit trail
    await db.sku_catalog_audit.insert_one({
        "id": str(uuid.uuid4()),
        "sku_code": code_uc,
        "changed_by": user["user_id"],
        "changed_by_name": user.get("name", ""),
        "changes": updates,
        "at": _now(),
    })
    return await db.sku_catalog.find_one({"code": code_uc}, {"_id": 0})


@router.post("/admin/skus/reset-defaults")
async def admin_reset_defaults(user: dict = Depends(get_current_user)):
    """Admin-only: hard-reset all SKU rows to the shipping defaults.

    Useful escape-hatch if pricing gets misconfigured. Returns the fresh list.
    """
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    for sku in DEFAULT_SKUS:
        await db.sku_catalog.update_one(
            {"code": sku["code"]},
            {"$set": {**sku, "updated_at": _now()}},
            upsert=True,
        )
    items = await db.sku_catalog.find({}, {"_id": 0}).sort("display_order", 1).to_list(50)
    logger.info("SKU catalog reset to defaults by %s", user["user_id"])
    return {"skus": items, "message": "Defaults restored"}


@router.post("/admin/seed-in-house-solutions")
async def admin_seed_in_house(user: dict = Depends(get_current_user)):
    """Admin-only: idempotently insert the 3 in-house solutions into the store."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    await ensure_in_house_solutions_seeded()
    docs = await db.solutions_store.find(
        {"org_id": 0, "slug": {"$in": ["module_dezider", "module_pros_cons", "module_swot"]}},
        {"_id": 0}
    ).to_list(10)
    return {"in_house_solutions": docs}


# ────────────────────────────────────────────────────────────────────────────
# ENTITLEMENTS — granted on payment, consumed on use.
# ────────────────────────────────────────────────────────────────────────────
# Shape (`user_entitlements` collection):
#   {
#     id, user_id, sku_code, balance, granted_qty,
#     consumed_qty, source_order_id, granted_at, last_used_at, status
#   }

async def grant_entitlement(
    user_id: str, sku_code: str, qty: int, source_order_id: str
) -> Dict[str, Any]:
    """Upsert/extend an entitlement row. Adds qty to balance (non-expiring)."""
    sku_code = sku_code.upper()
    sku = await db.sku_catalog.find_one({"code": sku_code})
    if not sku:
        raise HTTPException(status_code=404, detail=f"Unknown SKU {sku_code}")

    existing = await db.user_entitlements.find_one(
        {"user_id": user_id, "sku_code": sku_code, "status": "active"}
    )
    now = _now()
    if existing:
        await db.user_entitlements.update_one(
            {"id": existing["id"]},
            {"$set": {"last_topup_at": now}, "$inc": {"balance": qty, "granted_qty": qty}},
        )
        doc = await db.user_entitlements.find_one({"id": existing["id"]}, {"_id": 0})
    else:
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "sku_code": sku_code,
            "balance": qty,
            "granted_qty": qty,
            "consumed_qty": 0,
            "source_order_id": source_order_id,
            "granted_at": now,
            "last_topup_at": now,
            "last_used_at": None,
            "status": "active",
        }
        await db.user_entitlements.insert_one(doc)
        doc.pop("_id", None)
    logger.info("Granted entitlement %s qty=%d to %s (order=%s)", sku_code, qty, user_id, source_order_id)
    return doc


async def get_active_balance(user_id: str, sku_code: str) -> int:
    sku_code = sku_code.upper()
    cursor = db.user_entitlements.find(
        {"user_id": user_id, "sku_code": sku_code, "status": "active"}
    )
    total = 0
    async for doc in cursor:
        total += max(0, int(doc.get("balance") or 0))
    return total


@router.get("/my-entitlements")
async def my_entitlements(user: dict = Depends(get_current_user)):
    """Caller's active entitlement balances grouped by SKU."""
    docs = await db.user_entitlements.find(
        {"user_id": user["user_id"], "status": "active"}, {"_id": 0}
    ).to_list(100)

    # Roll up by sku_code for the storefront
    rollup: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        code = d["sku_code"]
        if code not in rollup:
            rollup[code] = {
                "sku_code": code,
                "balance": 0,
                "granted_qty": 0,
                "consumed_qty": 0,
                "last_used_at": None,
            }
        rollup[code]["balance"] += int(d.get("balance") or 0)
        rollup[code]["granted_qty"] += int(d.get("granted_qty") or 0)
        rollup[code]["consumed_qty"] += int(d.get("consumed_qty") or 0)
        lu = d.get("last_used_at")
        if lu and (not rollup[code]["last_used_at"] or lu > rollup[code]["last_used_at"]):
            rollup[code]["last_used_at"] = lu

    return {"entitlements": list(rollup.values()), "raw": docs}


async def has_any_paid_access(user_id: str, module: Optional[str] = None) -> Dict[str, Any]:
    """Returns whether user has ANY way to use the module without paying again.

    Checks (in order):
      1. Active monthly subscription on credit_wallets
      2. L2 balance > 0 (bundle covers all 3 modules)
      3. L1 balance > 0 (single report)
    """
    # Subscription check
    wallet = await db.credit_wallets.find_one(
        {"user_id": user_id}, {"_id": 0, "subscription_status": 1, "current_plan": 1}
    )
    if wallet and wallet.get("subscription_status") == "active" and (
        wallet.get("current_plan") not in (None, "", "free")
    ):
        return {"has_access": True, "via": "subscription", "plan": wallet["current_plan"]}

    l2 = await get_active_balance(user_id, "L2")
    if l2 > 0:
        return {"has_access": True, "via": "L2", "balance": l2}

    l1 = await get_active_balance(user_id, "L1")
    if l1 > 0:
        return {"has_access": True, "via": "L1", "balance": l1}

    return {"has_access": False, "via": None, "balance": 0}


@router.get("/access-check")
async def access_check(
    module: str = Query("dezider"),
    user: dict = Depends(get_current_user),
):
    """Frontend paywall hook — answers "can this user create a new decision?"."""
    return await has_any_paid_access(user["user_id"], module=module)


# ────────────────────────────────────────────────────────────────────────────
# CONSUMPTION
# ────────────────────────────────────────────────────────────────────────────
async def consume_one(
    user_id: str,
    sku_code: str,
    *,
    decision_id: Optional[str] = None,
    module: Optional[str] = None,
) -> bool:
    """Decrement 1 from oldest active entitlement of given SKU. Returns success."""
    sku_code = sku_code.upper()
    doc = await db.user_entitlements.find_one_and_update(
        {
            "user_id": user_id,
            "sku_code": sku_code,
            "status": "active",
            "balance": {"$gt": 0},
        },
        {"$inc": {"balance": -1, "consumed_qty": 1}, "$set": {"last_used_at": _now()}},
        sort=[("granted_at", 1)],
        return_document=True,
    )
    if not doc:
        return False

    await db.entitlement_consumption_log.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "sku_code": sku_code,
        "entitlement_id": doc.get("id"),
        "decision_id": decision_id,
        "module": module,
        "at": _now(),
    })
    return True


async def consume_for_decision(
    user_id: str,
    *,
    module: str,
    decision_id: str,
) -> Dict[str, Any]:
    """Decision-creation hook: prefers L2 bundle, falls back to L1 single-use.

    Returns {consumed_sku, balance_after} or {consumed_sku: None} if user
    relied on a subscription (no consumption needed).
    """
    # Subscription bypasses consumption
    wallet = await db.credit_wallets.find_one(
        {"user_id": user_id}, {"_id": 0, "subscription_status": 1, "current_plan": 1}
    )
    if wallet and wallet.get("subscription_status") == "active" and (
        wallet.get("current_plan") not in (None, "", "free")
    ):
        return {"consumed_sku": None, "via": "subscription"}

    # Prefer L2 (bundle) so we don't burn L1 reports first
    if await consume_one(user_id, "L2", decision_id=decision_id, module=module):
        return {
            "consumed_sku": "L2",
            "balance_after": await get_active_balance(user_id, "L2"),
        }
    if await consume_one(user_id, "L1", decision_id=decision_id, module=module):
        return {
            "consumed_sku": "L1",
            "balance_after": await get_active_balance(user_id, "L1"),
        }
    raise HTTPException(
        status_code=402,
        detail="No active entitlement. Purchase a plan or single decision report to continue.",
    )


# ────────────────────────────────────────────────────────────────────────────
# CHECKOUT (Razorpay)
# ────────────────────────────────────────────────────────────────────────────
class PurchaseRequest(BaseModel):
    sku_code: str
    decision_id: Optional[str] = None         # for L1/L3/L4 contextual purchase
    module: Optional[str] = None              # 'dezider' | 'pros_cons' | 'swot'


@router.post("/purchase")
async def purchase_sku(body: PurchaseRequest, user: dict = Depends(get_current_user)):
    """Create a Razorpay order for an SKU purchase. Verify via /store/verify."""
    if not _rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    code = body.sku_code.upper()
    sku = await db.sku_catalog.find_one({"code": code}, {"_id": 0})
    if not sku or not sku.get("active"):
        raise HTTPException(status_code=400, detail=f"SKU {code} is not available")

    try:
        order = _rzp_client.order.create({
            "amount": int(sku["price_paise"]),
            "currency": "INR",
            "receipt": f"sku_{code}_{user['user_id'][:8]}_{uuid.uuid4().hex[:6]}",
            "payment_capture": 1,
            "notes": {
                "user_id": user["user_id"],
                "type": "sku_purchase",
                "sku_code": code,
                "quota": str(sku.get("quota", 1)),
                "module": body.module or "",
                "decision_id": body.decision_id or "",
            },
        })
    except Exception as e:
        logger.error("Razorpay create order failed for SKU %s: %s", code, e)
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {str(e)[:200]}")

    await db.payment_orders.insert_one({
        "order_id": order["id"],
        "user_id": user["user_id"],
        "type": "sku_purchase",
        "sku_code": code,
        "quota": int(sku.get("quota", 1)),
        "amount_paise": int(sku["price_paise"]),
        "module": body.module,
        "decision_id": body.decision_id,
        "status": "created",
        "razorpay_order": order,
        "created_at": _now(),
    })

    return {
        "order_id": order["id"],
        "amount": int(sku["price_paise"]),
        "currency": "INR",
        "key_id": RZP_KEY_ID,
        "sku": sku,
        "user_name": user.get("name", ""),
        "user_email": user.get("email", ""),
    }


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify")
async def verify_sku_purchase(body: VerifyRequest, user: dict = Depends(get_current_user)):
    """Verify Razorpay signature and grant the entitlement."""
    if not RZP_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    expected = hmac.new(
        RZP_KEY_SECRET.encode("utf-8"),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if expected != body.razorpay_signature:
        raise HTTPException(status_code=400, detail="Signature mismatch")

    order = await db.payment_orders.find_one(
        {"order_id": body.razorpay_order_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("type") != "sku_purchase":
        raise HTTPException(status_code=400, detail="Not a SKU purchase order")

    if order.get("status") == "paid":
        # Already processed — idempotent
        bal = await get_active_balance(user["user_id"], order["sku_code"])
        return {"message": "Already processed", "sku_code": order["sku_code"], "balance": bal}

    await db.payment_orders.update_one(
        {"order_id": body.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": body.razorpay_payment_id,
            "razorpay_signature": body.razorpay_signature,
            "paid_at": _now(),
        }},
    )

    sku_code = order["sku_code"]
    qty = int(order.get("quota", 1))
    await grant_entitlement(user["user_id"], sku_code, qty, body.razorpay_order_id)

    # L4 manual fulfillment: also create an expert_deliveries placeholder so
    # admin sees this in the queue.
    if sku_code == "L4":
        await db.expert_deliveries.insert_one({
            "id": str(uuid.uuid4()),
            "order_id": body.razorpay_order_id,
            "user_id": user["user_id"],
            "user_name": user.get("name", ""),
            "sku_code": "L4",
            "decision_id": order.get("decision_id"),
            "module": order.get("module"),
            "status": "awaiting_assignment",
            "created_at": _now(),
        })

    return {
        "message": "Purchase verified",
        "sku_code": sku_code,
        "balance": await get_active_balance(user["user_id"], sku_code),
        "redirect_hint": _redirect_hint(sku_code, order),
    }


def _redirect_hint(sku_code: str, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tell the frontend where to send the user after a successful purchase."""
    if sku_code == "L1":
        decision_id = order.get("decision_id")
        module = order.get("module")
        if decision_id and module:
            return {"type": "report", "module": module, "decision_id": decision_id}
        return {"type": "modules"}
    if sku_code == "L2":
        return {"type": "modules"}
    if sku_code == "L3":
        return {
            "type": "expert_booking",
            "module": order.get("module"),
            "decision_id": order.get("decision_id"),
        }
    if sku_code == "L4":
        return {"type": "expert_review_queue"}
    return None


@router.get("/orders")
async def my_orders(user: dict = Depends(get_current_user)):
    """User's SKU purchase history."""
    docs = await db.payment_orders.find(
        {"user_id": user["user_id"], "type": "sku_purchase"}, {"_id": 0, "razorpay_order": 0}
    ).sort("created_at", -1).to_list(50)
    return {"orders": docs}


# ────────────────────────────────────────────────────────────────────────────
# L4 EXPERT REVIEW QUEUE — admin-only fulfillment workflow
# ────────────────────────────────────────────────────────────────────────────
# Collection: `expert_deliveries`
# Status machine:
#   awaiting_assignment  → admin picks an expert and assigns
#   in_progress          → expert is working on the review
#   delivered            → expert review document handed to user
#   cancelled            → refunded / dropped
L4_STATUSES = ["awaiting_assignment", "in_progress", "delivered", "cancelled"]


class L4AssignBody(BaseModel):
    expert_id: str
    expert_name: Optional[str] = None
    sla_hours: Optional[int] = 48
    admin_notes: Optional[str] = None


class L4StatusBody(BaseModel):
    status: str
    deliverable_url: Optional[str] = None
    deliverable_note: Optional[str] = None


@router.get("/admin/l4-queue")
async def admin_l4_queue(
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """Admin-only: list all L4 Expert Review deliveries with light enrichment."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    q: Dict[str, Any] = {"sku_code": "L4"}
    if status:
        if status not in L4_STATUSES:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status}")
        q["status"] = status
    rows = await db.expert_deliveries.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)

    # Enrich with payer info if missing
    for r in rows:
        if not r.get("user_email") and r.get("user_id"):
            u = await db.users.find_one({"user_id": r["user_id"]}, {"_id": 0, "email": 1, "name": 1})
            if u:
                r["user_email"] = u.get("email", "")
                r["user_name"] = r.get("user_name") or u.get("name", "")
    # Status counts for the header bar
    counts = {s: 0 for s in L4_STATUSES}
    async for row in db.expert_deliveries.aggregate([
        {"$match": {"sku_code": "L4"}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        if row["_id"] in counts:
            counts[row["_id"]] = row["n"]
    return {"items": rows, "counts": counts, "statuses": L4_STATUSES}


@router.post("/admin/l4-queue/{delivery_id}/assign")
async def admin_l4_assign(
    delivery_id: str,
    body: L4AssignBody,
    user: dict = Depends(get_current_user),
):
    """Admin-only: assign an expert to an L4 delivery."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")

    delivery = await db.expert_deliveries.find_one({"id": delivery_id, "sku_code": "L4"})
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    expert = await db.experts.find_one({"expert_id": body.expert_id}, {"_id": 0})
    expert_name = body.expert_name or (expert.get("name") if expert else "")

    due_at = None
    if body.sla_hours:
        from datetime import timedelta
        due_at = (datetime.now(timezone.utc) + timedelta(hours=body.sla_hours)).isoformat()

    await db.expert_deliveries.update_one(
        {"id": delivery_id},
        {"$set": {
            "expert_id": body.expert_id,
            "expert_name": expert_name,
            "status": "in_progress",
            "assigned_by": user["user_id"],
            "assigned_by_name": user.get("name", ""),
            "assigned_at": _now(),
            "due_at": due_at,
            "admin_notes": body.admin_notes,
        }},
    )
    return await db.expert_deliveries.find_one({"id": delivery_id}, {"_id": 0})


@router.put("/admin/l4-queue/{delivery_id}/status")
async def admin_l4_status(
    delivery_id: str,
    body: L4StatusBody,
    user: dict = Depends(get_current_user),
):
    """Admin-only: transition an L4 delivery (e.g. mark as delivered)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    if body.status not in L4_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Expected one of: {L4_STATUSES}")

    delivery = await db.expert_deliveries.find_one({"id": delivery_id, "sku_code": "L4"})
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    update: Dict[str, Any] = {"status": body.status, "updated_at": _now()}
    if body.status == "delivered":
        update["delivered_at"] = _now()
        update["delivered_by"] = user["user_id"]
        if body.deliverable_url:
            update["deliverable_url"] = body.deliverable_url
        if body.deliverable_note:
            update["deliverable_note"] = body.deliverable_note
    elif body.status == "cancelled":
        update["cancelled_at"] = _now()
        update["cancelled_by"] = user["user_id"]

    await db.expert_deliveries.update_one({"id": delivery_id}, {"$set": update})
    return await db.expert_deliveries.find_one({"id": delivery_id}, {"_id": 0})


@router.get("/admin/experts-pick-list")
async def admin_experts_pick_list(user: dict = Depends(get_current_user)):
    """Tiny lookup for the admin assign-modal dropdown."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    items = await db.experts.find(
        {"status": {"$ne": "disabled"}},
        {"_id": 0, "expert_id": 1, "name": 1, "specializations": 1, "rating_avg": 1, "is_online": 1},
    ).sort("rating_avg", -1).to_list(200)
    return {"experts": items}
