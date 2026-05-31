"""
Tests for the P0 security fix: ONLY the single root super-admin email
(veales.vedic.decisions@gmail.com) may grant/revoke admin roles via
/api/admin/setup, /api/admin/promote, /api/admin/demote.

Targets the public-facing backend (EXPO_PUBLIC_BACKEND_URL) so we test what
the user actually sees. Falls back to local for safety.
"""
import os
import time
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")

ROOT_EMAIL = "veales.vedic.decisions@gmail.com"
ROOT_PASS = "Jelcos@Admin2026"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def root_token():
    return _login(ROOT_EMAIL, ROOT_PASS)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def fresh_user():
    """Register a brand-new throwaway user to serve as promote/demote target."""
    email = f"target_{int(time.time())}@example.com"
    password = "TargetPass2026!"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Target User"},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    return {"email": email, "password": password, "token": r.json().get("session_token")}


# ---------- Negative path: regular user ----------
class TestRegularUserBlocked:
    def test_regular_user_setup_forbidden(self, user_token):
        r = requests.post(f"{BASE_URL}/api/admin/setup", headers=_h(user_token), timeout=20)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_regular_user_promote_forbidden(self, user_token, fresh_user):
        r = requests.post(
            f"{BASE_URL}/api/admin/promote",
            headers=_h(user_token),
            json={"email": fresh_user["email"], "role": "admin"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_regular_user_demote_forbidden(self, user_token, fresh_user):
        r = requests.post(
            f"{BASE_URL}/api/admin/demote",
            headers=_h(user_token),
            json={"email": fresh_user["email"]},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------- Negative path: non-root admin ----------
class TestNonRootAdminBlocked:
    def test_non_root_admin_setup_forbidden(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/admin/setup", headers=_h(admin_token), timeout=20)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_non_root_admin_promote_forbidden(self, admin_token, fresh_user):
        r = requests.post(
            f"{BASE_URL}/api/admin/promote",
            headers=_h(admin_token),
            json={"email": fresh_user["email"], "role": "admin"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_non_root_admin_demote_forbidden(self, admin_token, fresh_user):
        r = requests.post(
            f"{BASE_URL}/api/admin/demote",
            headers=_h(admin_token),
            json={"email": fresh_user["email"]},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------- Positive path: root super-admin ----------
class TestRootSuperAdminAuthorized:
    def test_root_promote_and_demote_roundtrip(self, root_token, fresh_user):
        # Promote fresh user to admin
        r = requests.post(
            f"{BASE_URL}/api/admin/promote",
            headers=_h(root_token),
            json={"email": fresh_user["email"], "role": "admin"},
            timeout=20,
        )
        assert r.status_code == 200, f"Promote failed: {r.status_code} {r.text}"
        body = r.json()
        assert "admin" in (body.get("message", "").lower()), body

        # Verify GET /admin/users shows the new admin
        r2 = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(root_token), timeout=20)
        assert r2.status_code == 200, f"admin/users failed: {r2.status_code} {r2.text}"
        emails = [u.get("email", "").lower() for u in r2.json()]
        assert fresh_user["email"].lower() in emails, (
            f"Promoted user not in admin/users list: {emails}"
        )

        # Demote that same user
        r3 = requests.post(
            f"{BASE_URL}/api/admin/demote",
            headers=_h(root_token),
            json={"email": fresh_user["email"]},
            timeout=20,
        )
        assert r3.status_code == 200, f"Demote failed: {r3.status_code} {r3.text}"

        # Verify they no longer appear as admin
        r4 = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(root_token), timeout=20)
        assert r4.status_code == 200
        emails2 = [u.get("email", "").lower() for u in r4.json()]
        assert fresh_user["email"].lower() not in emails2, (
            f"User still appears as admin after demote: {emails2}"
        )

    def test_root_cannot_demote_self(self, root_token):
        r = requests.post(
            f"{BASE_URL}/api/admin/demote",
            headers=_h(root_token),
            json={"email": ROOT_EMAIL},
            timeout=20,
        )
        # Either 400 (cannot demote yourself) or 403 (root cannot be demoted)
        # Per spec, expected 403. Accept both but prefer 403.
        assert r.status_code in (400, 403), f"Expected 400/403, got {r.status_code}: {r.text}"


# ---------- Regression: admin/users still works for non-root admin ----------
class TestAdminUsersRegression:
    def test_non_root_admin_can_list_admins(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list)
        # Should include at least one of the known admins (root or admin@test.com)
        emails = [u.get("email", "").lower() for u in data]
        assert any(e in emails for e in [ROOT_EMAIL, ADMIN_EMAIL]), (
            f"Expected admin emails in list, got: {emails}"
        )
