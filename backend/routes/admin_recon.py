"""Admin routes — Revenue Reconciliation (Razorpay ⟷ ledger ⟷ Google Cloud).

Super-Admin only. Powers the /admin/recon report screen.
"""
import csv
import io
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from core import recon
from core.auth import require_super_admin

router = APIRouter()
log = logging.getLogger("admin_recon")


@router.get("/admin/recon/summary")
async def recon_summary(user: dict = Depends(require_super_admin)):
    return await recon.summary()


@router.get("/admin/recon/transactions")
async def recon_transactions(limit: int = 100, skip: int = 0, month: Optional[str] = None,
                             user: dict = Depends(require_super_admin)):
    return await recon.transactions_tally(limit=limit, skip=skip, month=month)


@router.get("/admin/recon/daily")
async def recon_daily(days: int = 31, user: dict = Depends(require_super_admin)):
    return await recon.daily_tally(days=min(max(days, 1), 92))


@router.post("/admin/recon/sync")
async def recon_sync(user: dict = Depends(require_super_admin)):
    """On-demand sync of both sources. GCP failure does not block Razorpay."""
    rzp = await recon.sync_razorpay()
    gcp = await recon.sync_gcp()
    return {"razorpay": rzp, "gcp": gcp}


@router.get("/admin/recon/gcp-config")
async def get_gcp_config(user: dict = Depends(require_super_admin)):
    return await recon.get_config()


@router.put("/admin/recon/gcp-config")
async def put_gcp_config(body: Dict[str, Any], user: dict = Depends(require_super_admin)):
    try:
        return await recon.update_gcp_config(body, by=user.get("email") or user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/recon/transactions.csv", response_class=PlainTextResponse)
async def recon_transactions_csv(month: Optional[str] = None,
                                 user: dict = Depends(require_super_admin)):
    data = await recon.transactions_tally(limit=500, skip=0, month=month)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at", "order_id", "payment_id", "user_id", "credits",
                "collected_inr", "rzp_fee_inr", "routed_markup_inr", "net_treasury_inr",
                "earmarked_llm_cost_inr", "buffer_inr", "fx_usd_inr", "markup_pct",
                "route_applied", "at_loss"])
    for r in data["items"]:
        w.writerow([r["created_at"], r["order_id"], r["payment_id"], r["user_id"],
                    r["credits"], r["collected_inr"], r["rzp_fee_inr"],
                    r["routed_markup_inr"], r["net_treasury_inr"],
                    r["earmarked_llm_cost_inr"], r["buffer_inr"], r["fx_usd_inr"],
                    r["markup_pct"], r["route_applied"], r["flags"]["at_loss"]])
    return PlainTextResponse(content=buf.getvalue(), media_type="text/csv")
