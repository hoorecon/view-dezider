"""Iter 152 — Manifestation admin override + Collaboration OTP test endpoint."""
import os
import pytest
import requests

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL") or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
SUPER = {"email": "super@test.com", "password": "SuperPass2026!"}


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{BASE}/api/auth/login", json=SUPER, timeout=20)
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json()["session_token"]


@pytest.fixture(scope="module")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}"}


# ---------- Manifestation framework (public + admin) ----------

def test_public_framework_returns_7_stages():
    r = requests.get(f"{BASE}/api/goal-manifestation/framework", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data.get("stages"), list)
    assert data.get("total_stages") == 7
    assert len(data["stages"]) == 7


def test_admin_framework_requires_auth():
    r = requests.get(f"{BASE}/api/goal-manifestation/admin/framework", timeout=20)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


def test_admin_framework_get_with_super(super_headers):
    r = requests.get(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data.get("stages", [])) == 7
    assert "is_override" in data


def test_admin_framework_put_then_reset(super_headers):
    # GET baseline
    g = requests.get(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        timeout=20,
    )
    stages = g.json()["stages"]
    # Modify summary of stage 1 (mutation marker)
    stages[0]["summary"] = "TEST_iter152_marker"
    p = requests.put(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        json={"stages": stages},
        timeout=20,
    )
    assert p.status_code == 200, p.text
    assert p.json().get("saved") is True

    # Verify override now reflected
    g2 = requests.get(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        timeout=20,
    )
    assert g2.status_code == 200
    assert g2.json()["is_override"] is True
    assert g2.json()["stages"][0]["summary"] == "TEST_iter152_marker"

    # Public reflects override
    pub = requests.get(f"{BASE}/api/goal-manifestation/framework", timeout=20).json()
    assert pub["stages"][0]["summary"] == "TEST_iter152_marker"

    # Reset
    rst = requests.post(
        f"{BASE}/api/goal-manifestation/admin/framework/reset",
        headers=super_headers,
        timeout=20,
    )
    assert rst.status_code == 200
    assert rst.json().get("reset") is True

    g3 = requests.get(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        timeout=20,
    ).json()
    assert g3["is_override"] is False
    assert g3["stages"][0]["summary"] != "TEST_iter152_marker"


def test_admin_framework_put_validates_payload(super_headers):
    r = requests.put(
        f"{BASE}/api/goal-manifestation/admin/framework",
        headers=super_headers,
        json={"stages": []},
        timeout=20,
    )
    assert r.status_code == 400


# ---------- Collaboration OTP test ----------

def test_otp_test_requires_admin():
    r = requests.post(
        f"{BASE}/api/collaboration/admin/otp-test",
        json={"channel": "email", "contact": "veales.testing@gmail.com"},
        timeout=20,
    )
    assert r.status_code in (401, 403)


def test_otp_test_email(super_headers):
    r = requests.post(
        f"{BASE}/api/collaboration/admin/otp-test",
        headers=super_headers,
        json={"channel": "email", "contact": "veales.testing@gmail.com"},
        timeout=30,
    )
    assert r.status_code == 200, r.text


def test_otp_test_whatsapp(super_headers):
    r = requests.post(
        f"{BASE}/api/collaboration/admin/otp-test",
        headers=super_headers,
        json={"channel": "whatsapp", "contact": "+919999999999"},
        timeout=30,
    )
    # Allow 200 (sent) or non-fatal upstream failure surfaced as 400/502
    assert r.status_code in (200, 400, 502), r.text
