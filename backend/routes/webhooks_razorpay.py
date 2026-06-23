"""Razorpay webhook adapter for the Referral Bonus engine.

Receives Razorpay webhook events, verifies the signature, maps the payload to
our internal `CreditIn` shape, and credits the referral chain (L1/L2/L3).

Razorpay webhook signature scheme (different from our /credit HMAC):
  X-Razorpay-Signature = hex( hmac_sha256( RAZORPAY_WEBHOOK_SECRET, raw_body ) )

Subscribed events (configure in Razorpay Dashboard → Webhooks):
  - payment.captured           — one-off payments
  - subscription.charged       — recurring renewals (optional)

Idempotency: each Razorpay payment.id is stored once in razorpay_events;
re-deliveries are ignored.

Required Razorpay order/payment `notes` (set when initiating payment from
your checkout code):
  {
    "referrer_user_id":     "<user_id>",
    "referee_user_id":      "<user_id>",
    "is_first_purchase":    "true" | "false",      (optional — auto-computed if absent)
    "user_on_highest_tier": "true" | "false"       (optional, default false)
  }
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, Header

from core.database import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks · Razorpay"])

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

# Events we care about. Any other event is acknowledged (200) but ignored.
ACTIVE_EVENTS = {"payment.captured", "subscription.charged", "order.paid"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _verify_razorpay_signature(raw_body: bytes, signature: Optional[str]) -> Optional[str]:
    if not RAZORPAY_WEBHOOK_SECRET:
        return "RAZORPAY_WEBHOOK_SECRET not configured"
    if not signature:
        return "Missing X-Razorpay-Signature header"
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return "Signature mismatch"
    return None


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


async def _resolve_referrer_chain(referee_user_id: str, max_levels: int = 3) -> List[str]:
    """Walk up the referral tree for the referee — returns [L1, L2, L3] user_ids.

    Looks up `users.referred_by_user_id`; missing links short-circuit the chain.
    """
    chain: List[str] = []
    current = referee_user_id
    for _ in range(max_levels):
        user = await db.users.find_one(
            {"user_id": current}, {"_id": 0, "referred_by_user_id": 1}
        )
        ref_by = (user or {}).get("referred_by_user_id")
        if not ref_by or ref_by in chain or ref_by == referee_user_id:
            break
        chain.append(ref_by)
        current = ref_by
    return chain


async def _is_first_purchase(referee_user_id: str) -> bool:
    """True iff this is the referee's first credited purchase."""
    n = await db.referral_credits.count_documents({"referee_user_id": referee_user_id})
    return n == 0


