"""Recurring monthly subscriptions (Razorpay Subscriptions) + one-time fallback.

Hybrid model:
  • PRIMARY  — Razorpay Subscription (auto-debit via UPI AutoPay / Cards / eMandate)
  • FALLBACK — one-time order granting 1 month (manual renewal) when recurring
               methods are unavailable / rejected on the account.

Monthly entitlement = billing credits (credit_wallets), kept fully SEPARATE from
the AI-credits wallet. Dunning: a failed charge -> `pending` (grace + notify),
retry, then downgrade to Free on `halted` or when grace expires.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import get_current_user, require_super_admin
from core.database import db
from core.integrations import get_razorpay_client, resolve_razorpay_creds
from core import notify

router = APIRouter()
log = logging.getLogger("subscriptions")

GRACE_HOURS = 48
PUBLIC_APP_URL = notify.PUBLIC_APP_URL

# Real Razorpay plan IDs (verified via plan.all on the live account)
DEFAULT_PLANS: List[Dict[str, Any]] = [
    {
        "plan_id": "plan_SyQQFEOgXDv1iD", "tier": "basic", "name": "Basic",
        "price_inr": 999, "credits_per_month": 1500, "display_order": 1, "active": True,
        "features": ["Everything in Free", "CLD Engine", "Time Dezider", "AI Rescheduling", "1,500 credits / month"],
    },
    {
        "plan_id": "plan_SyQQoS2iyoiYgA", "tier": "pro", "name": "Pro",
        "price_inr": 1999, "credits_per_month": 4000, "display_order": 2, "active": True,
        "features": ["Everything in Basic", "Pros & Cons + SWOT AI", "Google Sheets sync", "Priority support", "4,000 credits / month"],
    },
    {
        "plan_id": "plan_SyQU7DMsIsdlqH", "tier": "premium", "name": "Premium",
        "price_inr": 3999, "credits_per_month": 9000, "display_order": 3, "active": True,
        "features": ["Everything in Pro", "Unlimited decisions", "Team sharing", "Dedicated success manager", "9,000 credits / month"],
    },
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ───────────────────────── plan config ─────────────────────────
async def get_plans(active_only: bool = False) -> List[Dict[str, Any]]:
    existing = await db.subscription_plans.find({}, {"_id": 0}).to_list(50)
    if not existing:
        for p in DEFAULT_PLANS:
            await db.subscription_plans.update_one(
                {"plan_id": p["plan_id"]}, {"$set": {**p, "source": "seed"}}, upsert=True
            )
        existing = await db.subscription_plans.find({}, {"_id": 0}).to_list(50)
    existing.sort(key=lambda x: x.get("display_order", 99))
    if active_only:
        existing = [p for p in existing if p.get("active", True)]
    return existing


async def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    return await db.subscription_plans.find_one({"plan_id": plan_id}, {"_id": 0})


async def recurring_available() -> bool:
    """Best-effort check whether at least one recurring method is enabled.

    We can't reliably introspect dashboard method flags via the SDK, so we treat
    recurring as 'attemptable' and rely on subscription.create succeeding. This
    helper exists for the UI hint and defaults to True.
    """
    return True


# ───────────────────────── entitlement ─────────────────────────
async def _ensure_wallet(user_id: str):
    from routes.payments import get_or_create_wallet  # deferred to avoid cycle
    return await get_or_create_wallet(user_id)


async def apply_charge(user_id: str, plan: Dict[str, Any], payment_id: str,
                       sub_id: str, mode: str) -> None:
    """Idempotently grant a month's credits + set active subscription state."""
    # idempotency: skip if this payment already processed
    if payment_id:
        seen = await db.subscriptions.find_one(
            {"subscription_id": sub_id, "processed_payments": payment_id}, {"_id": 1}
        )
        if seen:
            return
    from routes.payments import add_credits  # deferred
    from core import ai_wallet as _ai_wallet  # deferred to avoid cycle
    credits = int(plan.get("credits_per_month", 0))
    await _ensure_wallet(user_id)
    if credits > 0:
        # Legacy payments wallet (credit_wallets) — kept for audit + legacy modules
        # (ai_tools.decision_analyze, cld, time_dezider, deo) that still meter here.
        await add_credits(user_id, credits,
                          f"Subscription: {plan.get('name')} ({credits} credits/month)", payment_id)
        # Primary AI credits wallet (ai_wallets) — powers Profile → AI Credits and
        # all newer metered AI touchpoints (ai_metering, screener, conflict_breaker,
        # assessment_modes, scrape metering). This is what makes the configured
        # `credits_per_month` from Admin → Subscription Plans actually spendable
        # on AI usage across the app. Idempotency is guaranteed by the
        # payment_id/processed_payments guard above.
        try:
            await _ai_wallet.grant(
                user_id, float(credits),
                by="subscription",
                note=f"Subscription: {plan.get('name')} ({credits} credits/month) [pay={payment_id}]",
                kind="grant",
            )
        except Exception as _e:  # never break checkout on wallet write
            import logging as _lg
            _lg.getLogger("subscriptions").warning(
                "ai_wallet.grant failed for user=%s pay=%s: %s", user_id, payment_id, _e
            )
    now = _now()
    status = "manual" if mode == "onetime" else "active"
    await db.credit_wallets.update_one(
        {"user_id": user_id},
        {"$set": {
            "current_plan": plan.get("tier", plan.get("plan_id")),
            "subscription_plan_id": plan.get("plan_id"),
            "subscription_id": sub_id,
            "subscription_status": status,
            "subscription_mode": mode,
            "subscription_end": _iso(now + timedelta(days=30)),
            "plan_credits_remaining": credits,
            "grace_until": None,
            "updated_at": _iso(now),
        }},
        upsert=True,
    )
    if sub_id:
        await db.subscriptions.update_one(
            {"subscription_id": sub_id},
            {"$addToSet": {"processed_payments": payment_id}, "$set": {"status": status, "updated_at": _iso(now)}},
            upsert=True,
        )


