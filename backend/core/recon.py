"""Revenue Reconciliation engine — Razorpay ⟷ internal ledger ⟷ Google Cloud (Gemini).

Objective: ensure the PRIMARY account treasury is never in loss w.r.t. the
LLM-provider invoices (Gemini postpaid) — granular to the single transaction.

Data sources:
  1. Razorpay API (payments / transfers / settlements)  → synced into Mongo
  2. Internal: ai_wallet_orders + ai_wallet_ledger (credits sold / consumed)
  3. Google Cloud BigQuery Billing Export (actual Gemini spend, daily)

Collections:
  recon_config          {key:'singleton', gcp:{...}, last_rzp_sync, last_gcp_sync}
  recon_rzp_payments    one doc per Razorpay payment   (upsert by payment_id)
  recon_rzp_transfers   one doc per Route transfer     (upsert by transfer_id)
  recon_rzp_settlements one doc per settlement         (upsert by settlement_id)
  recon_gcp_costs       one doc per (usage_date, sku)  (upsert)
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.database import db
from core import ai_wallet, ai_billing
from core.integrations import get_razorpay_client

log = logging.getLogger("recon")

CONFIG_KEY = "singleton"
RZP_SYNC_OVERLAP_DAYS = 5     # re-fetch a window before last sync (late captures/settlements)
RZP_FIRST_SYNC_DAYS = 365     # initial backfill window
GCP_SYNC_DAYS = 62            # daily costs window pulled from BigQuery
GCP_MAX_BYTES_BILLED = 2 * 1024 ** 3  # 2 GB hard cap per query — cost guard


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─────────────────────────── config ───────────────────────────
async def get_config(mask: bool = True) -> Dict[str, Any]:
    doc = await db.recon_config.find_one({"key": CONFIG_KEY}, {"_id": 0}) or {"key": CONFIG_KEY}
    gcp = doc.get("gcp") or {}
    out = {
        "gcp": {
            "project_id": gcp.get("project_id", ""),
            "dataset": gcp.get("dataset", ""),
            "table": gcp.get("table", ""),
            "configured": bool(gcp.get("sa_json_b64")),
            "sa_client_email": gcp.get("sa_client_email", ""),
        },
        "last_rzp_sync": doc.get("last_rzp_sync"),
        "last_gcp_sync": doc.get("last_gcp_sync"),
        "last_rzp_sync_result": doc.get("last_rzp_sync_result"),
        "last_gcp_sync_result": doc.get("last_gcp_sync_result"),
    }
    if not mask:
        out["gcp"]["sa_json_b64"] = gcp.get("sa_json_b64", "")
    return out


async def update_gcp_config(patch: Dict[str, Any], by: str) -> Dict[str, Any]:
    """Save BigQuery billing-export connection details. `sa_json` is the raw
    pasted service-account JSON; stored base64-encoded, never returned."""
    sets: Dict[str, Any] = {}
    for k in ("project_id", "dataset", "table"):
        if k in patch and patch[k] is not None:
            sets[f"gcp.{k}"] = str(patch[k]).strip()
    sa_json = (patch.get("sa_json") or "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            email = info.get("client_email", "")
            if not (info.get("private_key") and email):
                raise ValueError("missing private_key/client_email")
        except Exception as e:
            raise ValueError(f"Invalid service-account JSON: {str(e)[:120]}")
        sets["gcp.sa_json_b64"] = base64.b64encode(sa_json.encode()).decode()
        sets["gcp.sa_client_email"] = email
        # default project from the key itself when not given explicitly
        if not sets.get("gcp.project_id") and info.get("project_id"):
            sets["gcp.project_id"] = info["project_id"]
    if patch.get("clear_credentials"):
        sets["gcp.sa_json_b64"] = ""
        sets["gcp.sa_client_email"] = ""
    if sets:
        sets["updated_at"] = _iso(_now())
        sets["updated_by"] = by
        await db.recon_config.update_one({"key": CONFIG_KEY}, {"$set": sets}, upsert=True)
    return await get_config()


# ─────────────────────── Razorpay sync ───────────────────────
def _fetch_rzp_collection(client, resource: str, frm: int, to: int) -> List[dict]:
    """Blocking paginated fetch of a Razorpay collection ('payment'|'transfer'|
    'settlement') between epoch seconds [frm, to]."""
    items: List[dict] = []
    skip = 0
    api = getattr(client, resource)
    while True:
        try:
            batch = api.all({"from": frm, "to": to, "count": 100, "skip": skip})
        except Exception as e:
            log.warning(f"Razorpay {resource}.all failed at skip={skip}: {str(e)[:160]}")
            break
        got = batch.get("items", []) or []
        items.extend(got)
        if len(got) < 100 or skip > 100_000:
            break
        skip += 100
    return items


async def sync_razorpay() -> Dict[str, Any]:
    """Pull payments / transfers / settlements from Razorpay into Mongo."""
    client, _, _ = await get_razorpay_client()
    if not client:
        return {"ok": False, "error": "Razorpay not configured"}

    cfg = await db.recon_config.find_one({"key": CONFIG_KEY}, {"_id": 0}) or {}
    last = cfg.get("last_rzp_sync")
    if last:
        frm_dt = datetime.fromisoformat(last) - timedelta(days=RZP_SYNC_OVERLAP_DAYS)
    else:
        frm_dt = _now() - timedelta(days=RZP_FIRST_SYNC_DAYS)
    frm, to = int(frm_dt.timestamp()), int(_now().timestamp())

    counts = {}
    for resource, coll, id_field in (
        ("payment", db.recon_rzp_payments, "payment_id"),
        ("transfer", db.recon_rzp_transfers, "transfer_id"),
        ("settlement", db.recon_rzp_settlements, "settlement_id"),
    ):
        items = await asyncio.to_thread(_fetch_rzp_collection, client, resource, frm, to)
        n = 0
        for it in items:
            rid = it.get("id")
            if not rid:
                continue
            doc = {
                id_field: rid,
                "entity": it,                      # full raw entity for audit
                "amount_paise": int(it.get("amount") or 0),
                "fee_paise": int(it.get("fee") or it.get("fees") or 0),
                "tax_paise": int(it.get("tax") or 0),
                "status": it.get("status", ""),
                "created_at_epoch": int(it.get("created_at") or 0),
                "order_id": it.get("order_id", ""),
                "source_payment_id": it.get("source", "") if resource == "transfer" else "",
                "recipient": it.get("recipient", "") if resource == "transfer" else "",
                "synced_at": _iso(_now()),
            }
            await coll.update_one({id_field: rid}, {"$set": doc}, upsert=True)
            n += 1
        counts[resource + "s"] = n

    result = {"ok": True, **counts, "window_from": _iso(frm_dt)}
    await db.recon_config.update_one(
        {"key": CONFIG_KEY},
        {"$set": {"last_rzp_sync": _iso(_now()), "last_rzp_sync_result": result}},
        upsert=True,
    )
    return result


# ─────────────────────── GCP (BigQuery) sync ───────────────────────
GEMINI_SQL_FILTER = (
    "(LOWER(service.description) LIKE '%vertex ai%' "
    "OR LOWER(service.description) LIKE '%generative language%' "
    "OR LOWER(service.description) LIKE '%gemini%' "
    "OR LOWER(sku.description) LIKE '%gemini%')"
)


def _bq_fetch_daily_costs(sa_json: str, project: str, table_fqn: str, days: int) -> List[dict]:
    """Blocking BigQuery query — daily Gemini-related cost grouped by SKU."""
    from google.cloud import bigquery
    from google.oauth2 import service_account

    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = bigquery.Client(project=project or info.get("project_id"), credentials=creds)
    sql = f"""
    SELECT
      DATE(usage_start_time) AS usage_date,
      service.description AS service_description,
      sku.id AS sku_id,
      sku.description AS sku_description,
      ANY_VALUE(currency) AS currency,
      (SUM(CAST(cost AS NUMERIC)) +
       SUM(IFNULL((SELECT SUM(CAST(c.amount AS NUMERIC)) FROM UNNEST(credits) AS c), 0))
      ) AS net_cost
    FROM `{table_fqn}`
    WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(days)} DAY)
      AND {GEMINI_SQL_FILTER}
    GROUP BY usage_date, service_description, sku_id, sku_description
    ORDER BY usage_date ASC
    """
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=GCP_MAX_BYTES_BILLED)
    rows = client.query(sql, job_config=job_config).result()
    return [
        {
            "usage_date": str(r["usage_date"]),
            "service_description": r["service_description"],
            "sku_id": r["sku_id"],
            "sku_description": r["sku_description"],
            "currency": r["currency"] or "USD",
            "net_cost": float(r["net_cost"]),
        }
        for r in rows
    ]


async def sync_gcp() -> Dict[str, Any]:
    cfg = await get_config(mask=False)
    gcp = cfg["gcp"]
    if not gcp.get("sa_json_b64"):
        return {"ok": False, "error": "GCP not configured — paste the service-account JSON in settings."}
    if not (gcp.get("dataset") and gcp.get("table")):
        return {"ok": False, "error": "GCP dataset/table not set."}
    sa_json = base64.b64decode(gcp["sa_json_b64"]).decode()
    table_fqn = f"{gcp['project_id']}.{gcp['dataset']}.{gcp['table']}"
    try:
        rows = await asyncio.to_thread(
            _bq_fetch_daily_costs, sa_json, gcp["project_id"], table_fqn, GCP_SYNC_DAYS
        )
    except Exception as e:
        err = str(e)[:300]
        await db.recon_config.update_one(
            {"key": CONFIG_KEY},
            {"$set": {"last_gcp_sync_result": {"ok": False, "error": err}}},
            upsert=True,
        )
        return {"ok": False, "error": err}

    n = 0
    for r in rows:
        key = {"usage_date": r["usage_date"], "sku_id": r["sku_id"]}
        await db.recon_gcp_costs.update_one(
            key, {"$set": {**r, "synced_at": _iso(_now())}}, upsert=True
        )
        n += 1
    result = {"ok": True, "rows": n, "days": GCP_SYNC_DAYS}
    await db.recon_config.update_one(
        {"key": CONFIG_KEY},
        {"$set": {"last_gcp_sync": _iso(_now()), "last_gcp_sync_result": result}},
        upsert=True,
    )
    return result


# ─────────────────────── per-transaction tally ───────────────────────
async def transactions_tally(limit: int = 100, skip: int = 0,
                             month: Optional[str] = None) -> Dict[str, Any]:
    """Per-transaction zero-loss tally. One row per PAID ai-wallet refill order:
      collected → razorpay fee+GST → routed markup → net treasury
      vs the LLM-cost portion earmarked at sale time (breakdown.cost_inr).
      buffer = net_treasury − earmarked_cost  (negative ⇒ that sale is a loss
      for the primary account even before Gemini bills arrive)."""
    q: Dict[str, Any] = {"status": "paid"}
    if month:  # 'YYYY-MM'
        q["created_at"] = {"$gte": f"{month}-01", "$lt": f"{month}-99"}
    total = await db.ai_wallet_orders.count_documents(q)
    orders = await (
        db.ai_wallet_orders.find(q, {"_id": 0})
        .sort("created_at", -1).skip(skip).limit(min(max(limit, 1), 500))
        .to_list(500)
    )

    rows: List[Dict[str, Any]] = []
    for o in orders:
        br = o.get("breakdown") or {}
        pid = o.get("razorpay_payment_id", "")
        pay = await db.recon_rzp_payments.find_one({"payment_id": pid}, {"_id": 0}) if pid else None
        # Route transfer linked to this payment
        tr = await db.recon_rzp_transfers.find_one({"source_payment_id": pid}, {"_id": 0}) if pid else None
        # internal credit grant (refill ledger entry)
        led = await db.ai_wallet_ledger.find_one(
            {"user_id": o["user_id"], "kind": "refill",
             "note": {"$regex": f"^Refill {int(o.get('credits', 0))} credits"}},
            {"_id": 0, "delta": 1, "created_at": 1},
        )

        collected = round(o.get("amount_paise", 0) / 100.0, 2)
        fee = round(((pay or {}).get("fee_paise", 0)) / 100.0, 2)         # incl. GST
        routed = round(((tr or {}).get("amount_paise", 0)) / 100.0, 2)
        net_treasury = round(collected - fee - routed, 2)
        cost_inr = float(br.get("cost_inr") or 0)
        buffer = round(net_treasury - cost_inr, 2)

        rows.append({
            "order_id": o.get("order_id"),
            "payment_id": pid,
            "user_id": o.get("user_id"),
            "created_at": o.get("created_at"),
            "credits": int(o.get("credits", 0)),
            "collected_inr": collected,
            "rzp_fee_inr": fee,
            "routed_markup_inr": routed,
            "net_treasury_inr": net_treasury,
            "earmarked_llm_cost_inr": round(cost_inr, 2),
            "buffer_inr": buffer,
            "fx_usd_inr": br.get("fx_usd_inr"),
            "markup_pct": br.get("markup_pct"),
            "route_applied": bool(o.get("route_applied")),
            "flags": {
                "payment_synced": pay is not None,
                "fee_known": bool(pay and pay.get("fee_paise")),
                "transfer_synced": tr is not None or not o.get("route_applied"),
                "credits_granted": led is not None,
                "captured": (pay or {}).get("status", "") in ("captured", "") if pay else False,
                "at_loss": buffer < 0,
            },
        })
    return {"items": rows, "total": total, "limit": limit, "skip": skip}


# ─────────────────────── daily consumption tally ───────────────────────
async def daily_tally(days: int = 31) -> Dict[str, Any]:
    """Per-day: tokens consumed → estimated provider cost (₹) vs GCP actual (₹)."""
    cfg = await ai_wallet.get_config()
    blended = float(cfg.get("blended_usd_per_mtok", 2.0))
    fx, fx_src = await ai_billing.get_usd_to_inr(cfg.get("usd_to_inr_fallback", 90.0))
    since = _now() - timedelta(days=days)

    pipeline = [
        {"$match": {"kind": "debit", "created_at": {"$gte": since}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "tokens": {"$sum": "$tokens"},
            "credits": {"$sum": {"$abs": "$delta"}},
            "calls": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    est_by_day: Dict[str, Dict[str, Any]] = {}
    async for g in db.ai_wallet_ledger.aggregate(pipeline):
        d = g["_id"]
        est_inr = g["tokens"] / 1_000_000.0 * blended * fx
        est_by_day[d] = {
            "date": d, "tokens": int(g["tokens"]), "credits": round(g["credits"], 2),
            "calls": g["calls"], "est_cost_inr": round(est_inr, 2),
        }

    # GCP actuals (convert USD→INR at current fx; INR rows used as-is)
    gcp_by_day: Dict[str, float] = {}
    since_str = since.strftime("%Y-%m-%d")
    async for r in db.recon_gcp_costs.find({"usage_date": {"$gte": since_str}}, {"_id": 0}):
        amt = float(r.get("net_cost", 0))
        inr = amt * fx if (r.get("currency") or "USD").upper() == "USD" else amt
        gcp_by_day[r["usage_date"]] = round(gcp_by_day.get(r["usage_date"], 0.0) + inr, 2)

    # ScraperAPI scrape costs per day (plan-rate, what we owe ScraperAPI)
    scrape_by_day: Dict[str, Dict[str, Any]] = {}
    async for g in db.scrape_usage.aggregate([
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "fetches": {"$sum": 1}, "usd_base": {"$sum": "$usd_base_cost"}}},
    ]):
        scrape_by_day[g["_id"]] = {"fetches": g["fetches"],
                                   "cost_inr": round(g["usd_base"] * fx, 2)}

    all_days = sorted(set(est_by_day) | set(gcp_by_day) | set(scrape_by_day))
    rows = []
    for d in all_days:
        est = est_by_day.get(d, {"date": d, "tokens": 0, "credits": 0, "calls": 0, "est_cost_inr": 0.0})
        actual = gcp_by_day.get(d)
        scr = scrape_by_day.get(d, {"fetches": 0, "cost_inr": 0.0})
        rows.append({
            **est,
            "gcp_actual_inr": actual,
            "variance_inr": round((actual - est["est_cost_inr"]), 2) if actual is not None else None,
            "scrape_fetches": scr["fetches"],
            "scrape_cost_inr": scr["cost_inr"],
        })
    return {"items": rows, "fx_usd_inr": round(fx, 4), "fx_source": fx_src,
            "blended_usd_per_mtok": blended}


# ─────────────────────── ScraperAPI (scrape metering) ───────────────────────
async def scraperapi_account() -> Optional[Dict[str, Any]]:
    """Live usage snapshot from ScraperAPI's /account endpoint (best-effort)."""
    from core.integrations import resolve_scraperapi
    import httpx
    sc = await resolve_scraperapi()
    if not sc.get("api_key"):
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get("https://api.scraperapi.com/account",
                              params={"api_key": sc["api_key"]})
        if r.status_code == 200:
            j = r.json()
            return {
                "request_count": j.get("requestCount"),
                "request_limit": j.get("requestLimit"),
                "failed_count": j.get("failedRequestCount"),
                "concurrency_limit": j.get("concurrencyLimit"),
            }
    except Exception as e:  # noqa: BLE001 — snapshot is best-effort
        log.warning(f"ScraperAPI account fetch failed: {str(e)[:120]}")
    return None


