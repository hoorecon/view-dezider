"""
Earnings & Payouts — Collaboration Epic Phase E.

Paid-clone purchases credit the seller's earnings ledger (minus an admin-set
platform commission). Sellers link a UPI/bank payout account. A weekly scheduler
auto-pays out every seller whose AVAILABLE balance is at/above the admin minimum
threshold, on the admin-configured weekday + hour (UTC), via RazorpayX.

Until RazorpayX is activated (X account number set in admin Payout Config),
payouts are still created but parked as `pending_manual` so the full flow works.

Collections:
  • earnings_ledger  — one credit row per paid clone (status available|paid_out)
  • payout_accounts  — seller's linked UPI/bank account
  • payout_config    — singleton admin config
  • payouts          — each payout run row
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from openpyxl import Workbook

from core.auth import get_current_user, require_admin
from core.database import db
from core.helpers import create_notification
from core import razorpayx

log = logging.getLogger("earnings")

router = APIRouter(prefix="/earnings", tags=["Earnings & Payouts"])
admin_router = APIRouter(prefix="/admin/payouts", tags=["Admin Payouts"])

DEFAULT_CONFIG = {
    "_id": "singleton",
    "min_payout_inr": 500,
    "payout_weekday": 4,          # 0=Mon … 6=Sun ; default Friday
    "payout_hour_utc": 6,
    "platform_commission_percent": 0,
    "enabled": True,
    "razorpayx_account_number": "",
    "idfc_debit_account_number": "",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat()


async def get_config() -> dict:
    cfg = await db.payout_config.find_one({"_id": "singleton"})
    if not cfg:
        await db.payout_config.insert_one(dict(DEFAULT_CONFIG))
        return dict(DEFAULT_CONFIG)
    merged = {**DEFAULT_CONFIG, **cfg}
    return merged


# ---------------------------------------------------------------------------
# seller credit (called from marketplace verify-payment)
# ---------------------------------------------------------------------------
async def credit_seller(listing: dict, *, order_id: str, gross_inr: int, payment_id: str,
                        buyer_id: str) -> dict:
    cfg = await get_config()
    commission_pct = max(0, min(100, cfg.get("platform_commission_percent", 0)))
    commission_inr = round(gross_inr * commission_pct / 100)
    net_inr = gross_inr - commission_inr
    entry = {
        "entry_id": f"earn_{uuid.uuid4().hex[:12]}",
        "user_id": listing["owner_id"],
        "source": "marketplace_clone",
        "listing_id": listing["listing_id"],
        "listing_title": listing.get("title"),
        "order_id": order_id,
        "payment_id": payment_id,
        "buyer_id": buyer_id,
        "gross_inr": gross_inr,
        "commission_inr": commission_inr,
        "net_inr": net_inr,
        "status": "available",   # available -> paid_out
        "payout_id": None,
        "created_at": _iso(),
    }
    await db.earnings_ledger.insert_one(entry)
    try:
        await create_notification(
            listing["owner_id"], "earnings", "You earned money 💰",
            f'You earned ₹{net_inr} from a clone of "{listing.get("title") or "your decision"}".',
            {"listing_id": listing["listing_id"]},
        )
    except Exception:
        pass
    return entry


# ---------------------------------------------------------------------------
# seller-facing endpoints
# ---------------------------------------------------------------------------
class PayoutAccountReq(BaseModel):
    method: str = Field(..., description="upi | bank")
    vpa: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    beneficiary_name: Optional[str] = None


def _next_payout_eta(cfg: dict) -> str:
    now = _now()
    target_wd = cfg.get("payout_weekday", 4)
    target_hr = cfg.get("payout_hour_utc", 6)
    days_ahead = (target_wd - now.weekday()) % 7
    candidate = (now + timedelta(days=days_ahead)).replace(hour=target_hr, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate = candidate + timedelta(days=7)
    return candidate.isoformat()


@router.get("/summary")
async def summary(user: dict = Depends(get_current_user)):
    cfg = await get_config()
    pipeline = [
        {"$match": {"user_id": user["user_id"]}},
        {"$group": {"_id": "$status", "total": {"$sum": "$net_inr"}, "count": {"$sum": 1}}},
    ]
    by_status: Dict[str, dict] = {}
    async for r in db.earnings_ledger.aggregate(pipeline):
        by_status[r["_id"]] = {"total": r["total"], "count": r["count"]}
    available = by_status.get("available", {}).get("total", 0)
    paid_out = by_status.get("paid_out", {}).get("total", 0)
    acct = await db.payout_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {
        "available_inr": available,
        "paid_out_inr": paid_out,
        "lifetime_inr": available + paid_out,
        "currency": "INR",
        "min_payout_inr": cfg["min_payout_inr"],
        "eligible_for_payout": available >= cfg["min_payout_inr"],
        "next_payout_eta": _next_payout_eta(cfg),
        "payout_weekday": WEEKDAYS[cfg["payout_weekday"]],
        "has_payout_account": bool(acct),
        "payout_account": acct,
    }


@router.get("/ledger")
async def ledger(user: dict = Depends(get_current_user)):
    cur = db.earnings_ledger.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": await cur.to_list(200)}


@router.get("/payouts")
async def my_payouts(user: dict = Depends(get_current_user)):
    cur = db.payouts.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": await cur.to_list(100)}


@router.get("/payout-account")
async def get_payout_account(user: dict = Depends(get_current_user)):
    acct = await db.payout_accounts.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return acct or {}


@router.post("/payout-account")
async def set_payout_account(body: PayoutAccountReq, user: dict = Depends(get_current_user)):
    if body.method not in ("upi", "bank"):
        raise HTTPException(400, "method must be 'upi' or 'bank'")
    if body.method == "upi" and not body.vpa:
        raise HTTPException(400, "UPI VPA is required")
    if body.method == "bank" and not (body.account_number and body.ifsc and body.beneficiary_name):
        raise HTTPException(400, "account_number, ifsc and beneficiary_name are required for bank")
    doc = {
        "user_id": user["user_id"],
        "method": body.method,
        "vpa": (body.vpa or "").strip() or None,
        "account_number": (body.account_number or "").strip() or None,
        "ifsc": (body.ifsc or "").strip().upper() or None,
        "beneficiary_name": (body.beneficiary_name or "").strip() or None,
        "verified": True,
        # reset cached RazorpayX ids whenever account details change
        "contact_id": None,
        "fund_account_id": None,
        "updated_at": _iso(),
    }
    await db.payout_accounts.update_one({"user_id": user["user_id"]}, {"$set": doc}, upsert=True)
    return {"ok": True, "payout_account": {k: v for k, v in doc.items() if k != "user_id"}}


@router.get("/config")
async def public_config(user: dict = Depends(get_current_user)):
    cfg = await get_config()
    return {
        "min_payout_inr": cfg["min_payout_inr"],
        "payout_weekday": WEEKDAYS[cfg["payout_weekday"]],
        "payout_hour_utc": cfg["payout_hour_utc"],
        "platform_commission_percent": cfg["platform_commission_percent"],
        "enabled": cfg["enabled"],
        "razorpayx_active": await razorpayx.is_configured(),
    }


# ---------------------------------------------------------------------------
# admin endpoints
# ---------------------------------------------------------------------------
class ConfigUpdate(BaseModel):
    min_payout_inr: Optional[int] = Field(None, ge=0)
    payout_weekday: Optional[int] = Field(None, ge=0, le=6)
    payout_hour_utc: Optional[int] = Field(None, ge=0, le=23)
    platform_commission_percent: Optional[int] = Field(None, ge=0, le=100)
    enabled: Optional[bool] = None
    razorpayx_account_number: Optional[str] = None
    idfc_debit_account_number: Optional[str] = None


@admin_router.get("/config")
async def admin_get_config(admin: dict = Depends(require_admin)):
    cfg = await get_config()
    cfg["razorpayx_active"] = await razorpayx.is_configured()
    cfg["weekday_label"] = WEEKDAYS[cfg["payout_weekday"]]
    return cfg


@admin_router.put("/config")
async def admin_update_config(body: ConfigUpdate, admin: dict = Depends(require_admin)):
    await get_config()  # ensure exists
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if updates:
        updates["updated_at"] = _iso()
        await db.payout_config.update_one({"_id": "singleton"}, {"$set": updates})
    cfg = await get_config()
    cfg["razorpayx_active"] = await razorpayx.is_configured()
    cfg["weekday_label"] = WEEKDAYS[cfg["payout_weekday"]]
    return cfg


@admin_router.get("")
async def admin_list_payouts(admin: dict = Depends(require_admin)):
    cur = db.payouts.find({}, {"_id": 0}).sort("created_at", -1)
    payouts = await cur.to_list(200)
    # pending available totals
    pipeline = [
        {"$match": {"status": "available"}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$net_inr"}}},
    ]
    pending = [{"user_id": r["_id"], "available_inr": r["total"]} async for r in db.earnings_ledger.aggregate(pipeline)]
    return {"payouts": payouts, "pending_balances": pending}


# ---------------------------------------------------------------------------
# Manual payout batch (IDFC bulk transfer / on-screen UPI) — no aggregator
# ---------------------------------------------------------------------------
async def run_manual_payout_batch() -> dict:
    """Create `pending_manual` payout rows for every eligible seller, snapshotting
    their beneficiary details so the IDFC export is self-contained. Does NOT call
    any payout API — admin pays via IDFC net-banking and then marks them paid."""
    cfg = await get_config()
    min_inr = cfg.get("min_payout_inr", 500)
    pipeline = [
        {"$match": {"status": "available"}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$net_inr"},
                    "entries": {"$push": "$entry_id"}}},
    ]
    rows = [r async for r in db.earnings_ledger.aggregate(pipeline)]
    created = 0
    bank = 0
    upi = 0
    skipped = 0
    for r in rows:
        user_id, total, entry_ids = r["_id"], r["total"], r["entries"]
        if total < min_inr:
            skipped += 1
            continue
        acct = await db.payout_accounts.find_one({"user_id": user_id}, {"_id": 0})
        if not acct or not acct.get("verified"):
            skipped += 1
            continue
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0}) or {}
        payout_id = f"pay_{uuid.uuid4().hex[:12]}"
        payout_doc = {
            "payout_id": payout_id,
            "user_id": user_id,
            "amount_inr": total,
            "method": acct.get("method"),
            "destination": acct.get("vpa") or acct.get("account_number"),
            # snapshot beneficiary details for a self-contained export
            "beneficiary_name": acct.get("beneficiary_name") or user.get("name") or user.get("email"),
            "account_number": acct.get("account_number"),
            "ifsc": acct.get("ifsc"),
            "vpa": acct.get("vpa"),
            "email": user.get("email"),
            "entry_ids": entry_ids,
            "status": "pending_manual",
            "razorpay_payout_id": None,
            "failure_reason": None,
            "channel": "manual_idfc",
            "created_at": _iso(),
            "processed_at": None,
        }
        await db.payouts.insert_one(payout_doc)
        await db.earnings_ledger.update_many(
            {"entry_id": {"$in": entry_ids}},
            {"$set": {"status": "paid_out", "payout_id": payout_id}},
        )
        created += 1
        bank += 1 if acct.get("method") == "bank" else 0
        upi += 1 if acct.get("method") == "upi" else 0
    return {"created": created, "bank": bank, "upi": upi, "skipped": skipped}


class RunBatchReq(BaseModel):
    channel: str  # "razorpayx" | "manual_idfc"


@admin_router.get("/eligible-summary")
async def admin_eligible_summary(admin: dict = Depends(require_admin)):
    """Count + total of sellers eligible for the next batch (available balance ≥
    min payout AND a verified payout account). Powers the run-confirm dialog."""
    cfg = await get_config()
    min_inr = cfg.get("min_payout_inr", 500)
    pipeline = [
        {"$match": {"status": "available"}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$net_inr"}}},
    ]
    eligible = 0
    total = 0
    async for r in db.earnings_ledger.aggregate(pipeline):
        if r["total"] < min_inr:
            continue
        acct = await db.payout_accounts.find_one({"user_id": r["_id"]}, {"_id": 0, "verified": 1})
        if not acct or not acct.get("verified"):
            continue
        eligible += 1
        total += r["total"]
    return {
        "eligible": eligible, "total_inr": total,
        "min_payout_inr": min_inr,
        "razorpayx_active": await razorpayx.is_configured(),
    }


@admin_router.post("/run")
async def admin_run_batch(body: RunBatchReq, admin: dict = Depends(require_admin)):
    """Run a payout batch on an EXPLICITLY chosen channel — prevents accidentally
    firing the wrong path during testing.
      • manual_idfc → never calls any payout API (queues pending_manual rows).
      • razorpayx   → sends real payouts; HARD-ERRORS if RazorpayX isn't configured
                       (does NOT silently fall back to manual)."""
    channel = (body.channel or "").strip()
    if channel == "manual_idfc":
        res = await run_manual_payout_batch()
        return {"ok": True, "channel": channel, **res}
    if channel == "razorpayx":
        if not await razorpayx.is_configured():
            raise HTTPException(
                400,
                "RazorpayX not configured — aborting. Activate RazorpayX (set the "
                "account number) or use the Manual-IDFC channel.",
            )
        res = await run_weekly_payouts(force=True)
        return {"ok": True, "channel": channel, **res}
    raise HTTPException(400, "channel must be 'razorpayx' or 'manual_idfc'")


def _idfc_txn_type(ifsc: Optional[str], amount: int) -> str:
    code = (ifsc or "").upper()
    if code.startswith("IDFB"):     # within IDFC FIRST Bank
        return "IFT"
    if amount >= 200000:            # RTGS floor
        return "RTGS"
    return "NEFT"


def _xlsx_b64(wb: Workbook) -> str:
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


IDFC_HEADERS = [
    "Beneficiary Name", "Beneficiary Account Number", "IFSC", "Transaction Type",
    "Debit Account Number", "Transaction Date", "Amount", "Currency",
    "Beneficiary Email ID", "Remarks", "Custom Header – 1", "Custom Header – 2",
    "Custom Header – 3", "Custom Header – 4", "Custom Header – 5",
]


@admin_router.get("/export/bank")
async def export_idfc_bank(admin: dict = Depends(require_admin)):
    """IDFC BLKPAY-format xlsx for all pending_manual BANK payouts."""
    cfg = await get_config()
    debit_acct = (cfg.get("idfc_debit_account_number") or "").strip()
    txn_date = _now().strftime("%d/%m/%Y")
    cur = db.payouts.find({"status": "pending_manual", "method": "bank"}, {"_id": 0}).sort("created_at", 1)
    rows = await cur.to_list(1000)

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(IDFC_HEADERS)
    total = 0
    for p in rows:
        amt = int(p.get("amount_inr") or 0)
        total += amt
        ws.append([
            p.get("beneficiary_name") or "",
            p.get("account_number") or "",
            (p.get("ifsc") or "").upper(),
            _idfc_txn_type(p.get("ifsc"), amt),
            debit_acct,
            txn_date,
            amt,
            "INR",
            p.get("email") or "",
            f"Dezider payout {p.get('payout_id')}",
            p.get("payout_id") or "", "", "", "", "",
        ])
    fname = f"BLKPAY_{_now().strftime('%Y%m%d')}.xlsx"
    return {"filename": fname, "count": len(rows), "total_inr": total,
            "content_base64": _xlsx_b64(wb),
            "debit_account_set": bool(debit_acct)}


@admin_router.get("/export/upi")
async def export_upi_list(admin: dict = Depends(require_admin)):
    """Simple VPA list xlsx for IDFC 'Bulk Pay On-Screen' (UPI/VPA group tool)."""
    cur = db.payouts.find({"status": "pending_manual", "method": "upi"}, {"_id": 0}).sort("created_at", 1)
    rows = await cur.to_list(1000)
    wb = Workbook()
    ws = wb.active
    ws.title = "UPI Payouts"
    ws.append(["Beneficiary Name", "UPI ID (VPA)", "Amount", "Currency", "Remarks", "Payout ID"])
    total = 0
    for p in rows:
        amt = int(p.get("amount_inr") or 0)
        total += amt
        ws.append([
            p.get("beneficiary_name") or "",
            p.get("vpa") or p.get("destination") or "",
            amt, "INR",
            f"Dezider payout {p.get('payout_id')}",
            p.get("payout_id") or "",
        ])
    fname = f"UPI_PAYOUTS_{_now().strftime('%Y%m%d')}.xlsx"
    return {"filename": fname, "count": len(rows), "total_inr": total,
            "content_base64": _xlsx_b64(wb)}


class MarkPaidReq(BaseModel):
    payout_ids: Optional[List[str]] = None   # None => all pending_manual


@admin_router.post("/mark-paid")
async def admin_mark_paid(body: MarkPaidReq, admin: dict = Depends(require_admin)):
    q: Dict[str, Any] = {"status": "pending_manual"}
    if body.payout_ids:
        q["payout_id"] = {"$in": body.payout_ids}
    rows = await db.payouts.find(q, {"_id": 0, "payout_id": 1, "user_id": 1, "amount_inr": 1}).to_list(1000)
    now = _iso()
    ids = [r["payout_id"] for r in rows]
    if ids:
        await db.payouts.update_many(
            {"payout_id": {"$in": ids}},
            {"$set": {"status": "processed", "processed_at": now, "channel": "manual_idfc"}},
        )
        for r in rows:
            try:
                await create_notification(r["user_id"], "payout", "Payout completed ✅",
                                          f"₹{r['amount_inr']} has been transferred to your account.",
                                          {"payout_id": r["payout_id"]})
            except Exception:
                pass
    return {"ok": True, "marked_paid": len(ids)}


@admin_router.post("/{payout_id}/mark-failed")
async def admin_mark_failed(payout_id: str, admin: dict = Depends(require_admin)):
    payout = await db.payouts.find_one({"payout_id": payout_id})
    if not payout:
        raise HTTPException(404, "payout not found")
    await db.payouts.update_one(
        {"payout_id": payout_id},
        {"$set": {"status": "failed", "failure_reason": "Marked failed by admin", "updated_at": _iso()}},
    )
    reverted = 0
    entry_ids = payout.get("entry_ids") or []
    if entry_ids:
        res = await db.earnings_ledger.update_many(
            {"entry_id": {"$in": entry_ids}},
            {"$set": {"status": "available", "payout_id": None}},
        )
        reverted = res.modified_count
    try:
        await create_notification(payout["user_id"], "payout", "Payout failed ⚠️",
                                  f"₹{payout.get('amount_inr')} payout failed and was returned to your available balance.",
                                  {"payout_id": payout_id})
    except Exception:
        pass
    return {"ok": True, "status": "failed", "reverted_entries": reverted}


# ---------------------------------------------------------------------------
# payout engine
# ---------------------------------------------------------------------------
async def run_weekly_payouts(force: bool = False) -> dict:
    cfg = await get_config()
    if not cfg.get("enabled") and not force:
        return {"skipped": "payouts disabled", "processed": 0}
    min_inr = cfg.get("min_payout_inr", 500)

    # aggregate available balance per seller
    pipeline = [
        {"$match": {"status": "available"}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$net_inr"},
                    "entries": {"$push": "$entry_id"}}},
    ]
    rows = [r async for r in db.earnings_ledger.aggregate(pipeline)]
    rzx_live = await razorpayx.is_configured()
    processed = 0
    queued = 0
    skipped = 0
    for r in rows:
        user_id, total, entry_ids = r["_id"], r["total"], r["entries"]
        if total < min_inr:
            skipped += 1
            continue
        acct = await db.payout_accounts.find_one({"user_id": user_id}, {"_id": 0})
        if not acct or not acct.get("verified"):
            skipped += 1
            continue
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0}) or {"user_id": user_id}
        payout_id = f"pay_{uuid.uuid4().hex[:12]}"
        status = "pending_manual"
        rzp_id = None
        failure = None
        if rzx_live:
            try:
                res = await razorpayx.execute_payout_for_account(user, acct, total, payout_id)
                rzp_id = res.get("razorpay_payout_id")
                status = "processing"
            except Exception as e:
                status = "failed"
                failure = str(e)[:300]
                log.error(f"payout failed for {user_id}: {failure}")
        payout_doc = {
            "payout_id": payout_id,
            "user_id": user_id,
            "amount_inr": total,
            "method": acct.get("method"),
            "destination": acct.get("vpa") or acct.get("account_number"),
            "entry_ids": entry_ids,
            "status": status,
            "razorpay_payout_id": rzp_id,
            "failure_reason": failure,
            "created_at": _iso(),
            "processed_at": _iso() if status in ("processing", "processed", "pending_manual") else None,
        }
        await db.payouts.insert_one(payout_doc)
        if status != "failed":
            await db.earnings_ledger.update_many(
                {"entry_id": {"$in": entry_ids}},
                {"$set": {"status": "paid_out", "payout_id": payout_id}},
            )
            processed += 1 if status == "processing" else 0
            queued += 1 if status == "pending_manual" else 0
            try:
                msg = (f"₹{total} payout initiated to your {acct.get('method','account')}." if status == "processing"
                       else f"₹{total} payout queued (will be sent once payouts are activated).")
                await create_notification(user_id, "payout", "Payout update 💸", msg, {"payout_id": payout_id})
            except Exception:
                pass
    return {"processed": processed, "queued_pending": queued, "skipped": skipped,
            "razorpayx_live": rzx_live, "total_sellers": len(rows)}


# ---------------------------------------------------------------------------
# hourly scheduler — runs the payout sweep on the configured weekday+hour
# ---------------------------------------------------------------------------
async def _payout_loop():
    last_run_key: Optional[str] = None
    while True:
        try:
            cfg = await get_config()
            now = _now()
            if cfg.get("enabled") and now.weekday() == cfg.get("payout_weekday", 4) and now.hour == cfg.get("payout_hour_utc", 6):
                run_key = now.strftime("%Y-%W-%w-%H")
                if run_key != last_run_key:
                    last_run_key = run_key
                    res = await run_weekly_payouts()
                    log.info(f"weekly payout run: {res}")
        except Exception as e:
            log.error(f"payout loop error: {str(e)[:160]}")
        await asyncio.sleep(1800)  # every 30 min


def start_payout_scheduler():
    # Multi-worker safety: run the weekly payout sweep in only ONE worker so it
    # doesn't fire N times (which could double-pay sellers).
    try:
        from core.boot_lock import try_acquire_named_lock
        if not try_acquire_named_lock("payout_scheduler"):
            log.info("Payout scheduler lock held by another worker; skipping.")
            return
    except Exception:
        pass
    try:
        asyncio.create_task(_payout_loop())
        log.info("Marketplace payout scheduler started (weekly auto-payout sweep).")
    except RuntimeError as e:
        log.error(f"payout scheduler start failed: {e}")
