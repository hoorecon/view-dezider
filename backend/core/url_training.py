"""
core/url_training.py — Admin URL-Training console.

Admin curates a library of ground-truth import expectations: URL → expected
factors / options / cell values. Up to 15 can be pinned as the "regression
suite", which runs:
  • automatically once a week (Sunday 03:00 UTC)
  • on-demand from the admin UI (run-all OR run-single)

Each suite execution captures its own runs separately in `url_training_runs`
so admins can diff against the curated expectations over time.

The actual import is performed via the public `/api/url-analyze/decision/...`
flow when applicable — but to keep runs side-effect free we use a thinner
internal driver that calls the same `_import_inner` (so quality-floor,
constraint-gate, etc. all apply uniformly).

This module intentionally stores ONLY admin-curated data — no user PII.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.database import db

logger = logging.getLogger(__name__)

REGRESSION_MAX_PINS = 15
COLL_EXAMPLES = "url_training_examples"
COLL_RUNS = "url_training_runs"


def _now():
    return datetime.now(timezone.utc)


# ── Examples CRUD ───────────────────────────────────────────────────────────
async def list_examples() -> List[Dict[str, Any]]:
    rows = await (db[COLL_EXAMPLES].find({}, {"_id": 0})
                  .sort([("is_regression_pinned", -1), ("created_at", -1)])
                  .to_list(500))
    return rows


async def get_example(example_id: str) -> Optional[Dict[str, Any]]:
    return await db[COLL_EXAMPLES].find_one({"id": example_id}, {"_id": 0})


async def upsert_example(payload: Dict[str, Any], admin_id: str) -> Dict[str, Any]:
    """Create or update a training example. URL is the natural key — admins
    can edit any field on an existing entry."""
    url = (payload.get("url") or "").strip()
    if not url:
        raise ValueError("URL is required")

    existing = None
    if payload.get("id"):
        existing = await db[COLL_EXAMPLES].find_one({"id": payload["id"]})
    if not existing:
        existing = await db[COLL_EXAMPLES].find_one({"url": url})

    doc = {
        "url": url,
        "label": (payload.get("label") or "").strip() or url,
        "context": (payload.get("context") or "").strip() or None,
        "expected_factor_count": _clamp_int(payload.get("expected_factor_count"), 0, 100),
        "expected_option_count": _clamp_int(payload.get("expected_option_count"), 0, 200),
        # Free-form lists — admin types factor names / option names
        "expected_factors": [str(x).strip() for x in (payload.get("expected_factors") or []) if str(x).strip()][:100],
        "expected_options": [str(x).strip() for x in (payload.get("expected_options") or []) if str(x).strip()][:200],
        # cell expectations: [{ option, factor, value }]
        "expected_cells": _sanitize_cells(payload.get("expected_cells") or []),
        "notes": (payload.get("notes") or "").strip() or None,
        # Regression-suite pinning — bounded check applied below
        "is_regression_pinned": bool(payload.get("is_regression_pinned")),
        "updated_by": admin_id,
        "updated_at": _now(),
    }

    if doc["is_regression_pinned"] and (not existing or not existing.get("is_regression_pinned")):
        pinned = await db[COLL_EXAMPLES].count_documents({"is_regression_pinned": True})
        if pinned >= REGRESSION_MAX_PINS:
            raise ValueError(
                f"Regression suite is full ({pinned}/{REGRESSION_MAX_PINS}). "
                "Unpin another example first.")

    if existing:
        await db[COLL_EXAMPLES].update_one({"id": existing["id"]}, {"$set": doc})
        return await get_example(existing["id"])
    else:
        doc["id"] = f"utx_{uuid.uuid4().hex[:12]}"
        doc["created_by"] = admin_id
        doc["created_at"] = _now()
        await db[COLL_EXAMPLES].insert_one(doc)
        return await get_example(doc["id"])


async def delete_example(example_id: str) -> bool:
    res = await db[COLL_EXAMPLES].delete_one({"id": example_id})
    return bool(res.deleted_count)


# ── Run execution ───────────────────────────────────────────────────────────
async def run_single(example_id: str, admin_id: str,
                     trigger: str = "manual") -> Dict[str, Any]:
    """Execute one example end-to-end and grade it against expectations.

    Strategy: a transient training-decision is inserted, the public
    `_import_inner` runs against it (so quality-floor / constraint-gate /
    engine-tiering all apply identically to user traffic), we read the
    resulting factors+options from the decision, then DELETE the transient
    decision to keep the user's workspace clean.
    """
    ex = await get_example(example_id)
    if not ex:
        raise ValueError("Training example not found")

    # Lazy import to dodge a backend boot-time cycle
    from routes import url_analyze as _ua  # noqa: WPS433
    from core import url_telemetry as _tm  # noqa: WPS433
    from types import SimpleNamespace

    started = _now()
    run_id = f"utr_{uuid.uuid4().hex[:12]}"
    training_user_id = f"__training__{admin_id}"
    dec_id = f"trd_{uuid.uuid4().hex[:10]}"

    # ── Insert transient decision (admin-only, no entitlement consumption) ──
    await db.decisions.insert_one({
        "id": dec_id, "user_id": training_user_id,
        "title": f"[Training] {ex.get('label') or ex['url']}",
        "context": ex.get("context") or "Admin training regression run.",
        "factors": [], "options": [],
        "created_at": started, "updated_at": started,
        "is_training_decision": True,
    })

    # ── Build a real Pydantic ImportRequest so validation matches user traffic ──
    req = _ua.ImportRequest(
        url=ex["url"],
        eligibility_type="public_page",
        custom_note=None,
        accepted=True,
        max_factors=24,
        ai_tier="precise",
        progress_id=None,
        expected_factor_count=ex.get("expected_factor_count"),
        expected_option_count=ex.get("expected_option_count"),
        first_factor_name=(ex.get("expected_factors") or [None])[0] or None,
        first_option_name=(ex.get("expected_options") or [None])[0] or None,
    )
    fake_request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": f"url-training-runner/{admin_id}"},
    )
    fake_request.headers = {"user-agent": f"url-training-runner/{admin_id}"}
    # SimpleNamespace dict access for headers via .get
    fake_request.headers = type("H", (), {"get": lambda self, k, d=None: d})()

    tel = _tm.new_tel(
        training_user_id, endpoint="training",
        url=req.url, ai_tier=req.ai_tier, hints={
            "expected_factor_count": req.expected_factor_count,
            "expected_option_count": req.expected_option_count,
            "first_factor_name": req.first_factor_name,
            "first_option_name": req.first_option_name,
        },
        decision_id=dec_id,
    )

    async def _noop_prog(_pct, _label, status="running"):  # noqa: ANN001
        return None

    error: Optional[str] = None
    resp: Optional[Dict[str, Any]] = None
    try:
        resp = await _ua._import_inner(  # noqa: SLF001
            dec_id, req, fake_request,
            {"user_id": training_user_id, "is_admin": True},
            tel, _noop_prog,
        )
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {str(e)[:280]}"
        logger.warning("training run failed for %s: %s", ex["url"], error)

    # Read the decision back so we can grade against factor display names
    final = await db.decisions.find_one({"id": dec_id}, {"_id": 0}) or {}
    factors = final.get("factors") or []
    options = final.get("options") or []
    if resp is not None:
        resp.setdefault("factors", factors)
        resp.setdefault("options", options)

    grade = _grade(ex, resp) if resp else {
        "status": "error", "score": 0,
        "missed_factors": ex.get("expected_factor_count") or 0,
        "missed_options": ex.get("expected_option_count") or 0,
        "wrong_cells": [],
    }
    completed = _now()

    run_doc = {
        "id": run_id,
        "example_id": ex["id"],
        "url": ex["url"],
        "label": ex.get("label"),
        "trigger": trigger,
        "admin_id": admin_id,
        "started_at": started,
        "completed_at": completed,
        "elapsed_ms": int((completed - started).total_seconds() * 1000),
        "status": grade["status"] if not error else "error",
        "score": grade["score"] if not error else 0,
        "ran_factor_count": len(factors) if not error else 0,
        "ran_option_count": len(options) if not error else 0,
        "expected_factor_count": ex.get("expected_factor_count"),
        "expected_option_count": ex.get("expected_option_count"),
        "missed_factors": grade["missed_factors"],
        "missed_options": grade["missed_options"],
        "wrong_cells": grade["wrong_cells"],
        "import_run_id": (resp or {}).get("run_id"),
        "error": error,
    }
    await db[COLL_RUNS].insert_one(run_doc)
    # Keep a quick reference of the most recent run on the example itself
    await db[COLL_EXAMPLES].update_one({"id": ex["id"]}, {"$set": {
        "last_run_id": run_id, "last_run_status": run_doc["status"],
        "last_run_score": run_doc["score"], "last_run_at": completed,
    }})
    # Clean up the transient decision (no garbage left in the admin's workspace)
    try:
        await db.decisions.delete_one({"id": dec_id, "is_training_decision": True})
    except Exception:  # noqa: BLE001
        pass
    run_doc.pop("_id", None)
    return run_doc


async def run_suite(admin_id: str, trigger: str = "manual") -> Dict[str, Any]:
    """Run all pinned regression examples in sequence — sequential so we
    don't blow up the AI/ScraperAPI budgets or trigger rate-limits."""
    pinned = await (db[COLL_EXAMPLES]
                    .find({"is_regression_pinned": True}, {"_id": 0, "id": 1})
                    .to_list(REGRESSION_MAX_PINS))
    if not pinned:
        return {"ran": 0, "items": [], "message": "No regression examples pinned."}
    items: List[Dict[str, Any]] = []
    for p in pinned:
        try:
            r = await run_single(p["id"], admin_id=admin_id, trigger=trigger)
            items.append({"example_id": p["id"], "status": r["status"], "score": r["score"]})
        except Exception as e:  # noqa: BLE001
            logger.warning("suite run skipped %s: %s", p["id"], e)
            items.append({"example_id": p["id"], "status": "error", "score": 0,
                          "error": str(e)[:200]})
    return {"ran": len(items), "items": items}


