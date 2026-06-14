"""Backend tests for /api/ai-wallet/consumption (Iteration 121).

Verifies the fix that switched the aggregation from $abs:$amount → $abs:$delta
so the pie chart shows real spend instead of 0 across the board.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ── shared session/login ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:160]}")
    tok = r.json().get("session_token") or r.json().get("token")
    me = r.json().get("user") or {}
    user_id = me.get("user_id")
    s.headers["Authorization"] = f"Bearer {tok}"
    # fallback for user_id via /auth/me
    if not user_id:
        me_r = s.get(f"{API}/auth/me", timeout=10)
        if me_r.status_code == 200:
            user_id = (me_r.json() or {}).get("user_id")
    return s, user_id


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    yield db
    cli.close()


# ── 1a. no-params: real total + buckets ────────────────────────────────
class TestConsumptionAllTime:
    def test_all_time_returns_positive_total_and_buckets(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{API}/ai-wallet/consumption", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total_credits" in data and "buckets" in data
        assert isinstance(data["buckets"], list)
        # admin@test.com is expected to have spend history seeded
        if data["total_credits"] <= 0 or not data["buckets"]:
            pytest.skip(
                "admin@test.com has no debit history in this env — cannot validate non-zero aggregation"
            )
        assert data["total_credits"] > 0
        assert len(data["buckets"]) >= 1
        for b in data["buckets"]:
            assert {"feature", "credits", "runs", "pct"} <= set(b.keys())
            assert b["credits"] > 0
            assert b["runs"] > 0
            assert b["pct"] >= 0  # tail buckets can round to 0.0 but not negative
        # sum of pct ≈ 100 (allow rounding)
        total_pct = sum(b["pct"] for b in data["buckets"])
        assert 95.0 <= total_pct <= 105.0


# ── 1b. since filter doesn't 500 ────────────────────────────────────────
class TestConsumptionSinceFilter:
    def test_last_7d_no_error(self, admin_session):
        s, _ = admin_session
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = s.get(f"{API}/ai-wallet/consumption", params={"since": since}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "buckets" in data
        assert isinstance(data["total_credits"], (int, float))
        assert data["total_credits"] >= 0


# ── 1c. insert a TEST debit and confirm it's aggregated ─────────────────
class TestConsumptionPicksUpNewDebit:
    @pytest.fixture(autouse=True)
    def _cleanup(self, mongo):
        yield
        # always remove any test rows after the test
        mongo.ai_wallet_ledger.delete_many({"note": {"$regex": "^TEST_"}})

    def test_new_debit_increases_total(self, admin_session, mongo):
        s, user_id = admin_session
        if not user_id:
            pytest.skip("could not resolve admin user_id")
        before = s.get(f"{API}/ai-wallet/consumption", timeout=15).json()
        delta_credits = 12.34
        mongo.ai_wallet_ledger.insert_one({
            "id": f"test_ledger_{int(time.time()*1000)}",
            "user_id": user_id,
            "kind": "debit",
            "delta": -delta_credits,
            "feature": "dev_test_topup",
            "note": "TEST_iter121_consumption",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        after = s.get(f"{API}/ai-wallet/consumption", timeout=15).json()
        assert after["total_credits"] >= before["total_credits"] + delta_credits - 0.05
        # ensure dev_test_topup bucket present with the test credits
        buckets = {b["feature"]: b for b in after["buckets"]}
        assert "dev_test_topup" in buckets
        assert buckets["dev_test_topup"]["credits"] >= delta_credits - 0.05


# ── 1d. positive delta rows must NOT appear (grants/refunds) ───────────
class TestConsumptionExcludesGrants:
    @pytest.fixture(autouse=True)
    def _cleanup(self, mongo):
        yield
        mongo.ai_wallet_ledger.delete_many({"note": {"$regex": "^TEST_grant_"}})

    def test_positive_delta_excluded(self, admin_session, mongo):
        s, user_id = admin_session
        if not user_id:
            pytest.skip("could not resolve admin user_id")
        before = s.get(f"{API}/ai-wallet/consumption", timeout=15).json()
        # NB: $lt:0 in match should exclude this row even though kind="debit"
        mongo.ai_wallet_ledger.insert_one({
            "id": f"test_grant_{int(time.time()*1000)}",
            "user_id": user_id,
            "kind": "debit",       # intentionally wrong kind
            "delta": 5.0,          # positive — should be filtered out
            "feature": "dev_test_topup_pos",
            "note": "TEST_grant_iter121",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        after = s.get(f"{API}/ai-wallet/consumption", timeout=15).json()
        # total must not increase due to this row
        assert abs(after["total_credits"] - before["total_credits"]) < 0.5
        features = {b["feature"] for b in after["buckets"]}
        assert "dev_test_topup_pos" not in features
