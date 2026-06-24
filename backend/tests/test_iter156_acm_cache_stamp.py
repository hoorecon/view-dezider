"""
Iteration 156 — ACM cache stamp propagation tests.

Bug context: Admin sets dash_report_quota to Hidden in Admin → Access Control,
but normal users still see the 'Your Report Quota' card on Home. Root cause:
ACM matrix was cached per-process; a PUT only refreshed the worker that served
it. Fix: DB-backed cache stamp (`acm_meta.acm_cache_stamp`) is bumped on writes;
readers reload when the stamp changes.

This test verifies the functional contract end-to-end against the live backend:
 - PUT /api/acm/feature/dash_report_quota toggling between Hidden and Full for
   the FREE audience immediately reflects in GET /api/acm/my-access for a
   freshly-registered FREE user (same-process here, but the contract is what
   matters).
 - The `acm_meta.acm_cache_stamp` doc exists after a PUT and changes on
   repeated PUTs (verified via repeated functional flips).
 - my-access still returns ~140 features (no regression in feature count).
 - State is restored to Full at the end so the default dashboard isn't broken.
"""

import os
import uuid
import time
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return v.rstrip("/")
    except Exception:
        return ""
    return ""

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
    or os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
    or _read_frontend_env()
)
assert BASE_URL, "Backend URL not configured"

ADMIN_EMAIL = "super@test.com"
ADMIN_PASSWORD = "SuperPass2026!"
FEATURE_ID = "dash_report_quota"
AUDIENCE_KEYS = [
    # Cover all known audience keys so my-access reflects the change regardless
    # of which key the resolver assigns to the FREE user.
    "free", "trial", "starter_trial", "pro_trial", "premium_trial",
    "paid_starter", "paid_pro", "paid_premium", "paid_enterprise",
    "on_demand_retail_buyer", "on_demand_bulk_buyer",
    "unit_tester", "integration_tester", "alpha", "beta",
    "platform_admin",
]


# ------------------ Fixtures ------------------

@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    token = body.get("session_token")
    assert token, "no session_token in admin login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def free_user_session():
    """Register a fresh FREE-tier user."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_iter156_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "TestPass2026!", "name": "Iter156 Free User"},
               timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    token = body.get("session_token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s, body.get("user_id"), email


# ------------------ Helpers ------------------

def _get_feature_access(admin_s):
    r = admin_s.get(f"{BASE_URL}/api/acm/matrix", timeout=30)
    assert r.status_code == 200, f"matrix fetch failed: {r.status_code}"
    data = r.json()
    for mod in data.get("modules", []):
        for feat in mod.get("features", []):
            if feat.get("feature_id") == FEATURE_ID:
                return mod, feat
    return None, None


def _put_feature(admin_s, new_access):
    r = admin_s.put(
        f"{BASE_URL}/api/acm/feature/{FEATURE_ID}",
        json={"access": new_access},
        timeout=30,
    )
    assert r.status_code == 200, f"PUT feature failed: {r.status_code} {r.text[:200]}"
    return r.json()


def _my_access_level(user_s):
    r = user_s.get(f"{BASE_URL}/api/acm/my-access", timeout=30)
    assert r.status_code == 200, f"my-access failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    feats = data.get("features") or {}
    entry = feats.get(FEATURE_ID) or {}
    return data, entry.get("access_level")


def _build_access(level):
    """Apply level to all audiences for an unambiguous toggle."""
    rule = {"level": level, "quota": -1 if level == "full" else 0}
    return {k: rule for k in AUDIENCE_KEYS}


# ------------------ Tests ------------------

class TestACMCacheStampPropagation:
    """Verifies cross-worker cache invalidation contract on dash_report_quota."""

    def test_01_matrix_has_dash_report_quota(self, admin_session):
        mod, feat = _get_feature_access(admin_session)
        assert mod is not None, "dashboard_tiles module not found"
        assert feat is not None, "dash_report_quota feature not found"
        assert mod["module_id"] == "dashboard_tiles"

    def test_02_baseline_free_user_my_access(self, admin_session, free_user_session):
        # Ensure we start from a known FULL state for FREE.
        _put_feature(admin_session, _build_access("full"))
        # tiny wait — though same-process here, mirrors prod behavior
        time.sleep(0.5)
        user_s, _, _ = free_user_session
        data, level = _my_access_level(user_s)
        # Either 'full' or 'read' both mean visible; we just confirm not hidden
        assert level in ("full", "read"), f"expected visible, got {level}"
        # Regression: feature count remains large (~140)
        assert len(data.get("features") or {}) >= 100, \
            f"too few features returned: {len(data.get('features') or {})}"

    def test_03_toggle_to_hidden_propagates(self, admin_session, free_user_session):
        put_resp = _put_feature(admin_session, _build_access("hidden"))
        assert "updated" in put_resp.get("message", "").lower()
        # Allow up to STAMP_CHECK_INTERVAL (2s) for cross-worker reload
        time.sleep(2.5)
        user_s, _, _ = free_user_session
        _, level = _my_access_level(user_s)
        assert level == "hidden", f"expected hidden after PUT, got {level}"

    def test_04_toggle_back_to_full_propagates(self, admin_session, free_user_session):
        _put_feature(admin_session, _build_access("full"))
        time.sleep(2.5)
        user_s, _, _ = free_user_session
        data, level = _my_access_level(user_s)
        assert level in ("full", "read"), f"expected visible after restore, got {level}"
        # Regression sanity check
        assert len(data.get("features") or {}) >= 100

    def test_05_repeated_toggle_consistency(self, admin_session, free_user_session):
        """Repeated PUTs should keep my-access in sync — implies stamp bumps."""
        user_s, _, _ = free_user_session
        for i, lvl in enumerate(["hidden", "full", "hidden", "full"]):
            _put_feature(admin_session, _build_access(lvl))
            time.sleep(2.5)
            _, observed = _my_access_level(user_s)
            if lvl == "hidden":
                assert observed == "hidden", f"iter {i}: expected hidden, got {observed}"
            else:
                assert observed in ("full", "read"), f"iter {i}: expected visible, got {observed}"

    def test_06_restore_full_state(self, admin_session, free_user_session):
        # CRITICAL: end with FULL so default dashboard is not left broken.
        _put_feature(admin_session, _build_access("full"))
        time.sleep(1.0)
        user_s, _, _ = free_user_session
        _, level = _my_access_level(user_s)
        assert level in ("full", "read"), f"final state not visible: {level}"
