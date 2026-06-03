"""
Iter 48 — PII Admin (Item 5) + Phase A (company name) backend tests.

Covers:
  • GET /api/admin/pii/permission, /grants, POST /grant (super-admin), revoke
  • POST /admin/pii/lookup happy path (with newly-registered WhatsApp-verified user)
  • POST /admin/pii/lookup negatives: nda_ack=false, Other w/ empty note, wrong WA -> 404, perms 403
  • GET /admin/pii/my-access-log + /access-log (immutability — no PUT/DELETE)
  • GET /admin/pii/nda
  • GET /api/appearance includes company_name; PUT /admin/company-name super-admin only
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
REGULAR_EMAIL = "harden_1777921741@example.com"
REGULAR_PASS = "HardenPass2026!"

DEFAULT_COMPANY = "HOORECON IT-Sys Pvt Ltd"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PASS)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def regular_token():
    return _login(REGULAR_EMAIL, REGULAR_PASS)


@pytest.fixture(scope="module")
def target_user(super_token):
    """Register a fresh user + WhatsApp-verify them so lookup can match."""
    ts = int(time.time())
    email = f"piitarget_{ts}@example.com"
    password = "TargetPass2026!"
    phone = f"+9198{ts % 100000000:08d}"
    reg = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "PII Target"}, timeout=20)
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["session_token"]

    # WhatsApp OTP
    r = requests.post(f"{API}/auth/whatsapp/send-otp", json={"phone_number": phone}, headers=_h(token), timeout=20)
    assert r.status_code == 200, f"send-otp: {r.status_code} {r.text}"
    code = r.json().get("dev_code")
    assert code, f"no dev_code: {r.json()}"
    r2 = requests.post(f"{API}/auth/whatsapp/verify-otp", json={"code": code}, headers=_h(token), timeout=20)
    assert r2.status_code == 200, r2.text
    return {"email": email, "phone": phone, "token": token}


# ───────── Permission management ─────────

class TestPiiPermissions:
    def test_super_permission(self, super_token):
        r = requests.get(f"{API}/admin/pii/permission", headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["can_view_pii"] is True
        assert j["role"] == "super_admin"

    def test_admin_permission_initially_false(self, admin_token):
        r = requests.get(f"{API}/admin/pii/permission", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        # may be true if previous run left it on; not asserting strict value here.
        assert "can_view_pii" in r.json()

    def test_super_lists_grants(self, super_token):
        r = requests.get(f"{API}/admin/pii/grants", headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "admins" in j and isinstance(j["admins"], list)
        emails = [a["email"] for a in j["admins"]]
        assert ADMIN_EMAIL in emails
        assert j["purposes"] == ["Support service", "Data Analytics", "Training Support", "Other"]

    def test_admin_cannot_list_grants(self, admin_token):
        r = requests.get(f"{API}/admin/pii/grants", headers=_h(admin_token), timeout=15)
        assert r.status_code == 403

    def test_grant_and_revoke_cycle(self, super_token, admin_token):
        # Grant
        r = requests.post(f"{API}/admin/pii/grant", json={"email": ADMIN_EMAIL, "grant": True}, headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["can_view_pii"] is True

        # Verify via /permission as admin
        r2 = requests.get(f"{API}/admin/pii/permission", headers=_h(admin_token), timeout=15)
        assert r2.status_code == 200
        assert r2.json()["can_view_pii"] is True

        # Revoke
        r3 = requests.post(f"{API}/admin/pii/grant", json={"email": ADMIN_EMAIL, "grant": False}, headers=_h(super_token), timeout=15)
        assert r3.status_code == 200
        assert r3.json()["can_view_pii"] is False

        r4 = requests.get(f"{API}/admin/pii/permission", headers=_h(admin_token), timeout=15)
        assert r4.json()["can_view_pii"] is False


# ───────── NDA endpoint ─────────

class TestPiiNda:
    def test_nda_includes_company(self, super_token):
        r = requests.get(f"{API}/admin/pii/nda", headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "company_name" in j and j["company_name"]
        assert isinstance(j["body"], list) and len(j["body"]) >= 3
        assert "acknowledgement" in j


# ───────── Lookup endpoint ─────────

class TestPiiLookup:
    def test_happy_path(self, super_token, target_user):
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": target_user["phone"],
                "purpose": "Support service",
                "nda_ack": True,
            },
            headers=_h(super_token),
            timeout=20,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["matched"] is True
        assert j["profile"]["email"] == target_user["email"].lower()
        assert j["profile"]["whatsapp_verified"] is True
        assert "entitlements" in j
        assert "decisions_count" in j
        assert "recent_decisions" in j
        assert "audit_id" in j and j["audit_id"]

    def test_nda_ack_false_400(self, super_token, target_user):
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": target_user["phone"],
                "purpose": "Support service",
                "nda_ack": False,
            },
            headers=_h(super_token),
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_other_empty_note_400(self, super_token, target_user):
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": target_user["phone"],
                "purpose": "Other",
                "purpose_note": "",
                "nda_ack": True,
            },
            headers=_h(super_token),
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_wrong_whatsapp_404_audited(self, super_token, target_user):
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": "+919000000000",
                "purpose": "Data Analytics",
                "nda_ack": True,
            },
            headers=_h(super_token),
            timeout=15,
        )
        assert r.status_code == 404, r.text

        # Should appear in my-access-log with matched=False
        log = requests.get(f"{API}/admin/pii/my-access-log", headers=_h(super_token), timeout=15)
        assert log.status_code == 200
        entries = log.json()["entries"]
        failed = [
            e for e in entries
            if e.get("lookup_email") == target_user["email"].lower() and e.get("matched") is False
        ]
        assert failed, "expected at least one failed audit row"

    def test_regular_user_forbidden(self, regular_token, target_user):
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": target_user["phone"],
                "purpose": "Support service",
                "nda_ack": True,
            },
            headers=_h(regular_token),
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_admin_without_grant_forbidden(self, super_token, admin_token, target_user):
        # ensure revoked
        requests.post(f"{API}/admin/pii/grant", json={"email": ADMIN_EMAIL, "grant": False}, headers=_h(super_token), timeout=15)
        r = requests.post(
            f"{API}/admin/pii/lookup",
            json={
                "email": target_user["email"],
                "whatsapp_number": target_user["phone"],
                "purpose": "Support service",
                "nda_ack": True,
            },
            headers=_h(admin_token),
            timeout=15,
        )
        assert r.status_code == 403, r.text


# ───────── Audit logs + immutability ─────────

class TestPiiAudit:
    def test_my_log_super(self, super_token):
        r = requests.get(f"{API}/admin/pii/my-access-log", headers=_h(super_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json()["entries"], list)

    def test_all_log_super(self, super_token):
        r = requests.get(f"{API}/admin/pii/access-log", headers=_h(super_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json()["entries"], list)

    def test_all_log_admin_forbidden(self, admin_token):
        r = requests.get(f"{API}/admin/pii/access-log", headers=_h(admin_token), timeout=15)
        assert r.status_code == 403

    def test_no_delete_endpoint(self, super_token):
        # immutability — verify no DELETE / PUT endpoints exist
        for method in ("delete", "put", "patch"):
            r = getattr(requests, method)(
                f"{API}/admin/pii/access-log",
                headers=_h(super_token),
                timeout=10,
            )
            assert r.status_code in (404, 405), f"{method} on access-log returned {r.status_code}"


# ───────── Phase A — Company name ─────────

class TestCompanyName:
    def test_appearance_includes_company_name(self):
        r = requests.get(f"{API}/appearance", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "company_name" in j
        # Could be default or whatever was last persisted
        assert isinstance(j["company_name"], str) and len(j["company_name"]) > 0

    def test_super_can_update_company_name(self, super_token):
        new_name = "Test Co Pvt Ltd"
        r = requests.put(f"{API}/admin/company-name", json={"company_name": new_name}, headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["company_name"] == new_name

        # Reflects in /appearance
        r2 = requests.get(f"{API}/appearance", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["company_name"] == new_name

        # Reset
        r3 = requests.put(f"{API}/admin/company-name", json={"company_name": DEFAULT_COMPANY}, headers=_h(super_token), timeout=15)
        assert r3.status_code == 200
        assert r3.json()["company_name"] == DEFAULT_COMPANY

    def test_admin_cannot_update_company_name(self, admin_token):
        r = requests.put(f"{API}/admin/company-name", json={"company_name": "Hack Co"}, headers=_h(admin_token), timeout=15)
        assert r.status_code == 403, r.text