async def downgrade_to_free(user_id: str, reason: str = "") -> None:
    now = _now()
    await db.credit_wallets.update_one(
        {"user_id": user_id},
        {"$set": {
            "current_plan": "free", "subscription_status": "none", "subscription_mode": None,
            "subscription_end": None, "grace_until": None, "plan_credits_remaining": 0,
            "updated_at": _iso(now), "downgrade_reason": reason,
        }},
    )


async def _start_grace(user_id: str, sub_id: str) -> None:
    now = _now()
    await db.credit_wallets.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_status": "pending", "grace_until": _iso(now + timedelta(hours=GRACE_HOURS)),
                  "updated_at": _iso(now)}},
    )


# ───────────────────────── user endpoints ─────────────────────────
@router.get("/subscriptions/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    plans = await get_plans(active_only=True)
    return {
        "plans": [{
            "plan_id": p["plan_id"], "tier": p["tier"], "name": p["name"],
            "price_inr": p["price_inr"], "credits_per_month": p["credits_per_month"],
            "features": p.get("features", []), "display_order": p.get("display_order", 99),
        } for p in plans],
        "recurring_available": await recurring_available(),
        "currency": "INR",
    }


@router.get("/subscriptions/me")
async def my_subscription(user: dict = Depends(get_current_user)):
    w = await _ensure_wallet(user["user_id"])
    # lazy dunning: if grace expired and still pending, downgrade
    status = w.get("subscription_status")
    grace = w.get("grace_until")
    if status == "pending" and grace and grace < _iso(_now()):
        await downgrade_to_free(user["user_id"], "grace_expired")
        await notify.notify_user(
            user["user_id"], "Your JELCOS AI subscription was downgraded",
            ["We couldn't process your renewal after multiple attempts, so your plan has been moved to Free.",
             "Re-subscribe anytime to restore your monthly credits and premium features."],
            "JELCOS AI: Your subscription renewal failed and your plan is now Free. Re-subscribe anytime to restore premium features.",
            cta_text="Re-subscribe", cta_url=f"{PUBLIC_APP_URL}",
        )
        w = await _ensure_wallet(user["user_id"])
    plan = None
    if w.get("subscription_plan_id"):
        plan = await get_plan(w["subscription_plan_id"])
    return {
        "current_plan": w.get("current_plan") or "free",
        "subscription_plan_id": w.get("subscription_plan_id"),
        "status": w.get("subscription_status") or "none",
        "mode": w.get("subscription_mode"),
        "subscription_id": w.get("subscription_id"),
        "subscription_end": w.get("subscription_end"),
        "grace_until": w.get("grace_until"),
        "plan_credits_remaining": w.get("plan_credits_remaining", 0),
        "plan": plan,
    }


@router.post("/subscriptions/create")
async def create_subscription(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Try a real recurring subscription; auto-fallback to a one-time order."""
    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")
    plan_id = body.get("plan_id", "")
    plan = await get_plan(plan_id)
    if not plan or not plan.get("active", True):
        raise HTTPException(status_code=400, detail="Invalid or inactive plan.")

    # 1) Attempt recurring subscription — auto-attach highest-priority
    # Razorpay subscription offer if the admin has flagged one for
    # apply_flows = ['recurring']. Silently no-op if none configured.
    try:
        from routes.razorpay_offers import get_best_offer_for_flow
        recurring_offer_id = await get_best_offer_for_flow("recurring")
    except Exception:
        recurring_offer_id = None

    try:
        sub_payload: Dict[str, Any] = {
            "plan_id": plan_id,
            "total_count": 120,          # up to 10 years of monthly cycles
            "quantity": 1,
            "customer_notify": 1,
            "notes": {"user_id": user["user_id"], "tier": plan["tier"], "name": user.get("name", "")},
        }
        if recurring_offer_id:
            sub_payload["offer_id"] = recurring_offer_id
        sub = rzp_client.subscription.create(sub_payload)
        await db.subscriptions.update_one(
            {"subscription_id": sub["id"]},
            {"$set": {
                "subscription_id": sub["id"], "user_id": user["user_id"], "plan_id": plan_id,
                "tier": plan["tier"], "status": sub.get("status", "created"),
                "mode": "recurring", "short_url": sub.get("short_url"),
                "offer_id": recurring_offer_id,
                "created_at": _iso(_now()), "processed_payments": [],
            }},
            upsert=True,
        )
        return {
            "mode": "recurring", "subscription_id": sub["id"], "short_url": sub.get("short_url"),
            "key_id": key_id, "plan": {"name": plan["name"], "price_inr": plan["price_inr"]},
            "status": sub.get("status"), "offer_id": recurring_offer_id,
        }
    except Exception as e:
        log.warning(f"subscription.create failed ({str(e)[:160]}); falling back to one-time order.")

    # 2) Fallback — one-time order (manual renewal)
    return await _make_onetime_order(rzp_client, key_id, plan, user)


async def _make_onetime_order(rzp_client, key_id, plan, user) -> Dict[str, Any]:
    amount_paise = int(plan["price_inr"]) * 100
    ts = int(_now().timestamp())

    # Auto-attach any active Razorpay one-time offers (bank / card / UPI
    # instant-discount + cashback) admin has flagged for this flow.
    try:
        from routes.razorpay_offers import get_offers_for_flow
        onetime_offer_ids = await get_offers_for_flow("onetime")
    except Exception:
        onetime_offer_ids = []

    order_payload: Dict[str, Any] = {
        "amount": amount_paise, "currency": "INR", "payment_capture": 1,
        "receipt": f"sub1_{user['user_id'][:8]}_{ts}"[:40],
        "notes": {"user_id": user["user_id"], "plan_id": plan["plan_id"], "tier": plan["tier"], "type": "subscription_onetime"},
    }
    if onetime_offer_ids:
        order_payload["offers"] = onetime_offer_ids

    order = rzp_client.order.create(order_payload)
    await db.payment_orders.insert_one({
        "order_id": order["id"], "user_id": user["user_id"], "type": "subscription_onetime",
        "plan_id": plan["plan_id"], "tier": plan["tier"], "credits": plan["credits_per_month"],
        "amount_paise": amount_paise, "status": "created", "created_at": _iso(_now()),
        "offer_ids": onetime_offer_ids,
    })
    return {
        "mode": "onetime", "order_id": order["id"], "amount": amount_paise, "key_id": key_id,
        "credits": plan["credits_per_month"], "plan": {"name": plan["name"], "price_inr": plan["price_inr"]},
        "user_name": user.get("name", ""), "user_email": user.get("email", ""),
        "offer_ids": onetime_offer_ids,
    }


@router.post("/subscriptions/create-onetime")
async def create_onetime(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Explicit one-time monthly payment (used by the 'Pay once' fallback button)."""
    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")
    plan = await get_plan(body.get("plan_id", ""))
    if not plan or not plan.get("active", True):
        raise HTTPException(status_code=400, detail="Invalid or inactive plan.")
    return await _make_onetime_order(rzp_client, key_id, plan, user)


@router.post("/subscriptions/verify-onetime")
async def verify_onetime(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    oid = body.get("razorpay_order_id", "")
    pid = body.get("razorpay_payment_id", "")
    sig = body.get("razorpay_signature", "")
    if not all([oid, pid, sig]):
        raise HTTPException(status_code=400, detail="Missing payment verification fields.")
    _, key_secret, _ = await resolve_razorpay_creds()
    expected = hmac.new(key_secret.encode("utf-8"), f"{oid}|{pid}".encode("utf-8"), hashlib.sha256).hexdigest()
    if expected != sig:
        raise HTTPException(status_code=400, detail="Payment verification failed — invalid signature.")
    order_doc = await db.payment_orders.find_one({"order_id": oid, "user_id": user["user_id"]}, {"_id": 0})
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order_doc.get("status") == "paid":
        return {"message": "Already processed"}
    await db.payment_orders.update_one(
        {"order_id": oid}, {"$set": {"status": "paid", "razorpay_payment_id": pid, "paid_at": _iso(_now())}})
    plan = await get_plan(order_doc["plan_id"])
    if plan:
        await apply_charge(user["user_id"], plan, pid, sub_id=f"onetime_{pid}", mode="onetime")
    return {"message": "Payment verified", "credits_added": order_doc.get("credits", 0), "mode": "onetime"}


@router.post("/subscriptions/cancel")
async def cancel_subscription(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    w = await _ensure_wallet(user["user_id"])
    sub_id = w.get("subscription_id")
    mode = w.get("subscription_mode")
    if mode != "recurring" or not sub_id or str(sub_id).startswith("onetime_"):
        # nothing to cancel at Razorpay (manual/one-time) — just stop auto-renew locally
        await db.credit_wallets.update_one({"user_id": user["user_id"]},
                                           {"$set": {"subscription_status": "cancelled", "updated_at": _iso(_now())}})
        return {"message": "Subscription will not renew. Access continues until the period ends."}
    rzp_client, _, _ = await get_razorpay_client()
    cancel_at_cycle_end = 0 if body.get("immediate") else 1
    try:
        rzp_client.subscription.cancel(sub_id, {"cancel_at_cycle_end": cancel_at_cycle_end})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not cancel subscription: {str(e)[:160]}")
    await db.credit_wallets.update_one({"user_id": user["user_id"]},
                                       {"$set": {"subscription_status": "cancelled", "updated_at": _iso(_now())}})
    await db.subscriptions.update_one({"subscription_id": sub_id}, {"$set": {"status": "cancelled"}})
    return {"message": "Subscription cancelled.", "cancel_at_cycle_end": bool(cancel_at_cycle_end)}


# ───────────────────────── webhook ─────────────────────────
@router.post("/subscriptions/webhook")
async def subscription_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    _, _, webhook_secret = await resolve_razorpay_creds()
    if webhook_secret and sig:
        expected = hmac.new(webhook_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        if expected != sig:
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    try:
        data = json.loads(payload)
    except Exception:
        return {"status": "ignored"}

    event = data.get("event", "")
    sub_entity = (data.get("payload", {}) or {}).get("subscription", {}).get("entity", {}) or {}
    pay_entity = (data.get("payload", {}) or {}).get("payment", {}).get("entity", {}) or {}
    sub_id = sub_entity.get("id", "")

    sub_doc = await db.subscriptions.find_one({"subscription_id": sub_id}, {"_id": 0}) if sub_id else None
    user_id = (sub_doc or {}).get("user_id") or (sub_entity.get("notes", {}) or {}).get("user_id")
    plan_id = (sub_doc or {}).get("plan_id") or sub_entity.get("plan_id")

    try:
        if event in ("subscription.charged", "subscription.activated") and user_id and plan_id:
            plan = await get_plan(plan_id)
            if plan:
                await apply_charge(user_id, plan, pay_entity.get("id", ""), sub_id, mode="recurring")
        elif event == "subscription.pending" and user_id:
            await _start_grace(user_id, sub_id)
            await notify.notify_user(
                user_id, "Action needed: your JELCOS AI renewal failed",
                ["We couldn't auto-debit your subscription this cycle.",
                 f"We'll retry automatically within {GRACE_HOURS} hours. Your access continues for now.",
                 "If the retry also fails, your plan will be downgraded to Free. Please ensure your payment method is active."],
                f"JELCOS AI: Your subscription renewal failed. We'll retry within {GRACE_HOURS}h — access continues. If it fails again your plan will downgrade to Free.",
                cta_text="Update payment", cta_url=PUBLIC_APP_URL,
            )
        elif event == "subscription.halted" and user_id:
            await downgrade_to_free(user_id, "halted")
            await db.subscriptions.update_one({"subscription_id": sub_id}, {"$set": {"status": "halted"}})
            await notify.notify_user(
                user_id, "Your JELCOS AI subscription was downgraded",
                ["After repeated failed renewal attempts, your subscription has been moved to Free.",
                 "Re-subscribe anytime to instantly restore your monthly credits and premium features."],
                "JELCOS AI: Your subscription was downgraded to Free after failed renewals. Re-subscribe anytime to restore premium features.",
                cta_text="Re-subscribe", cta_url=PUBLIC_APP_URL,
            )
        elif event in ("subscription.cancelled", "subscription.completed") and user_id:
            await db.credit_wallets.update_one({"user_id": user_id},
                                               {"$set": {"subscription_status": "cancelled", "updated_at": _iso(_now())}})
            await db.subscriptions.update_one({"subscription_id": sub_id}, {"$set": {"status": event.split(".")[1]}})
    except Exception as e:
        log.error(f"subscription webhook handling error for {event}: {str(e)[:200]}")
    return {"status": "processed"}


# ───────────────────────── admin endpoints ─────────────────────────
@router.get("/admin/subscriptions/plans")
async def admin_list_plans(user: dict = Depends(require_super_admin)):
    return {"plans": await get_plans(active_only=False)}


@router.put("/admin/subscriptions/plans/{plan_id}")
async def admin_update_plan(plan_id: str, body: Dict[str, Any], user: dict = Depends(require_super_admin)):
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    patch: Dict[str, Any] = {}
    if "credits_per_month" in body:
        try:
            patch["credits_per_month"] = max(0, int(float(body["credits_per_month"])))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="credits_per_month must be a number.")
    if "name" in body:
        patch["name"] = str(body["name"]).strip() or plan["name"]
    if "active" in body:
        patch["active"] = bool(body["active"])
    if "display_order" in body:
        try:
            patch["display_order"] = int(body["display_order"])
        except (TypeError, ValueError):
            pass
    if "features" in body and isinstance(body["features"], list):
        patch["features"] = [str(f) for f in body["features"]][:12]
    if not patch:
        return plan
    patch["updated_by"] = user["user_id"]
    patch["updated_at"] = _iso(_now())
    await db.subscription_plans.update_one({"plan_id": plan_id}, {"$set": patch})
    return await get_plan(plan_id)


@router.post("/admin/subscriptions/sync")
async def admin_sync_plans(user: dict = Depends(require_super_admin)):
    """Pull live plans from Razorpay so the local catalog *actually* mirrors
    the gateway.

    Behaviour:
      - UPSERTS every Razorpay plan (previously we only UPDATE'd existing rows,
        so brand-new Razorpay plans were silently skipped — that was the bug
        the user reported).
      - New plans are inserted as ACTIVE with sensible defaults so admin can
        immediately set 'credits_per_month' and Save.
      - Plans that no longer exist on Razorpay are marked orphaned+inactive so
        they disappear from the user-facing pricing page but stay in DB for
        history/audit.
      - Paginates over Razorpay in batches of 100 (was hardcoded 25 → could
        silently truncate once catalog grows).
      - Returns counts so the admin UI can show a real result.
    """
    rzp_client, _, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")
    await get_plans()  # ensure seeded

    inserted = updated = 0
    seen_ids: List[str] = []
    try:
        # Paginate to be safe once the catalog grows past 25 plans.
        skip = 0
        while True:
            page = rzp_client.plan.all({"count": 100, "skip": skip})
            items = page.get("items", [])
            if not items:
                break
            for p in items:
                pid = p["id"]
                seen_ids.append(pid)
                item = p.get("item", {})
                name = item.get("name", "") or "Unnamed plan"
                price_inr = int(int(item.get("amount", 0)) / 100)
                interval_unit = p.get("period") or "monthly"
                billing_cycle = "monthly" if interval_unit.startswith("mon") else interval_unit
                now_iso = _iso(_now())

                existing = await db.subscription_plans.find_one({"plan_id": pid}, {"_id": 0})
                if existing:
                    # Refresh price/name; do NOT clobber admin-set fields
                    # (credits_per_month, key_benefits, active toggle, tier).
                    await db.subscription_plans.update_one(
                        {"plan_id": pid},
                        {"$set": {
                            "price_inr": price_inr,
                            "razorpay_name": name,
                            "billing_cycle": billing_cycle,
                            "source": "razorpay_sync",
                            "synced_at": now_iso,
                        }},
                    )
                    updated += 1
                else:
                    # Brand-new Razorpay plan → INSERT with safe defaults so
                    # admin can immediately edit credits & benefits.
                    slug = name.lower().replace(" ", "_")[:40] or pid
                    await db.subscription_plans.update_one(
                        {"plan_id": pid},
                        {"$set": {
                            "plan_id": pid,
                            "tier": slug,
                            "name": name,
                            "razorpay_name": name,
                            "price_inr": price_inr,
                            "billing_cycle": billing_cycle,
                            "credits_per_month": 0,
                            "key_benefits": [],
                            "active": True,
                            "display_order": 99,
                            "source": "razorpay_sync",
                            "synced_at": now_iso,
                            "created_at": now_iso,
                        }},
                        upsert=True,
                    )
                    inserted += 1
            if len(items) < 100:
                break
            skip += 100

        # Mark any DB plan not seen on Razorpay as orphaned+inactive.
        orphaned = await db.subscription_plans.update_many(
            {"plan_id": {"$nin": seen_ids}, "source": {"$ne": "seed_manual"}},
            {"$set": {"active": False, "source": "orphaned", "synced_at": _iso(_now())}},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)[:160]}")

    return {
        "message": f"Synced from Razorpay — {inserted} new, {updated} updated, {orphaned.modified_count} orphaned.",
        "inserted": inserted,
        "updated": updated,
        "orphaned": orphaned.modified_count,
        "plans": await get_plans(),
    }


# ───────────────────────── admin: subscribers & backfill ─────────────────────────
@router.get("/admin/subscribers")
async def admin_list_subscribers(
    status: Optional[str] = None,
    limit: int = 500,
    user: dict = Depends(require_super_admin),
):
    """Roster of every user who ever paid — active, cancelled, pending or manual.

    Optional `status` filter matches `credit_wallets.subscription_status`.
    Attaches user email/name, current plan info, and BOTH wallet balances
    (`credit_wallets.credits` legacy + `ai_wallets.balance` primary) so the
    Admin can see exactly what a paid user sees on their Profile.
    """
    q: Dict[str, Any] = {"subscription_plan_id": {"$ne": None}}
    if status:
        q["subscription_status"] = status
    cursor = db.credit_wallets.find(q, {"_id": 0}).sort("updated_at", -1).limit(min(max(limit, 1), 2000))
    rows = await cursor.to_list(2000)

    uids = [r["user_id"] for r in rows if r.get("user_id")]
    users_map: Dict[str, Dict[str, Any]] = {}
    ai_map: Dict[str, float] = {}
    plans_map: Dict[str, Dict[str, Any]] = {}
    if uids:
        async for u in db.users.find(
            {"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "email": 1, "name": 1, "user_type": 1}
        ):
            users_map[u["user_id"]] = u
        async for aw in db.ai_wallets.find(
            {"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "balance": 1}
        ):
            ai_map[aw["user_id"]] = float(aw.get("balance", 0))
    plan_ids = list({r.get("subscription_plan_id") for r in rows if r.get("subscription_plan_id")})
    if plan_ids:
        async for p in db.subscription_plans.find(
            {"plan_id": {"$in": plan_ids}}, {"_id": 0, "plan_id": 1, "name": 1, "tier": 1, "price_inr": 1, "credits_per_month": 1}
        ):
            plans_map[p["plan_id"]] = p

    items = []
    for r in rows:
        uid = r.get("user_id")
        u = users_map.get(uid, {})
        p = plans_map.get(r.get("subscription_plan_id"), {})
        items.append({
            "user_id": uid,
            "email": u.get("email", ""),
            "name": u.get("name", ""),
            "user_type": u.get("user_type", ""),
            "plan_id": r.get("subscription_plan_id"),
            "plan_name": p.get("name", ""),
            "tier": r.get("current_plan") or p.get("tier", ""),
            "plan_price_inr": p.get("price_inr", 0),
            "plan_credits_per_month": p.get("credits_per_month", 0),
            "subscription_id": r.get("subscription_id"),
            "subscription_status": r.get("subscription_status"),
            "subscription_mode": r.get("subscription_mode"),
            "subscription_end": r.get("subscription_end"),
            "legacy_credit_wallet": int(r.get("credits", 0)),
            "ai_wallet_balance": round(float(ai_map.get(uid, 0.0)), 2),
            "updated_at": r.get("updated_at"),
        })
    return {"count": len(items), "items": items}


@router.post("/admin/subscriptions/backfill-ai-wallet")
async def admin_backfill_ai_wallet(
    body: Optional[Dict[str, Any]] = None,
    user: dict = Depends(require_super_admin),
):
    """One-shot retroactive credit grant for users who paid BEFORE the
    `apply_charge → ai_wallet.grant` fix (v3.143). Historical paid data lives
    in MULTIPLE places (`credit_wallets` was populated inconsistently by three
    different subscription flows over time), so this scans ALL of them:

      1. `payment_orders` with status='paid' and type in ('subscription',
         'subscription_onetime')   → primary source of truth for what a user
         actually paid for. `order.credits` is the amount to grant.
      2. `subscriptions` with a non-empty `processed_payments` list        →
         real Razorpay recurring charges. For each captured payment_id we
         grant one month of `plan.credits_per_month` (Razorpay plan_id looked
         up in `db.subscription_plans`).
      3. `credit_transactions` where description starts with "Subscription:"
         or "Webhook: payment captured" (legacy `add_credits` from the old
         `routes/payments.py` flow) → uses the transaction's `credits` field.

    All entries are deduped by `(user_id, payment_id)` and idempotent — a
    second call skips users who already have an `ai_wallet_ledger` row for
    that same payment_id.

    body (optional): { dry_run: bool }
    """
    from core import ai_wallet as _ai_wallet
    body = body or {}
    dry_run = bool(body.get("dry_run", False))

    # Preload admin-configured plans for Razorpay plan_id → credits/name lookup
    plans_map: Dict[str, Dict[str, Any]] = {}
    async for p in db.subscription_plans.find({}, {"_id": 0}):
        plans_map[p["plan_id"]] = p

    # dedup by (user_id, payment_id)  →  grant record
    grants: Dict[str, Dict[str, Any]] = {}

    def _add(uid: str, payment_id: str, credits: int, plan_label: str, source: str,
             sub_id: str = ""):
        if not uid or credits <= 0:
            return
        key = f"{uid}|{payment_id or source}"
        if key in grants:
            return  # already captured from another source
        grants[key] = {
            "user_id": uid,
            "payment_id": payment_id,
            "credits": int(credits),
            "plan_label": plan_label,
            "source": source,
            "sub_id": sub_id,
        }

    # (1) payment_orders — paid subscriptions
    async for o in db.payment_orders.find(
        {"status": "paid", "type": {"$in": ["subscription", "subscription_onetime"]}},
        {"_id": 0},
    ):
        uid = o.get("user_id") or ""
        pid = o.get("razorpay_payment_id") or o.get("order_id") or ""
        plan_id = o.get("plan_id") or ""
        credits = int(o.get("credits") or 0)
        # If plan_id is an admin Razorpay plan, prefer the current credits_per_month
        p = plans_map.get(plan_id)
        if p and int(p.get("credits_per_month", 0)) > 0:
            credits = int(p["credits_per_month"])
            plan_label = p.get("name") or plan_id
        else:
            plan_label = plan_id or "subscription"
        _add(uid, pid, credits, plan_label, source="payment_orders")

    # (2) subscriptions — real Razorpay recurring, one grant per captured payment
    async for s in db.subscriptions.find(
        {"processed_payments": {"$exists": True, "$ne": []}},
        {"_id": 0},
    ):
        uid = s.get("user_id") or ""
        plan_id = s.get("plan_id") or ""
        p = plans_map.get(plan_id) or {}
        credits = int(p.get("credits_per_month", 0))
        if credits <= 0:
            continue
        plan_label = p.get("name") or plan_id or "subscription"
        for pid in (s.get("processed_payments") or []):
            _add(uid, str(pid), credits, plan_label,
                 source="subscriptions", sub_id=s.get("subscription_id") or "")

    # (3) credit_transactions — legacy add_credits audit trail
    async for tx in db.credit_transactions.find(
        {"type": "purchase",
         "description": {"$regex": "Subscription|Webhook: payment captured", "$options": "i"}},
        {"_id": 0},
    ):
        uid = tx.get("user_id") or ""
        pid = tx.get("payment_id") or ""
        credits = int(tx.get("credits") or 0)
        _add(uid, pid, credits, tx.get("description", "subscription"),
             source="credit_transactions")

    # Apply grants (with idempotency check per (user_id, payment_id))
    scanned = len(grants)
    granted = skipped = 0
    total_credits = 0
    details: List[Dict[str, Any]] = []

    for g in grants.values():
        uid = g["user_id"]
        pid = g["payment_id"]
        credits = g["credits"]

        # Idempotency: has this payment_id already been backfilled?
        marker = {"user_id": uid, "by": "subscription-backfill"}
        if pid:
            marker["note"] = {"$regex": f"pay={re.escape(pid)}"}
        existing = await db.ai_wallet_ledger.find_one(marker, {"_id": 1})
        if existing:
            skipped += 1
            details.append({**g, "action": "skip", "reason": "already_backfilled"})
            continue

        if dry_run:
            granted += 1
            total_credits += credits
            details.append({**g, "action": "would_grant"})
            continue

        try:
            await _ai_wallet.grant(
                uid, float(credits),
                by="subscription-backfill",
                note=f"Backfill: {g['plan_label']} ({credits} credits) [pay={pid} src={g['source']}]",
                kind="grant",
            )
            granted += 1
            total_credits += credits
            details.append({**g, "action": "granted"})
        except Exception as e:
            skipped += 1
            details.append({**g, "action": "error", "reason": str(e)[:120]})

    # Also update the credit_wallets subscription pointer for any user whose
    # subscription_plan_id is currently missing, using the latest paid order.
    # This makes the /admin/subscribers screen surface them properly.
    if not dry_run:
        seen_users: set = set()
        for g in grants.values():
            uid = g["user_id"]
            if uid in seen_users:
                continue
            seen_users.add(uid)
            # Find the most recent paid subscription order for this user
            latest = await db.payment_orders.find_one(
                {"user_id": uid, "status": "paid",
                 "type": {"$in": ["subscription", "subscription_onetime"]}},
                {"_id": 0}, sort=[("paid_at", -1)],
            )
            if not latest:
                continue
            plan_id = latest.get("plan_id") or ""
            # Only set fields that are currently blank — never clobber
            existing_w = await db.credit_wallets.find_one(
                {"user_id": uid}, {"_id": 0, "subscription_plan_id": 1, "current_plan": 1},
            )
            set_fields: Dict[str, Any] = {}
            if existing_w and not existing_w.get("subscription_plan_id") and plan_id:
                set_fields["subscription_plan_id"] = plan_id
            if existing_w and (existing_w.get("current_plan") in (None, "", "free")):
                p = plans_map.get(plan_id, {})
                if p.get("tier"):
                    set_fields["current_plan"] = p["tier"]
                elif plan_id:
                    set_fields["current_plan"] = plan_id
            if set_fields:
                set_fields["updated_at"] = _iso(_now())
                set_fields.setdefault("subscription_status", "manual")
                await db.credit_wallets.update_one(
                    {"user_id": uid}, {"$set": set_fields}, upsert=True,
                )

    return {
        "dry_run": dry_run,
        "scanned": scanned,
        "granted": granted,
        "skipped": skipped,
        "total_credits_granted": total_credits,
        "sources_scanned": ["payment_orders", "subscriptions", "credit_transactions"],
        "details": details[:200],  # cap payload
    }


# ───────────────────────── dunning background task ─────────────────────────
async def _dunning_loop():
    """Hourly: downgrade subscriptions whose 48h grace has expired (belt-and-suspenders
    in addition to Razorpay's subscription.halted webhook)."""
    while True:
        try:
            now_iso = _iso(_now())
            cursor = db.credit_wallets.find(
                {"subscription_status": "pending", "grace_until": {"$lt": now_iso, "$ne": None}},
                {"_id": 0, "user_id": 1},
            )
            async for w in cursor:
                uid = w["user_id"]
                await downgrade_to_free(uid, "grace_expired")
                await notify.notify_user(
                    uid, "Your JELCOS AI subscription was downgraded",
                    ["We couldn't process your renewal after multiple attempts, so your plan is now Free.",
                     "Re-subscribe anytime to restore your monthly credits and premium features."],
                    "JELCOS AI: Your subscription renewal failed and your plan is now Free. Re-subscribe anytime.",
                    cta_text="Re-subscribe", cta_url=PUBLIC_APP_URL,
                )
        except Exception as e:
            log.error(f"dunning loop error: {str(e)[:160]}")
        await asyncio.sleep(3600)  # 1 hour


def start_dunning_task():
    try:
        asyncio.create_task(_dunning_loop())
        log.info("Subscription dunning task started (hourly grace-expiry sweep).")
    except RuntimeError as e:
        log.warning(f"Could not start dunning task: {e}")


# ───────────────────────── hosted one-time checkout ─────────────────────────
from fastapi.responses import HTMLResponse  # noqa: E402

_SUB_CHECKOUT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JELCOS AI — Subscription Payment</title>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<style>body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#F5F7FA;margin:0;
 display:flex;align-items:center;justify-content:center;height:100vh;color:#1A1A2E}
 .card{background:#fff;border-radius:16px;padding:28px;max-width:360px;width:90%;
 box-shadow:0 6px 24px rgba(0,0,0,.08);text-align:center}
 h2{margin:8px 0 4px}.ok{color:#10B981;font-weight:700}.err{color:#EF4444;font-weight:700}
 .btn{margin-top:16px;background:#5E35B1;color:#fff;border:none;border-radius:12px;padding:12px 20px;font-size:15px;font-weight:700;cursor:pointer}</style>
</head><body><div class="card"><h2>JELCOS AI Subscription</h2>
<p id="msg">Opening secure Razorpay checkout…</p>
<button class="btn" id="payBtn" style="display:none" onclick="startPay()">Pay now</button></div>
<script>
 var O={order_id:"__ORDER_ID__",key:"__KEY_ID__",amount:__AMOUNT__,name:"__NAME__",email:"__EMAIL__",token:"__TOKEN__"};
 function setMsg(t,c){var m=document.getElementById('msg');m.innerHTML=t;m.className=c||'';}
 function startPay(){document.getElementById('payBtn').style.display='none';
  var rzp=new Razorpay({key:O.key,amount:O.amount,currency:"INR",order_id:O.order_id,
   name:"JELCOS AI",description:"Monthly plan",prefill:{name:O.name,email:O.email},theme:{color:"#5E35B1"},
   handler:function(r){setMsg('Verifying payment…');
    fetch('/api/subscriptions/verify-onetime',{method:'POST',
     headers:{'Content-Type':'application/json','Authorization':'Bearer '+O.token},
     body:JSON.stringify({razorpay_order_id:r.razorpay_order_id,razorpay_payment_id:r.razorpay_payment_id,razorpay_signature:r.razorpay_signature})})
     .then(function(res){return res.json().then(function(d){return {ok:res.ok,d:d}})})
     .then(function(x){if(x.ok){setMsg('✓ Payment successful — your plan is active. You can close this window.','ok');}
      else{setMsg('Verification failed: '+((x.d&&x.d.detail)||'')+'. Contact support if charged.','err');}})
     .catch(function(){setMsg('Verification network error. If charged, your plan will activate shortly.','err');});},
   modal:{ondismiss:function(){setMsg('Payment cancelled.','err');document.getElementById('payBtn').style.display='inline-block';}}});
  rzp.on('payment.failed',function(){setMsg('Payment failed. Please try again.','err');document.getElementById('payBtn').style.display='inline-block';});
  rzp.open();}
 window.onload=function(){if(window.Razorpay){startPay();}else{setMsg('Could not load Razorpay.','err');}};
</script></body></html>"""


@router.get("/subscriptions/checkout", response_class=HTMLResponse)
async def subscription_checkout(order_id: str, key_id: str, amount: int, token: str = "", name: str = "", email: str = ""):
    def esc(s: str) -> str:
        return (s or "").replace("\\", "").replace('"', "'").replace("<", "").replace(">", "")
    html = (_SUB_CHECKOUT_HTML
            .replace("__ORDER_ID__", esc(order_id)).replace("__KEY_ID__", esc(key_id))
            .replace("__AMOUNT__", str(int(amount))).replace("__NAME__", esc(name))
            .replace("__EMAIL__", esc(email)).replace("__TOKEN__", esc(token)))
    # Route-scoped CSP so the Razorpay checkout script/iframe is allowed on this
    # payment page (the global security middleware honours a route-set CSP).
    from core.hardening import RAZORPAY_CSP
    return HTMLResponse(content=html, headers={"Content-Security-Policy": RAZORPAY_CSP})
