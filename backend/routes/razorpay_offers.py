"""
Razorpay Offers — Admin Sync + Auto-attach Engine
==================================================
Razorpay has TWO promotion products (as of 2025):
  1. Discounts & Cash Backs — attaches via `offers: [id, ...]` on order.create
  2. Offers on Subscriptions — attaches via `offer_id: id` on subscription.create

Merchants create/manage them on the Razorpay Dashboard (Payments Products →
Offers). This module lets an admin **sync** the live list into a local
`razorpay_offers` collection and mark which flows each offer should auto-attach
to. Downstream, `_make_onetime_order()` and `create_subscription()` read this
config to auto-apply the right offer per transaction.

NOTE: The Razorpay Python SDK (razorpay==1.x) does NOT expose a `client.offer`
resource — that resource was never wrapped. We therefore hit the REST API
directly at GET https://api.razorpay.com/v1/offers using HTTP Basic Auth with
the same (key_id, key_secret) credentials the SDK client is built from.

Endpoints:
  POST /api/admin/razorpay-offers/sync        Pull latest from Razorpay
  GET  /api/admin/razorpay-offers             List stored offers
  PUT  /api/admin/razorpay-offers/{offer_id}  Toggle apply_flows / active
"""
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import db
from core.integrations import get_razorpay_client
from core.auth import require_super_admin

router = APIRouter(prefix="/admin/razorpay-offers", tags=["Razorpay Offers"])

# Razorpay REST base — offers resource isn't in the Python SDK so we call it
# directly. Same host/auth as the SDK uses internally.
_RZP_BASE = "https://api.razorpay.com/v1"


class OfferPatch(BaseModel):
    apply_flows: List[str] | None = None   # any of: onetime, recurring, sku, topup, decision_flow
    active: bool | None = None
    priority: int | None = None            # lower = higher priority when multiple match


def _map_flow(offer: Dict[str, Any]) -> List[str]:
    """Best-effort default apply_flows based on Razorpay offer metadata.
    Subscription offers → recurring; everything else → onetime + sku + topup."""
    otype = (offer.get("type") or "").lower()
    # Razorpay marks subscription offers with type in {"subscription", "discount_subscription"}
    if "subscription" in otype:
        return ["recurring"]
    return ["onetime", "sku", "topup"]


async def _fetch_razorpay_offers(key_id: str, key_secret: str) -> List[Dict[str, Any]]:
    """Call GET /v1/offers directly with basic auth (SDK doesn't wrap this).
    Razorpay returns all offers in a single response — no pagination cursor
    is documented for this endpoint, so we just take `items`."""
    async with httpx.AsyncClient(timeout=15.0) as ac:
        r = await ac.get(f"{_RZP_BASE}/offers", auth=(key_id, key_secret))
    if r.status_code != 200:
        # Bubble up Razorpay's message so admin can see WHY (e.g. API not enabled).
        try:
            err = r.json().get("error", {}).get("description") or r.text[:180]
        except Exception:
            err = r.text[:180]
        raise HTTPException(r.status_code, f"Razorpay offers API returned {r.status_code}: {err}")
    body = r.json() or {}
    return body.get("items", []) or []


@router.post("/sync")
async def sync_offers(user: dict = Depends(require_super_admin)):
    """Pull the live list of offers from Razorpay and upsert to Mongo.
    - New offers: inserted with best-effort default apply_flows (admin can override)
    - Existing offers: refresh Razorpay-side fields; PRESERVE admin overrides
      (apply_flows, active, priority)
    - Offers deleted on Razorpay side: marked inactive locally with source='orphaned'
    """
    rzp, key_id, key_secret = await get_razorpay_client()
    if not rzp or not key_id or not key_secret:
        raise HTTPException(500, "Razorpay not configured. Set Key ID + Secret in Admin → Payments.")

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    inserted = updated = 0
    seen: List[str] = []
    try:
        items = await _fetch_razorpay_offers(key_id, key_secret)
        for o in items:
            oid = o.get("id")
            if not oid:
                continue
            seen.append(oid)
            existing = await db.razorpay_offers.find_one({"offer_id": oid}, {"_id": 0})
            # Razorpay-side fields (always refreshed).
            rzp_fields = {
                "offer_id": oid,
                "name": o.get("name") or "",
                "display_text": o.get("display_text") or "",
                "payment_method": o.get("payment_method") or "",
                "type": o.get("type") or "",
                "discount_amount": o.get("discount_amount"),
                "discount_percentage": o.get("percent_rate"),
                "min_order_value": o.get("min_amount"),
                "max_offer_amount": o.get("max_cashback"),
                "issuer": o.get("issuer") or "",
                "starts_at": o.get("starts_at"),
                "ends_at": o.get("ends_at"),
                "status": o.get("status") or "",
                "raw": o,
                "synced_at": now_iso,
                "source": "razorpay_sync",
            }
            if existing:
                await db.razorpay_offers.update_one(
                    {"offer_id": oid}, {"$set": rzp_fields}
                )
                updated += 1
            else:
                # Brand-new offer → seed defaults, admin can tweak.
                rzp_fields.update({
                    "apply_flows": _map_flow(o),
                    "active": True,
                    "priority": 100,
                    "created_at": now_iso,
                })
                await db.razorpay_offers.update_one(
                    {"offer_id": oid}, {"$set": rzp_fields}, upsert=True
                )
                inserted += 1

        # Mark orphaned (deleted-on-Razorpay) offers inactive.
        orphaned = await db.razorpay_offers.update_many(
            {"offer_id": {"$nin": seen}, "source": {"$ne": "orphaned"}},
            {"$set": {"active": False, "source": "orphaned", "synced_at": now_iso}},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)[:180]}")

    return {
        "message": f"Synced from Razorpay — {inserted} new, {updated} refreshed, {orphaned.modified_count} orphaned.",
        "inserted": inserted, "updated": updated, "orphaned": orphaned.modified_count,
        "offers": await _list_all(),
    }


async def _list_all() -> List[Dict[str, Any]]:
    rows = await db.razorpay_offers.find({}, {"_id": 0, "raw": 0}).sort([("active", -1), ("priority", 1)]).to_list(500)
    return rows


@router.get("")
async def list_offers(user: dict = Depends(require_super_admin)):
    return {"offers": await _list_all()}


@router.put("/{offer_id}")
async def patch_offer(offer_id: str, body: OfferPatch, user: dict = Depends(require_super_admin)):
    update: Dict[str, Any] = {}
    if body.apply_flows is not None:
        # Whitelist known flow values so we don't corrupt the collection.
        allowed = {"onetime", "recurring", "sku", "topup", "decision_flow"}
        update["apply_flows"] = [f for f in body.apply_flows if f in allowed]
    if body.active is not None:
        update["active"] = bool(body.active)
    if body.priority is not None:
        update["priority"] = int(body.priority)
    if not update:
        raise HTTPException(400, "Nothing to update.")
    res = await db.razorpay_offers.update_one({"offer_id": offer_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Offer not found. Run Sync first.")
    return {"message": "Updated", "offer": await db.razorpay_offers.find_one({"offer_id": offer_id}, {"_id": 0, "raw": 0})}


# ──────────────────── shared helpers for other routes ────────────────────

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
