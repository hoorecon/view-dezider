"""
Payment & Credits System
- Credit balance tracking per user/org
- 5 Monthly subscription packages (Razorpay Subscriptions)
- 5 Top-up credit packs (Razorpay Orders)
- Credit deduction per AI action
- SuperAdmin configurable initial credits
- Payment history
"""

import uuid
import os
import hmac
import hashlib
import json as json_module
import logging
import razorpay
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user
from core.integrations import get_razorpay_client, resolve_razorpay_creds
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)
router = APIRouter()

# ========================
# RAZORPAY CLIENT
# ========================

RZP_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RZP_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

rzp_client = None
if RZP_KEY_ID and RZP_KEY_SECRET:
    rzp_client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))

# ========================
# PRICING CONFIGURATION
# ========================

# Subscription Plans (monthly, prices in paise)
SUBSCRIPTION_PLANS = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_inr": 0,
        "price_paise": 0,
        "credits_per_month": 0,
        "features": ["Basic PRR Flow", "CTT Task Tracker", "Lifestyle Dezider", "TEPFI Matrix"],
        "description": "Get started with core decision tools",
        "badge_color": "#94A3B8",
    },
    "starter": {
        "id": "starter",
        "name": "Starter",
        "price_inr": 149,
        "price_paise": 14900,
        "credits_per_month": 300,
        "features": ["Everything in Free", "CLD Engine", "Time Dezider", "AI Rescheduling", "Google Calendar Sync"],
        "description": "For individuals optimizing daily decisions",
        "badge_color": "#3B82F6",
        "popular": False,
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_inr": 399,
        "price_paise": 39900,
        "credits_per_month": 800,
        "features": ["Everything in Starter", "Time Store", "DEO Engine", "Solutions Store", "Advanced Simulation"],
        "description": "For professionals who value every hour",
        "badge_color": "#7C3AED",
        "popular": True,
    },
    "business": {
        "id": "business",
        "name": "Business",
        "price_inr": 799,
        "price_paise": 79900,
        "credits_per_month": 2000,
        "features": ["Everything in Pro", "Organization Features", "Team Management", "API Access (DEO)", "Priority Processing"],
        "description": "For teams making better decisions together",
        "badge_color": "#059669",
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Enterprise",
        "price_inr": 1999,
        "price_paise": 199900,
        "credits_per_month": 5000,
        "features": ["Everything in Business", "Unlimited Team Members", "White-label Options", "Dedicated Support", "Custom Integrations"],
        "description": "For organizations transforming decision culture",
        "badge_color": "#DC2626",
    },
}

# Top-up Packs (one-time, prices in paise)
TOPUP_PACKS = [
    {"id": "micro", "name": "Micro", "price_inr": 29, "price_paise": 2900, "credits": 50, "badge": "Starter"},
    {"id": "mini", "name": "Mini", "price_inr": 79, "price_paise": 7900, "credits": 150, "badge": "Popular"},
    {"id": "standard", "name": "Standard", "price_inr": 199, "price_paise": 19900, "credits": 400, "badge": "Value"},
    {"id": "mega", "name": "Mega", "price_inr": 499, "price_paise": 49900, "credits": 1200, "badge": "Best Deal"},
    {"id": "ultra", "name": "Ultra", "price_inr": 999, "price_paise": 99900, "credits": 3000, "badge": "Power User"},
]

# Credit costs per AI action
CREDIT_COSTS = {
    "cld_generate": 3,
    "cld_simulate": 0,
    "time_dezider_reschedule": 3,
    "time_store_analyze": 5,
    "deo_scrape": 3,
    "decision_analyze": 2,
    "solution_finder": 2,
}

DEFAULT_INITIAL_CREDITS = 100

# ========================
# HELPER FUNCTIONS
# ========================

