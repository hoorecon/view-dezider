"""
Iter166 — Backend tests for ACM set_user_type + PII lookup user_type reflection.

Scope (per review_request):
1. PUT /api/acm/user/{uid}/type as super-admin: cycles through user_type values
   beta / unit_tester / alpha / trial / free → 200 each and response echoes value.
2. Gate: a non-super, non-can_view_pii principal (a fresh free user) calling the
   same PUT → 403.
3. POST /api/admin/pii/lookup as super with target's email+WhatsApp+purpose+nda_ack
   → 200 and profile.user_type reflects the last value set above.
"""
import os
import uuid
import requests
import pytest

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL/EXPO_BACKEND_URL must be set"

SUPER_EMAIL = "super@test.com"
SUPER_PASSWORD = "SuperPass2026!"

TARGET_UID = "user_0f76e1bfb3b7"
TARGET_EMAIL = "acmtarget@test.com"
TARGET_WHATSAPP = "+919900112233"

# In order; the LAST value will be asserted by the PII lookup test.
TYPE_CYCLE = ["beta", "unit_tester", "alpha", "trial", "free"]


# ───────────────────────── helpers ─────────────────────────
def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("session_token") or body.get("token") or body.get("access_token")
    assert tok, f"no session token in body: {body}"
    return tok


def _register_free():
    suffix = uuid.uuid4().hex[:10]
    email = f"TEST_free_{suffix}@example.com"
    pw = "FreeUserPass2026!"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": pw,
                            "name": "TEST Free", "full_name": "TEST Free"},
                      timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    tok = body.get("session_token") or body.get("token")
    if not tok:
        tok = _login(email, pw)
    return {"email": email, "token": tok}


# ───────────────────────── fixtures ─────────────────────────
@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="module")
def free_user():
    return _register_free()


# ───────────────────────── 1) set_user_type (super) ─────────────────────────
class TestSetUserTypeSuper:
    @pytest.mark.parametrize("user_type", TYPE_CYCLE)
    def test_set_user_type_cycle(self, super_token, user_type):
        r = requests.put(
            f"{BASE_URL}/api/acm/user/{TARGET_UID}/type",
            headers=_hdr(super_token),
            json={"user_type": user_type},
            timeout=30,
        )
        assert r.status_code == 200, f"PUT {user_type} → {r.status_code} {r.text}"
        body = r.json()
        assert body.get("user_type") == user_type, (
            f"expected echoed user_type={user_type}, got {body}"
        )

    def test_invalid_user_type_400(self, super_token):
        r = requests.put(
            f"{BASE_URL}/api/acm/user/{TARGET_UID}/type",
            headers=_hdr(super_token),
            json={"user_type": "not_a_real_tier"},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400 invalid user_type, got {r.status_code} {r.text}"


# ───────────────────────── 2) gate: non-super, non-pii → 403 ─────────────────────────
class TestSetUserTypeGate:
    def test_free_user_forbidden(self, free_user):
        r = requests.put(
            f"{BASE_URL}/api/acm/user/{TARGET_UID}/type",
            headers=_hdr(free_user["token"]),
            json={"user_type": "beta"},
            timeout=30,
        )
        assert r.status_code == 403, (
            f"free user should be 403 on set_user_type, got {r.status_code} {r.text}"
        )


# ───────────────────────── 3) PII lookup reflects user_type ─────────────────────────
class TestPiiLookupReflectsType:
    def test_lookup_user_type_present(self, super_token):
        # First, set a known value so we can assert it's reflected.
        final_type = "beta"
        rset = requests.put(
            f"{BASE_URL}/api/acm/user/{TARGET_UID}/type",
            headers=_hdr(super_token),
            json={"user_type": final_type},
            timeout=30,
        )
        assert rset.status_code == 200, rset.text

        r = requests.post(
            f"{BASE_URL}/api/admin/pii/lookup",
            headers=_hdr(super_token),
            json={
                "email": TARGET_EMAIL,
                "whatsapp_number": TARGET_WHATSAPP,
                "purpose": "Support service",
                "nda_ack": True,
            },
            timeout=30,
        )
        assert r.status_code == 200, f"lookup failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("matched") is True, f"matched should be True: {body}"
        prof = body.get("profile") or {}
        assert "user_type" in prof, f"profile.user_type missing: {prof}"
        assert prof["user_type"] == final_type, (
            f"profile.user_type expected {final_type}, got {prof.get('user_type')}"
        )
        # Sanity: user_id should match the target
        assert prof.get("user_id") == TARGET_UID, (
            f"profile.user_id expected {TARGET_UID}, got {prof.get('user_id')}"
        )
