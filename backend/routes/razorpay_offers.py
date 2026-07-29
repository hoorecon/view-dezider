"""
Razorpay Offers — Admin Add + Auto-attach Engine
==================================================
Razorpay has TWO promotion products (as of 2026):
  1. Discounts & Cash Backs — attaches via `offers: [id, ...]` on order.create
  2. Offers on Subscriptions — attaches via `offer_id: id` on subscription.create

Merchants create/manage them on the Razorpay Dashboard (Payments Products →
Offers). Razorpay does NOT expose a "list all offers" REST endpoint — they
can only be fetched by ID (GET /v1/offers/{id}). So this module lets an admin
paste each offer ID + label + apply_flows manually, one at a time. Downstream,
`_make_onetime_order()` and `create_subscription()` read this config to auto-apply
the right offer per transaction.

Endpoints:
  POST   /api/admin/razorpay-offers            Add offer manually
  GET    /api/admin/razorpay-offers            List stored offers
  PUT    /api/admin/razorpay-offers/{id}       Toggle apply_flows / active / priority / label
  DELETE /api/admin/razorpay-offers/{id}       Remove
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import require_super_admin

router = APIRouter(prefix="/admin/razorpay-offers", tags=["Razorpay Offers"])

_ALLOWED_FLOWS = {"onetime", "recurring", "sku", "topup", "decision_flow"}


class OfferCreate(BaseModel):
    offer_id: str = Field(..., min_length=6, max_length=64)
    label: str = Field("", max_length=120)
    display_text: str = Field("", max_length=180)
    apply_flows: List[str] = Field(default_factory=list)
    active: bool = True
    priority: int = 100


class OfferPatch(BaseModel):
    label: str | None = None
    display_text: str | None = None
    apply_flows: List[str] | None = None
    active: bool | None = None
    priority: int | None = None


async def _list_all() -> List[Dict[str, Any]]:
    return await db.razorpay_offers.find({}, {"_id": 0}).sort(
        [("active", -1), ("priority", 1)]
    ).to_list(500)


@router.get("")
async def list_offers(user: dict = Depends(require_super_admin)):
    return {"offers": await _list_all()}


@router.post("")
async def add_offer(body: OfferCreate, user: dict = Depends(require_super_admin)):
    oid = body.offer_id.strip()
    if not oid.startswith("offer_"):
        raise HTTPException(400, "Offer ID must start with 'offer_' — copy the full ID from Razorpay Dashboard.")
    flows = [f for f in body.apply_flows if f in _ALLOWED_FLOWS]
    if not flows:
        raise HTTPException(400, "Select at least one flow to auto-attach this offer to.")
    existing = await db.razorpay_offers.find_one({"offer_id": oid}, {"_id": 0})
    if existing:
        raise HTTPException(409, f"Offer {oid} is already added. Edit it in the list below.")
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "offer_id": oid,
        "label": body.label.strip() or oid,
        "display_text": body.display_text.strip(),
        "apply_flows": flows,
        "active": bool(body.active),
        "priority": int(body.priority),
        "source": "admin_manual",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.razorpay_offers.insert_one(doc)
    return {"message": "Offer added.", "offer": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/{offer_id}")
async def patch_offer(offer_id: str, body: OfferPatch, user: dict = Depends(require_super_admin)):
    update: Dict[str, Any] = {}
    if body.apply_flows is not None:
        update["apply_flows"] = [f for f in body.apply_flows if f in _ALLOWED_FLOWS]
    if body.active is not None:
        update["active"] = bool(body.active)
    if body.priority is not None:
        update["priority"] = int(body.priority)
    if body.label is not None:
        update["label"] = body.label.strip()
    if body.display_text is not None:
        update["display_text"] = body.display_text.strip()
    if not update:
        raise HTTPException(400, "Nothing to update.")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.razorpay_offers.update_one({"offer_id": offer_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Offer not found.")
    return {"message": "Updated", "offer": await db.razorpay_offers.find_one({"offer_id": offer_id}, {"_id": 0})}


@router.delete("/{offer_id}")
async def delete_offer(offer_id: str, user: dict = Depends(require_super_admin)):
    res = await db.razorpay_offers.delete_one({"offer_id": offer_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Offer not found.")
    return {"message": "Deleted", "offer_id": offer_id}


# ──────────────────── shared helpers for checkout routes ────────────────────

async def get_offers_for_flow(flow: str) -> List[str]:
    """Return offer_ids currently marked to auto-attach to `flow`."""
    rows = await db.razorpay_offers.find(
        {"active": True, "apply_flows": flow},
        {"_id": 0, "offer_id": 1, "priority": 1},
    ).sort("priority", 1).to_list(50)
    return [r["offer_id"] for r in rows]


async def get_best_offer_for_flow(flow: str) -> str | None:
    """Highest-priority single offer for flows that only allow one (subscriptions)."""
    ids = await get_offers_for_flow(flow)
    return ids[0] if ids else None