async def _do_internal_credit(
    referrer_user_id: str,
    referee_user_id: str,
    purchase_amount_inr: float,
    level: int,
    is_first_purchase: bool,
    purchase_ref: Optional[str],
    user_on_highest_tier: bool,
) -> Dict[str, Any]:
    """Replicates the credit storage path from /api/referral/credit but in-process.

    Avoids the HTTP round-trip + dependency-injection of the public endpoint
    so the webhook can run as a system actor.
    """
    # Lazy-import to avoid circular import at module load time
    from routes.referral import simulate, SimulateIn, _ensure_config  # type: ignore

    await _ensure_config()
    cfg = await db.referral_config.find_one({"_id": "global"}, {"_id": 0})

    sim = await simulate(
        SimulateIn(
            purchase_amount_inr=purchase_amount_inr,
            level=level,
            is_first_purchase=is_first_purchase,
            user_on_highest_tier=user_on_highest_tier,
        ),
        user={"user_id": "_system_razorpay"},  # not used inside simulate()
    )

    now = _now()
    credit_id = str(uuid.uuid4())

    # Karma credit (immediate)
    if sim["breakdown"]["karma_points"] > 0:
        await db.referral_profiles.update_one(
            {"user_id": referrer_user_id},
            {"$inc": {"karma_balance": sim["breakdown"]["karma_points"]}},
            upsert=True,
        )
    # Coupon (immediate, expires after validity)
    if sim["breakdown"]["coupon_value_inr"] > 0:
        await db.referral_coupons.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": referrer_user_id,
            "value_inr": sim["breakdown"]["coupon_value_inr"],
            "pct_off": cfg["coupon_default_pct"],
            "expires_at": now + timedelta(days=cfg["coupon_validity_days"]),
            "used": False,
            "source_credit_id": credit_id,
            "created_at": now,
        })
    # Special-access entitlement (immediate)
    if sim["breakdown"]["special_access_value_inr"] > 0:
        await db.referral_entitlements.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": referrer_user_id,
            "strategy": sim["breakdown"]["special_access_resolution"]["strategy"],
            "value_inr": sim["breakdown"]["special_access_value_inr"],
            "source_credit_id": credit_id,
            "used": False,
            "created_at": now,
        })
    # Cash — held until refund-window expires
    if sim["breakdown"]["cash_inr"] > 0:
        await db.referral_cash_ledger.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": referrer_user_id,
            "amount_inr": sim["breakdown"]["cash_inr"],
            "status": "held",
            "hold_until": now + timedelta(days=cfg["cash_refund_window_days"]),
            "source_credit_id": credit_id,
            "purchase_ref": purchase_ref,
            "created_at": now,
        })

    await db.referral_credits.insert_one({
        "id": credit_id,
        "referrer_user_id": referrer_user_id,
        "referee_user_id": referee_user_id,
        "purchase_amount_inr": purchase_amount_inr,
        "level": level,
        "is_first_purchase": is_first_purchase,
        "purchase_ref": purchase_ref,
        "source": "razorpay_webhook",
        "breakdown": sim["breakdown"],
        "created_at": now,
    })
    return {"credit_id": credit_id, "level": level, "breakdown": sim["breakdown"]}


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(default=None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(default=None, alias="X-Razorpay-Event-Id"),
):
    raw = await request.body()

    err = _verify_razorpay_signature(raw, x_razorpay_signature)
    if err:
        logger.warning("Razorpay webhook rejected: %s", err)
        raise HTTPException(status_code=403, detail=f"Razorpay verification failed: {err}")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = (payload.get("event") or "").lower()
    if event not in ACTIVE_EVENTS:
        # Acknowledge but ignore — keeps Razorpay from retrying unknown events.
        return {"ok": True, "ignored_event": event}

    # Extract payment entity (present in all 3 active events)
    payment = (
        ((payload.get("payload") or {}).get("payment") or {}).get("entity")
        or {}
    )
    payment_id = payment.get("id")
    amount_paise = payment.get("amount") or 0
    currency = (payment.get("currency") or "INR").upper()
    status = (payment.get("status") or "").lower()
    notes = payment.get("notes") or {}

    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment.entity.id")
    if currency != "INR":
        # Skip non-INR for now (referral engine is INR-priced)
        return {"ok": True, "ignored_currency": currency}
    if status not in ("captured", "paid"):
        return {"ok": True, "ignored_status": status}

    # Idempotency — store the event_id (or payment_id) once
    dedupe_key = x_razorpay_event_id or f"pay_{payment_id}"
    existing = await db.razorpay_events.find_one({"event_id": dedupe_key})
    if existing:
        return {"ok": True, "duplicate": True, "event_id": dedupe_key}

    # Extract referral metadata from payment.notes
    referrer_from_notes = (notes.get("referrer_user_id") or "").strip()
    referee_user_id = (notes.get("referee_user_id") or "").strip()
    if not referee_user_id:
        # Cannot credit without a referee — store the event so we don't retry forever
        await db.razorpay_events.insert_one({
            "event_id": dedupe_key, "payment_id": payment_id,
            "event": event, "raw": payload, "outcome": "skip_no_referee",
            "created_at": _now(),
        })
        return {"ok": True, "skipped": "no_referee_user_id_in_notes"}

    # Resolve full chain
    if referrer_from_notes:
        chain = [referrer_from_notes]
        # Optionally walk up for L2/L3
        rest = await _resolve_referrer_chain(referrer_from_notes, max_levels=2)
        chain.extend(rest)
    else:
        chain = await _resolve_referrer_chain(referee_user_id, max_levels=3)

    if not chain:
        await db.razorpay_events.insert_one({
            "event_id": dedupe_key, "payment_id": payment_id,
            "event": event, "raw": payload, "outcome": "skip_no_chain",
            "created_at": _now(),
        })
        return {"ok": True, "skipped": "no_referrer_chain"}

    # Compute amount + flags
    purchase_amount_inr = amount_paise / 100.0
    if "is_first_purchase" in notes:
        is_first = _truthy(notes.get("is_first_purchase"))
    else:
        is_first = await _is_first_purchase(referee_user_id)
    user_top_tier = _truthy(notes.get("user_on_highest_tier", False))

    # Credit each level (1-indexed)
    results = []
    for idx, referrer_id in enumerate(chain[:3], start=1):
        try:
            res = await _do_internal_credit(
                referrer_user_id=referrer_id,
                referee_user_id=referee_user_id,
                purchase_amount_inr=purchase_amount_inr,
                level=idx,
                is_first_purchase=is_first,
                purchase_ref=payment_id,
                user_on_highest_tier=user_top_tier,
            )
            results.append({"level": idx, "referrer": referrer_id, **res})
        except Exception as e:
            logger.exception("Razorpay credit failed for level %s: %s", idx, e)
            results.append({"level": idx, "referrer": referrer_id, "error": str(e)})

    # Store the processed event
    await db.razorpay_events.insert_one({
        "event_id": dedupe_key,
        "payment_id": payment_id,
        "event": event,
        "amount_inr": purchase_amount_inr,
        "referee_user_id": referee_user_id,
        "chain": chain,
        "is_first_purchase": is_first,
        "results": results,
        "outcome": "credited",
        "created_at": _now(),
    })
    return {"ok": True, "event": event, "credited": results, "payment_id": payment_id}


