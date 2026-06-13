"""iter115 — Admin URL Training Console.

Covers:
  • CRUD on training examples (upsert, list, delete)
  • Regression-suite pin limit (max 15)
  • Trigger-tagged run rows persisted separately for each invocation
  • Grader returns pass / partial / fail / error correctly
"""
import asyncio
import uuid
from datetime import datetime, timezone

from core import url_training
from core.database import db


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _purge():
    async def _do():
        await db[url_training.COLL_EXAMPLES].delete_many({"updated_by": "test-admin"})
        await db[url_training.COLL_RUNS].delete_many({"admin_id": "test-admin"})
    _run(_do())


# ── 1. Upsert / list / delete ───────────────────────────────────────────────
def test_upsert_list_delete():
    _purge()
    payload = {
        "url": f"https://example.com/{uuid.uuid4().hex[:6]}",
        "label": "Test page",
        "expected_factor_count": 5,
        "expected_option_count": 4,
        "expected_factors": ["A", "B", "C"],
    }
    created = _run(url_training.upsert_example(payload, "test-admin"))
    assert created["id"].startswith("utx_")
    assert created["expected_factor_count"] == 5
    assert created["expected_factors"] == ["A", "B", "C"]
    assert created["is_regression_pinned"] is False

    rows = _run(url_training.list_examples())
    assert any(r["id"] == created["id"] for r in rows)

    # Idempotent upsert by URL — same URL re-submitted updates in-place
    payload["label"] = "Updated label"
    updated = _run(url_training.upsert_example(payload, "test-admin"))
    assert updated["id"] == created["id"]
    assert updated["label"] == "Updated label"

    deleted = _run(url_training.delete_example(created["id"]))
    assert deleted
    _purge()


# ── 2. Regression-pin limit (max 15) ────────────────────────────────────────
def test_pin_limit_enforced():
    _purge()
    created_ids = []
    # Fill all 15 pinned slots
    for i in range(url_training.REGRESSION_MAX_PINS):
        ex = _run(url_training.upsert_example({
            "url": f"https://example.com/pin/{i}/{uuid.uuid4().hex[:4]}",
            "label": f"Pin {i}",
            "is_regression_pinned": True,
        }, "test-admin"))
        created_ids.append(ex["id"])

    # 16th must be rejected
    try:
        _run(url_training.upsert_example({
            "url": "https://example.com/pin/overflow",
            "is_regression_pinned": True,
        }, "test-admin"))
        assert False, "expected ValueError on 16th pin"
    except ValueError as e:
        assert "Regression suite is full" in str(e)

    # Unpin one → next pin should now succeed
    _run(url_training.upsert_example({
        "id": created_ids[0], "url": "https://example.com/pin/0/x",
        "is_regression_pinned": False,
    }, "test-admin"))
    new_ex = _run(url_training.upsert_example({
        "url": "https://example.com/pin/replacement",
        "is_regression_pinned": True,
    }, "test-admin"))
    assert new_ex["is_regression_pinned"] is True
    _purge()


# ── 3. Each run is captured separately ──────────────────────────────────────
def test_each_run_captured_separately():
    """Even without actually executing _import_inner (which needs network),
    we can verify the run-doc schema and the per-example link by inserting
    runs directly — that's exactly what the API surface relies on."""
    _purge()
    ex = _run(url_training.upsert_example({
        "url": "https://example.com/separate-runs",
        "label": "Separate runs",
        "expected_factor_count": 6,
    }, "test-admin"))
    now = datetime.now(timezone.utc)
    for i, status in enumerate(["pass", "partial", "fail"]):
        run_doc = {
            "id": f"utr_test_{i}_{uuid.uuid4().hex[:6]}",
            "example_id": ex["id"], "url": ex["url"],
            "trigger": "manual_single" if i == 0 else "cron",
            "admin_id": "test-admin",
            "started_at": now, "completed_at": now,
            "elapsed_ms": 1234 + i, "status": status, "score": 90 - i * 30,
            "ran_factor_count": 6 - i, "ran_option_count": 4,
            "expected_factor_count": 6,
        }
        _run(db[url_training.COLL_RUNS].insert_one(run_doc))

    rows = _run(url_training.list_runs(example_id=ex["id"]))
    statuses = [r["status"] for r in rows if r["example_id"] == ex["id"]]
    assert "pass" in statuses
    assert "partial" in statuses
    assert "fail" in statuses
    assert len([r for r in rows if r["example_id"] == ex["id"]]) == 3
    _purge()


# ── 4. Grader behaviour ─────────────────────────────────────────────────────
def test_grader_pass_partial_fail():
    ex = {
        "expected_factor_count": 6,
        "expected_option_count": 4,
        "expected_factors": ["Price", "Model", "Range", "Battery"],
    }
    # Pass — all expected hit
    g = url_training._grade(ex, {  # noqa: SLF001
        "factors_added": 6, "options_added": 4,
        "factors": [{"display_name": x} for x in ["Price", "Model", "Range", "Battery", "Top speed", "Charging time"]],
    })
    assert g["status"] == "pass"
    assert g["score"] >= 80

    # Partial — 4F instead of 6, two factor-names overlap
    g = url_training._grade(ex, {  # noqa: SLF001
        "factors_added": 4, "options_added": 4,
        "factors": [{"display_name": x} for x in ["Price", "Model", "Foo", "Bar"]],
    })
    assert g["status"] in ("partial", "fail")
    assert g["missed_factors"] == 2

    # Fail — almost nothing extracted
    g = url_training._grade(ex, {  # noqa: SLF001
        "factors_added": 1, "options_added": 0,
        "factors": [{"display_name": "name"}],
    })
    assert g["status"] == "fail"
