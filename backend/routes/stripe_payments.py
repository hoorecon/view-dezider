"""Stripe Checkout — runs ALONGSIDE Razorpay.

Covers two purchase flows (marketplace/store is a separate follow-up):
  • kind="ai_wallet"    → buy AI credits (reuses ai_wallet refill pricing + `_credit_refill`)
  • kind="subscription" → one-time charge for a monthly plan (reuses subscriptions.apply_charge)

Currency: USD or INR. Prices are computed SERVER-SIDE from the existing
INR/USD pricing engine — the client never sends an amount. Fulfillment is
idempotent: a session is fulfilled exactly once via an atomic pending→completed
flip on `stripe_payments`, so the webhook and the status-poll can't double-grant.

Uses the pod-provided STRIPE_API_KEY. STRIPE_WEBHOOK_SECRET is optional — when
set the webhook signature is verified; the success-URL status poll works either
way (primary confirmation path in this environment).
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, HTTPException, Request, Depends

from core.database import db
from core.auth import get_current_user

log = logging.getLogger("stripe_payments")
router = APIRouter(prefix="/stripe", tags=["Payments · Stripe"])

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
if STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat()


def _configured() -> bool:
    return bool(STRIPE_API_KEY)


async def _amount_for(kind: str, currency: str, body: Dict[str, Any],
                      user: dict) -> Dict[str, Any]:
    """Resolve the SERVER-SIDE amount + label + fulfillment metadata.

    Returns a dict with: unit_amount (smallest currency unit), label, and the
    per-kind fields needed to fulfil later (order_doc for ai_wallet; plan for
    subscription).
    """
    from core import ai_billing, ai_wallet
    cur = currency.lower()
    if cur not in ("usd", "inr"):
        raise HTTPException(400, "currency must be 'usd' or 'inr'")

    if kind == "ai_wallet":
        from routes.ai_wallet import _resolve_credits, _buyer_is_admin
        cfg = await ai_wallet.get_config()
        is_admin = _buyer_is_admin(user)
        credits = await _resolve_credits(body, cfg)
        fx, _src = await ai_billing.get_usd_to_inr(cfg.get("usd_to_inr_fallback", 90.0))
        pr = ai_billing.price_for_credits(credits, is_admin, cfg, fx)
        if pr.get("below_min"):
            raise HTTPException(400, f"Amount is below the minimum — buy more credits.")
        unit_amount = int(round(pr["total_usd"] * 100)) if cur == "usd" else int(pr["total_paise"])
        label = f"{credits} AI credits"
        order_id = f"stcr_{uuid.uuid4().hex[:16]}"
        order_doc = {
            "order_id": order_id, "user_id": user["user_id"], "credits": credits,
            "is_admin": is_admin, "amount_paise": pr["total_paise"], "breakdown": pr,
            "provider": "stripe", "status": "pending", "created_at": _iso(),
        }
        return {"unit_amount": unit_amount, "label": label,
                "order_doc": order_doc, "credits": credits}

    if kind == "subscription":
        from routes.subscriptions import get_plan
        plan_id = (body.get("plan_id") or "").strip()
        if not plan_id:
            raise HTTPException(400, "plan_id is required for a subscription")
        plan = await get_plan(plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        price_inr = float(plan.get("price_inr") or 0)
        if price_inr <= 0:
            raise HTTPException(400, "This plan is free — no payment required.")
        if cur == "inr":
            unit_amount = int(round(price_inr * 100))
        else:
            fx, _src = await ai_billing.get_usd_to_inr(90.0)
            unit_amount = int(round((price_inr / fx) * 100))
        return {"unit_amount": unit_amount, "label": f"{plan.get('name')} plan (1 month)",
                "plan": plan, "sub_id": f"stsub_{uuid.uuid4().hex[:16]}"}

    raise HTTPException(400, "kind must be 'ai_wallet' or 'subscription'")


@router.get("/status")
async def stripe_status(user: dict = Depends(get_current_user)):
    return {"configured": _configured(),
            "webhook_verified": bool(STRIPE_WEBHOOK_SECRET),
            "currencies": ["usd", "inr"]}


@router.post("/checkout")
async def create_checkout(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    if not _configured():
        raise HTTPException(500, "Stripe is not configured.")
    kind = (body.get("kind") or "").strip()
    currency = (body.get("currency") or "usd").strip().lower()
    success_url = (body.get("success_url") or "").strip()
    cancel_url = (body.get("cancel_url") or success_url).strip()
    if not success_url:
        raise HTTPException(400, "success_url is required")

    resolved = await _amount_for(kind, currency, body, user)

    sep = "&" if "?" in success_url else "?"
    session_success = f"{success_url}{sep}stripe_session={{CHECKOUT_SESSION_ID}}"

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": resolved["label"]},
                    "unit_amount": resolved["unit_amount"],
                },
                "quantity": 1,
            }],
            success_url=session_success,
            cancel_url=cancel_url,
            metadata={"user_id": user["user_id"], "kind": kind},
        )
    except Exception as e:  # noqa: BLE001
        log.error(f"Stripe session create failed: {e}")
        raise HTTPException(502, f"Stripe checkout failed: {str(e)[:160]}")

    tx: Dict[str, Any] = {
        "session_id": session.id, "user_id": user["user_id"], "kind": kind,
        "provider": "stripe", "currency": currency,
        "amount": resolved["unit_amount"], "status": "pending",
        "created_at": _iso(),
    }
    if kind == "ai_wallet":
        await db.ai_wallet_orders.insert_one({**resolved["order_doc"], "session_id": session.id})
        tx["order_id"] = resolved["order_doc"]["order_id"]
        tx["credits"] = resolved["credits"]
    elif kind == "subscription":
        tx["plan_id"] = resolved["plan"]["plan_id"]
        tx["sub_id"] = resolved["sub_id"]
    await db.stripe_payments.insert_one(tx)

    return {"checkout_url": session.url, "session_id": session.id}


async def _fulfill(session_id: str, *, source: str) -> Dict[str, Any]:
    """Fulfil a paid session exactly once (atomic pending→completed flip)."""
    tx = await db.stripe_payments.find_one_and_update(
        {"session_id": session_id, "status": "pending"},
        {"$set": {"status": "completed", "fulfilled_at": _iso(), "fulfilled_via": source}},
    )
    if not tx:
        return {"fulfilled": False, "reason": "already_fulfilled_or_unknown"}

    kind = tx.get("kind")
    try:
        if kind == "ai_wallet":
            from routes.ai_wallet import _credit_refill
            order = await db.ai_wallet_orders.find_one({"order_id": tx["order_id"]})
            if order:
                await _credit_refill(order, f"stripe:{session_id}", by="stripe")
        elif kind == "subscription":
            from routes.subscriptions import get_plan, apply_charge
            plan = await get_plan(tx["plan_id"])
            if plan:
                await apply_charge(tx["user_id"], plan, f"stripe:{session_id}",
                                   tx["sub_id"], "onetime")
    except Exception as e:  # noqa: BLE001 — revert status so a retry can re-fulfil
        log.error(f"Stripe fulfillment failed ({kind}): {e}")
        await db.stripe_payments.update_one(
            {"session_id": session_id},
            {"$set": {"status": "pending", "fulfill_error": str(e)[:200]}},
        )
        raise HTTPException(500, "Fulfillment failed; please retry.")
    return {"fulfilled": True, "kind": kind}


@router.get("/status/{session_id}")
async def payment_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.stripe_payments.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transaction not found")

    if tx["status"] == "pending" and _configured():
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:  # noqa: BLE001
            log.warning(f"Stripe session retrieve failed: {e}")
            session = None
        if session and session.get("payment_status") == "paid":
            await _fulfill(session_id, source="poll")
            tx = await db.stripe_payments.find_one(
                {"session_id": session_id}, {"_id": 0}) or tx

    return {"status": tx["status"], "kind": tx.get("kind"),
            "credits": tx.get("credits"), "plan_id": tx.get("plan_id")}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except ValueError:
            raise HTTPException(400, "Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid signature")
    else:
        # No secret configured (dev/preview) — parse without verification.
        import json
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(400, "Invalid payload")

    etype = event.get("type") if isinstance(event, dict) else event["type"]
    if etype == "checkout.session.completed":
        obj = (event["data"]["object"] if isinstance(event, dict) else event.data.object)
        session_id = obj.get("id")
        if session_id:
            try:
                await _fulfill(session_id, source="webhook")
            except HTTPException:
                pass  # let Stripe retry
    return {"received": True}


@router.get("/health")
async def stripe_health():
    return {"configured": _configured(),
            "webhook_secret_configured": bool(STRIPE_WEBHOOK_SECRET),
            "endpoint": "/api/stripe/webhook",
            "flows": ["ai_wallet", "subscription"],
            "currencies": ["usd", "inr"]}