async def _scrape_totals() -> Dict[str, float]:
    rows = await db.scrape_usage.aggregate([
        {"$group": {"_id": None, "fetches": {"$sum": 1},
                    "scraper_credits": {"$sum": "$scraper_credits"},
                    "app_credits": {"$sum": "$app_credits"},
                    "usd_base": {"$sum": "$usd_base_cost"},
                    "usd_charged": {"$sum": "$usd_cost"}}}]).to_list(1)
    g = rows[0] if rows else {}
    return {"fetches": int(g.get("fetches") or 0),
            "scraper_credits": int(g.get("scraper_credits") or 0),
            "app_credits": round(float(g.get("app_credits") or 0), 2),
            "usd_base": float(g.get("usd_base") or 0),
            "usd_charged": float(g.get("usd_charged") or 0)}


# ─────────────────────── summary ───────────────────────
async def summary() -> Dict[str, Any]:
    cfg_w = await ai_wallet.get_config()
    blended = float(cfg_w.get("blended_usd_per_mtok", 2.0))
    fx, fx_src = await ai_billing.get_usd_to_inr(cfg_w.get("usd_to_inr_fallback", 90.0))

    # Sales side — all paid orders
    sales = {"collected": 0.0, "earmarked_cost": 0.0, "markup": 0.0, "orders": 0, "credits_sold": 0}
    async for o in db.ai_wallet_orders.find({"status": "paid"}, {"_id": 0, "breakdown": 1, "amount_paise": 1, "credits": 1}):
        br = o.get("breakdown") or {}
        sales["collected"] += o.get("amount_paise", 0) / 100.0
        sales["earmarked_cost"] += float(br.get("cost_inr") or 0)
        sales["markup"] += float(br.get("markup_inr") or 0)
        sales["orders"] += 1
        sales["credits_sold"] += int(o.get("credits", 0))

    # Razorpay side — fees on those payments + routed transfers
    fee_agg = await db.recon_rzp_payments.aggregate([
        {"$match": {"status": "captured"}},
        {"$group": {"_id": None, "fees": {"$sum": "$fee_paise"}, "n": {"$sum": 1}}},
    ]).to_list(1)
    rzp_fees = round((fee_agg[0]["fees"] / 100.0) if fee_agg else 0.0, 2)
    tr_agg = await db.recon_rzp_transfers.aggregate([
        {"$group": {"_id": None, "amt": {"$sum": "$amount_paise"}, "n": {"$sum": 1}}},
    ]).to_list(1)
    routed = round((tr_agg[0]["amt"] / 100.0) if tr_agg else 0.0, 2)

    # Consumption side — total tokens ever debited → estimated liability
    cons = await db.ai_wallet_ledger.aggregate([
        {"$match": {"kind": "debit"}},
        {"$group": {"_id": None, "tokens": {"$sum": "$tokens"},
                    "credits": {"$sum": {"$abs": "$delta"}}}},
    ]).to_list(1)
    tokens_used = int(cons[0]["tokens"]) if cons else 0
    credits_used = round(float(cons[0]["credits"]), 2) if cons else 0.0
    est_liability = round(tokens_used / 1_000_000.0 * blended * fx, 2)

    # GCP actuals total (synced window)
    gcp_total = 0.0
    gcp_rows = 0
    async for r in db.recon_gcp_costs.find({}, {"_id": 0, "net_cost": 1, "currency": 1}):
        amt = float(r.get("net_cost", 0))
        gcp_total += amt * fx if (r.get("currency") or "USD").upper() == "USD" else amt
        gcp_rows += 1

    # ScraperAPI scrape consumption (per-user metered) + live account snapshot
    scrape = await _scrape_totals()
    scrape_cost_inr = round(scrape["usd_base"] * fx, 2)
    scrape_charged_inr = round(scrape["usd_charged"] * fx, 2)
    sc_account = await scraperapi_account()

    net_treasury = round(sales["collected"] - rzp_fees - routed, 2)
    surplus_vs_est = round(net_treasury - est_liability - scrape_cost_inr, 2)
    surplus_vs_gcp = round(net_treasury - gcp_total - scrape_cost_inr, 2) if gcp_rows else None

    recon_cfg = await get_config()
    return {
        "fx_usd_inr": round(fx, 4), "fx_source": fx_src, "blended_usd_per_mtok": blended,
        "sales": {
            "orders": sales["orders"],
            "credits_sold": sales["credits_sold"],
            "collected_inr": round(sales["collected"], 2),
            "earmarked_llm_cost_inr": round(sales["earmarked_cost"], 2),
            "markup_inr": round(sales["markup"], 2),
        },
        "razorpay": {
            "fees_inr": rzp_fees,
            "routed_markup_inr": routed,
            "net_treasury_inr": net_treasury,
        },
        "consumption": {
            "tokens_used": tokens_used,
            "credits_used": credits_used,
            "est_liability_inr": est_liability,
        },
        "gcp": {
            "actual_cost_inr": round(gcp_total, 2) if gcp_rows else None,
            "rows_synced": gcp_rows,
            "configured": recon_cfg["gcp"]["configured"],
        },
        "scraperapi": {
            "fetches": scrape["fetches"],
            "scraper_credits_used": scrape["scraper_credits"],
            "est_cost_inr": scrape_cost_inr,          # what we owe ScraperAPI (plan-rate)
            "charged_credits": scrape["app_credits"],  # app credits debited from users
            "charged_value_inr": scrape_charged_inr,   # incl. scrape markup
            "account": sc_account,                     # live /account snapshot (None when unavailable)
            "plan": {
                "usd_month": float(cfg_w.get("scraperapi_plan_usd_month") or 0),
                "credits_month": float(cfg_w.get("scraperapi_plan_credits_month") or 0),
                "markup_pct": float(cfg_w.get("scrape_markup_pct") or 0),
            },
        },
        "verdict": {
            "surplus_vs_estimate_inr": surplus_vs_est,
            "surplus_vs_gcp_actual_inr": surplus_vs_gcp,
            "at_risk": surplus_vs_est < 0 or (surplus_vs_gcp is not None and surplus_vs_gcp < 0),
        },
        "last_rzp_sync": recon_cfg["last_rzp_sync"],
        "last_gcp_sync": recon_cfg["last_gcp_sync"],
    }


# ─────────────────────── daily background sync ───────────────────────
_task_started = False


def start_daily_sync_task() -> None:
    """Fire-and-forget daily sync loop (Razorpay + GCP). First run 10 min after
    boot, then every 24 h. On-demand sync is always available via the API."""
    global _task_started
    if _task_started:
        return
    _task_started = True

    async def _loop():
        await asyncio.sleep(600)
        while True:
            try:
                r = await sync_razorpay()
                g = await sync_gcp()
                log.info(f"recon daily sync — rzp={r.get('ok')} gcp={g.get('ok', g.get('error', ''))}")
            except Exception as e:
                log.error(f"recon daily sync failed: {e}")
            await asyncio.sleep(24 * 3600)

    asyncio.get_event_loop().create_task(_loop())
    log.info("Revenue-recon daily sync task started (24h cadence).")
