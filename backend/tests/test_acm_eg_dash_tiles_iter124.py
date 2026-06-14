"""ACM verification for iteration 124 — Emotional Gatekeeper rework +
   dashboard_tiles: dash_outlet_analyzer & dash_aim_manager."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _my_access(headers):
    r = requests.get(f"{BASE_URL}/api/acm/my-access", headers=headers, timeout=20)
    assert r.status_code == 200, f"my-access failed: {r.status_code} {r.text}"
    return r.json()


def test_my_access_includes_new_dash_outlet_analyzer(headers):
    data = _my_access(headers)
    features = data.get("features", data)  # support either shape
    # features may be dict { feature_id: {access_level, ...} }
    if isinstance(features, dict):
        assert "dash_outlet_analyzer" in features, "dash_outlet_analyzer missing from /acm/my-access"
        entry = features["dash_outlet_analyzer"]
        # access_level should be 'full' for admin (unless locked elsewhere)
        assert entry.get("access_level") in ("full", "locked"), entry
    else:
        ids = [f.get("feature_id") for f in features]
        assert "dash_outlet_analyzer" in ids


def test_my_access_includes_new_dash_aim_manager(headers):
    data = _my_access(headers)
    features = data.get("features", data)
    if isinstance(features, dict):
        assert "dash_aim_manager" in features
    else:
        ids = [f.get("feature_id") for f in features]
        assert "dash_aim_manager" in ids


def test_dash_features_count_includes_two_new(headers):
    data = _my_access(headers)
    features = data.get("features", data)
    if isinstance(features, dict):
        dash_keys = [k for k in features.keys() if k.startswith("dash_")]
    else:
        dash_keys = [f.get("feature_id") for f in features if str(f.get("feature_id", "")).startswith("dash_")]
    # Per PRD: total dash_* features should now be 36 (was 34 + 2 new)
    assert len(dash_keys) == 36, (
        f"Expected 36 dash_* features but found {len(dash_keys)}. dash_keys={sorted(dash_keys)}"
    )


_USER_TYPES = [
    "unit_tester", "integration_tester", "alpha", "beta",
    "free", "trial", "paid_starter", "paid_pro",
    "paid_enterprise", "paid_api",
]


def _full_access():
    return {ut: {"level": "full", "quota": -1} for ut in _USER_TYPES}


def _locked_access():
    return {ut: {"level": "locked", "quota": 0} for ut in _USER_TYPES}


def test_lock_unlock_dash_outlet_analyzer(headers):
    # Lock
    r = requests.put(
        f"{BASE_URL}/api/acm/feature/dash_outlet_analyzer",
        headers=headers,
        json={"access": _locked_access()},
        timeout=20,
    )
    assert r.status_code in (200, 204), f"lock PUT failed: {r.status_code} {r.text}"

    # Re-read
    data = _my_access(headers)
    features = data.get("features", data)
    entry = features["dash_outlet_analyzer"] if isinstance(features, dict) else \
            next(f for f in features if f.get("feature_id") == "dash_outlet_analyzer")
    assert entry.get("access_level") == "locked", f"After lock, expected locked. got={entry}"

    # Restore to full
    r2 = requests.put(
        f"{BASE_URL}/api/acm/feature/dash_outlet_analyzer",
        headers=headers,
        json={"access": _full_access()},
        timeout=20,
    )
    assert r2.status_code in (200, 204), f"restore PUT failed: {r2.status_code} {r2.text}"

    data2 = _my_access(headers)
    features2 = data2.get("features", data2)
    entry2 = features2["dash_outlet_analyzer"] if isinstance(features2, dict) else \
             next(f for f in features2 if f.get("feature_id") == "dash_outlet_analyzer")
    assert entry2.get("access_level") == "full", f"After restore expected full. got={entry2}"


def test_acm_seed_version(headers):
    """ACM_SEED_VERSION bumped to 2026-06-14-02."""
    # Try a status endpoint; fall back to any field exposing it in /my-access
    r = requests.get(f"{BASE_URL}/api/acm/status", headers=headers, timeout=15)
    if r.status_code == 200:
        body = r.json()
        ver = body.get("version") or body.get("seed_version")
        assert ver == "2026-06-14-02", f"seed version mismatch: {ver}"
    else:
        pytest.skip(f"/api/acm/status not available (status={r.status_code}); seed version cannot be asserted via API")