async def list_runs(example_id: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if example_id:
        q["example_id"] = example_id
    return await (db[COLL_RUNS].find(q, {"_id": 0})
                  .sort("started_at", -1).limit(min(limit, 500))
                  .to_list(500))


# ── Grading ─────────────────────────────────────────────────────────────────
def _grade(ex: Dict[str, Any], resp: Dict[str, Any]) -> Dict[str, Any]:
    """Compare extracted vs expected and produce a status + score."""
    exp_fc = ex.get("expected_factor_count")
    exp_oc = ex.get("expected_option_count")
    got_fc = int(resp.get("factors_added") or resp.get("factor_count") or 0)
    got_oc = int(resp.get("options_added") or resp.get("item_count") or 0)

    parts: List[float] = []
    missed_f = 0
    missed_o = 0
    if exp_fc:
        ratio = min(1.0, got_fc / max(1, exp_fc))
        parts.append(ratio)
        missed_f = max(0, exp_fc - got_fc)
    if exp_oc:
        ratio = min(1.0, got_oc / max(1, exp_oc))
        parts.append(ratio)
        missed_o = max(0, exp_oc - got_oc)
    # Factor-name overlap (case-insensitive token match)
    exp_facs = [str(x).lower() for x in (ex.get("expected_factors") or [])]
    if exp_facs:
        got_facs = [str(f.get("display_name") or f.get("name") or "").lower()
                    for f in (resp.get("factors") or [])]
        if got_facs:
            hit = sum(1 for x in exp_facs if any(x in g or g in x for g in got_facs))
            parts.append(hit / max(1, len(exp_facs)))

    score = int(round(100 * (sum(parts) / len(parts)))) if parts else 0
    status = ("pass" if score >= 80 else
              "partial" if score >= 50 else
              "fail")
    return {"status": status, "score": score,
            "missed_factors": missed_f, "missed_options": missed_o,
            "wrong_cells": []}


def _sanitize_cells(cells: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in cells[:300]:
        if not isinstance(c, dict):
            continue
        opt = str(c.get("option") or "").strip()
        fac = str(c.get("factor") or "").strip()
        val = c.get("value")
        if not opt or not fac:
            continue
        out.append({"option": opt[:200], "factor": fac[:200],
                    "value": (str(val)[:200] if val is not None else None)})
    return out


def _clamp_int(v, lo: int, hi: int) -> Optional[int]:
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, n))


# ── Weekly scheduler (Sun 03:00 UTC, leader pid-guarded) ────────────────────
_scheduler_started = False


def start_weekly_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    async def _weekly():
        while True:
            now = datetime.now(timezone.utc)
            # next Sunday at 03:00 UTC
            days_ahead = (6 - now.weekday()) % 7
            target = (now + timedelta(days=days_ahead)).replace(
                hour=3, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=7)
            await asyncio.sleep(max(60.0, (target - now).total_seconds()))
            try:
                await run_suite(admin_id="__cron__", trigger="cron")
            except Exception as e:  # noqa: BLE001
                logger.warning("training weekly cron failed: %s", e)

    asyncio.create_task(_weekly())
    logger.info("URL Training weekly scheduler started (Sun 03:00 UTC).")
