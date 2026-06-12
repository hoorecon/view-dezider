"""AI credits wallet routes — user balance/ledger + Super-Admin configuration & grants.

Also hosts the Phase-3 Razorpay refill flow (Gemini-cost-pegged packs + hidden
markup, with Razorpay Route to split the markup to a linked account).
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from core import ai_wallet, ai_billing
from core.auth import get_current_user, require_admin, require_super_admin
from core.database import db
from core.integrations import get_razorpay_client, resolve_razorpay_creds
from core.hardening import RAZORPAY_CSP

router = APIRouter()
log = logging.getLogger("ai_wallet_routes")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────── user ───────────────────────────
@router.get("/ai-wallet")
async def my_wallet(user: dict = Depends(get_current_user)):
    return await ai_wallet.get_balance(user["user_id"])


@router.get("/ai-wallet/ledger")
async def my_wallet_ledger(limit: int = 30, user: dict = Depends(get_current_user)):
    return {"items": await ai_wallet.get_ledger(user["user_id"], min(max(limit, 1), 100))}


@router.get("/ai-wallet/estimates")
async def my_wallet_estimates(user: dict = Depends(get_current_user)):
    """Per-feature estimated credit cost + the confirm threshold (for "~N cr"
    badges and the >threshold confirmation prompt before an AI spend)."""
    return await ai_wallet.estimates()


@router.get("/ai-wallet/import-estimate")
async def import_estimate(endpoint: str = "import", pages: int = 1, tier: str = "fast",
                          user: dict = Depends(get_current_user)):
    """Upfront cost preview for the URL-import flows ("≈ N cr needed · M cr
    available"). Estimate is HISTORY-based — the avg total_credits of recent
    successful runs of the same endpoint/tier (per crawled page for deep
    imports) — falling back to static defaults until history accumulates."""
    endpoint = endpoint if endpoint in ("import", "analyze", "deep_import") else "import"
    tier = tier if tier in ("fast", "precise") else "fast"
    pages = max(1, min(int(pages), 10))
    q: Dict[str, Any] = {"status": "success", "total_credits": {"$gt": 0},
                         "endpoint": ("deep_import" if endpoint == "deep_import"
                                      else {"$in": ["import", "analyze"]})}
    rows = await (db.url_import_runs
                  .find(q, {"_id": 0, "total_credits": 1, "item_count": 1, "ai_tier": 1})
                  .sort("ts", -1).limit(20).to_list(20))
    tier_rows = [r for r in rows if r.get("ai_tier") == tier] or rows
    basis, sampled = "default", 0
    if endpoint == "deep_import":
        if tier_rows:
            per_page = (sum(float(r["total_credits"]) / max(int(r.get("item_count") or 1), 1)
                            for r in tier_rows) / len(tier_rows))
            estimate, basis, sampled = per_page * pages, "history", len(tier_rows)
        else:
            estimate = 250.0 * pages
    else:
        if tier_rows:
            estimate = sum(float(r["total_credits"]) for r in tier_rows) / len(tier_rows)
            basis, sampled = "history", len(tier_rows)
        else:
            estimate = 90.0 if tier == "fast" else 350.0
    bal = await ai_wallet.get_balance(user["user_id"])
    balance = float(bal.get("balance") or 0)
    estimate = round(estimate, 1)
    return {"endpoint": endpoint, "pages": pages, "tier": tier,
            "estimate": estimate, "balance": round(balance, 1),
            "sufficient": balance >= estimate,
            "shortfall": round(max(0.0, estimate - balance), 1),
            "basis": basis, "runs_sampled": sampled}


# ───────── AI provider consent (OpenAI free, data-sharing) ─────────
@router.get("/ai-wallet/provider-consent")
async def get_provider_consent(user: dict = Depends(get_current_user)):
    """The user's consent to use OpenAI's free (data-sharing) tier as a fallback.
    `mode`: 'ask' ⇒ prompt at each no-balance failure (default); 'always' ⇒ use
    OpenAI automatically without prompting."""
    u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "ai_provider_consent": 1})
    c = (u or {}).get("ai_provider_consent") or {}
    openai_available = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "allow_openai": bool(c.get("allow_openai", False)),
        "mode": c.get("mode") or "ask",
        "openai_available": openai_available,
    }


@router.put("/ai-wallet/provider-consent")
async def set_provider_consent(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Save OpenAI fallback consent. Body: { allow_openai: bool, mode?: 'ask'|'always' }."""
    allow = bool(body.get("allow_openai"))
    mode = body.get("mode") if body.get("mode") in ("ask", "always") else "ask"
    consent = {"allow_openai": allow, "mode": mode, "updated_at": _now_iso()}
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"ai_provider_consent": consent}},
    )
    return {"allow_openai": allow, "mode": mode, "openai_available": bool(os.getenv("OPENAI_API_KEY"))}


