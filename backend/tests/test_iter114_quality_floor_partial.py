"""iter114 — Quality-floor partial-status guard for URL imports.

Reproduces the carwale.com regression (Jun 2026): the deterministic flat
parser produced 2 factors (Name + Price), and the system silently stamped
the run as `success`. After the fix, runs with fewer than the admin-tunable
quality floor MUST be stamped `partial`, recorded with a `partial_reason`,
and surfaced via the analytics summary + Auto-Tune candidate pool.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import engine_recos, url_telemetry, url_prompt_tuning  # noqa: E402
from core.database import db  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _purge():
    await db.url_import_runs.delete_many({"endpoint": "import-iter114"})
    await db.app_config.delete_one({"key": "import_quality_floor"})


# ── 1. Quality-floor config ─────────────────────────────────────────────────
def test_default_quality_floor_is_four():
    _run(_purge())
    assert _run(engine_recos.get_quality_floor()) == engine_recos.DEFAULT_QUALITY_FLOOR
    assert engine_recos.DEFAULT_QUALITY_FLOOR == 4


def test_admin_can_tune_floor_and_invalid_rejected():
    _run(_purge())
    assert _run(engine_recos.set_quality_floor(6, "test-admin")) == 6
    assert _run(engine_recos.get_quality_floor()) == 6
    try:
        _run(engine_recos.set_quality_floor(0, "test-admin"))
        assert False, "expected ValueError for 0"
    except ValueError:
        pass
    try:
        _run(engine_recos.set_quality_floor(99, "test-admin"))
        assert False, "expected ValueError for 99"
    except ValueError:
        pass


# ── 2. Partial status taxonomy ──────────────────────────────────────────────
def test_partial_status_recorded_with_reason():
    """A 2F/4O run on the quality floor (4) must store status=partial and
    persist BOTH the response counts (so the user sees what they got) and
    the partial_reason (so admin Intel can render it)."""
    _run(_purge())
    _run(engine_recos.set_quality_floor(4, "test-admin"))
    user_id = f"u_iter114_{uuid.uuid4().hex[:6]}"
    tel = url_telemetry.new_tel(user_id, endpoint="import-iter114",
                                url="https://www.carwale.com/new/best-Electric-cars-under-10-lakh/",
                                ai_tier="fast", hints=None)
    tel["route"] = "deterministic_flat"
    reason = ("Extracted 2 factor(s) across 4 option(s) — below the "
              "configured quality floor of 4.")
    run_id = _run(url_telemetry.record_run(
        tel, status="partial",
        response={"item_count": 4, "factors_added": 2, "options_added": 4, "mode": "flat"},
        error=reason))

    doc = _run(db.url_import_runs.find_one({"id": run_id}))
    assert doc is not None
    assert doc["status"] == "partial"
    assert doc["partial_reason"] == reason
    assert doc["factors_added"] == 2
    assert doc["options_added"] == 4
    assert doc["route"] == "deterministic_flat"


# ── 3. Failure-alert isolation ──────────────────────────────────────────────
def test_partial_does_not_trigger_failure_alert(monkeypatch):
    """The Notification Engine failure alert (`import-run-failed`) must fire
    only on hard `error`. Partial runs go into Auto-Tune, not user inbox."""
    _run(_purge())
    user_id = f"u_iter114_{uuid.uuid4().hex[:6]}"

    fired = {"events": []}

    def _fake_emit(event, payload):
        fired["events"].append((event, payload))

    import core.notification_engine as ne
    monkeypatch.setattr(ne, "emit_event_bg", _fake_emit)

    # Partial → no alert
    tel = url_telemetry.new_tel(user_id, endpoint="import-iter114",
                                url="https://example.com/", ai_tier="fast", hints=None)
    _run(url_telemetry.record_run(
        tel, status="partial",
        response={"factors_added": 2, "options_added": 4}, error="thin"))
    assert not fired["events"], f"partial must not fire alert: {fired['events']}"

    # Error → alert
    tel2 = url_telemetry.new_tel(user_id, endpoint="import-iter114",
                                 url="https://example.com/x", ai_tier="fast", hints=None)
    _run(url_telemetry.record_run(tel2, status="error", error="boom"))
    assert any(e[0] == "import-run-failed" for e in fired["events"]), \
        f"hard error must fire alert: {fired['events']}"


# ── 4. Auto-Tune picks up partial as a failing candidate ────────────────────
def test_partial_run_visible_to_auto_tune():
    """url_prompt_tuning._failing_runs must include partial runs so silent
    under-extractions surface in the prompt-tuning candidate pool."""
    _run(_purge())
    user_id = f"u_iter114_{uuid.uuid4().hex[:6]}"

    tel = url_telemetry.new_tel(user_id, endpoint="import-iter114",
                                url="https://example.com/listing", ai_tier="fast", hints=None)
    tel["page_type"] = "listing_filter"
    tel["route"] = "deterministic_flat"
    _run(url_telemetry.record_run(
        tel, status="partial",
        response={"factors_added": 2, "options_added": 4},
        error="thin parse — below quality floor 4"))

    rows = _run(url_prompt_tuning._failing_runs("listing_filter", days=30))  # noqa: SLF001
    iter114_rows = [r for r in rows if str(r.get("url", "")).endswith("/listing")]
    assert iter114_rows, "expected at least one iter114 run in failing-runs pool"
    assert any(r.get("status") == "partial" for r in iter114_rows), \
        f"partial run missing from pool: {[r.get('status') for r in iter114_rows]}"

    _run(_purge())