# ───────────────────────────────────────────────────────────────────────────
# RazorpayX Payout-status webhook (Collaboration Epic Phase E)
#
# Subscribe in the RazorpayX Dashboard → Webhooks to:
#   payout.processed, payout.failed, payout.reversed
# Uses a SEPARATE secret (RAZORPAYX_WEBHOOK_SECRET) so it never collides with
# the payment-collection webhook above. Reconciles `payouts` + `earnings_ledger`.
# ───────────────────────────────────────────────────────────────────────────
RAZORPAYX_WEBHOOK_SECRET = os.getenv("RAZORPAYX_WEBHOOK_SECRET", "").strip()
PAYOUT_EVENTS = {"payout.processed", "payout.failed", "payout.reversed"}


def _verify_razorpayx_signature(raw_body: bytes, signature: Optional[str]) -> Optional[str]:
    if not RAZORPAYX_WEBHOOK_SECRET:
        return "RAZORPAYX_WEBHOOK_SECRET not configured"
    if not signature:
        return "Missing X-Razorpay-Signature header"
    expected = hmac.new(
        RAZORPAYX_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return "Signature mismatch"
    return None


@router.post("/razorpayx")
async def razorpayx_payout_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(default=None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: Optional[str] = Header(default=None, alias="X-Razorpay-Event-Id"),
):
    raw = await request.body()

    err = _verify_razorpayx_signature(raw, x_razorpay_signature)
    if err:
        logger.warning("RazorpayX webhook rejected: %s", err)
        raise HTTPException(status_code=403, detail=f"RazorpayX verification failed: {err}")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = (payload.get("event") or "").lower()
    if event not in PAYOUT_EVENTS:
        return {"ok": True, "ignored_event": event}

    payout_entity = (
        ((payload.get("payload") or {}).get("payout") or {}).get("entity") or {}
    )
    rzp_payout_id = payout_entity.get("id")
    reference_id = (payout_entity.get("reference_id") or "").strip()  # our internal payout_id
    failure_reason = payout_entity.get("failure_reason") or payout_entity.get("status_details", {}).get("description")

    if not (rzp_payout_id or reference_id):
        raise HTTPException(status_code=400, detail="Missing payout id / reference_id")

    # Idempotency
    dedupe_key = x_razorpay_event_id or f"{event}:{rzp_payout_id or reference_id}"
    if await db.razorpayx_events.find_one({"event_id": dedupe_key}):
        return {"ok": True, "duplicate": True, "event_id": dedupe_key}

    # Match our payout row by RazorpayX id first, then by our reference_id
    query: Dict[str, Any] = {}
    if rzp_payout_id:
        query = {"razorpay_payout_id": rzp_payout_id}
    payout = await db.payouts.find_one(query) if query else None
    if not payout and reference_id:
        payout = await db.payouts.find_one({"payout_id": reference_id})

    if not payout:
        await db.razorpayx_events.insert_one({
            "event_id": dedupe_key, "event": event, "razorpay_payout_id": rzp_payout_id,
            "reference_id": reference_id, "outcome": "no_matching_payout",
            "raw": payload, "created_at": _now(),
        })
        return {"ok": True, "skipped": "no_matching_payout"}

    payout_id = payout["payout_id"]
    new_status = {
        "payout.processed": "processed",
        "payout.failed": "failed",
        "payout.reversed": "reversed",
    }[event]

    updates: Dict[str, Any] = {
        "status": new_status,
        "razorpay_payout_id": rzp_payout_id or payout.get("razorpay_payout_id"),
        "webhook_event": event,
        "updated_at": _now().isoformat(),
    }
    if new_status == "processed":
        updates["processed_at"] = _now().isoformat()
    if new_status in ("failed", "reversed") and failure_reason:
        updates["failure_reason"] = str(failure_reason)[:300]

    await db.payouts.update_one({"payout_id": payout_id}, {"$set": updates})

    reverted = 0
    if new_status in ("failed", "reversed"):
        # Revert the bundled earnings back to `available` so the next weekly
        # sweep retries them.
        entry_ids = payout.get("entry_ids") or []
        if entry_ids:
            res = await db.earnings_ledger.update_many(
                {"entry_id": {"$in": entry_ids}},
                {"$set": {"status": "available", "payout_id": None}},
            )
            reverted = res.modified_count

    # Notify the seller
    try:
        from core.helpers import create_notification
        if new_status == "processed":
            msg = f"✅ Your ₹{payout.get('amount_inr')} payout was completed."
        elif new_status == "failed":
            msg = f"⚠️ Your ₹{payout.get('amount_inr')} payout failed and was returned to your available balance."
        else:
            msg = f"↩️ Your ₹{payout.get('amount_inr')} payout was reversed and returned to your available balance."
        await create_notification(payout["user_id"], "payout", "Payout update 💸", msg, {"payout_id": payout_id})
    except Exception:
        pass

    await db.razorpayx_events.insert_one({
        "event_id": dedupe_key, "event": event, "razorpay_payout_id": rzp_payout_id,
        "reference_id": reference_id, "payout_id": payout_id, "new_status": new_status,
        "reverted_entries": reverted, "outcome": "reconciled", "created_at": _now(),
    })
    return {"ok": True, "event": event, "payout_id": payout_id,
            "status": new_status, "reverted_entries": reverted}


@router.get("/razorpayx/health")
async def razorpayx_health():
    """Quick configuration sanity check for the SuperAdmin."""
    from core import razorpayx
    return {
        "webhook_secret_configured": bool(RAZORPAYX_WEBHOOK_SECRET),
        "payout_events": sorted(PAYOUT_EVENTS),
        "endpoint": "/api/webhooks/razorpayx",
        "payouts_live": await razorpayx.is_configured(),
        "isolated_keys": bool(os.getenv("RAZORPAYX_KEY_ID") and os.getenv("RAZORPAYX_KEY_SECRET")),
    }


@router.get("/razorpay/health")
async def razorpay_health():
    """Quick configuration sanity check for the SuperAdmin."""
    return {
        "configured": bool(RAZORPAY_WEBHOOK_SECRET),
        "active_events": sorted(ACTIVE_EVENTS),
        "endpoint": "/api/webhooks/razorpay",
        "required_notes_keys": [
            "referee_user_id (required)",
            "referrer_user_id (optional — falls back to user's referred_by_user_id)",
            "is_first_purchase (optional — auto-computed)",
            "user_on_highest_tier (optional, default false)",
        ],
    }
