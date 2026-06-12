"""Generic Notification Engine — CRUD-able trigger events → Email + WhatsApp.

Admins register *triggers* against a fixed registry of trigger-event keys
(EVENT_REGISTRY). Two kinds:

* ``scheduled`` — cron-style (daily / weekly / monthly at HH:MM in a timezone).
  A 60-second APScheduler tick fires due triggers (``next_run_at <= now``).
* ``event``     — fired in-code via :func:`emit_event` (e.g. an import run
  fails). Throttled per-trigger via ``throttle_minutes`` to avoid spam.

Channels per trigger (independent on/off toggles):
* email     → Resend  (core.notify.send_email)
* whatsapp  → UltraMsg (core.notify.send_whatsapp)

Every dispatch is logged to ``db.notification_runs`` for the admin UI.
First registered event: ``import-analytics`` — the weekly Import-URL
Intelligence digest (summary + per-page-type breakdown + top failures +
👍/👎 feedback, last 7 days).

Multi-worker safety: the scheduler start is gated behind an fcntl advisory
lock (same pattern as core/regression/scheduler.py).
Override: ``NOTIFICATION_SCHEDULER_DISABLED=true``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.database import db
from core.notify import PUBLIC_APP_URL, send_email, send_whatsapp

logger = logging.getLogger(__name__)

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABEL = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
             "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
FREQUENCIES = ("daily", "weekly", "monthly")
RUN_HISTORY_LIMIT = 200  # capped per query; collection pruned lazily


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Payload builders — one per registered trigger-event key
# ─────────────────────────────────────────────────────────────────────────────

def _pct(v) -> str:
    return "—" if v is None else f"{v}%"


def _digest_html(s: Dict[str, Any], fails: List[Dict[str, Any]], days: int) -> str:
    """Branded HTML digest email: KPIs + page-type table + top failures."""
    fb = s.get("feedback") or {}
    kpis = [
        ("Runs", s.get("total_runs", 0)),
        ("Success", _pct(s.get("success_rate"))),
        ("Hint pass", _pct(s.get("hint_pass_rate"))),
        ("AI escalation", _pct(s.get("ai_escalation_rate"))),
        ("👍 Satisfaction", "—" if fb.get("satisfaction") is None
         else f"{fb['satisfaction']}% ({fb.get('up', 0)}↑ {fb.get('down', 0)}↓)"),
        ("Avg latency", f"{(s.get('avg_latency_ms') or 0) / 1000:.1f}s"),
    ]
    kpi_cells = "".join(
        f'<td style="padding:10px 14px;border:1px solid #E2E8F0;border-radius:8px">'
        f'<div style="font-size:11px;color:#64748b;font-weight:600">{k}</div>'
        f'<div style="font-size:18px;font-weight:800;color:#0F172A">{v}</div></td>'
        for k, v in kpis)
    pt_rows = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #F1F5F9;font-weight:600">{r["key"]}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9">{r["runs"]}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9">{_pct(r["success_rate"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9">{_pct(r["hint_pass_rate"])}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9">{r["feedback_up"]}↑ {r["feedback_down"]}↓</td></tr>'
        for r in (s.get("by_page_type") or []))
    fail_rows = "".join(
        f'<tr><td style="padding:6px 10px;border-bottom:1px solid #F1F5F9">{f["page_type"] or "(unclassified)"}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9;color:#DC2626">{(f["error"] or "(no message)")[:120]}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #F1F5F9;font-weight:700">{f["count"]}</td></tr>'
        for f in fails) or '<tr><td colspan="3" style="padding:8px 10px;color:#059669">No failures 🎉</td></tr>'
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:640px;margin:0 auto;color:#1f2937">
  <h2 style="color:#5E35B1;margin-bottom:2px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Leaders' Operating System — Powered by AI</p>
  <h3 style="margin:16px 0 4px">Import Analytics Digest — last {days} days</h3>
  <table cellspacing="6" style="border-collapse:separate;margin:10px 0"><tr>{kpi_cells}</tr></table>
  <h4 style="margin:18px 0 6px;color:#0F172A">By page type</h4>
  <table style="border-collapse:collapse;width:100%;font-size:13px">
    <tr style="color:#64748b;font-size:11px;text-align:left">
      <th style="padding:6px 10px">Page type</th><th style="padding:6px 10px">Runs</th>
      <th style="padding:6px 10px">Success</th><th style="padding:6px 10px">Hint pass</th>
      <th style="padding:6px 10px">👍/👎</th></tr>
    {pt_rows or '<tr><td colspan="5" style="padding:8px 10px;color:#64748b">No runs this window.</td></tr>'}
  </table>
  <h4 style="margin:18px 0 6px;color:#0F172A">Top failures</h4>
  <table style="border-collapse:collapse;width:100%;font-size:13px">
    <tr style="color:#64748b;font-size:11px;text-align:left">
      <th style="padding:6px 10px">Page type</th><th style="padding:6px 10px">Error</th>
      <th style="padding:6px 10px">Count</th></tr>
    {fail_rows}
  </table>
  <a href="{PUBLIC_APP_URL}/admin/import-analytics" style="display:inline-block;margin-top:16px;background:#5E35B1;color:#fff;
     text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:700">Open Import Analytics</a>
  <p style="color:#94a3b8;font-size:12px;margin-top:18px">Automated digest from the JELCOS AI Notification Engine.</p>
</div>"""


