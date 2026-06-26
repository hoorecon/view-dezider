"""
RazorpayX Payouts helper (Collaboration Epic Phase E).

Wraps the RazorpayX Contacts → Fund Accounts → Payouts flow. Uses the same
RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET as Razorpay Payments (RazorpayX shares the
key pair) plus a RazorpayX virtual *account number* which must be supplied via
the admin Payout Config (or RAZORPAYX_ACCOUNT_NUMBER env).

IMPORTANT: RazorpayX is a SEPARATELY-ACTIVATED product. Until the merchant
activates RazorpayX and we store the X account number, `is_configured()` returns
False and callers should QUEUE the payout as `pending_manual` instead of calling
the live API. Everything else (ledger, scheduling, thresholds) works regardless.
"""
from __future__ import annotations

import os
import uuid
import logging
from typing import Optional, Tuple

import httpx

from core.database import db
from core.integrations import resolve_razorpay_creds

log = logging.getLogger("razorpayx")
RZP_BASE = "https://api.razorpay.com/v1"


async def _account_number() -> str:
    cfg = await db.payout_config.find_one({"_id": "singleton"}) or {}
    return (cfg.get("razorpayx_account_number") or os.getenv("RAZORPAYX_ACCOUNT_NUMBER", "")).strip()


async def _payout_creds() -> Tuple[str, str, str]:
    """Resolve credentials used for RazorpayX *payout* API calls.

    Priority:
      1. Dedicated RAZORPAYX_KEY_ID / RAZORPAYX_KEY_SECRET env vars (isolated
         test/payout account). When set, ALL payout calls use these — payment
         collection is completely unaffected.
      2. Fallback to the shared Razorpay payment credentials (live account that
         has RazorpayX activated on the same key pair).

    Returns (key_id, key_secret, source) where source ∈ {"razorpayx_env", "shared"}.
    """
    x_kid = os.getenv("RAZORPAYX_KEY_ID", "").strip()
    x_ks = os.getenv("RAZORPAYX_KEY_SECRET", "").strip()
    if x_kid and x_ks:
        return x_kid, x_ks, "razorpayx_env"
    key_id, key_secret, _ = await resolve_razorpay_creds()
    return key_id, key_secret, "shared"


async def is_configured() -> bool:
    key_id, key_secret, _ = await _payout_creds()
    acct = await _account_number()
    return bool(key_id and key_secret and acct)


# ---------------------------------------------------------------------------
# IFSC lookup (Razorpay FREE public API — no auth, no cost) + bank-account
# penny-drop validation (RazorpayX Fund Account Validation, needs RazorpayX live)
# ---------------------------------------------------------------------------
IFSC_BASE = "https://ifsc.razorpay.com"


async def lookup_ifsc(ifsc: str) -> Optional[dict]:
    """Validate an IFSC and return its bank + branch via Razorpay's free public
    IFSC API. Returns {bank, branch, address, city, state, ifsc} or None if the
    IFSC is invalid / unknown. No credentials required."""
    code = (ifsc or "").strip().upper()
    if len(code) != 11:
        return None
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(f"{IFSC_BASE}/{code}")
        if resp.status_code != 200:
            return None
        d = resp.json()
        return {
            "ifsc": d.get("IFSC") or code,
            "bank": d.get("BANK"),
            "branch": d.get("BRANCH"),
            "city": d.get("CITY"),
            "state": d.get("STATE"),
            "address": d.get("ADDRESS"),
        }
    except Exception as e:  # network / parse failure — treat as unverifiable
        log.warning(f"IFSC lookup failed for {code}: {str(e)[:120]}")
        return None


