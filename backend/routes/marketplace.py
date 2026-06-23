"""
Knowledge Marketplace — Collaboration Epic Phase D.

A user can publish a completed decision so others can learn from it. Three access
tiers:
  • view_only   — others can read the decision's structure, cannot clone.
  • free_clone  — others can read AND clone it into their own decisions for free.
  • paid_clone  — cloning requires payment (INR via Razorpay — Phase E) or karma
                  redemption (Phase F). Preview is gated until purchased.

Cloning copies the decision's factors (with classifications/categories and
priorities/weights) and options into a fresh decision owned by the buyer; the
buyer's own Step-7 assessments start clean so they score it for themselves.

Collections:
  • marketplace_listings — one per published decision
  • marketplace_clones   — every successful clone (also feeds Phase E earnings)
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.database import db
from core.helpers import create_notification
from core.integrations import get_razorpay_client, resolve_razorpay_creds
from core import karma as karma_engine

router = APIRouter(prefix="/marketplace", tags=["Knowledge Marketplace"])

TIERS = {"view_only", "free_clone", "paid_clone"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip(d: dict) -> dict:
    if d and "_id" in d:
        d.pop("_id", None)
    return d


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class PublishRequest(BaseModel):
    decision_id: str
    tier: str = Field(..., description="view_only | free_clone | paid_clone")
    price_inr: Optional[int] = Field(None, ge=0)
    price_karma: Optional[int] = Field(None, ge=0)
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=3000)
    tags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# shared clone helper (reused by Phase E paid-clone & karma redemption)
# ---------------------------------------------------------------------------
async def clone_listing_to_user(listing: dict, buyer: dict, *, paid_amount_inr: int = 0,
                                 paid_karma: int = 0, payment_id: Optional[str] = None,
                                 order_id: Optional[str] = None) -> dict:
    """Copy the listing's source decision into a brand-new decision owned by buyer.
    Records a marketplace_clones row and bumps the listing clone_count."""
    source = await db.decisions.find_one({"id": listing["decision_id"]}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Original decision is no longer available")

    new_id = str(uuid.uuid4())
    # copy factors (keep classifications + priorities/weights) verbatim
    factors = [dict(f) for f in source.get("factors", [])]
    # copy options but reset the cloner's own assessments
    options = []
    for o in source.get("options", []):
        options.append({**{k: v for k, v in o.items() if k not in ("assessments", "worth_percentage")},
                        "assessments": [], "worth_percentage": 0})
    now = datetime.now(timezone.utc)
    new_decision = {
        "id": new_id,
        "user_id": buyer["user_id"],
        "title": f'{source.get("title", "Decision")} (cloned)',
        "context": source.get("context", ""),
        "factors": factors,
        "options": options,
        "status": "draft",
        "decision_case": None,
        "chosen_option_id": None,
        "notes": "",
        "life_area": source.get("life_area"),
        "decision_type": source.get("decision_type"),
        "cloned_from_listing_id": listing["listing_id"],
        "cloned_from_decision_id": listing["decision_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.decisions.insert_one(new_decision)

    clone_row = {
        "clone_id": f"mclone_{uuid.uuid4().hex[:12]}",
        "listing_id": listing["listing_id"],
        "buyer_id": buyer["user_id"],
        "buyer_name": buyer.get("name") or buyer.get("email"),
        "owner_id": listing["owner_id"],
        "source_decision_id": listing["decision_id"],
        "new_decision_id": new_id,
        "tier": listing["tier"],
        "amount_inr": paid_amount_inr,
        "amount_karma": paid_karma,
        "payment_id": payment_id,
        "order_id": order_id,
        "created_at": _now(),
    }
    await db.marketplace_clones.insert_one(clone_row)
    await db.marketplace_listings.update_one(
        {"listing_id": listing["listing_id"]}, {"$inc": {"clone_count": 1}}
    )
    try:
        if listing["owner_id"] != buyer["user_id"]:
            await create_notification(
                listing["owner_id"], "marketplace",
                "Your decision was cloned 🎉",
                f'{clone_row["buyer_name"]} cloned "{listing.get("title") or "your decision"}"'
                + (f" for ₹{paid_amount_inr}" if paid_amount_inr else ""),
                {"listing_id": listing["listing_id"]},
            )
    except Exception:
        pass
    # award karma to the seller for the clone (Phase F)
    try:
        if listing["owner_id"] != buyer["user_id"]:
            event = "decision_cloned_paid" if (paid_amount_inr or 0) > 0 else "decision_cloned_free"
            await karma_engine.award_karma(
                listing["owner_id"], event,
                ref={"listing_id": listing["listing_id"]},
                reason="Your decision was cloned",
            )
    except Exception:
        pass
    return {"new_decision_id": new_id, "clone_id": clone_row["clone_id"]}


async def _has_purchased(listing_id: str, user_id: str) -> bool:
    """True only if the user has actually PAID for this listing (a completed
    order, or a clone that carried a payment / non-zero amount). Free clones do
    NOT count as a paid purchase."""
    o = await db.marketplace_orders.find_one(
        {"listing_id": listing_id, "buyer_id": user_id, "status": "paid"}, {"_id": 1}
    )
    if o:
        return True
    c = await db.marketplace_clones.find_one(
        {"listing_id": listing_id, "buyer_id": user_id,
         "$or": [{"payment_id": {"$ne": None}}, {"amount_inr": {"$gt": 0}}, {"amount_karma": {"$gt": 0}}]},
        {"_id": 1},
    )
    return bool(c)


# ---------------------------------------------------------------------------
# publish / manage listing
# ---------------------------------------------------------------------------
@router.post("/publish")
async def publish(body: PublishRequest, user: dict = Depends(get_current_user)):
    if body.tier not in TIERS:
        raise HTTPException(400, "Invalid tier")
    decision = await db.decisions.find_one({"id": body.decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")
    if not decision.get("factors"):
        raise HTTPException(400, "Add at least one factor before publishing")
    if not decision.get("options"):
        raise HTTPException(400, "Add at least one option before publishing")
    if body.tier == "paid_clone" and not (body.price_inr or body.price_karma):
        raise HTTPException(400, "Set a price (INR and/or karma) for a paid-clone listing")

    snapshot = {
        "factor_count": len(decision.get("factors", [])),
        "option_count": len(decision.get("options", [])),
        "factor_names": [f.get("name") for f in decision.get("factors", [])],
        "option_names": [o.get("name") for o in decision.get("options", [])],
    }
    existing = await db.marketplace_listings.find_one({"decision_id": body.decision_id}, {"_id": 0})
    payload = {
        "owner_id": user["user_id"],
        "owner_name": user.get("name") or user.get("email"),
        "decision_id": body.decision_id,
        "title": (body.title or decision.get("title") or "Untitled decision").strip(),
        "description": (body.description or "").strip(),
        "tier": body.tier,
        "price_inr": body.price_inr or 0,
        "price_karma": body.price_karma or 0,
        "tags": body.tags,
        "life_area": decision.get("life_area"),
        "snapshot": snapshot,
        "status": "active",
        "updated_at": _now(),
    }
    if existing:
        await db.marketplace_listings.update_one({"listing_id": existing["listing_id"]}, {"$set": payload})
        return _strip(await db.marketplace_listings.find_one({"listing_id": existing["listing_id"]}, {"_id": 0}))
    listing = {
        "listing_id": f"mkt_{uuid.uuid4().hex[:12]}",
        **payload,
        "view_count": 0,
        "clone_count": 0,
        "rating_avg": None,
        "rating_count": 0,
        "created_at": _now(),
    }
    await db.marketplace_listings.insert_one(listing)
    return _strip(listing)


@router.post("/{listing_id}/unpublish")
async def unpublish(listing_id: str, user: dict = Depends(get_current_user)):
    listing = await db.marketplace_listings.find_one({"listing_id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the owner can unpublish")
    await db.marketplace_listings.update_one({"listing_id": listing_id}, {"$set": {"status": "unpublished", "updated_at": _now()}})
    return {"ok": True, "status": "unpublished"}


@router.get("/mine")
async def my_listings(user: dict = Depends(get_current_user)):
    cur = db.marketplace_listings.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": [_strip(d) for d in await cur.to_list(100)]}


# ---------------------------------------------------------------------------
# browse + detail
# ---------------------------------------------------------------------------
@router.get("")
async def browse(
    tier: Optional[str] = Query(None),
    life_area: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("newest"),
    limit: int = Query(60, le=200),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {"status": "active"}
    if tier and tier in TIERS:
        q["tier"] = tier
    if life_area:
        q["life_area"] = life_area
    if search:
        import re
        rx = re.escape(search.strip())
        q["$or"] = [
            {"title": {"$regex": rx, "$options": "i"}},
            {"description": {"$regex": rx, "$options": "i"}},
            {"tags": {"$regex": rx, "$options": "i"}},
        ]
    sort_key = {"newest": [("created_at", -1)], "popular": [("clone_count", -1)],
                "viewed": [("view_count", -1)]}.get(sort, [("created_at", -1)])
    cur = db.marketplace_listings.find(q, {"_id": 0}).sort(sort_key)
    items = [_strip(d) for d in await cur.to_list(limit)]
    # gate paid snapshots in list view
    for it in items:
        if it["tier"] == "paid_clone" and it["owner_id"] != user["user_id"]:
            it["snapshot"] = {
                "factor_count": it["snapshot"].get("factor_count", 0),
                "option_count": it["snapshot"].get("option_count", 0),
                "factor_names": (it["snapshot"].get("factor_names") or [])[:3],
                "option_names": [],
                "locked": True,
            }
    return {"items": items, "count": len(items)}


@router.get("/{listing_id}")
async def detail(listing_id: str, user: dict = Depends(get_current_user)):
    listing = await db.marketplace_listings.find_one({"listing_id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    await db.marketplace_listings.update_one({"listing_id": listing_id}, {"$inc": {"view_count": 1}})
    is_owner = listing["owner_id"] == user["user_id"]
    purchased = is_owner or await _has_purchased(listing_id, user["user_id"])
    locked = listing["tier"] == "paid_clone" and not purchased
    out = _strip(listing)
    out["is_owner"] = is_owner
    out["purchased"] = purchased
    out["can_clone"] = listing["tier"] != "view_only" and listing["status"] == "active"
    if locked:
        snap = out.get("snapshot", {})
        out["snapshot"] = {
            "factor_count": snap.get("factor_count", 0),
            "option_count": snap.get("option_count", 0),
            "factor_names": (snap.get("factor_names") or [])[:3],
            "option_names": [],
            "locked": True,
        }
    return out


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------
@router.post("/{listing_id}/clone")
async def clone(listing_id: str, user: dict = Depends(get_current_user)):
    listing = await db.marketplace_listings.find_one({"listing_id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing["status"] != "active":
        raise HTTPException(409, "This listing is no longer available")
    if listing["tier"] == "view_only":
        raise HTTPException(403, "This decision is view-only and cannot be cloned")
    is_owner = listing["owner_id"] == user["user_id"]

    if listing["tier"] == "paid_clone" and not is_owner:
        # paid clone requires a completed purchase (Phase E) — block here
        if not await _has_purchased(listing_id, user["user_id"]):
            raise HTTPException(
                status_code=402,
                detail={"message": "Payment required", "price_inr": listing.get("price_inr", 0),
                        "price_karma": listing.get("price_karma", 0), "listing_id": listing_id},
            )
    result = await clone_listing_to_user(listing, user)
    return {"ok": True, **result, "message": "Cloned to your decisions"}


# ---------------------------------------------------------------------------
# paid-clone purchase (Razorpay) — Phase E
# ---------------------------------------------------------------------------
@router.post("/{listing_id}/create-order")
async def create_order(listing_id: str, user: dict = Depends(get_current_user)):
    listing = await db.marketplace_listings.find_one({"listing_id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing["status"] != "active":
        raise HTTPException(409, "This listing is no longer available")
    if listing["tier"] != "paid_clone":
        raise HTTPException(400, "This listing is not a paid clone")
    if listing["owner_id"] == user["user_id"]:
        raise HTTPException(400, "You can't purchase your own listing")
    if await _has_purchased(listing_id, user["user_id"]):
        return {"already_purchased": True}
    price = int(listing.get("price_inr") or 0)
    if price <= 0:
        raise HTTPException(400, "This listing has no INR price set")

    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(500, "Payment gateway not configured")
    try:
        order = rzp_client.order.create({
            "amount": price * 100,
            "currency": "INR",
            "receipt": f"mkt_{listing_id[:12]}_{user['user_id'][:8]}"[:40],
            "payment_capture": 1,
            "notes": {"type": "marketplace_clone", "listing_id": listing_id,
                      "buyer_id": user["user_id"], "seller_id": listing["owner_id"]},
        })
    except Exception as e:
        raise HTTPException(500, f"Payment order creation failed: {str(e)[:200]}")

    await db.marketplace_orders.insert_one({
        "order_id": order["id"],
        "listing_id": listing_id,
        "buyer_id": user["user_id"],
        "seller_id": listing["owner_id"],
        "amount_paise": price * 100,
        "amount_inr": price,
        "status": "created",
        "created_at": _now(),
    })
    return {"order_id": order["id"], "amount": price * 100, "currency": "INR",
            "key_id": key_id, "user_name": user.get("name", ""), "user_email": user.get("email", "")}


@router.post("/{listing_id}/verify-payment")
async def verify_payment(listing_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    order_id = body.get("razorpay_order_id", "")
    payment_id = body.get("razorpay_payment_id", "")
    signature = body.get("razorpay_signature", "")
    if not all([order_id, payment_id, signature]):
        raise HTTPException(400, "Missing payment fields")

    _, key_secret, _ = await resolve_razorpay_creds()
    expected = hmac.new(key_secret.encode("utf-8"), f"{order_id}|{payment_id}".encode("utf-8"), hashlib.sha256).hexdigest()
    if expected != signature:
        raise HTTPException(400, "Payment verification failed — invalid signature")

    order = await db.marketplace_orders.find_one({"order_id": order_id, "buyer_id": user["user_id"]}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    listing = await db.marketplace_listings.find_one({"listing_id": order["listing_id"]}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing no longer available")

    if order["status"] == "paid":
        existing = await db.marketplace_clones.find_one(
            {"order_id": order_id, "buyer_id": user["user_id"]}, {"_id": 0, "new_decision_id": 1})
        return {"ok": True, "new_decision_id": existing.get("new_decision_id") if existing else None,
                "message": "Already processed"}

    await db.marketplace_orders.update_one(
        {"order_id": order_id},
        {"$set": {"status": "paid", "razorpay_payment_id": payment_id, "razorpay_signature": signature, "paid_at": _now()}},
    )
    gross = int(order.get("amount_inr") or listing.get("price_inr") or 0)
    result = await clone_listing_to_user(listing, user, paid_amount_inr=gross,
                                         payment_id=payment_id, order_id=order_id)
    # credit the seller's earnings ledger
    from routes.earnings import credit_seller
    await credit_seller(listing, order_id=order_id, gross_inr=gross, payment_id=payment_id, buyer_id=user["user_id"])
    return {"ok": True, **result, "message": "Purchase successful"}
