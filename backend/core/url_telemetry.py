"""Import-from-URL telemetry — the data backbone of the admin
"Import Analytics" dashboard (learning & prompt-tuning loop).

Every import/analyze run is recorded to `db.url_import_runs` (source of
truth, full granularity incl. the EXACT prompt + raw LLM response, truncated)
AND emitted as a lightweight PostHog event (`url_import_completed`) so the
feature shows up in the existing PostHog product-analytics timeline.

Retention: prompt/response bodies are purged after PURGE_DAYS (lazy purge on
insert); run metadata is kept indefinitely for trend analytics.
NEVER raises — telemetry must not break the import flow.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.database import db
from core import posthog_client

logger = logging.getLogger(__name__)

TRUNC = 15000          # max chars stored for prompt / raw-response bodies
CALL_TRUNC = 6000      # per-call bodies inside the multi-call AI trace
PURGE_DAYS = 90        # bodies older than this are unset (metadata kept)


def _now():
    return datetime.now(timezone.utc)


def _trunc(v: Any, limit: int = TRUNC) -> Optional[str]:
    if v in (None, ""):
        return None
    s = str(v)
    return s[:limit] + ("…[truncated]" if len(s) > limit else "")


def new_tel(user_id: str, *, endpoint: str, url: str, ai_tier: str,
            hints: Optional[Dict[str, Any]], decision_id: Optional[str] = None) -> Dict[str, Any]:
    """Mutable telemetry context threaded through one import run."""
    return {
        "run_id": uuid.uuid4().hex,
        "user_id": user_id, "endpoint": endpoint, "url": (url or "").strip()[:500],
        "ai_tier": ai_tier, "hints": hints or {}, "decision_id": decision_id,
        "t0": _now(),
        # filled along the way:
        "page_type": None, "page_type_confidence": None, "classifier_provider": None,
        "route": None, "ai": None,
    }


def add_ai_call(tel: Dict[str, Any], *, stage: str, system_prompt: str,
                prompt_text: str, raw_response: str,
                meta: Optional[Dict[str, Any]] = None,
                started: Optional[datetime] = None) -> None:
    """Append one AI call to the run's multi-call trace (R&D / auto-tuning gold:
    exact engineered prompt + engine/model + tokens + credits per stage).
    Used by multi-stage flows like Deep Import. Never raises."""
    try:
        m = meta or {}
        provider, model = m.get("provider"), m.get("model")
        tel.setdefault("ai_calls", []).append({
            "stage": str(stage)[:60],
            "provider": provider, "model": model,
            "engine": "/".join(str(x) for x in (provider, model) if x) or None,
            "tokens": int(m.get("tokens") or 0),
            "credits": round(float(m.get("credits") or 0), 4),
            "latency_ms": (int((_now() - started).total_seconds() * 1000)
                           if started else None),
            "system_prompt": _trunc(system_prompt, CALL_TRUNC),
            "prompt_text": _trunc(prompt_text, CALL_TRUNC),
            "raw_response": _trunc(raw_response, CALL_TRUNC),
        })
    except Exception as e:  # noqa: BLE001 — telemetry never breaks the flow
        logger.warning("add_ai_call failed (non-fatal): %s", str(e)[:120])


async def record_run(tel: Dict[str, Any], *, status: str = "success",
                     response: Optional[Dict[str, Any]] = None,
                     error: Optional[str] = None) -> str:
    """Persist one run + emit the PostHog event. Returns run_id."""
    try:
        now = _now()
        ai = tel.get("ai") or {}
        resp = response or {}
        hint_warnings = list(resp.get("hint_warnings") or [])
        doc = {
            "id": tel["run_id"], "ts": now,
            "user_id": tel["user_id"], "endpoint": tel["endpoint"],
            "decision_id": tel.get("decision_id"),
            "url": tel["url"], "ai_tier": tel["ai_tier"], "hints": tel["hints"],
            "hints_given": bool(tel["hints"]),
            "page_type": tel.get("page_type"),
            "page_type_confidence": tel.get("page_type_confidence"),
            "classifier_provider": tel.get("classifier_provider"),
            "route": tel.get("route"),
            "status": status, "error": (error or None),
            "latency_ms": int((now - tel["t0"]).total_seconds() * 1000),
            # outcome
            "mode": resp.get("mode"), "structure": resp.get("structure"),
            "ai_provider": resp.get("ai_provider") or ai.get("provider"),
            "item_count": resp.get("item_count"),
            "factor_count": resp.get("factor_count") or resp.get("factors_added"),
            "factors_added": resp.get("factors_added"),
            "options_added": resp.get("options_added"),
            "hint_warnings": hint_warnings,
            "hint_pass": (not hint_warnings) if (status == "success" and tel["hints"]) else None,
            # AI internals (prompt-tuning gold)
            "ai_retry_used": bool(ai.get("retry_used")),
            "ai_attempts": ai.get("attempts") or 0,
            "ai_tokens": ai.get("tokens") or 0,
            "ai_system_prompt": _trunc(ai.get("system_prompt")),
            "ai_prompt_text": _trunc(ai.get("prompt_text")),
            "ai_raw_response": _trunc(ai.get("raw_response")),
            # page-grounding verification + provenance quotes (P0 trust)
            "verification": tel.get("verification"),
            "evidence": (tel.get("evidence") or [])[:80],
            # user accuracy verdict (👍/👎) — set later via feedback endpoint
            "feedback": None, "feedback_at": None,
            # ScraperAPI scrape-fetch costs incurred during this run (metered)
            "scrape": None,
        }
        # Multi-call AI trace (deep imports & other multi-stage flows) + rollups
        ai_calls = list(tel.get("ai_calls") or [])
        doc["ai_calls"] = ai_calls
        doc["ai_calls_count"] = len(ai_calls)
        if ai_calls:
            doc["ai_tokens"] = sum(int(c.get("tokens") or 0) for c in ai_calls)
            doc["ai_engines"] = sorted({c["engine"] for c in ai_calls if c.get("engine")})
            if not doc["ai_provider"]:
                doc["ai_provider"] = ai_calls[-1].get("provider")
        else:
            doc["ai_engines"] = [doc["ai_provider"]] if doc["ai_provider"] else []
        srows = await db.scrape_usage.aggregate([
            {"$match": {"user_id": tel["user_id"], "created_at": {"$gte": tel["t0"]}}},
            {"$group": {"_id": None, "fetches": {"$sum": 1},
                        "scraper_credits": {"$sum": "$scraper_credits"},
                        "app_credits": {"$sum": "$app_credits"},
                        "usd": {"$sum": "$usd_cost"}}}]).to_list(1)
        if srows:
            g = srows[0]
            doc["scrape"] = {"fetches": g["fetches"],
                             "scraper_credits": g["scraper_credits"],
                             "app_credits": round(g["app_credits"], 4),
                             "usd_cost": round(g["usd"], 6)}
        # AI credits consumed during this run (wallet-ledger debit rollup —
        # covers every metered stage incl. flows that predate the call trace)
        arows = await db.ai_wallet_ledger.aggregate([
            {"$match": {"user_id": tel["user_id"], "created_at": {"$gte": tel["t0"]},
                        "kind": "debit", "feature": {"$ne": "scrape_fetch"}}},
            {"$group": {"_id": None,
                        "credits": {"$sum": {"$multiply": [-1, "$delta"]}}}}]).to_list(1)
        ai_credits = round(float(arows[0]["credits"]), 4) if arows else 0.0
        doc["ai_credits"] = ai_credits
        doc["total_credits"] = round(
            ai_credits + float((doc.get("scrape") or {}).get("app_credits") or 0), 4)
        await db.url_import_runs.insert_one(doc)
        await _lazy_purge(now)
        posthog_client.track(tel["user_id"], "url_import_completed", {
            "endpoint": tel["endpoint"], "status": status,
            "page_type": tel.get("page_type"), "route": tel.get("route"),
            "ai_tier": tel["ai_tier"], "ai_provider": doc["ai_provider"],
            "hints_given": doc["hints_given"], "hint_pass": doc["hint_pass"],
            "latency_ms": doc["latency_ms"],
            "factor_count": doc["factor_count"], "option_count": doc["item_count"],
            "retry_used": doc["ai_retry_used"],
            "ai_credits": ai_credits, "total_credits": doc["total_credits"],
        })
    except Exception as e:  # noqa: BLE001 — telemetry never breaks the import
        logger.warning("url-import telemetry record failed (non-fatal): %s", str(e)[:200])
    if status != "success":
        # Notification Engine — fire-and-forget failure alert (throttled per trigger)
        try:
            from core.notification_engine import emit_event_bg
            emit_event_bg("import-run-failed", {
                "url": tel["url"], "error": error, "page_type": tel.get("page_type"),
                "endpoint": tel["endpoint"], "user_id": tel["user_id"], "run_id": tel["run_id"],
            })
        except Exception:  # noqa: BLE001
            pass
    return tel["run_id"]


async def _lazy_purge(now: datetime) -> None:
    """Unset prompt/response bodies older than PURGE_DAYS (metadata kept)."""
    cutoff = now - timedelta(days=PURGE_DAYS)
    await db.url_import_runs.update_many(
        {"ts": {"$lt": cutoff}, "ai_system_prompt": {"$ne": None}},
        {"$unset": {"ai_system_prompt": "", "ai_prompt_text": "", "ai_raw_response": ""},
         "$set": {"bodies_purged": True}})
    # Multi-call trace bodies: keep stage/engine/tokens/credits, drop the texts.
    await db.url_import_runs.update_many(
        {"ts": {"$lt": cutoff}, "ai_calls.0": {"$exists": True},
         "ai_calls_bodies_purged": {"$ne": True}},
        {"$unset": {"ai_calls.$[].system_prompt": "", "ai_calls.$[].prompt_text": "",
                    "ai_calls.$[].raw_response": ""},
         "$set": {"ai_calls_bodies_purged": True}})


async def set_feedback(run_id: str, user_id: str, verdict: str) -> bool:
    """1-tap user accuracy verdict ('up'|'down'); owner-only. Returns found."""
    r = await db.url_import_runs.update_one(
        {"id": run_id, "user_id": user_id},
        {"$set": {"feedback": verdict, "feedback_at": _now()}})
    if r.matched_count:
        posthog_client.track(user_id, "url_import_feedback", {"run_id": run_id, "verdict": verdict})
    return bool(r.matched_count)


# ── Admin aggregations (Import Analytics dashboard) ─────────────────────────
def _rate(num: int, den: int) -> Optional[float]:
    return round(num / den * 100, 1) if den else None


async def summary(days: int = 30) -> Dict[str, Any]:
    since = _now() - timedelta(days=days)
    match = {"ts": {"$gte": since}}
    total = await db.url_import_runs.count_documents(match)
    ok = await db.url_import_runs.count_documents({**match, "status": "success"})
    hinted = await db.url_import_runs.count_documents({**match, "hints_given": True, "status": "success"})
    hint_pass = await db.url_import_runs.count_documents({**match, "hint_pass": True})
    ai_routes = await db.url_import_runs.count_documents({**match, "route": "ai_extraction"})
    retries = await db.url_import_runs.count_documents({**match, "ai_retry_used": True})
    fb_up = await db.url_import_runs.count_documents({**match, "feedback": "up"})
    fb_down = await db.url_import_runs.count_documents({**match, "feedback": "down"})

    async def _breakdown(field: str) -> List[Dict[str, Any]]:
        pipe = [
            {"$match": match},
            {"$group": {"_id": f"${field}", "runs": {"$sum": 1},
                        "ok": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                        "hint_pass": {"$sum": {"$cond": [{"$eq": ["$hint_pass", True]}, 1, 0]}},
                        "hinted": {"$sum": {"$cond": [{"$eq": ["$hints_given", True]}, 1, 0]}},
                        "fb_up": {"$sum": {"$cond": [{"$eq": ["$feedback", "up"]}, 1, 0]}},
                        "fb_down": {"$sum": {"$cond": [{"$eq": ["$feedback", "down"]}, 1, 0]}},
                        "avg_latency_ms": {"$avg": "$latency_ms"},
                        "avg_credits": {"$avg": "$total_credits"},
                        "avg_factors": {"$avg": "$factor_count"}}},
            {"$sort": {"runs": -1}},
        ]
        rows = await db.url_import_runs.aggregate(pipe).to_list(20)
        return [{"key": r["_id"] or "(none)", "runs": r["runs"],
                 "success_rate": _rate(r["ok"], r["runs"]),
                 "hint_pass_rate": _rate(r["hint_pass"], r["hinted"]),
                 "feedback_up": r["fb_up"], "feedback_down": r["fb_down"],
                 "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                 "avg_credits": round(r["avg_credits"] or 0, 2),
                 "avg_factors": round(r["avg_factors"] or 0, 1)} for r in rows]

    lat = await db.url_import_runs.aggregate([
        {"$match": {**match, "status": "success"}},
        {"$group": {"_id": None, "avg": {"$avg": "$latency_ms"}}}]).to_list(1)
    return {
        "days": days, "total_runs": total,
        "success_rate": _rate(ok, total),
        "hint_adoption_rate": _rate(hinted, ok),
        "hint_pass_rate": _rate(hint_pass, hinted),
        "ai_escalation_rate": _rate(ai_routes, total),
        "retry_rate": _rate(retries, total),
        "feedback": {"up": fb_up, "down": fb_down,
                     "satisfaction": _rate(fb_up, fb_up + fb_down)},
        "avg_latency_ms": int((lat[0]["avg"] if lat else 0) or 0),
        "by_page_type": await _breakdown("page_type"),
        "by_provider": await _breakdown("ai_provider"),
        "by_route": await _breakdown("route"),
    }


_LIST_PROJECTION = {"_id": 0, "ai_system_prompt": 0, "ai_prompt_text": 0, "ai_raw_response": 0,
                    "hints": 0}


async def list_runs(*, days: int = 30, page_type: Optional[str] = None,
                    route: Optional[str] = None, status: Optional[str] = None,
                    feedback: Optional[str] = None,
                    limit: int = 50, skip: int = 0) -> Dict[str, Any]:
    q: Dict[str, Any] = {"ts": {"$gte": _now() - timedelta(days=days)}}
    if page_type:
        q["page_type"] = page_type
    if route:
        q["route"] = route
    if status:
        q["status"] = status
    if feedback:
        q["feedback"] = feedback
    total = await db.url_import_runs.count_documents(q)
    rows = await (db.url_import_runs.find(q, _LIST_PROJECTION)
                  .sort("ts", -1).skip(skip).limit(min(limit, 200)).to_list(200))
    return {"total": total, "items": rows}


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return await db.url_import_runs.find_one({"id": run_id}, {"_id": 0})