async def get_or_create_wallet(user_id: str) -> dict:
    """Get or create a credit wallet for a user"""
    wallet = await db.credit_wallets.find_one({"user_id": user_id}, {"_id": 0})
    if not wallet:
        # Check if org has custom initial credits
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        org_id = user.get("org_id") if user else None
        initial_credits = DEFAULT_INITIAL_CREDITS

        if org_id:
            org_settings = await db.org_settings.find_one({"org_id": org_id}, {"_id": 0})
            if org_settings and "initial_credits" in org_settings:
                initial_credits = org_settings["initial_credits"]

        wallet = {
            "user_id": user_id,
            "credits": initial_credits,
            "initial_credits": initial_credits,
            "total_purchased": 0,
            "total_used": 0,
            "current_plan": "free",
            "plan_credits_remaining": 0,
            "subscription_id": None,
            "subscription_status": None,
            "subscription_end": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.credit_wallets.insert_one(wallet)
        wallet.pop("_id", None)

        # Log the initial credit grant
        await db.credit_transactions.insert_one({
            "tx_id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "grant",
            "credits": initial_credits,
            "balance_after": initial_credits,
            "description": "Initial free credits",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return wallet


async def deduct_credits(user_id: str, action: str, amount: Optional[int] = None) -> dict:
    """Deduct credits for an AI action. Returns updated wallet or raises error."""
    cost = amount if amount is not None else CREDIT_COSTS.get(action, 1)
    if cost == 0:
        wallet = await get_or_create_wallet(user_id)
        return wallet

    wallet = await get_or_create_wallet(user_id)
    if wallet["credits"] < cost:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "required": cost,
                "available": wallet["credits"],
                "action": action,
                "message": f"You need {cost} credits for this action but have {wallet['credits']}. Please purchase more credits or upgrade your plan.",
            }
        )

    new_balance = wallet["credits"] - cost
    await db.credit_wallets.update_one(
        {"user_id": user_id},
        {"$set": {
            "credits": new_balance,
            "total_used": wallet.get("total_used", 0) + cost,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    await db.credit_transactions.insert_one({
        "tx_id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "deduction",
        "credits": -cost,
        "balance_after": new_balance,
        "action": action,
        "description": f"AI action: {action}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    wallet["credits"] = new_balance
    return wallet


async def add_credits(user_id: str, amount: int, reason: str, payment_id: str = "") -> dict:
    """Add credits to a user's wallet"""
    wallet = await get_or_create_wallet(user_id)
    new_balance = wallet["credits"] + amount

    await db.credit_wallets.update_one(
        {"user_id": user_id},
        {"$set": {
            "credits": new_balance,
            "total_purchased": wallet.get("total_purchased", 0) + amount,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    await db.credit_transactions.insert_one({
        "tx_id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "purchase",
        "credits": amount,
        "balance_after": new_balance,
        "description": reason,
        "payment_id": payment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    wallet["credits"] = new_balance
    return wallet


# ========================
# PRICING ENDPOINTS
# ========================

@router.get("/payments/plans")
async def get_plans():
    """Get all subscription plans and top-up packs (public)"""
    return {
        "plans": list(SUBSCRIPTION_PLANS.values()),
        "topup_packs": TOPUP_PACKS,
        "credit_costs": CREDIT_COSTS,
    }


@router.get("/payments/wallet")
async def get_wallet(user: dict = Depends(get_current_user)):
    """Get current user's credit wallet"""
    wallet = await get_or_create_wallet(user["user_id"])
    return wallet


@router.get("/payments/history")
async def get_payment_history(user: dict = Depends(get_current_user)):
    """Get user's credit transaction history"""
    transactions = await db.credit_transactions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"transactions": transactions}


# ========================
# RAZORPAY ORDER (TOP-UP)
# ========================

@router.post("/payments/create-topup-order")
async def create_topup_order(request: Request, user: dict = Depends(get_current_user)):
    """Create a Razorpay order for a credit top-up pack"""
    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    body = await request.json()
    pack_id = body.get("pack_id", "")
    pack = next((p for p in TOPUP_PACKS if p["id"] == pack_id), None)

    if not pack:
        raise HTTPException(status_code=400, detail="Invalid top-up pack")

    try:
        order = rzp_client.order.create({
            "amount": pack["price_paise"],
            "currency": "INR",
            "receipt": f"topup_{pack_id}_{user['user_id'][:8]}",
            "payment_capture": 1,
            "notes": {
                "user_id": user["user_id"],
                "pack_id": pack_id,
                "credits": str(pack["credits"]),
                "type": "topup",
            }
        })

        # Store order in DB
        await db.payment_orders.insert_one({
            "order_id": order["id"],
            "user_id": user["user_id"],
            "type": "topup",
            "pack_id": pack_id,
            "amount_paise": pack["price_paise"],
            "credits": pack["credits"],
            "status": "created",
            "razorpay_order": order,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "order_id": order["id"],
            "amount": pack["price_paise"],
            "currency": "INR",
            "key_id": key_id,
            "pack": pack,
            "user_name": user.get("name", ""),
            "user_email": user.get("email", ""),
        }
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment order creation failed: {str(e)[:200]}")


# ========================
# RAZORPAY SUBSCRIPTION
# ========================

@router.post("/payments/create-subscription")
async def create_subscription(request: Request, user: dict = Depends(get_current_user)):
    """Create a Razorpay subscription for a monthly plan"""
    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    body = await request.json()
    plan_id = body.get("plan_id", "")
    plan = SUBSCRIPTION_PLANS.get(plan_id)

    if not plan or plan_id == "free":
        raise HTTPException(status_code=400, detail="Invalid subscription plan")

    try:
        # Create a Razorpay subscription
        # First check if a plan exists in Razorpay, or create an order-based approach
        # For simplicity, we'll use order-based monthly billing
        order = rzp_client.order.create({
            "amount": plan["price_paise"],
            "currency": "INR",
            "receipt": f"sub_{plan_id}_{user['user_id'][:8]}",
            "payment_capture": 1,
            "notes": {
                "user_id": user["user_id"],
                "plan_id": plan_id,
                "credits": str(plan["credits_per_month"]),
                "type": "subscription",
            }
        })

        await db.payment_orders.insert_one({
            "order_id": order["id"],
            "user_id": user["user_id"],
            "type": "subscription",
            "plan_id": plan_id,
            "amount_paise": plan["price_paise"],
            "credits": plan["credits_per_month"],
            "status": "created",
            "razorpay_order": order,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "order_id": order["id"],
            "amount": plan["price_paise"],
            "currency": "INR",
            "key_id": RZP_KEY_ID,
            "plan": plan,
            "user_name": user.get("name", ""),
            "user_email": user.get("email", ""),
        }
    except Exception as e:
        logger.error(f"Subscription creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Subscription creation failed: {str(e)[:200]}")


# ========================
# PAYMENT VERIFICATION
# ========================

@router.post("/payments/verify")
async def verify_payment(request: Request, user: dict = Depends(get_current_user)):
    """Verify Razorpay payment and credit the user's wallet"""
    body = await request.json()
    razorpay_order_id = body.get("razorpay_order_id", "")
    razorpay_payment_id = body.get("razorpay_payment_id", "")
    razorpay_signature = body.get("razorpay_signature", "")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Missing payment verification fields")

    _, key_secret, _ = await resolve_razorpay_creds()
    if not key_secret:
        raise HTTPException(status_code=500, detail="Payment gateway not configured")

    # Verify signature
    try:
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature != razorpay_signature:
            raise HTTPException(status_code=400, detail="Payment verification failed - invalid signature")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Find the order
    order_doc = await db.payment_orders.find_one(
        {"order_id": razorpay_order_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found")

    if order_doc.get("status") == "paid":
        return {"message": "Payment already processed", "wallet": await get_or_create_wallet(user["user_id"])}

    # Update order status
    await db.payment_orders.update_one(
        {"order_id": razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    credits_to_add = order_doc.get("credits", 0)
    order_type = order_doc.get("type", "topup")

    if order_type == "topup":
        pack_id = order_doc.get("pack_id", "")
        wallet = await add_credits(
            user["user_id"],
            credits_to_add,
            f"Top-up: {pack_id} pack ({credits_to_add} credits)",
            razorpay_payment_id
        )
    elif order_type == "subscription":
        plan_id = order_doc.get("plan_id", "")
        plan = SUBSCRIPTION_PLANS.get(plan_id, {})

        # Update wallet with subscription info
        wallet = await add_credits(
            user["user_id"],
            credits_to_add,
            f"Subscription: {plan.get('name', plan_id)} plan ({credits_to_add} credits/month)",
            razorpay_payment_id
        )

        # Update plan
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        sub_end = (now + timedelta(days=30)).isoformat()

        await db.credit_wallets.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "current_plan": plan_id,
                "plan_credits_remaining": credits_to_add,
                "subscription_id": razorpay_payment_id,
                "subscription_status": "active",
                "subscription_end": sub_end,
                "updated_at": now.isoformat(),
            }}
        )
        wallet["current_plan"] = plan_id
        wallet["subscription_status"] = "active"
        wallet["subscription_end"] = sub_end
    else:
        wallet = await get_or_create_wallet(user["user_id"])

    return {
        "message": "Payment verified successfully",
        "credits_added": credits_to_add,
        "wallet": wallet,
    }


# ========================
# RAZORPAY WEBHOOK
# ========================

@router.post("/payments/webhook")
async def razorpay_webhook(request: Request):
    """Handle Razorpay webhook events (no auth required)"""
    try:
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")

        # Verify webhook signature if secret is configured
        _, _, webhook_secret = await resolve_razorpay_creds()
        if webhook_secret and signature:
            expected = hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            if expected != signature:
                raise HTTPException(status_code=400, detail="Invalid webhook signature")

        data = json_module.loads(payload)
        event = data.get("event", "")
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})

        if event == "payment.captured":
            order_id = payment_entity.get("order_id", "")
            payment_id = payment_entity.get("id", "")

            order_doc = await db.payment_orders.find_one({"order_id": order_id}, {"_id": 0})
            if order_doc and order_doc.get("status") != "paid":
                user_id = order_doc.get("user_id")
                credits_to_add = order_doc.get("credits", 0)

                await db.payment_orders.update_one(
                    {"order_id": order_id},
                    {"$set": {"status": "paid", "razorpay_payment_id": payment_id, "paid_at": datetime.now(timezone.utc).isoformat()}}
                )

                if user_id and credits_to_add > 0:
                    await add_credits(user_id, credits_to_add, f"Webhook: payment captured", payment_id)

        elif event == "payment.failed":
            order_id = payment_entity.get("order_id", "")
            await db.payment_orders.update_one(
                {"order_id": order_id},
                {"$set": {"status": "failed", "failed_at": datetime.now(timezone.utc).isoformat()}}
            )

        return {"status": "processed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return {"status": "error"}


# ========================
# ADMIN: CONFIGURE INITIAL CREDITS
# ========================

@router.put("/payments/admin/initial-credits")
async def set_initial_credits(request: Request, user: dict = Depends(get_current_user)):
    """SuperAdmin: Set default initial credits for new users in the org"""
    if user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    initial_credits = body.get("initial_credits", DEFAULT_INITIAL_CREDITS)

    if not isinstance(initial_credits, int) or initial_credits < 0 or initial_credits > 10000:
        raise HTTPException(status_code=400, detail="Credits must be between 0 and 10000")

    org_id = user.get("org_id", user["user_id"])

    await db.org_settings.update_one(
        {"org_id": org_id},
        {"$set": {
            "initial_credits": initial_credits,
            "updated_by": user["user_id"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )

    return {"message": f"Initial credits set to {initial_credits}", "initial_credits": initial_credits}


@router.get("/payments/admin/initial-credits")
async def get_initial_credits(user: dict = Depends(get_current_user)):
    """Get current initial credits setting"""
    org_id = user.get("org_id", user["user_id"])
    settings = await db.org_settings.find_one({"org_id": org_id}, {"_id": 0})
    return {"initial_credits": settings.get("initial_credits", DEFAULT_INITIAL_CREDITS) if settings else DEFAULT_INITIAL_CREDITS}


# ========================
# CREDIT CHECK (for use in other routes)
# ========================

@router.post("/payments/check-credits")
async def check_credits(request: Request, user: dict = Depends(get_current_user)):
    """Check if user has enough credits for an action"""
    body = await request.json()
    action = body.get("action", "")
    cost = CREDIT_COSTS.get(action, 1)
    wallet = await get_or_create_wallet(user["user_id"])

    return {
        "action": action,
        "cost": cost,
        "available": wallet["credits"],
        "sufficient": wallet["credits"] >= cost,
    }
