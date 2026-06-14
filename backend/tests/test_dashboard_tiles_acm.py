"""
ACM Dashboard Tiles gating — backend regression for iteration_123.

Verifies that the new `dashboard_tiles` module (34 dash_* features) was
seeded correctly and that admin can toggle individual tiles off/on via
`PUT /api/acm/feature/{feature_id}` without affecting other dash_* keys.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"

EXPECTED_TILES = [
    "pna", "gem", "instant_dezider", "my_dezider", "pros_cons", "swot",
    "solution_finder", "solution_store", "review_net", "emotional_gatekeeper",
    "conflict_breaker", "goal_setter", "goal_manifestation", "action_tracker",
    "ctt", "lifestyle_dezider", "lifestyle_designer", "lifestyle_analyzer",
    "consciousness_diary", "unconditional_happiness", "collaboration_hub",
    "aala", "time_dezider", "gem_flight", "contacts", "calendar",
    "ai_assistant", "public_pulse", "social_learning", "capabilities_index",
    "deo", "cld_engine", "time_store", "subscription",
]
DASH_KEYS = [f"dash_{t}" for t in EXPECTED_TILES]


def _full_access():
    return {
        ut: {"level": "full", "quota": -1}
        for ut in [
            "unit_tester", "integration_tester", "alpha", "beta",
            "free", "trial", "paid_starter", "paid_pro",
            "paid_enterprise", "paid_api",
        ]
    }


def _locked_access():
    return {
        ut: {"level": "locked", "quota": 0}
        for ut in [
            "unit_tester", "integration_tester", "alpha", "beta",
            "free", "trial", "paid_starter", "paid_pro",
            "paid_enterprise", "paid_api",
        ]
    }


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No session token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ─── 1. Matrix contains dashboard_tiles with 34 features ─────────────
def test_matrix_includes_dashboard_tiles_module(auth):
    r = requests.get(f"{API}/acm/matrix", headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    dt = next(
        (m for m in data["modules"] if m["module_id"] == "dashboard_tiles"),
        None,
    )
    assert dt is not None, "dashboard_tiles module missing from matrix"
    assert dt["module_name"] == "Dashboard Tiles (Home Screen)"
    assert dt["order"] == 99
    feature_ids = {f["feature_id"] for f in dt["features"]}
    assert len(dt["features"]) == 34, f"Expected 34 features, got {len(dt['features'])}"
    missing = set(DASH_KEYS) - feature_ids
    assert not missing, f"Missing dash_ keys in matrix: {missing}"


def test_matrix_totals(auth):
    r = requests.get(f"{API}/acm/matrix", headers=auth, timeout=20)
    data = r.json()
    # Per problem statement: 33 modules, 123 features
    assert data["total_modules"] == 33, f"Expected 33 modules, got {data['total_modules']}"
    assert data["total_features"] == 123, f"Expected 123 features, got {data['total_features']}"


# ─── 2. /my-access returns all 34 dash_* keys ────────────────────────
def test_my_access_returns_all_dash_keys(auth):
    r = requests.get(f"{API}/acm/my-access", headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    feats = data["features"]
    missing = [k for k in DASH_KEYS if k not in feats]
    assert not missing, f"Missing dash_* keys in /my-access: {missing}"
    # Admin → free user_type → full per seed
    assert feats["dash_swot"]["access_level"] in ("full", "read")


# ─── 3. PUT lock + verify + restore ───────────────────────────────────
def _set_access(auth, feature_id, access):
    r = requests.put(
        f"{API}/acm/feature/{feature_id}",
        headers=auth,
        json={"access": access},
        timeout=20,
    )
    assert r.status_code == 200, f"PUT {feature_id} failed: {r.status_code} {r.text}"
    return r.json()


def test_lock_and_restore_dash_swot(auth):
    # Lock
    _set_access(auth, "dash_swot", _locked_access())
    # Verify locked via my-access
    r = requests.get(f"{API}/acm/my-access", headers=auth, timeout=20)
    feats = r.json()["features"]
    assert feats["dash_swot"]["access_level"] == "locked", (
        f"dash_swot not locked after PUT: {feats['dash_swot']}"
    )
    # Other tiles still full
    assert feats["dash_aala"]["access_level"] in ("full", "read")
    assert feats["dash_pros_cons"]["access_level"] in ("full", "read")
    # Restore
    _set_access(auth, "dash_swot", _full_access())
    r = requests.get(f"{API}/acm/my-access", headers=auth, timeout=20)
    feats = r.json()["features"]
    assert feats["dash_swot"]["access_level"] in ("full", "read"), (
        f"Restore failed: {feats['dash_swot']}"
    )


# ─── 4. Toggling several tiles does NOT affect siblings ───────────────
def test_multi_toggle_isolation(auth):
    targets = ["dash_swot", "dash_aala", "dash_review_net"]
    try:
        for t in targets:
            _set_access(auth, t, _locked_access())

        r = requests.get(f"{API}/acm/my-access", headers=auth, timeout=20)
        feats = r.json()["features"]
        for t in targets:
            assert feats[t]["access_level"] == "locked", f"{t} not locked"
        # Other dash_* keys must remain unlocked
        others = [k for k in DASH_KEYS if k not in targets]
        for k in others:
            assert feats[k]["access_level"] in ("full", "read"), (
                f"Sibling {k} unexpectedly affected: {feats[k]}"
            )
    finally:
        # Always restore
        for t in targets:
            _set_access(auth, t, _full_access())
        r = requests.get(f"{API}/acm/my-access", headers=auth, timeout=20)
        feats = r.json()["features"]
        for t in targets:
            assert feats[t]["access_level"] in ("full", "read"), (
                f"Restore for {t} failed"
            )
