"""Edge tests for /deep-import/dismiss-rank-prompt and budget-estimate.

Covers acceptance criteria from review request:
- POST .../dismiss-rank-prompt returns {ok:true} & flips flag false
- 404 for unknown decision
- 401/403 without auth
- GET .../budget-estimate?budget_count=0 returns JSON estimate without 500
"""
import os
import time
import uuid
import asyncio
import requests
import pytest

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def auth():
    em = f"iter141_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": em, "password": "TestPass2026!", "name": "Iter141"},
                      timeout=30)
    assert r.status_code in (200, 201), r.text
    tok = r.json()["session_token"]
    me = requests.get(f"{API}/auth/me", headers=_h(tok), timeout=10).json()
    return {"tok": tok, "uid": me["user_id"]}


def _seed_decision(user_id, pending=True):
    from core.database import db
    factors = [
        {"id": "f1", "name": "F1", "rating": 9, "category": "primary",
         "expected_value": "10", "operator": ">=", "order": 0},
        {"id": "f2", "name": "F2", "rating": 7, "category": "primary",
         "expected_value": "5", "operator": ">=", "order": 1},
    ]
    options = [
        {"id": "oa", "name": "OptA", "assessments": [
            {"factor_id": "f1", "percentage": 80},
            {"factor_id": "f2", "percentage": 60}]},
        {"id": "ob", "name": "OptB", "assessments": [
            {"factor_id": "f1", "percentage": 70},
            {"factor_id": "f2", "percentage": 90}]},
    ]
    did = str(uuid.uuid4())
    asyncio.get_event_loop().run_until_complete(
        db.decisions.insert_one({
            "id": did, "user_id": user_id, "title": "TEST_iter141",
            "context": "smoke", "status": "draft",
            "factors": factors, "options": options,
            "deep_import_pending_rank": pending,
        })
    )
    return did


# ── Budget estimate ────────────────────────────────────────
def test_budget_estimate_no_500_with_zero(auth):
    did = _seed_decision(auth["uid"])
    r = requests.get(f"{API}/decisions/{did}/deep-import/budget-estimate",
                     params={"budget_count": 0}, headers=_h(auth["tok"]), timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("total_options", "top_n", "lower", "upper", "requested",
              "estimate_credits", "balance", "sufficient"):
        assert k in data, f"missing key {k}: {data}"
    assert data["total_options"] == 2


# ── Dismiss flag flow ─────────────────────────────────────
def test_dismiss_flips_pending_false(auth):
    did = _seed_decision(auth["uid"], pending=True)
    # Pre-condition: flag true via direct GET
    pre = requests.get(f"{API}/decisions/{did}", headers=_h(auth["tok"]), timeout=10).json()
    assert pre.get("deep_import_pending_rank") is True
    # Action
    r = requests.post(f"{API}/decisions/{did}/deep-import/dismiss-rank-prompt",
                      headers=_h(auth["tok"]), timeout=10)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    # Post-condition: flag false
    post = requests.get(f"{API}/decisions/{did}", headers=_h(auth["tok"]), timeout=10).json()
    assert post.get("deep_import_pending_rank") is False


# ── 404 unknown decision ──────────────────────────────────
def test_dismiss_404_for_unknown(auth):
    r = requests.post(
        f"{API}/decisions/{uuid.uuid4()}/deep-import/dismiss-rank-prompt",
        headers=_h(auth["tok"]), timeout=10)
    assert r.status_code == 404, r.text


# ── No-auth rejected ──────────────────────────────────────
def test_dismiss_requires_auth(auth):
    did = _seed_decision(auth["uid"])
    r = requests.post(
        f"{API}/decisions/{did}/deep-import/dismiss-rank-prompt",
        timeout=10)
    assert r.status_code in (401, 403), r.text


# ── Idempotent ──────────────────────────────────────
def test_dismiss_idempotent(auth):
    did = _seed_decision(auth["uid"], pending=False)
    r = requests.post(f"{API}/decisions/{did}/deep-import/dismiss-rank-prompt",
                      headers=_h(auth["tok"]), timeout=10)
    assert r.status_code == 200
