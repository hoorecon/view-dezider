"""Backend tests for collaboration OTP + auth-config (iter 151)."""
import os
import time
import uuid
import pytest
import requests

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
        or open("/app/frontend/.env").read().split("EXPO_PUBLIC_BACKEND_URL=")[1].split("\n")[0].strip()
       ).rstrip("/")
SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token")


def _register_user():
    email = f"TEST_otp_{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass2026!"
    r = requests.post(f"{BASE}/api/auth/register", json={
        "name": "OTP Tester", "email": email, "password": pw,
    }, timeout=20)
    assert r.status_code in (200, 201), f"register {r.status_code} {r.text}"
    j = r.json()
    return email, pw, (j.get("session_token") or j.get("access_token") or j.get("token"))


# ---------------- auth-config ----------------

def test_auth_config_public():
    email, pw, tok = _register_user()
    r = requests.get(f"{BASE}/api/collaboration/auth-config",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "advanced_methods_enabled" in j
    assert isinstance(j["advanced_methods_enabled"], bool)
    assert j.get("otp_channels") == ["whatsapp", "email"]


def test_admin_auth_config_requires_admin():
    # No auth header → 401/403
    r = requests.get(f"{BASE}/api/collaboration/admin/auth-config", timeout=15)
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    r = requests.put(f"{BASE}/api/collaboration/admin/auth-config",
                     json={"advanced_methods_enabled": True}, timeout=15)
    assert r.status_code in (401, 403)


def test_admin_auth_config_get_put_roundtrip():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    H = {"Authorization": f"Bearer {tok}"}

    # GET current
    r = requests.get(f"{BASE}/api/collaboration/admin/auth-config", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    orig = r.json().get("advanced_methods_enabled", False)

    # Flip
    new_val = not orig
    r = requests.put(f"{BASE}/api/collaboration/admin/auth-config",
                     headers=H, json={"advanced_methods_enabled": new_val}, timeout=15)
    assert r.status_code == 200
    assert r.json()["advanced_methods_enabled"] is new_val

    # GET → reflects new
    r = requests.get(f"{BASE}/api/collaboration/admin/auth-config", headers=H, timeout=15)
    assert r.json()["advanced_methods_enabled"] is new_val

    # Restore
    r = requests.put(f"{BASE}/api/collaboration/admin/auth-config",
                     headers=H, json={"advanced_methods_enabled": orig}, timeout=15)
    assert r.status_code == 200


# ---------------- OTP send / verify ----------------

def _get_or_create_session(token):
    H = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/api/collaboration/sessions", headers=H, timeout=20)
    if r.status_code == 200:
        sessions = r.json()
        if sessions:
            return sessions[0]["id"]
    return None  # caller will skip if no session


def test_otp_send_email_returns_200():
    """Use super admin which is likely to have sessions; else try participant approach."""
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    sid = _get_or_create_session(tok)
    if not sid:
        pytest.skip("No existing collaboration session to test OTP send against.")

    contact = f"TEST_otp_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(
        f"{BASE}/api/collaboration/sessions/{sid}/otp/send",
        headers={"Authorization": f"Bearer {tok}"},
        json={"channel": "email", "contact": contact}, timeout=30,
    )
    assert r.status_code == 200, f"OTP send email failed {r.status_code} {r.text}"
    j = r.json()
    assert j.get("sent") is True
    assert j.get("channel") == "email"


def test_otp_send_throttle_429():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    sid = _get_or_create_session(tok)
    if not sid:
        pytest.skip("No existing collaboration session.")

    contact = f"TEST_throttle_{uuid.uuid4().hex[:6]}@example.com"
    H = {"Authorization": f"Bearer {tok}"}
    body = {"channel": "email", "contact": contact}

    r1 = requests.post(f"{BASE}/api/collaboration/sessions/{sid}/otp/send",
                       headers=H, json=body, timeout=30)
    assert r1.status_code == 200, r1.text

    # immediate resend should be throttled
    r2 = requests.post(f"{BASE}/api/collaboration/sessions/{sid}/otp/send",
                       headers=H, json=body, timeout=30)
    assert r2.status_code == 429, f"expected 429 got {r2.status_code} {r2.text}"


def test_otp_verify_wrong_code_401():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    sid = _get_or_create_session(tok)
    if not sid:
        pytest.skip("No existing collaboration session.")

    contact = f"TEST_wrong_{uuid.uuid4().hex[:6]}@example.com"
    H = {"Authorization": f"Bearer {tok}"}

    # Ensure record exists
    r = requests.post(f"{BASE}/api/collaboration/sessions/{sid}/otp/send",
                      headers=H, json={"channel": "email", "contact": contact}, timeout=30)
    assert r.status_code == 200, r.text

    r = requests.post(f"{BASE}/api/collaboration/sessions/{sid}/otp/verify",
                      headers=H, json={"channel": "email", "contact": contact, "otp": "000000"},
                      timeout=20)
    assert r.status_code == 401, f"expected 401 got {r.status_code} {r.text}"
    assert "Incorrect" in r.text or "incorrect" in r.text


def test_otp_send_invalid_channel_400():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    sid = _get_or_create_session(tok)
    if not sid:
        pytest.skip("No existing collaboration session.")

    r = requests.post(f"{BASE}/api/collaboration/sessions/{sid}/otp/send",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"channel": "sms", "contact": "test@x.com"}, timeout=15)
    assert r.status_code == 400


def test_otp_send_unknown_session_404():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    r = requests.post(f"{BASE}/api/collaboration/sessions/collab_doesnotexist/otp/send",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"channel": "email", "contact": "test@x.com"}, timeout=15)
    assert r.status_code == 404
