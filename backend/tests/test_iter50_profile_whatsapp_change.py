"""Iter 50 — Profile patch (gender, profile_picture) + WhatsApp change-number flow."""
import os
import time
import requests
import pytest

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL") or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")

# Tiny 1x1 PNG data URL (valid)
TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

PHONE_A = "+919812340001"
PHONE_B = "+919812340002"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth(session):
    ts = int(time.time())
    email = f"iter50_{ts}@example.com"
    password = "TestPass2026!"
    r = session.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": password, "name": "Iter50 User"})
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    return {"email": email, "token": token}


class TestProfilePatch:
    def test_gender_valid(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"gender": "Male"})
        assert r.status_code == 200, r.text
        assert r.json().get("gender") == "Male"
        me = session.get(f"{BASE_URL}/api/auth/me")
        assert me.json().get("gender") == "Male"

    def test_gender_invalid(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"gender": "XYZ"})
        assert r.status_code == 400, r.text

    def test_gender_clear(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"gender": ""})
        assert r.status_code == 200, r.text
        me = session.get(f"{BASE_URL}/api/auth/me")
        assert me.json().get("gender") in (None, "")

    def test_name_update(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"name": "New Name"})
        assert r.status_code == 200, r.text
        me = session.get(f"{BASE_URL}/api/auth/me")
        assert me.json().get("name") == "New Name"

    def test_picture_set_and_remove(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"profile_picture": TINY_PNG})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("has_custom_picture") is True
        me = session.get(f"{BASE_URL}/api/auth/me").json()
        assert me.get("has_custom_picture") is True
        assert me.get("picture") == TINY_PNG

        # Remove
        r2 = session.patch(f"{BASE_URL}/api/auth/profile", json={"profile_picture": ""})
        assert r2.status_code == 200, r2.text
        me2 = session.get(f"{BASE_URL}/api/auth/me").json()
        assert me2.get("has_custom_picture") is False

    def test_picture_oversized(self, session, auth):
        # ~1.2 MB raw -> base64 ~1.6 MB
        big = "A" * (1_300_000)
        data_url = f"data:image/png;base64,{big}"
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"profile_picture": data_url})
        assert r.status_code == 400, r.text

    def test_picture_bad_mime(self, session, auth):
        r = session.patch(f"{BASE_URL}/api/auth/profile", json={"profile_picture": "data:image/gif;base64,R0lGODlhAQABAAAAACw="})
        assert r.status_code == 400, r.text


class TestAuthMeShape:
    def test_me_has_new_fields(self, session, auth):
        me = session.get(f"{BASE_URL}/api/auth/me").json()
        # Must include the new keys
        for key in ("gender", "has_custom_picture", "picture", "whatsapp_number", "whatsapp_verified"):
            assert key in me, f"missing {key} in /auth/me; got keys={list(me.keys())}"


class TestWhatsAppChangeFlow:
    def test_full_change_flow(self, session, auth):
        # 1) Send OTP for first number
        r = session.post(f"{BASE_URL}/api/auth/whatsapp/send-otp", json={"phone_number": PHONE_A})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "dev_code" in body, body
        dev_code_a = body["dev_code"]

        # 2) Verify it
        v = session.post(f"{BASE_URL}/api/auth/whatsapp/verify-otp", json={"code": dev_code_a})
        assert v.status_code == 200, v.text
        assert v.json().get("whatsapp_verified") is True

        # 3) status reflects
        st = session.get(f"{BASE_URL}/api/auth/whatsapp/status").json()
        assert st.get("whatsapp_verified") is True

        # 4) Same number -> already_verified short-circuit
        r2 = session.post(f"{BASE_URL}/api/auth/whatsapp/send-otp", json={"phone_number": PHONE_A})
        assert r2.status_code == 200, r2.text
        assert r2.json().get("already_verified") is True

        # 5) Different number -> normal OTP (NOT already_verified)
        # NOTE: 60s resend cooldown only applies if there's a pending unverified OTP.
        # After verification, the record is marked verified so a new send is allowed immediately.
        r3 = session.post(f"{BASE_URL}/api/auth/whatsapp/send-otp", json={"phone_number": PHONE_B})
        assert r3.status_code == 200, r3.text
        b3 = r3.json()
        assert not b3.get("already_verified"), b3
        assert "dev_code" in b3
        assert "delivered" in b3
        dev_code_b = b3["dev_code"]

        # 6) Verify new number
        v2 = session.post(f"{BASE_URL}/api/auth/whatsapp/verify-otp", json={"code": dev_code_b})
        assert v2.status_code == 200, v2.text

        # 7) status reflects new number, still verified
        st2 = session.get(f"{BASE_URL}/api/auth/whatsapp/status").json()
        assert st2.get("whatsapp_verified") is True
        # Normalised: PHONE_B becomes 919812340002
        assert (st2.get("whatsapp_number") or "").endswith("9812340002"), st2
