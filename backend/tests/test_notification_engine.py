"""Regression tests for the generic Notification Engine (v3.18.0).

Covers: trigger-event registry sanity, schedule math (daily/weekly/monthly,
IST→UTC), idempotent boot seed, dispatch statuses (skipped_no_recipients),
event-emit throttling, and both payload builders (digest + failure alert).
Run: cd /app/backend && python -m pytest tests/test_notification_engine.py -q
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "/app/backend")

from core import notification_engine as ne  # noqa: E402
from core.database import db  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestRegistry:
    def test_first_trigger_event_is_import_analytics(self):
        assert "import-analytics" in ne.EVENT_REGISTRY
        assert ne.EVENT_REGISTRY["import-analytics"]["kind"] == "scheduled"
        ds = ne.EVENT_REGISTRY["import-analytics"]["default_schedule"]
        assert (ds["frequency"], ds["day_of_week"], ds["hour"], ds["minute"]) == ("weekly", "mon", 9, 0)
        assert ds["timezone"] == "Asia/Kolkata"

    def test_event_kind_trigger_registered(self):
        assert ne.EVENT_REGISTRY["import-run-failed"]["kind"] == "event"
        assert ne.EVENT_REGISTRY["import-run-failed"]["sample_payload"]

    def test_registry_public_has_no_callables(self):
        for row in ne.registry_public():
            assert set(row) == {"key", "name", "description", "kind", "default_schedule"}


class TestComputeNextRun:
    def test_weekly_monday_9am_ist_is_0330_utc(self):
        # Friday 2026-06-12 12:00 UTC → next Monday 2026-06-15 09:00 IST = 03:30 UTC
        after = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
        nxt = ne.compute_next_run(
            {"frequency": "weekly", "day_of_week": "mon", "hour": 9, "minute": 0,
             "timezone": "Asia/Kolkata"}, after=after)
        assert nxt == datetime(2026, 6, 15, 3, 30, tzinfo=timezone.utc)

    def test_weekly_same_day_past_time_rolls_a_week(self):
        # Monday 10:00 IST (04:30 UTC) → 9:00 already passed → next Monday
        after = datetime(2026, 6, 15, 4, 30, tzinfo=timezone.utc)
        nxt = ne.compute_next_run(
            {"frequency": "weekly", "day_of_week": "mon", "hour": 9, "minute": 0,
             "timezone": "Asia/Kolkata"}, after=after)
        assert nxt == datetime(2026, 6, 22, 3, 30, tzinfo=timezone.utc)

    def test_daily_rolls_to_tomorrow(self):
        after = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)  # 17:30 IST
        nxt = ne.compute_next_run(
            {"frequency": "daily", "hour": 9, "minute": 0, "timezone": "Asia/Kolkata"},
            after=after)
        assert nxt == datetime(2026, 6, 13, 3, 30, tzinfo=timezone.utc)

    def test_monthly_clamps_and_rolls(self):
        after = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)
        nxt = ne.compute_next_run(
            {"frequency": "monthly", "day_of_month": 1, "hour": 9, "minute": 0,
             "timezone": "Asia/Kolkata"}, after=after)
        assert nxt == datetime(2026, 7, 1, 3, 30, tzinfo=timezone.utc)

    def test_schedule_label(self):
        assert ne.schedule_label({"frequency": "weekly", "day_of_week": "mon",
                                  "hour": 9, "minute": 0, "timezone": "Asia/Kolkata"}) \
            == "Weekly · Monday 09:00 Asia/Kolkata"
        assert ne.schedule_label(None) == "On event"


class TestSeed:
    def test_seed_is_idempotent(self):
        async def flow():
            await ne.seed_default_triggers()  # may or may not create (env-dependent)
            n1 = await db.notification_triggers.count_documents({"event_key": "import-analytics"})
            created_again = await ne.seed_default_triggers()
            n2 = await db.notification_triggers.count_documents({"event_key": "import-analytics"})
            return n1, created_again, n2
        n1, created_again, n2 = _run(flow())
        assert n1 >= 1
        assert created_again is False
        assert n2 == n1


def _temp_trigger(kind="scheduled", event_key="import-analytics", **over):
    t = {
        "id": f"test-{uuid.uuid4().hex[:10]}",
        "event_key": event_key, "name": "pytest temp", "description": "",
        "kind": kind, "enabled": True,
        "schedule": ({"frequency": "weekly", "day_of_week": "mon", "hour": 9,
                      "minute": 0, "timezone": "Asia/Kolkata"} if kind == "scheduled" else None),
        "channels": {"email": {"enabled": True, "recipients": []},
                     "whatsapp": {"enabled": False, "numbers": []}},
        "throttle_minutes": 60 if kind == "event" else None,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "created_by": "pytest", "last_run_at": None, "last_status": None, "next_run_at": None,
    }
    t.update(over)
    return t


class TestDispatch:
    def test_run_trigger_no_recipients_skips_and_logs(self):
        trig = _temp_trigger()
        async def flow():
            run = await ne.run_trigger(trig, run_kind="test")
            logged = await db.notification_runs.find_one({"trigger_id": trig["id"]}, {"_id": 0})
            await db.notification_runs.delete_many({"trigger_id": trig["id"]})
            return run, logged
        run, logged = _run(flow())
        assert run["status"] == "skipped_no_recipients"
        assert logged and logged["status"] == "skipped_no_recipients"
        assert logged["run_kind"] == "test"
        assert "Import Analytics weekly digest" in (run.get("subject") or "")

    def test_run_trigger_unknown_event_key_errors_gracefully(self):
        trig = _temp_trigger(event_key="nope-not-registered")
        async def flow():
            run = await ne.run_trigger(trig, run_kind="test")
            await db.notification_runs.delete_many({"trigger_id": trig["id"]})
            return run
        run = _run(flow())
        assert run["status"] == "error"
        assert "Unknown event_key" in run["error"]


class TestEmitEvent:
    def test_throttled_trigger_is_skipped(self):
        trig = _temp_trigger(kind="event", event_key="import-run-failed",
                             last_run_at=datetime.now(timezone.utc), throttle_minutes=60)
        async def flow():
            await db.notification_triggers.insert_one(dict(trig))
            n = await ne.emit_event("import-run-failed", {"url": "x", "error": "y"})
            await db.notification_triggers.delete_one({"id": trig["id"]})
            await db.notification_runs.delete_many({"trigger_id": trig["id"]})
            return n
        assert _run(flow()) == 0

    def test_unthrottled_trigger_dispatches(self):
        trig = _temp_trigger(kind="event", event_key="import-run-failed",
                             last_run_at=None, throttle_minutes=60)
        async def flow():
            await db.notification_triggers.insert_one(dict(trig))
            n = await ne.emit_event("import-run-failed", {"url": "https://e.com", "error": "boom"})
            logged = await db.notification_runs.find_one({"trigger_id": trig["id"]}, {"_id": 0})
            fresh = await db.notification_triggers.find_one({"id": trig["id"]}, {"_id": 0})
            await db.notification_triggers.delete_one({"id": trig["id"]})
            await db.notification_runs.delete_many({"trigger_id": trig["id"]})
            return n, logged, fresh
        n, logged, fresh = _run(flow())
        assert n == 1
        assert logged["status"] == "skipped_no_recipients"  # no recipients configured
        assert logged["run_kind"] == "event"
        assert fresh["last_run_at"] is not None  # throttle anchor updated

    def test_disabled_trigger_not_dispatched(self):
        trig = _temp_trigger(kind="event", event_key="import-run-failed", enabled=False)
        async def flow():
            await db.notification_triggers.insert_one(dict(trig))
            n = await ne.emit_event("import-run-failed", {"url": "x", "error": "y"})
            await db.notification_triggers.delete_one({"id": trig["id"]})
            return n
        assert _run(flow()) == 0

    def test_scheduled_key_never_event_dispatched(self):
        assert _run(ne.emit_event("import-analytics", {})) == 0


class TestBuilders:
    def test_digest_builder_contents(self):
        out = _run(ne.build_import_analytics_digest(_temp_trigger()))
        assert set(out) == {"subject", "email_html", "wa_text"}
        assert "Import Analytics" in out["subject"]
        assert "By page type" in out["email_html"]
        assert "Top failures" in out["email_html"]
        assert "/admin/import-analytics" in out["wa_text"]

    def test_failure_alert_builder_contents(self):
        out = _run(ne.build_import_run_failed(
            _temp_trigger(kind="event", event_key="import-run-failed"),
            {"url": "https://x.com/a", "error": "timeout!", "page_type": "detail"}))
        assert "failed" in out["subject"].lower()
        assert "https://x.com/a" in out["email_html"]
        assert "timeout!" in out["wa_text"]
