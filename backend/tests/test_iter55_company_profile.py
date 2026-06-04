"""
Iter 55 — Admin Company Profile (brand/legal/contact) via /api/appearance.

Covers:
- Public GET /api/appearance returns new keys (brand_name, tagline, legal_name,
  company_name, address, phone, email, website, support_hours) with defaults.
- PUT /api/admin/company-info as Super Admin updates fields; GET reflects them.
- Non-super-admin PUT → 403.
- Cleanup: restore production-like defaults at end.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or \
           os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

DEFAULTS = {
    "brand_name": "JELCOS AI",
    "legal_name": "HOORECON IT-Sys Pvt Ltd",
    "phone": "+(91)-(0)44-46972104",
    "email": "admin@hoorecon.com",
    "website": "www.hoorecon.com",
    "tagline": "Joyful Executive's Life Choices Operating System — Powered by AI",
    "address": (
        "Innov8 Millenia, 2nd Floor, East Wing, RMZ,\n"
        "Millennia Business Park, Campus 1A, No. 143,\n"
        "MGR Road (North Veeranam Salai), Perungudi,\n"
        "Sholinganallur, Chennai-600096, Tamil Nadu, India."
    ),
    "support_hours": "Monday–Friday, 10:00 AM – 6:00 PM IST",
}


# ───────────────────────── Fixtures ─────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, password):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    return r


@pytest.fixture(scope="module")
def super_token(session):
    r = _login(session, SUPER_EMAIL, SUPER_PASS)
    if r.status_code != 200:
        pytest.skip(f"Super admin login failed: {r.status_code} {r.text[:120]}")
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token(session):
    r = _login(session, ADMIN_EMAIL, ADMIN_PASS)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:120]}")
    return r.json().get("session_token") or r.json().get("token")


# ───────────────────────── Public appearance ─────────────────────────
class TestGetAppearance:
    REQUIRED_KEYS = {
        "font_family", "company_name", "brand_name", "tagline", "legal_name",
        "address", "phone", "email", "website", "support_hours",
    }

    def test_get_appearance_returns_new_fields(self, session):
        r = session.get(f"{API}/appearance", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"missing keys: {missing}"

    def test_defaults_when_not_configured(self, session):
        # Just sanity: values are non-empty strings
        data = session.get(f"{API}/appearance", timeout=15).json()
        for k in ("brand_name", "tagline", "legal_name", "company_name",
                  "address", "phone", "email", "website", "support_hours"):
            assert isinstance(data.get(k), str) and len(data.get(k)) > 0, f"empty {k}"


# ───────────────────────── Auth on PUT ─────────────────────────
class TestCompanyInfoAuth:
    def test_non_super_admin_forbidden(self, session, admin_token):
        r = session.put(
            f"{API}/admin/company-info",
            json={"brand_name": "Should Not Apply"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code} body={r.text[:200]}"

    def test_unauthenticated_forbidden(self, session):
        r = session.put(f"{API}/admin/company-info", json={"brand_name": "X"}, timeout=15)
        assert r.status_code in (401, 403)


# ───────── PUT + GET round-trip as Super Admin ─────────
class TestCompanyInfoUpdate:
    QA_PAYLOAD = {
        "brand_name": "JELCOS AI",
        "legal_name": "QA Legal Entity Pvt Ltd",
        "phone": "+91 99999 11111",
        "email": "qa@example.com",
        "website": "qa.example.com",
        "address": "12 QA Street, Test City, 600001, India",
        "tagline": "QA tagline",
        "support_hours": "Mon-Sat 9-5",
    }

    def test_super_admin_put_updates(self, session, super_token):
        r = session.put(
            f"{API}/admin/company-info",
            json=self.QA_PAYLOAD,
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("success") is True
        updated = set(body.get("updated") or [])
        assert {"company_name", "brand_name", "tagline", "phone", "email",
                "website", "address", "support_hours"} <= updated, f"updated={updated}"

    def test_get_appearance_reflects_qa_values(self, session):
        data = session.get(f"{API}/appearance", timeout=15).json()
        assert data["brand_name"] == "JELCOS AI"
        assert data["legal_name"] == "QA Legal Entity Pvt Ltd"
        # `company_name` is the legacy alias for legal_name
        assert data["company_name"] == "QA Legal Entity Pvt Ltd"
        assert data["phone"] == "+91 99999 11111"
        assert data["email"] == "qa@example.com"
        assert data["website"] == "qa.example.com"
        assert data["address"] == "12 QA Street, Test City, 600001, India"
        assert data["tagline"] == "QA tagline"
        assert data["support_hours"] == "Mon-Sat 9-5"


# ───────── Cleanup / restore production-like defaults ─────────
class TestRestoreDefaults:
    def test_restore_defaults(self, session, super_token):
        r = session.put(
            f"{API}/admin/company-info",
            json=DEFAULTS,
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text

    def test_get_reflects_defaults(self, session):
        data = session.get(f"{API}/appearance", timeout=15).json()
        assert data["brand_name"] == DEFAULTS["brand_name"]
        assert data["legal_name"] == DEFAULTS["legal_name"]
        assert data["company_name"] == DEFAULTS["legal_name"]
        assert data["phone"] == DEFAULTS["phone"]
        assert data["email"] == DEFAULTS["email"]
        assert data["website"] == DEFAULTS["website"]
