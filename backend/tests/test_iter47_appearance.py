"""Iter47: Appearance (font_family) admin API tests."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@test.com", "password": "AdminPass2026!"})
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def user_token():
    # register fresh non-admin user
    email = f"iter47_{int(time.time())}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "TestPass2026!", "name": "Iter47 User"})
    assert r.status_code in (200, 201), r.text
    return r.json()["session_token"]


def _auth(tok): return {"Authorization": f"Bearer {tok}"}


# --- Public appearance GET ---
def test_get_appearance_public_no_auth_returns_options():
    r = requests.get(f"{API}/appearance")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "font_family" in data
    assert "font_options" in data and isinstance(data["font_options"], list)
    assert len(data["font_options"]) == 8
    assert data.get("default_font") == "Inter"
    expected = {"System", "Inter", "Roboto", "Poppins", "Plus Jakarta Sans", "Hind", "Noto Sans Devanagari", "JetBrains Mono"}
    assert set(data["font_options"]) == expected


# --- Admin PUT happy path + GET reflects ---
def test_put_appearance_admin_updates_and_get_reflects(admin_token):
    try:
        r = requests.put(f"{API}/admin/appearance", json={"font_family": "Poppins"}, headers=_auth(admin_token))
        assert r.status_code == 200, r.text
        assert r.json() == {"success": True, "font_family": "Poppins"}

        # GET reflects the change
        g = requests.get(f"{API}/appearance")
        assert g.status_code == 200
        assert g.json()["font_family"] == "Poppins"
    finally:
        # Reset back to Inter
        rr = requests.put(f"{API}/admin/appearance", json={"font_family": "Inter"}, headers=_auth(admin_token))
        assert rr.status_code == 200
        assert rr.json()["font_family"] == "Inter"
        g2 = requests.get(f"{API}/appearance")
        assert g2.json()["font_family"] == "Inter"


# --- Non-admin gets 403 ---
def test_put_appearance_non_admin_forbidden(user_token):
    r = requests.put(f"{API}/admin/appearance", json={"font_family": "Roboto"}, headers=_auth(user_token))
    assert r.status_code == 403, r.text


# --- Invalid font value rejected ---
def test_put_appearance_invalid_font_400(admin_token):
    r = requests.put(f"{API}/admin/appearance", json={"font_family": "Comic Sans"}, headers=_auth(admin_token))
    assert r.status_code == 400, r.text
    assert "Unsupported" in r.json().get("detail", "")


# --- Unauthenticated PUT rejected ---
def test_put_appearance_no_auth_rejected():
    r = requests.put(f"{API}/admin/appearance", json={"font_family": "Roboto"})
    assert r.status_code in (401, 403), r.text


# --- Item 3 re-test: whatsapp verify flow returns success and /me reflects verified ---
def test_whatsapp_verify_marks_user_verified():
    email = f"iter47_wa_{int(time.time())}@example.com"
    reg = requests.post(f"{API}/auth/register", json={"email": email, "password": "TestPass2026!", "name": "WA Tester"})
    assert reg.status_code in (200, 201), reg.text
    tok = reg.json()["session_token"]
    h = _auth(tok)

    # Initially unverified
    me0 = requests.get(f"{API}/auth/me", headers=h).json()
    assert me0.get("whatsapp_verified") in (False, None)

    send = requests.post(f"{API}/auth/whatsapp/send-otp", json={"phone_number": "+919876543210"}, headers=h)
    assert send.status_code == 200, send.text
    code = send.json().get("dev_code")
    assert code, f"no dev_code in response: {send.json()}"

    v = requests.post(f"{API}/auth/whatsapp/verify-otp", json={"code": code}, headers=h)
    assert v.status_code == 200, v.text
    assert v.json().get("success") is True

    me1 = requests.get(f"{API}/auth/me", headers=h).json()
    assert me1.get("whatsapp_verified") is True


# --- Item 2 re-test: /store/skus + /store/my-entitlements both work (powers quota card) ---
def test_quota_card_data_sources(user_token):
    h = _auth(user_token)
    skus = requests.get(f"{API}/store/skus", headers=h)
    assert skus.status_code == 200
    body = skus.json()
    assert "skus" in body and isinstance(body["skus"], list)

    ents = requests.get(f"{API}/store/my-entitlements", headers=h)
    assert ents.status_code == 200
    ej = ents.json()
    assert "entitlements" in ej and isinstance(ej["entitlements"], list)
