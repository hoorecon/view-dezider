"""Verifies that credits configured in Admin → Subscription Plans
(`credits_per_month`) land in the Profile AI wallet (`ai_wallets`) that
powers AI usage across the app — via the new `ai_wallet.grant()` call
added to `apply_charge()` in `backend/routes/subscriptions.py`.

Also asserts:
  • Legacy `credit_wallets.credits` continues to receive the same top-up
    (kept for audit + legacy modules).
  • Idempotency by `payment_id` — a second `apply_charge()` with the same
    payment_id does NOT double-credit either wallet.
"""
import asyncio
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

# make backend importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


# Single, module-level event loop — Motor binds a global executor to the loop
# it first saw, so we cannot spawn/close a new loop between calls.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _cleanup(user_id: str):
    d = _mongo()
    d.credit_wallets.delete_many({"user_id": user_id})
    d.ai_wallets.delete_many({"user_id": user_id})
    d.ai_wallet_ledger.delete_many({"user_id": user_id})
    d.credit_transactions.delete_many({"user_id": user_id})
    d.subscriptions.delete_many({"user_id": user_id})
    d.users.delete_many({"user_id": user_id})


@pytest.fixture
def sub_user():
    uid = f"utest_{uuid.uuid4().hex[:10]}"
    d = _mongo()
    d.users.insert_one({"user_id": uid, "email": f"{uid}@t.co", "role": "user",
                        "user_type": "free"})
    yield uid
    _cleanup(uid)


def test_subscription_credits_land_in_ai_wallet(sub_user):
    """apply_charge() must credit BOTH credit_wallets AND ai_wallets."""
    from routes.subscriptions import apply_charge

    plan = {
        "plan_id": "test_plan_pro",
        "name": "Test Pro",
        "tier": "pro",
        "credits_per_month": 1500,
    }
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    sub_id = f"sub_{uuid.uuid4().hex[:14]}"

    _run(apply_charge(sub_user, plan, payment_id, sub_id, mode="recurring"))

    d = _mongo()
    cw = d.credit_wallets.find_one({"user_id": sub_user})
    aw = d.ai_wallets.find_one({"user_id": sub_user})

    assert cw is not None, "credit_wallets row was not created"
    assert aw is not None, "ai_wallets row was not created — Profile wallet won't reflect the plan"

    # credit_wallets.credits = default initial (100) + 1500
    assert cw["credits"] >= 1500, f"credit_wallets.credits too low: {cw['credits']}"

    # ai_wallets.balance should include the 1500 grant on top of default seed.
    assert aw["balance"] >= 1500, (
        f"ai_wallets.balance did not receive the subscription credits: {aw['balance']}"
    )

    # subscription bookkeeping fields set
    assert cw.get("current_plan") == "pro"
    assert cw.get("subscription_status") in ("active", "manual")

    # ledger row present with kind='grant' by='subscription'
    ledger_row = d.ai_wallet_ledger.find_one({
        "user_id": sub_user, "by": "subscription", "kind": "grant"
    })
    assert ledger_row is not None, "ai_wallet_ledger has no subscription grant row"
    assert ledger_row.get("delta") == 1500


def test_apply_charge_is_idempotent_on_payment_id(sub_user):
    """A duplicate webhook / retried verification must not double-credit."""
    from routes.subscriptions import apply_charge

    plan = {
        "plan_id": "test_plan_pro",
        "name": "Test Pro",
        "tier": "pro",
        "credits_per_month": 1500,
    }
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    sub_id = f"sub_{uuid.uuid4().hex[:14]}"

    _run(apply_charge(sub_user, plan, payment_id, sub_id, mode="recurring"))
    _run(apply_charge(sub_user, plan, payment_id, sub_id, mode="recurring"))  # duplicate

    d = _mongo()
    cw = d.credit_wallets.find_one({"user_id": sub_user})
    aw = d.ai_wallets.find_one({"user_id": sub_user})

    # Only ONE grant of 1500 should have landed in each wallet, not 3000.
    # credit_wallets starts at 100 (default), + 1500 once = 1600.
    assert cw["credits"] < 3000, f"credit_wallets double-credited: {cw['credits']}"
    assert aw["balance"] < 3000, f"ai_wallets double-credited: {aw['balance']}"

    # Ledger should only carry ONE subscription grant for this user.
    grants = list(d.ai_wallet_ledger.find({
        "user_id": sub_user, "by": "subscription", "kind": "grant"
    }))
    assert len(grants) == 1, f"expected 1 grant, got {len(grants)}"