# ───────────────────────── admin ─────────────────────────
@router.get("/admin/ai-wallet/config")
async def get_wallet_config(user: dict = Depends(require_super_admin)):
    return await ai_wallet.get_config()


@router.put("/admin/ai-wallet/config")
async def update_wallet_config(body: Dict[str, Any], user: dict = Depends(require_super_admin)):
    try:
        return await ai_wallet.update_config(body, by=user.get("email") or user["user_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _resolve_user_id(body: Dict[str, Any]) -> str:
    uid = body.get("user_id")
    if uid:
        return uid
    email = (body.get("email") or "").strip().lower()
    if email:
        u = await db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        if u:
            return u["user_id"]
    raise HTTPException(status_code=404, detail="User not found (provide a valid user_id or email).")


@router.post("/admin/ai-wallet/grant")
async def grant_credits(body: Dict[str, Any], user: dict = Depends(require_admin)):
    """Add or set a user's AI credits. body: {user_id|email, credits, mode:'add'|'set'}."""
    target = await _resolve_user_id(body)
    try:
        credits = float(body.get("credits"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="`credits` must be a number.")
    mode = body.get("mode", "add")
    kind = "set" if mode == "set" else "grant"
    res = await ai_wallet.grant(
        target, credits, by=user.get("email") or user["user_id"],
        note=body.get("note") or ("Set by admin" if kind == "set" else "Granted by admin"),
        kind=kind,
    )
    return {"user_id": target, **res}


@router.get("/admin/ai-wallet/users")
async def list_wallets(limit: int = 100, user: dict = Depends(require_admin)):
    wallets = await db.ai_wallets.find({}, {"_id": 0}).sort("updated_at", -1).limit(min(max(limit, 1), 500)).to_list(500)
    # attach email/name
    ids = [w["user_id"] for w in wallets]
    users = {}
    if ids:
        async for u in db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "user_id": 1, "email": 1, "name": 1}):
            users[u["user_id"]] = u
    for w in wallets:
        u = users.get(w["user_id"], {})
        w["email"] = u.get("email", "")
        w["name"] = u.get("name", "")
        w["balance"] = round(float(w.get("balance", 0)), 2)
    return {"items": wallets}


# ════════════════════════════════════════════════════════════════════
# Phase 3 — Razorpay refill (Gemini-cost-pegged packs + hidden markup)
# ════════════════════════════════════════════════════════════════════
def _buyer_is_admin(user: dict) -> bool:
    role = (user.get("role") or "user").lower()
    return role in ("admin", "co_admin", "super_admin") or bool(user.get("is_admin"))


async def _resolve_credits(body: Dict[str, Any], cfg: Dict[str, Any]) -> int:
    pack_id = body.get("pack_id")
    if pack_id:
        pack = next((p for p in cfg.get("credit_packs", []) if p.get("id") == pack_id), None)
        if not pack:
            raise HTTPException(status_code=400, detail="Invalid credit pack.")
        return int(pack["credits"])
    try:
        credits = int(float(body.get("credits")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Provide a pack_id or a numeric `credits` amount.")
    if credits <= 0:
        raise HTTPException(status_code=400, detail="Credits must be a positive number.")
    min_c = int(float(cfg.get("min_custom_credits", 150)))
    if credits < min_c:
        raise HTTPException(status_code=400, detail=f"Minimum custom refill is {min_c} credits.")
    return credits


async def _credit_refill(order_doc: Dict[str, Any], payment_id: str, by: str) -> None:
    """Idempotently add purchased credits + record the cost/markup breakdown."""
    br = order_doc.get("breakdown", {}) or {}
    credits = int(order_doc.get("credits", 0))
    note = (
        f"Refill {credits} credits — ₹{br.get('total_inr')} "
        f"(cost ₹{br.get('cost_inr')}, markup ₹{br.get('markup_inr')}"
        f"{', routed' if order_doc.get('route_applied') else ''})"
    )
    await ai_wallet.grant(order_doc["user_id"], float(credits), by=by, note=note, kind="refill")
    await db.ai_wallet_orders.update_one(
        {"order_id": order_doc["order_id"]},
        {"$set": {"status": "paid", "razorpay_payment_id": payment_id, "paid_at": _now_iso()}},
    )


@router.get("/ai-wallet/packs")
async def refill_packs(user: dict = Depends(get_current_user)):
    cfg = await ai_wallet.get_config()
    is_admin = _buyer_is_admin(user)
    fx, fx_src = await ai_billing.get_usd_to_inr(cfg.get("usd_to_inr_fallback", 90.0))
    return {
        "packs": ai_billing.packs_priced(cfg, is_admin, fx),
        "is_admin": is_admin,
        "markup_pct": cfg.get("markup_admin_pct" if is_admin else "markup_user_pct"),
        "tokens_per_credit": cfg.get("tokens_per_credit"),
        "blended_usd_per_mtok": cfg.get("blended_usd_per_mtok"),
        "min_custom_credits": int(float(cfg.get("min_custom_credits", 150))),
        "fx_usd_inr": round(fx, 4),
        "fx_source": fx_src,
        "currency": "INR",
    }


@router.post("/ai-wallet/refill/quote")
async def refill_quote(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    cfg = await ai_wallet.get_config()
    is_admin = _buyer_is_admin(user)
    credits = await _resolve_credits(body, cfg)
    fx, fx_src = await ai_billing.get_usd_to_inr(cfg.get("usd_to_inr_fallback", 90.0))
    pr = ai_billing.price_for_credits(credits, is_admin, cfg, fx)
    pr["fx_source"] = fx_src
    return pr


@router.post("/ai-wallet/refill/order")
async def refill_order(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    rzp_client, key_id, _ = await get_razorpay_client()
    if not rzp_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")
    cfg = await ai_wallet.get_config()
    is_admin = _buyer_is_admin(user)
    credits = await _resolve_credits(body, cfg)
    fx, fx_src = await ai_billing.get_usd_to_inr(cfg.get("usd_to_inr_fallback", 90.0))
    pr = ai_billing.price_for_credits(credits, is_admin, cfg, fx)
    if pr["below_min"]:
        raise HTTPException(
            status_code=400,
            detail=f"Amount ₹{pr['total_inr']} is below the ₹{pr['min_inr']} minimum — buy more credits.",
        )

    ts = int(datetime.now(timezone.utc).timestamp())
    order_payload: Dict[str, Any] = {
        "amount": pr["total_paise"],
        "currency": "INR",
        "receipt": f"aicr_{user['user_id'][:8]}_{ts}"[:40],
        "payment_capture": 1,
        "notes": {"user_id": user["user_id"], "credits": str(credits), "type": "ai_credits_refill"},
    }
    linked = (cfg.get("route_linked_account_id") or "").strip()
    route_applied = False
    routed_paise = int(pr.get("routed_paise", 0))
    if linked and routed_paise >= ai_billing.ROUTE_MIN_TRANSFER_PAISE:
        order_payload["transfers"] = [{
            "account": linked,
            "amount": routed_paise,
            "currency": "INR",
            "notes": {"type": "ai_credits_markup", "user_id": user["user_id"]},
            "on_hold": 0,
        }]
        route_applied = True

    try:
        order = rzp_client.order.create(order_payload)
    except Exception as e:
        # Route may not be enabled / linked account not activated → retry WITHOUT
        # the transfer so checkout still works (markup stays in the main account).
        if route_applied:
            log.warning(f"Razorpay Route order failed ({str(e)[:140]}); retrying without Route.")
            order_payload.pop("transfers", None)
            route_applied = False
            try:
                order = rzp_client.order.create(order_payload)
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"Payment order creation failed: {str(e2)[:160]}")
        else:
            raise HTTPException(status_code=500, detail=f"Payment order creation failed: {str(e)[:160]}")

    await db.ai_wallet_orders.insert_one({
        "order_id": order["id"],
        "user_id": user["user_id"],
        "credits": credits,
        "is_admin": is_admin,
        "amount_paise": pr["total_paise"],
        "breakdown": pr,
        "route_applied": route_applied,
        "fx_source": fx_src,
        "status": "created",
        "created_at": _now_iso(),
    })
    return {
        "order_id": order["id"],
        "amount": pr["total_paise"],
        "currency": "INR",
        "key_id": key_id,
        "credits": credits,
        "price_inr": pr["total_inr"],
        "route_applied": route_applied,
        "user_name": user.get("name", ""),
        "user_email": user.get("email", ""),
        "breakdown": pr,
    }


@router.post("/ai-wallet/refill/verify")
async def refill_verify(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    oid = body.get("razorpay_order_id", "")
    pid = body.get("razorpay_payment_id", "")
    sig = body.get("razorpay_signature", "")
    if not all([oid, pid, sig]):
        raise HTTPException(status_code=400, detail="Missing payment verification fields.")
    _, key_secret, _ = await resolve_razorpay_creds()
    if not key_secret:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")
    expected = hmac.new(key_secret.encode("utf-8"), f"{oid}|{pid}".encode("utf-8"), hashlib.sha256).hexdigest()
    if expected != sig:
        raise HTTPException(status_code=400, detail="Payment verification failed — invalid signature.")
    order_doc = await db.ai_wallet_orders.find_one({"order_id": oid, "user_id": user["user_id"]}, {"_id": 0})
    if not order_doc:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order_doc.get("status") == "paid":
        bal = await ai_wallet.get_balance(user["user_id"])
        return {"message": "Payment already processed", "credits_added": 0, **bal}
    await _credit_refill(order_doc, pid, by="razorpay_verify")
    bal = await ai_wallet.get_balance(user["user_id"])
    return {"message": "Payment verified", "credits_added": int(order_doc["credits"]), **bal}


@router.post("/ai-wallet/refill/webhook")
async def refill_webhook(request: Request):
    """Razorpay webhook backup (no auth). Idempotently credits captured payments."""
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
    ent = (data.get("payload", {}) or {}).get("payment", {}).get("entity", {}) or {}
    oid = ent.get("order_id", "")
    if event == "payment.captured" and oid:
        order_doc = await db.ai_wallet_orders.find_one({"order_id": oid}, {"_id": 0})
        if order_doc and order_doc.get("status") != "paid":
            await _credit_refill(order_doc, ent.get("id", ""), by="razorpay_webhook")
    elif event == "payment.failed" and oid:
        await db.ai_wallet_orders.update_one({"order_id": oid}, {"$set": {"status": "failed", "failed_at": _now_iso()}})
    return {"status": "processed"}


_CHECKOUT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Credits — Payment</title>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#F5F7FA;margin:0;
  display:flex;align-items:center;justify-content:center;height:100vh;color:#1A1A2E}
 .card{background:#fff;border-radius:16px;padding:28px;max-width:360px;width:90%;
  box-shadow:0 6px 24px rgba(0,0,0,.08);text-align:center}
 h2{margin:8px 0 4px} p{color:#6B7280;font-size:14px;margin:6px 0}
 .btn{margin-top:16px;background:#8E24AA;color:#fff;border:none;border-radius:12px;
  padding:12px 20px;font-size:15px;font-weight:700;cursor:pointer}
 .ok{color:#10B981;font-weight:700} .err{color:#EF4444;font-weight:700}
</style></head><body>
<div class="card">
 <h2>AI Credits Top-up</h2>
 <p id="msg">Opening secure Razorpay checkout…</p>
 <button class="btn" id="payBtn" style="display:none" onclick="startPay()">Pay now</button>
</div>
<script>
 var OPTS={order_id:"__ORDER_ID__",key:"__KEY_ID__",amount:__AMOUNT__,name:"__NAME__",email:"__EMAIL__",token:"__TOKEN__"};
 function setMsg(t,c){var m=document.getElementById('msg');m.innerHTML=t;m.className=c||'';}
 function startPay(){
  document.getElementById('payBtn').style.display='none';
  var rzp=new Razorpay({
   key:OPTS.key, amount:OPTS.amount, currency:"INR", order_id:OPTS.order_id,
   name:"AI Credits", description:"Wallet top-up",
   prefill:{name:OPTS.name,email:OPTS.email},
   theme:{color:"#8E24AA"},
   handler:function(r){
     setMsg('Verifying payment…');
     fetch('/api/ai-wallet/refill/verify',{method:'POST',
       headers:{'Content-Type':'application/json','Authorization':'Bearer '+OPTS.token},
       body:JSON.stringify({razorpay_order_id:r.razorpay_order_id,razorpay_payment_id:r.razorpay_payment_id,razorpay_signature:r.razorpay_signature})})
      .then(function(res){return res.json().then(function(d){return {ok:res.ok,d:d}})})
      .then(function(x){ if(x.ok){setMsg('✓ Payment successful — '+(x.d.credits_added||'')+' credits added. You can close this window.','ok');}
        else{setMsg('Payment captured but verification failed: '+((x.d&&x.d.detail)||'')+'. Contact support.','err');} })
      .catch(function(){setMsg('Verification network error. If charged, credits will be added shortly.','err');});
   },
   modal:{ondismiss:function(){setMsg('Payment cancelled.','err');document.getElementById('payBtn').style.display='inline-block';}}
  });
  rzp.on('payment.failed',function(){setMsg('Payment failed. Please try again.','err');document.getElementById('payBtn').style.display='inline-block';});
  rzp.open();
 }
 window.onload=function(){ if(window.Razorpay){startPay();} else {setMsg('Could not load Razorpay.','err');} };
</script></body></html>"""


@router.get("/ai-wallet/refill/checkout", response_class=HTMLResponse)
async def refill_checkout(order_id: str, key_id: str, amount: int, token: str = "", name: str = "", email: str = ""):
    """Backend-hosted Razorpay checkout page (works on web + mobile in-app browser)."""
    def esc(s: str) -> str:
        return (s or "").replace("\\", "").replace('"', "'").replace("<", "").replace(">", "")
    html = (_CHECKOUT_HTML
            .replace("__ORDER_ID__", esc(order_id))
            .replace("__KEY_ID__", esc(key_id))
            .replace("__AMOUNT__", str(int(amount)))
            .replace("__NAME__", esc(name))
            .replace("__EMAIL__", esc(email))
            .replace("__TOKEN__", esc(token)))
    # Route-scoped CSP that permits the Razorpay checkout script/iframe. The global
    # SecurityHeadersMiddleware honours a route-set CSP, so this only loosens the
    # policy for this single payment page (not the rest of the API).
    return HTMLResponse(content=html, headers={"Content-Security-Policy": RAZORPAY_CSP})