async def validate_bank_pennydrop(user: dict, acct: dict) -> dict:
    """Trigger a RazorpayX Fund Account Validation (₹1 penny-drop) on the seller's
    BANK account. Requires RazorpayX to be live (is_configured()). Returns
    {validation_id, status, account_status, registered_name}. Raises on API error.

    status is async: 'created' → later 'completed' (with results.account_status
    'active'|'invalid') or 'failed'. We persist whatever we get; a webhook/poll
    can finalise it later."""
    account_number = await _account_number()
    contact_id = acct.get("contact_id") or await ensure_contact(user)
    bank_acct = {
        "method": "bank",
        "beneficiary_name": acct.get("beneficiary_name"),
        "ifsc": acct.get("ifsc"),
        "account_number": acct.get("account_number"),
    }
    fund_account_id = acct.get("fund_account_id") or await ensure_fund_account(contact_id, bank_acct)
    res = await _post("fund_accounts/validations", {
        "account_number": account_number,
        "fund_account": {"id": fund_account_id},
        "amount": 100,            # ₹1 penny-drop (paise)
        "currency": "INR",
        "notes": {"purpose": "seller_bank_verification", "user_id": user.get("user_id", "")},
    }, idempotency=str(uuid.uuid4()))
    results = res.get("results") or {}
    return {
        "validation_id": res.get("id"),
        "status": res.get("status"),                  # created | completed | failed
        "account_status": results.get("account_status"),   # active | invalid | None
        "registered_name": results.get("registered_name"),
        "contact_id": contact_id,
        "fund_account_id": fund_account_id,
    }


async def _auth() -> Tuple[str, str]:
    key_id, key_secret, _ = await _payout_creds()
    return key_id, key_secret


async def _post(path: str, payload: dict, idempotency: Optional[str] = None) -> dict:
    key_id, key_secret = await _auth()
    headers = {"Content-Type": "application/json"}
    if idempotency:
        headers["X-Payout-Idempotency"] = idempotency
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{RZP_BASE}/{path}", json=payload, headers=headers, auth=(key_id, key_secret))
    if resp.status_code >= 400:
        raise RuntimeError(f"RazorpayX {path} failed [{resp.status_code}]: {resp.text[:300]}")
    return resp.json()


async def ensure_contact(user: dict) -> str:
    """Create (or reuse) a RazorpayX contact for the seller."""
    existing = await db.payout_accounts.find_one({"user_id": user["user_id"], "contact_id": {"$ne": None}}, {"_id": 0, "contact_id": 1})
    if existing and existing.get("contact_id"):
        return existing["contact_id"]
    res = await _post("contacts", {
        "name": user.get("name") or user.get("email") or "Dezider Seller",
        "email": user.get("email") or "",
        "type": "vendor",
        "reference_id": f"user_{user['user_id'][:18]}",
    })
    return res["id"]


async def ensure_fund_account(contact_id: str, acct: dict) -> str:
    """Create a fund account for either UPI (vpa) or bank_account."""
    if acct.get("method") == "upi":
        payload = {"contact_id": contact_id, "account_type": "vpa", "vpa": {"address": acct["vpa"]}}
    else:
        payload = {"contact_id": contact_id, "account_type": "bank_account",
                   "bank_account": {"name": acct["beneficiary_name"], "ifsc": acct["ifsc"], "account_number": acct["account_number"]}}
    res = await _post("fund_accounts", payload)
    return res["id"]


async def create_payout(account_number: str, fund_account_id: str, amount_inr: int, *, mode: str,
                        reference_id: str, narration: str = "Dezider marketplace payout") -> dict:
    payload = {
        "account_number": account_number,
        "fund_account_id": fund_account_id,
        "amount": int(amount_inr) * 100,
        "currency": "INR",
        "mode": mode,
        "purpose": "payout",
        "queue_if_low_balance": True,
        "reference_id": reference_id[:40],
        "narration": narration[:30],
    }
    return await _post("payouts", payload, idempotency=str(uuid.uuid4()))


async def execute_payout_for_account(user: dict, acct: dict, amount_inr: int, reference_id: str) -> dict:
    """High-level: ensure contact + fund account, then create the payout.
    Returns {razorpay_payout_id, fund_account_id, status}. Raises on API error."""
    account_number = await _account_number()
    contact_id = acct.get("contact_id") or await ensure_contact(user)
    fund_account_id = acct.get("fund_account_id") or await ensure_fund_account(contact_id, acct)
    # persist ids for reuse
    await db.payout_accounts.update_one(
        {"user_id": user["user_id"]}, {"$set": {"contact_id": contact_id, "fund_account_id": fund_account_id}}
    )
    mode = "UPI" if acct.get("method") == "upi" else "IMPS"
    res = await create_payout(account_number, fund_account_id, amount_inr, mode=mode, reference_id=reference_id)
    return {"razorpay_payout_id": res.get("id"), "fund_account_id": fund_account_id, "status": res.get("status", "processing")}