async def _top_failures(days: int) -> List[Dict[str, Any]]:
    since = _now() - timedelta(days=days)
    rows = await db.url_import_runs.aggregate([
        {"$match": {"ts": {"$gte": since}, "status": {"$ne": "success"}}},
        {"$group": {"_id": {"page_type": "$page_type", "error": "$error"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 5},
    ]).to_list(5)
    return [{"page_type": r["_id"].get("page_type"), "error": r["_id"].get("error"),
             "count": r["count"]} for r in rows]


async def build_import_analytics_digest(trigger: Dict[str, Any],
                                        event_payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Weekly Import-URL Intelligence digest (summary + breakdowns + failures)."""
    from core import url_telemetry  # local import — avoids cycle (telemetry emits events)
    days = 7
    s = await url_telemetry.summary(days=days)
    fails = await _top_failures(days)
    fb = s.get("feedback") or {}
    top_pt = (s.get("by_page_type") or [{}])[0].get("key", "—") if s.get("by_page_type") else "—"
    sat = "—" if fb.get("satisfaction") is None else f"{fb['satisfaction']}%"
    wa_text = (
        f"📊 *JELCOS AI — Import Analytics* (last {days}d)\n"
        f"Runs: {s.get('total_runs', 0)} · Success: {_pct(s.get('success_rate'))}\n"
        f"👍 Satisfaction: {sat} ({fb.get('up', 0)}↑ {fb.get('down', 0)}↓)\n"
        f"Top page type: {top_pt} · Failures: {sum(f['count'] for f in fails)}\n"
        f"Details: {PUBLIC_APP_URL}/admin/import-analytics"
    )
    return {"subject": f"JELCOS AI · Import Analytics weekly digest — {s.get('total_runs', 0)} runs, "
                       f"{_pct(s.get('success_rate'))} success",
            "email_html": _digest_html(s, fails, days),
            "wa_text": wa_text}


async def build_import_run_failed(trigger: Dict[str, Any],
                                  event_payload: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Instant alert when an Import-from-URL run fails."""
    p = event_payload or {}
    url = p.get("url") or "(unknown url)"
    err = (p.get("error") or "(no error message)")[:300]
    pt = p.get("page_type") or "(unclassified)"
    lines = [f"<b>URL:</b> {url}", f"<b>Page type:</b> {pt}",
             f"<b>Endpoint:</b> {p.get('endpoint') or '—'}", f"<b>Error:</b> {err}"]
    body = "".join(f'<p style="margin:8px 0;color:#374151">{ln}</p>' for ln in lines)
    html = f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#5E35B1;margin-bottom:2px">JELCOS AI</h2>
  <h3 style="margin:16px 0 6px;color:#DC2626">⚠ Import-from-URL run failed</h3>
  {body}
  <a href="{PUBLIC_APP_URL}/admin/import-analytics" style="display:inline-block;margin-top:14px;background:#5E35B1;color:#fff;
     text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:700">Open Import Analytics</a>
</div>"""
    wa_text = (f"⚠ *JELCOS AI — Import run FAILED*\nURL: {url}\nPage type: {pt}\nError: {err[:150]}\n"
               f"Details: {PUBLIC_APP_URL}/admin/import-analytics")
    return {"subject": "JELCOS AI · ⚠ Import-from-URL run failed", "email_html": html, "wa_text": wa_text}


# ─────────────────────────────────────────────────────────────────────────────
# Trigger-event registry — the catalogue admins pick from when creating triggers
# ─────────────────────────────────────────────────────────────────────────────
EVENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "import-analytics": {
        "name": "Import Analytics Digest",
        "description": "Periodic Import-from-URL intelligence digest: runs, success %, "
                       "hint pass, per-page-type breakdown, top failures, 👍/👎 feedback (last 7 days).",
        "kind": "scheduled",
        "default_schedule": {"frequency": "weekly", "day_of_week": "mon",
                             "hour": 9, "minute": 0, "timezone": "Asia/Kolkata"},
        "builder": build_import_analytics_digest,
        "sample_payload": None,
    },
    "import-run-failed": {
        "name": "Import Run Failure Alert",
        "description": "Instant alert fired whenever an Import-from-URL run errors out "
                       "(throttled per trigger to avoid spam).",
        "kind": "event",
        "default_schedule": None,
        "builder": build_import_run_failed,
        "sample_payload": {"url": "https://example.com/compare", "error": "Sample: extraction timeout",
                           "page_type": "comparison_matrix", "endpoint": "import"},
    },
}


def registry_public() -> List[Dict[str, Any]]:
    """Registry view safe for the API (no builder callables)."""
    return [{"key": k, "name": v["name"], "description": v["description"],
             "kind": v["kind"], "default_schedule": v["default_schedule"]}
            for k, v in EVENT_REGISTRY.items()]


# ─────────────────────────────────────────────────────────────────────────────
# Schedule math
# ─────────────────────────────────────────────────────────────────────────────

def compute_next_run(schedule: Dict[str, Any], after: Optional[datetime] = None) -> datetime:
    """Next UTC datetime this schedule fires strictly after ``after`` (default now)."""
    tz = ZoneInfo(schedule.get("timezone") or "Asia/Kolkata")
    now_local = (_as_utc(after) or _now()).astimezone(tz)
    hh = int(schedule.get("hour", 9))
    mm = int(schedule.get("minute", 0))
    freq = schedule.get("frequency", "weekly")
    cand = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if freq == "daily":
        if cand <= now_local:
            cand += timedelta(days=1)
    elif freq == "weekly":
        target = DAYS.index(schedule.get("day_of_week", "mon"))
        cand += timedelta(days=(target - cand.weekday()) % 7)
        if cand <= now_local:
            cand += timedelta(days=7)
    else:  # monthly
        dom = min(max(int(schedule.get("day_of_month", 1)), 1), 28)
        cand = cand.replace(day=dom)
        if cand <= now_local:
            month, year = (1, cand.year + 1) if cand.month == 12 else (cand.month + 1, cand.year)
            cand = cand.replace(year=year, month=month)
    return cand.astimezone(timezone.utc)


def schedule_label(schedule: Optional[Dict[str, Any]]) -> str:
    if not schedule:
        return "On event"
    hh, mm = int(schedule.get("hour", 9)), int(schedule.get("minute", 0))
    t = f"{hh:02d}:{mm:02d} {schedule.get('timezone', 'Asia/Kolkata')}"
    freq = schedule.get("frequency", "weekly")
    if freq == "daily":
        return f"Daily · {t}"
    if freq == "weekly":
        return f"Weekly · {DAY_LABEL.get(schedule.get('day_of_week', 'mon'), 'Monday')} {t}"
    return f"Monthly · day {schedule.get('day_of_month', 1)} · {t}"


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch — run a trigger once (scheduled tick / event emit / admin test)
# ─────────────────────────────────────────────────────────────────────────────

async def run_trigger(trigger: Dict[str, Any], run_kind: str = "scheduled",
                      event_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the payload + fan out to enabled channels. Logs a notification_run.

    run_kind: "scheduled" | "event" | "test". Never raises.
    """
    entry = EVENT_REGISTRY.get(trigger.get("event_key"))
    now = _now()
    run_doc: Dict[str, Any] = {
        "id": uuid.uuid4().hex, "trigger_id": trigger.get("id"),
        "event_key": trigger.get("event_key"), "trigger_name": trigger.get("name"),
        "ts": now, "run_kind": run_kind, "status": "error", "error": None,
        "report": {"email": {"attempted": 0, "sent": 0, "recipients": []},
                   "whatsapp": {"attempted": 0, "sent": 0, "numbers": []}},
    }
    try:
        if not entry:
            raise ValueError(f"Unknown event_key '{trigger.get('event_key')}'")
        if run_kind == "test" and entry["kind"] == "event" and event_payload is None:
            event_payload = entry.get("sample_payload")
        payload = await entry["builder"](trigger, event_payload)

        ch = trigger.get("channels") or {}
        email_cfg = ch.get("email") or {}
        wa_cfg = ch.get("whatsapp") or {}
        recipients = [r for r in (email_cfg.get("recipients") or []) if r] if email_cfg.get("enabled") else []
        numbers = [n for n in (wa_cfg.get("numbers") or []) if n] if wa_cfg.get("enabled") else []

        if not recipients and not numbers:
            run_doc["status"] = "skipped_no_recipients"
        else:
            sent_any = False
            for r in recipients:
                ok = await send_email(r, payload["subject"], payload["email_html"])
                run_doc["report"]["email"]["attempted"] += 1
                run_doc["report"]["email"]["sent"] += int(ok)
                run_doc["report"]["email"]["recipients"].append({"to": r, "sent": ok})
                sent_any = sent_any or ok
            for n in numbers:
                ok = await send_whatsapp(n, payload["wa_text"])
                run_doc["report"]["whatsapp"]["attempted"] += 1
                run_doc["report"]["whatsapp"]["sent"] += int(ok)
                run_doc["report"]["whatsapp"]["numbers"].append({"to": n, "sent": ok})
                sent_any = sent_any or ok
            run_doc["status"] = "sent" if sent_any else "failed"
        run_doc["subject"] = payload.get("subject")
    except Exception as e:  # noqa: BLE001 — engine must never break callers
        run_doc["error"] = str(e)[:300]
        logger.warning("notification run failed (trigger=%s): %s", trigger.get("id"), str(e)[:200])

    try:
        await db.notification_runs.insert_one(dict(run_doc))
        updates: Dict[str, Any] = {"last_run_at": now, "last_status": run_doc["status"]}
        if trigger.get("kind") == "scheduled" and trigger.get("schedule") and run_kind == "scheduled":
            updates["next_run_at"] = compute_next_run(trigger["schedule"], after=now)
        if run_kind != "test":
            await db.notification_triggers.update_one({"id": trigger["id"]}, {"$set": updates})
        # lazy prune: keep newest 500 runs
        total = await db.notification_runs.estimated_document_count()
        if total > 600:
            cutoff_rows = await (db.notification_runs.find({}, {"ts": 1})
                                 .sort("ts", -1).skip(500).limit(1).to_list(1))
            if cutoff_rows:
                await db.notification_runs.delete_many({"ts": {"$lt": cutoff_rows[0]["ts"]}})
    except Exception as e:  # noqa: BLE001
        logger.warning("notification run-log persist failed: %s", str(e)[:200])
    run_doc.pop("_id", None)
    return run_doc


async def emit_event(event_key: str, payload: Optional[Dict[str, Any]] = None) -> int:
    """Fire all enabled event-kind triggers for ``event_key`` (throttled).

    Returns number of triggers dispatched. Best-effort — never raises.
    """
    dispatched = 0
    try:
        if EVENT_REGISTRY.get(event_key, {}).get("kind") != "event":
            return 0
        now = _now()
        cursor = db.notification_triggers.find(
            {"event_key": event_key, "kind": "event", "enabled": True}, {"_id": 0})
        async for trig in cursor:
            throttle = int(trig.get("throttle_minutes") or 60)
            last = _as_utc(trig.get("last_run_at"))
            if last and (now - last) < timedelta(minutes=throttle):
                continue
            await run_trigger(trig, run_kind="event", event_payload=payload)
            dispatched += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("emit_event(%s) failed: %s", event_key, str(e)[:200])
    return dispatched


def emit_event_bg(event_key: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Fire-and-forget wrapper safe to call from request handlers."""
    try:
        asyncio.get_running_loop().create_task(emit_event(event_key, payload))
    except RuntimeError:  # no running loop (sync/test context)
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler — 60s tick fires due scheduled triggers
# ─────────────────────────────────────────────────────────────────────────────
_scheduler: Optional[AsyncIOScheduler] = None
_lock_fd = None


async def tick() -> int:
    """Run every scheduled+enabled trigger whose next_run_at is due. Returns count run."""
    ran = 0
    now = _now()
    try:
        cursor = db.notification_triggers.find(
            {"kind": "scheduled", "enabled": True}, {"_id": 0})
        async for trig in cursor:
            nxt = _as_utc(trig.get("next_run_at"))
            if nxt is None and trig.get("schedule"):
                # self-heal: compute + persist, don't fire immediately
                await db.notification_triggers.update_one(
                    {"id": trig["id"]},
                    {"$set": {"next_run_at": compute_next_run(trig["schedule"])}})
                continue
            if nxt and nxt <= now:
                await run_trigger(trig, run_kind="scheduled")
                ran += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("notification tick failed: %s", str(e)[:200])
    return ran


def _try_acquire_singleton_lock() -> bool:
    global _lock_fd
    try:
        import fcntl
    except ImportError:  # pragma: no cover
        return True
    lock_path = os.environ.get("NOTIFICATION_SCHEDULER_LOCK",
                               "/tmp/dezider_notification_scheduler.lock")
    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except (BlockingIOError, OSError):
        if _lock_fd is not None:
            try:
                _lock_fd.close()
            except Exception:
                pass
            _lock_fd = None
        return False


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if os.environ.get("NOTIFICATION_SCHEDULER_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("Notification scheduler disabled via env")
        return
    if not _try_acquire_singleton_lock():
        logger.info("Notification scheduler lock held by another worker; skipping")
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(tick, IntervalTrigger(seconds=60), id="notification_tick",
                       replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("Notification engine scheduler started (60s tick) pid=%s", os.getpid())


def stop_scheduler() -> None:
    global _scheduler, _lock_fd
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    if _lock_fd is not None:
        try:
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None


# ─────────────────────────────────────────────────────────────────────────────
# Boot seed — idempotent default trigger: weekly import-analytics digest
# ─────────────────────────────────────────────────────────────────────────────

async def seed_default_triggers() -> bool:
    """Create the default weekly import-analytics digest trigger once. Idempotent."""
    if await db.notification_triggers.count_documents({"event_key": "import-analytics"}) > 0:
        return False
    entry = EVENT_REGISTRY["import-analytics"]
    schedule = dict(entry["default_schedule"])
    now = _now()
    await db.notification_triggers.insert_one({
        "id": uuid.uuid4().hex,
        "event_key": "import-analytics",
        "name": "Weekly Import Analytics Digest",
        "description": entry["description"],
        "kind": "scheduled",
        "enabled": True,
        "schedule": schedule,
        "channels": {"email": {"enabled": True, "recipients": []},
                     "whatsapp": {"enabled": False, "numbers": []}},
        "throttle_minutes": None,
        "created_at": now, "updated_at": now, "created_by": "system-seed",
        "last_run_at": None, "last_status": None,
        "next_run_at": compute_next_run(schedule),
    })
    logger.info("Notification engine: seeded default weekly import-analytics digest trigger")
    return True
