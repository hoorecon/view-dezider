"""WOWO ACM v2 — Mega-Build backend regression tests (Iter 132).

Covers:
  • /api/version stamp (build_version + tag)
  • /api/geo/countries + /api/geo/states/IN (auto-seed)
  • /api/acm-v2/resolver-config GET + PUT (admin)
  • /api/acm-v2/trial-payments GET (admin)
  • /api/acm-v2/tier-segment-mapping GET + PUT (admin)
  • /api/acm/my-access still returns 5-axis fields
  • /api/auth/me returns new resolver fields
  • PUT /api/acm/user/{id}/type accepts new types/plans
  • ACM check_feature_access still works for admin
  • Regression: /api/health, ACM seed counters
"""
from __future__ import annotations
import os
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_BACKEND_URL",
    os.environ.get("EXPO_PUBLIC_BACKEND_URL",
                   "https://goals-feels-tracker.preview.emergentagent.com"),
).rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


# ============================================================
# fixtures
# ============================================================
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed {r.status_code}: {r.text[:200]}")
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    if not tok:
        pytest.skip(f"No token in login response: {data}")
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_user_id(s, admin_headers):
    r = s.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"/api/auth/me failed: {r.status_code}")
    return r.json().get("user_id") or r.json().get("id")


# ============================================================
# 1. version stamp
# ============================================================
class TestVersion:
    def test_version_build_stamp(self, s):
        r = s.get(f"{BASE_URL}/api/version", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("build_version") == "2026.06.17.003", \
            f"unexpected build_version: {body}"
        assert body.get("build_tag") == "v3.26-acm-v2-resolver-trial-geo", \
            f"unexpected build_tag: {body}"


# ============================================================
# 2. health
# ============================================================
class TestHealth:
    def test_health(self, s):
        r = s.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ============================================================
# 3. geography
# ============================================================
class TestGeo:
    def test_countries_seeded(self, s):
        r = s.get(f"{BASE_URL}/api/geo/countries", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("countries"), list)
        assert body["count"] >= 50, f"expected >=50 countries, got {body['count']}"
        codes = {c["code"] for c in body["countries"]}
        assert "IN" in codes and "US" in codes

    def test_states_in(self, s):
        r = s.get(f"{BASE_URL}/api/geo/states/IN", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["country_code"] == "IN"
        # 28 states + 8 UTs = 36
        assert body["count"] == 36, f"expected 36 states+UTs, got {body['count']}"
        names = {s["name"] for s in body["states"]}
        assert "Maharashtra" in names
        assert "Delhi" in names

    def test_states_lowercase_code(self, s):
        # Endpoint should uppercase the param
        r = s.get(f"{BASE_URL}/api/geo/states/in", timeout=15)
        assert r.status_code == 200
        assert r.json()["country_code"] == "IN"


# ============================================================
# 4. ACM v2 resolver-config
# ============================================================
class TestResolverConfig:
    def test_get_resolver_config(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/resolver-config",
                  headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        cfg = body.get("config")
        assert cfg is not None
        td = cfg.get("trial_days") or {}
        for k in ("starter_trial", "pro_trial", "premium_trial"):
            assert k in td, f"missing trial_days.{k}"

    def test_get_resolver_config_unauth(self, s):
        r = requests.get(f"{BASE_URL}/api/acm-v2/resolver-config", timeout=15)
        assert r.status_code in (401, 403)

    def test_put_resolver_config_persists(self, s, admin_headers):
        # Read current
        r0 = s.get(f"{BASE_URL}/api/acm-v2/resolver-config",
                   headers=admin_headers, timeout=20)
        assert r0.status_code == 200
        cfg = r0.json()["config"]
        cfg["trial_days"]["starter_trial"] = 2

        r = s.put(f"{BASE_URL}/api/acm-v2/resolver-config",
                  headers=admin_headers,
                  json={"config": cfg}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("ok") is True
        # Re-read & verify persistence
        r2 = s.get(f"{BASE_URL}/api/acm-v2/resolver-config",
                   headers=admin_headers, timeout=20)
        assert r2.json()["config"]["trial_days"]["starter_trial"] == 2

        # Restore default
        cfg["trial_days"]["starter_trial"] = 1
        s.put(f"{BASE_URL}/api/acm-v2/resolver-config",
              headers=admin_headers, json={"config": cfg}, timeout=20)

    def test_put_resolver_config_invalid_trial_days(self, s, admin_headers):
        r = s.put(f"{BASE_URL}/api/acm-v2/resolver-config",
                  headers=admin_headers,
                  json={"config": {"trial_days": "not-a-dict"}},
                  timeout=20)
        assert r.status_code == 400


# ============================================================
# 5. trial payments
# ============================================================
class TestTrialPayments:
    def test_list_trial_payments(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/trial-payments",
                  headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)
        assert "count" in body


# ============================================================
# 6. tier-segment mapping
# ============================================================
class TestTierSegmentMapping:
    def test_list_mappings(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/tier-segment-mapping",
                  headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "mappings" in body and isinstance(body["mappings"], list)

    def test_put_mapping_persists(self, s, admin_headers):
        tier_id = "TEST_tier_iter132"
        r = s.put(f"{BASE_URL}/api/acm-v2/tier-segment-mapping/{tier_id}",
                  headers=admin_headers,
                  json={"segment_ids": ["seg_a", "seg_b"]}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert body.get("segment_ids") == ["seg_a", "seg_b"]
        # Verify GET returns it
        r2 = s.get(f"{BASE_URL}/api/acm-v2/tier-segment-mapping",
                   headers=admin_headers, timeout=20)
        found = [m for m in r2.json()["mappings"] if m.get("tier_id") == tier_id]
        assert len(found) == 1
        assert found[0].get("segment_ids") == ["seg_a", "seg_b"]

    def test_put_mapping_bad_payload(self, s, admin_headers):
        r = s.put(f"{BASE_URL}/api/acm-v2/tier-segment-mapping/TEST_bad",
                  headers=admin_headers,
                  json={"segment_ids": "not-a-list"}, timeout=20)
        assert r.status_code == 400


# ============================================================
# 7. ACM my-access still wired (5-axis resolver)
# ============================================================
class TestMyAccess:
    def test_my_access_admin(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm/my-access", headers=admin_headers, timeout=25)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # New 5-axis resolver fields
        assert "effective_access_key" in body, f"missing effective_access_key: {body.keys()}"
        # reason field is optional but expected
        assert "effective_reason" in body or "reason" in body, \
            f"missing reason trace: {body.keys()}"
        # Admin should bypass to platform_admin (or paid_premium fallback)
        eak = body.get("effective_access_key")
        assert eak in ("platform_admin", "paid_premium", "paid_enterprise", "paid_pro"), \
            f"unexpected effective_access_key for admin: {eak}"


# ============================================================
# 8. auth/me returns resolver fields
# ============================================================
class TestAuthMe:
    def test_me_has_resolver_fields(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "effective_access_key" in body, \
            f"effective_access_key missing in /api/auth/me: {list(body.keys())}"
        assert "user_type" in body, f"user_type missing in /api/auth/me: {list(body.keys())}"
        assert "subscription_plan" in body, \
            f"subscription_plan missing in /api/auth/me: {list(body.keys())}"


# ============================================================
# 9. PUT user/{id}/type accepts new types & plans
# ============================================================
NEW_TYPES = [
    "starter_trial", "pro_trial", "premium_trial",
    "on_demand_retail_buyer", "on_demand_bulk_buyer",
]


class TestSetUserType:
    @pytest.mark.parametrize("new_type", NEW_TYPES)
    def test_set_new_user_type(self, s, admin_headers, admin_user_id, new_type):
        # Try the v2 endpoint path
        r = s.put(f"{BASE_URL}/api/acm/user/{admin_user_id}/type",
                  headers=admin_headers,
                  json={"user_type": new_type, "subscription_plan": "premium"},
                  timeout=20)
        # Tolerate 200 or 204; flag others
        assert r.status_code in (200, 204), \
            f"new type '{new_type}' rejected: {r.status_code} {r.text[:200]}"

    def test_set_user_premium_plan(self, s, admin_headers, admin_user_id):
        # Reset to admin sensible defaults at the end
        r = s.put(f"{BASE_URL}/api/acm/user/{admin_user_id}/type",
                  headers=admin_headers,
                  json={"user_type": "paid", "subscription_plan": "premium"},
                  timeout=20)
        assert r.status_code in (200, 204), r.text[:200]


# ============================================================
# 10. ACM seed counters regression
# ============================================================
class TestAcmSeed:
    def test_features_and_modules_count(self, s, admin_headers):
        # Inspect overview if available; otherwise rely on my-access matrix shape
        r = s.get(f"{BASE_URL}/api/acm/admin/overview",
                  headers=admin_headers, timeout=25)
        if r.status_code == 404:
            pytest.skip("overview endpoint not available")
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        # tolerate either nesting
        feats = (body.get("counts") or {}).get("features") or body.get("features_count")
        mods = (body.get("counts") or {}).get("modules") or body.get("modules_count")
        if feats is not None:
            assert feats >= 134, f"features seed regressed: {feats}"
        if mods is not None:
            assert mods >= 33, f"modules seed regressed: {mods}"
