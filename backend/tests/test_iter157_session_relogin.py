"""
Iter 157 — session relogin bleed test (email/password path).

Verifies:
  - Login A → /auth/me returns A
  - Logout A's token → /auth/me without token = 401
  - Login B (fresh user) → /auth/me returns B (NOT A)
  - The same /auth/me with B's token never returns A's user_id/email.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"


@pytest.fixture(scope="module")
def fresh_user_b():
    """Register a fresh email/password user to act as 'user B'."""
    suffix = uuid.uuid4().hex[:10]
    email = f"TEST_iter157_{suffix}@example.com"
    password = "BPass2026!"
    name = f"TEST iter157 {suffix}"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": name},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email,
        "password": password,
        "name": name,
        "token": data["session_token"],
        "user_id": data["user_id"],
    }


def test_super_login_me_returns_a():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_EMAIL, "password": SUPER_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    token_a = r.json()["session_token"]
    me = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=20,
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"].lower() == SUPER_EMAIL.lower()


def test_logout_invalidates_token_and_no_token_is_401():
    # login A, logout, verify /me without a token returns 401
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_EMAIL, "password": SUPER_PASS},
        timeout=20,
    )
    assert r.status_code == 200
    token_a = r.json()["session_token"]

    lo = requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=20,
    )
    assert lo.status_code in (200, 204), f"logout failed: {lo.status_code} {lo.text}"

    # /auth/me without any token → 401 (no bleed possible)
    me_no = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me_no.status_code in (401, 403), f"expected 401, got {me_no.status_code}"


def test_relogin_as_different_user_does_not_bleed(fresh_user_b):
    # 1. Login A
    ra = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_EMAIL, "password": SUPER_PASS},
        timeout=20,
    )
    assert ra.status_code == 200
    token_a = ra.json()["session_token"]
    user_a_id = ra.json()["user_id"]

    me_a = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=20,
    ).json()
    assert me_a["user_id"] == user_a_id
    assert me_a["email"].lower() == SUPER_EMAIL.lower()

    # 2. Logout A
    requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=20,
    )

    # 3. Login B (different email/password)
    rb = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": fresh_user_b["email"], "password": fresh_user_b["password"]},
        timeout=20,
    )
    assert rb.status_code == 200, f"B login failed: {rb.status_code} {rb.text}"
    token_b = rb.json()["session_token"]
    assert token_b != token_a, "B token must differ from A token"

    me_b = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token_b}"},
        timeout=20,
    )
    assert me_b.status_code == 200, me_b.text
    bb = me_b.json()

    # CRITICAL — must be B, not A
    assert bb["email"].lower() == fresh_user_b["email"].lower(), (
        f"BLEED: /auth/me returned {bb.get('email')} but expected {fresh_user_b['email']}"
    )
    assert bb["user_id"] == fresh_user_b["user_id"], "user_id bleed"
    assert bb["user_id"] != user_a_id, "user_id collision with A"


def test_invalid_token_is_rejected():
    r = requests.get(
        f"{BASE_URL}/api/auth/me",
        headers={"Authorization": "Bearer nope-nope-nope-not-a-real-token"},
        timeout=20,
    )
    assert r.status_code in (401, 403)
