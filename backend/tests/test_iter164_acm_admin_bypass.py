"""
Iter164 — ACM platform_admin bypass tests.

Bug: Super-admin viewing the normal user app had 5 features hidden by ACM
(collab_knowledge_marketplace, collab_my_earnings, collab_karma_fame,
digilocker, sub_auto_renew) because platform_admin fell back to
paid_enterprise/paid_pro. Fix: early-return in check_feature_access and
get_all_feature_access when access_key == 'platform_admin'.

Tests:
- super-admin: /api/acm/my-access -> every feature access_level=='full'
- super-admin: /api/acm/check/digilocker -> allowed=true, level=full (+ the 5)
- regression: a fresh free user does NOT get full for everything,
  and /api/acm/check/digilocker returns allowed=false (hidden|locked)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL (or EXPO_BACKEND_URL) must be set"
BASE_URL = BASE_URL.rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASSWORD = "SuperPass2026!"

# These were the 5 features hidden for super-admin before the fix.
PREVIOUSLY_HIDDEN = [
    "collab_knowledge_marketplace",
    "collab_my_earnings",
    "collab_karma_fame",
    "digilocker",
    "sub_auto_renew",
]


# ---------------- helpers ----------------

def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("token") or body.get("access_token")
    assert token, f"no session_token in login response: {body}"
    return token


def _register_free_user() -> tuple[str, str, str]:
    """Register a fresh free user; return (email, password, token).
    Falls back to login if registration says already exists."""
    suffix = uuid.uuid4().hex[:10]
    email = f"TEST_free_{suffix}@example.com"
    password = "FreeUserPass2026!"
    payload = {
        "email": email,
        "password": password,
        "name": "TEST Free User",
        "full_name": "TEST Free User",
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=30)
    if r.status_code in (200, 201):
        body = r.json()
        token = body.get("session_token") or body.get("token")
        if token:
            return email, password, token
        # Some flows: register doesn't return token; login next.
        return email, password, _login(email, password)
    # Unexpected; show body for debugging
    pytest.skip(f"register endpoint failed: {r.status_code} {r.text[:200]}")


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def super_token() -> str:
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="module")
def free_user():
    email, password, token = _register_free_user()
    return {"email": email, "password": password, "token": token}


# ---------------- tests: super-admin ----------------

class TestSuperAdminBypass:
    def test_super_my_access_all_full(self, super_token):
        r = requests.get(
            f"{BASE_URL}/api/acm/my-access",
            headers=_auth_header(super_token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("access_key") == "platform_admin", (
            f"expected access_key=platform_admin, got {body.get('access_key')}"
        )
        features = body.get("features") or {}
        assert isinstance(features, dict) and len(features) > 0, "features map empty"

        # Tally levels
        levels: dict[str, int] = {}
        non_full = {}
        for fid, info in features.items():
            lvl = (info or {}).get("access_level", "?")
            levels[lvl] = levels.get(lvl, 0) + 1
            if lvl != "full":
                non_full[fid] = lvl

        print(f"super-admin feature level counts: {levels}")
        assert not non_full, (
            f"super-admin should see ALL features as 'full'. "
            f"Non-full features: {non_full}"
        )

    def test_super_previously_hidden_now_full(self, super_token):
        r = requests.get(
            f"{BASE_URL}/api/acm/my-access",
            headers=_auth_header(super_token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        features = r.json().get("features") or {}
        bad = {}
        for fid in PREVIOUSLY_HIDDEN:
            info = features.get(fid)
            assert info is not None, f"feature {fid} missing from my-access"
            if info.get("access_level") != "full":
                bad[fid] = info.get("access_level")
        assert not bad, f"Previously-hidden features still not full for super-admin: {bad}"

    def test_super_check_digilocker_allowed(self, super_token):
        r = requests.get(
            f"{BASE_URL}/api/acm/check/digilocker",
            headers=_auth_header(super_token),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("allowed") is True, f"digilocker not allowed for super-admin: {body}"
        assert body.get("access_level") == "full", (
            f"expected access_level=full for super-admin digilocker, got {body}"
        )

    def test_super_check_each_previously_hidden(self, super_token):
        bad = {}
        for fid in PREVIOUSLY_HIDDEN:
            r = requests.get(
                f"{BASE_URL}/api/acm/check/{fid}",
                headers=_auth_header(super_token),
                timeout=30,
            )
            if r.status_code != 200:
                bad[fid] = f"HTTP {r.status_code}: {r.text[:120]}"
                continue
            body = r.json()
            if not body.get("allowed") or body.get("access_level") != "full":
                bad[fid] = body
        assert not bad, f"Single-feature check failures for super-admin: {bad}"


# ---------------- tests: regression (free user) ----------------

class TestFreeUserRegression:
    def test_free_my_access_not_all_full(self, free_user):
        r = requests.get(
            f"{BASE_URL}/api/acm/my-access",
            headers=_auth_header(free_user["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        ak = body.get("access_key")
        assert ak != "platform_admin", (
            f"free user must NOT have platform_admin access_key, got {ak}"
        )
        features = body.get("features") or {}
        assert features, "features map empty for free user"
        levels: dict[str, int] = {}
        for info in features.values():
            lvl = (info or {}).get("access_level", "?")
            levels[lvl] = levels.get(lvl, 0) + 1
        print(f"free user feature level counts: {levels}, access_key={ak}")
        # Must NOT all be full — ACM still governs normal users.
        assert levels.get("full", 0) < len(features), (
            f"free user is getting full for ALL features ({len(features)}); "
            f"bypass is leaking. Levels={levels}"
        )

    def test_free_check_digilocker_not_allowed(self, free_user):
        r = requests.get(
            f"{BASE_URL}/api/acm/check/digilocker",
            headers=_auth_header(free_user["token"]),
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("allowed") is False, (
            f"digilocker should NOT be allowed for free user, got {body}"
        )
        assert body.get("access_level") in ("hidden", "locked"), (
            f"digilocker access_level should be hidden/locked for free user, got {body}"
        )
