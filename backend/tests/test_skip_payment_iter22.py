"""
Iter22 — Verify admin Skip Payment toggle correctly bypasses paywall via
GET /api/store/access-check.

Critical bug: sku_store.py queries db.app_settings.find_one({"key": "payment_settings"})
but payment_admin.py stores it with {"_key": "payments_global"}. Keys mismatch!
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def free_user_token():
    email = f"freeuser_iter22_{int(time.time())}@example.com"
    pw = "Pass2026!"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": pw, "name": "Free Iter22"},
                      timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    if not tok:
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"email": email, "password": pw}, timeout=15)
        tok = r2.json().get("session_token") or r2.json().get("access_token") or r2.json().get("token")
    assert tok
    return tok


def _set_skip(admin_token, flag: bool, reason: str = ""):
    r = requests.put(
        f"{BASE_URL}/api/admin/payment-settings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"skip_payment_all_flows": flag, "skip_payment_reason": reason},
        timeout=15,
    )
    return r


def _access_check(token, module="dezider"):
    return requests.get(
        f"{BASE_URL}/api/store/access-check",
        headers={"Authorization": f"Bearer {token}"},
        params={"module": module},
        timeout=15,
    )


# ---------- Baseline: skip OFF, free user has no access ----------
def test_baseline_skip_off_no_access(admin_token, free_user_token):
    r = _set_skip(admin_token, False)
    assert r.status_code == 200, f"toggle off failed: {r.text}"

    for module in ("dezider", "pros_cons", "swot"):
        ac = _access_check(free_user_token, module)
        assert ac.status_code == 200, ac.text
        data = ac.json()
        assert data.get("has_access") is False, f"{module}: expected no access, got {data}"
        assert data.get("via") in (None, "null"), f"{module}: {data}"


# ---------- Enable skip → free user should have access via admin_skip ----------
def test_skip_on_grants_access_to_all_modules(admin_token, free_user_token):
    r = _set_skip(admin_token, True, "Production testing")
    assert r.status_code == 200, f"toggle on failed: {r.text}"
    body = r.json()
    assert body.get("skip_payment_all_flows") is True, body

    for module in ("dezider", "pros_cons", "swot"):
        ac = _access_check(free_user_token, module)
        assert ac.status_code == 200, ac.text
        data = ac.json()
        assert data.get("has_access") is True, (
            f"BUG: skip ON but {module} access-check still returns has_access=False. "
            f"Response: {data}. Root cause: sku_store.py queries db.app_settings "
            f"with key='payment_settings' but payment_admin.py stores it as _key='payments_global'."
        )
        assert data.get("via") == "admin_skip", f"{module}: expected via=admin_skip, got {data}"
        assert data.get("skip_reason") == "Production testing", f"{module}: {data}"


# ---------- Idempotency: hitting access-check repeatedly returns same shape ----------
def test_idempotent_when_skip_on(admin_token, free_user_token):
    _set_skip(admin_token, True, "Production testing")
    results = []
    for _ in range(3):
        ac = _access_check(free_user_token, "dezider")
        assert ac.status_code == 200
        results.append(ac.json())
    assert all(r.get("has_access") is True and r.get("via") == "admin_skip" for r in results), results


# ---------- Toggle OFF again → access flips back to False ----------
def test_skip_off_again_revokes_access(admin_token, free_user_token):
    r = _set_skip(admin_token, False)
    assert r.status_code == 200
    for module in ("dezider", "pros_cons", "swot"):
        ac = _access_check(free_user_token, module)
        data = ac.json()
        assert data.get("has_access") is False, f"{module}: skip OFF but still has access: {data}"


# ---------- Cleanup: ensure skip is OFF at end ----------
def test_cleanup_skip_off(admin_token):
    r = _set_skip(admin_token, False)
    assert r.status_code == 200
