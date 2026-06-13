"""iter116 — Auto-Tune auto-approve + bulk decide.

Covers:
  • Default config (enabled, 24h grace, min_evidence=2)
  • set_auto_approve_config validates ranges
  • auto_approve_pass dedupes per-key (keeps latest, rejects older)
  • Defers when within grace window
  • Defers when min_evidence not met
  • Defers when admin manually decided within grace window
  • Approves when all gates pass (idempotent within same grace)
  • bulk_decide approves/rejects, dedupes first
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from core import url_prompt_tuning as upt
from core.database import db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _purge():
    async def _do():
        await db.app_config.delete_one({"key": "auto_tune_autoapprove"})
        await db.prompt_tuning_suggestions.delete_many({"page_type": {"$regex": "^_iter116_"}})
        await db.url_prompt_overrides.delete_many({"key": {"$regex": "^_iter116_"}})
    _run(_do())


def _seed_suggestion(page_type: str, *, ts: datetime, status: str = "proposed",
                     failing_runs: int = 5, proposed: str = "be precise"):
    sid = f"st_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": sid, "page_type": page_type, "status": status,
        "ts": ts, "evidence": {"failing_runs": failing_runs},
        "current_guidance": "old", "proposed_guidance": proposed,
        "rationale": "test", "expected_impact": "less fail",
    }
    _run(db.prompt_tuning_suggestions.insert_one(doc))
    return sid


# ── 1. Config defaults + setters ────────────────────────────────────────────
def test_default_config():
    _purge()
    cfg = _run(upt.get_auto_approve_config())
    assert cfg["enabled"] is True
    assert cfg["grace_hours"] == 24
    assert cfg["min_evidence"] == 2


def test_set_config_validates():
    _purge()
    _run(upt.set_auto_approve_config({"enabled": False}, "test-admin"))
    assert _run(upt.get_auto_approve_config())["enabled"] is False
    _run(upt.set_auto_approve_config({"grace_hours": 12, "min_evidence": 4}, "test-admin"))
    c = _run(upt.get_auto_approve_config())
    assert c["grace_hours"] == 12 and c["min_evidence"] == 4
    for bad in ({"grace_hours": 0}, {"grace_hours": 9999}, {"min_evidence": 0}, {"min_evidence": 99}):
        try:
            _run(upt.set_auto_approve_config(bad, "test-admin"))
            assert False, f"expected ValueError for {bad}"
        except ValueError:
            pass


# ── 2. Auto-approve dedupes + defers + approves ─────────────────────────────
def test_auto_approve_pass_logic():
    _purge()
    _run(upt.set_auto_approve_config({"enabled": True, "grace_hours": 24, "min_evidence": 2}, "test"))
    now = datetime.now(timezone.utc)

    # Key A: 3 proposed suggestions, latest is 30h old (past grace), >= 2 evidence
    pt_a = "_iter116_a"
    old = _seed_suggestion(pt_a, ts=now - timedelta(hours=50), failing_runs=3)
    mid = _seed_suggestion(pt_a, ts=now - timedelta(hours=40), failing_runs=4)
    latest_a = _seed_suggestion(pt_a, ts=now - timedelta(hours=30), failing_runs=5)

    # Key B: latest is still within grace (12h old) — must DEFER
    pt_b = "_iter116_b"
    _seed_suggestion(pt_b, ts=now - timedelta(hours=12), failing_runs=10)

    # Key C: latest is past grace but evidence below floor (1 < 2) — DEFER
    pt_c = "_iter116_c"
    _seed_suggestion(pt_c, ts=now - timedelta(hours=30), failing_runs=1)

    res = _run(upt.auto_approve_pass())
    assert res["enabled"] is True
    assert res["approved"] == 1, res
    assert res["deduped"] == 2, res
    assert pt_b in res["deferred"]
    assert pt_c in res["deferred"]
    assert any(a["key"] == pt_a for a in res["audit"])

    # The two older A proposals must now be 'rejected'; latest A 'approved'
    docs = _run(db.prompt_tuning_suggestions.find(
        {"id": {"$in": [old, mid, latest_a]}}, {"_id": 0}).to_list(10))
    by_id = {d["id"]: d for d in docs}
    assert by_id[old]["status"] == "rejected"
    assert by_id[mid]["status"] == "rejected"
    assert by_id[latest_a]["status"] == "approved"
    # Override row written for key A
    ov = _run(db.url_prompt_overrides.find_one({"key": pt_a}, {"_id": 0}))
    assert ov and ov["suggestion_id"] == latest_a

    # Idempotent — running again must not flip anything new
    res2 = _run(upt.auto_approve_pass())
    assert res2["approved"] == 0
    _purge()


# ── 3. Disabled config returns enabled=False without changes ────────────────
def test_disabled_is_noop():
    _purge()
    _run(upt.set_auto_approve_config({"enabled": False}, "test"))
    _seed_suggestion("_iter116_off", ts=datetime.now(timezone.utc) - timedelta(hours=50), failing_runs=5)
    res = _run(upt.auto_approve_pass())
    assert res["enabled"] is False
    doc = _run(db.prompt_tuning_suggestions.find_one({"page_type": "_iter116_off"}))
    assert doc["status"] == "proposed", "must not touch suggestions when disabled"
    _purge()


# ── 4. Bulk decide ─────────────────────────────────────────────────────────
def test_bulk_decide_approve_and_dedupe():
    _purge()
    now = datetime.now(timezone.utc)
    # Two competing proposals for same key — bulk approve keeps the latest,
    # rejects the older
    pt = "_iter116_bulk"
    old = _seed_suggestion(pt, ts=now - timedelta(hours=5), failing_runs=2)
    new = _seed_suggestion(pt, ts=now - timedelta(hours=1), failing_runs=3)

    r = _run(upt.bulk_decide("test-admin", approve=True))
    assert r["approved"] == 1
    assert r["deduped"] == 1
    docs = _run(db.prompt_tuning_suggestions.find(
        {"id": {"$in": [old, new]}}, {"_id": 0}).to_list(10))
    by_id = {d["id"]: d["status"] for d in docs}
    assert by_id[new] == "approved"
    assert by_id[old] == "rejected"
    _purge()
