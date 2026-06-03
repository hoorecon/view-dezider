"""
Iter 49 — App Logo (super-admin) backend tests.

Covers:
  * PUT /api/admin/logo upload (PNG happy path) + GET /api/appearance + GET /api/appearance/logo
  * Validation: invalid base64, unsupported mime (image/gif), oversized (>1MB)
  * Authz: non-super-admin PUT and DELETE → 403
  * DELETE /api/admin/logo → 404 on /api/appearance/logo afterwards
  * PDF generation with logo SET and after logo REMOVED must both return 200 application/pdf
  * Regression: /api/appearance still has font_family, company_name, font_options.

IMPORTANT: leaves the logo REMOVED at the end so default branding is restored.
"""
import os
import base64
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or \
           os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

# 1x1 PNG (~70 bytes)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
TINY_PNG_DATAURL = "data:image/png;base64," + TINY_PNG_B64
# 1x1 GIF
TINY_GIF_DATAURL = (
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("session_token") or j.get("token") or j.get("access_token")
    assert tok, f"No token in login response: {j}"
    return tok, j


@pytest.fixture(scope="module")
def super_token():
    tok, _ = _login(SUPER_EMAIL, SUPER_PASS)
    return tok


@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN_EMAIL, ADMIN_PASS)
    return tok


@pytest.fixture(scope="module")
def user_token():
    """Regular user for PDF generation tests."""
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "harden_1777921741@example.com",
                            "password": "HardenPass2026!"}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Regular user login failed: {r.status_code}")
    j = r.json()
    return j.get("session_token") or j.get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ─────────────────────────── Upload happy path ───────────────────────────────
class TestLogoUpload:
    def test_initial_state_no_logo(self):
        r = requests.get(f"{BASE_URL}/api/appearance", timeout=10)
        assert r.status_code == 200
        j = r.json()
        # Could be either way depending on prior state; we'll verify after delete

    def test_super_admin_uploads_png(self, super_token):
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": TINY_PNG_DATAURL},
                         headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True
        assert j.get("has_logo") is True

    def test_appearance_shows_logo(self):
        r = requests.get(f"{BASE_URL}/api/appearance", timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j.get("has_logo") is True
        assert j.get("logo_url") == "/api/appearance/logo"
        assert int(j.get("logo_version") or 0) > 0
        # Regression: still has font + company
        assert j.get("font_family")
        assert j.get("company_name")
        assert isinstance(j.get("font_options"), list) and len(j["font_options"]) > 0

    def test_serve_logo_returns_image(self):
        r = requests.get(f"{BASE_URL}/api/appearance/logo", timeout=10)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert ct.startswith("image/"), f"Expected image content-type, got {ct}"
        assert len(r.content) > 50


# ─────────────────────────── Validation ──────────────────────────────────────
class TestLogoValidation:
    def test_invalid_base64_returns_400(self, super_token):
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": "data:image/png;base64,!!!not-valid$$$"},
                         headers=_h(super_token), timeout=10)
        assert r.status_code == 400, r.text

    def test_unsupported_mime_gif_returns_400(self, super_token):
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": TINY_GIF_DATAURL},
                         headers=_h(super_token), timeout=10)
        assert r.status_code == 400, r.text

    def test_oversized_payload_returns_400(self, super_token):
        # 1.2 MB raw → base64 ~1.6MB. Use PNG mime so it passes the mime check
        # and falls into the size check.
        big_raw = b"\x89PNG\r\n\x1a\n" + os.urandom(1024 * 1024 + 200_000)
        b64 = base64.b64encode(big_raw).decode()
        data_url = f"data:image/png;base64,{b64}"
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": data_url},
                         headers=_h(super_token), timeout=20)
        assert r.status_code == 400, r.text
        assert "1 MB" in r.text or "1MB" in r.text or "smaller" in r.text.lower()


# ─────────────────────────── AuthZ ──────────────────────────────────────────
class TestLogoAuthz:
    def test_non_super_admin_put_forbidden(self, admin_token):
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": TINY_PNG_DATAURL},
                         headers=_h(admin_token), timeout=10)
        assert r.status_code == 403, r.text

    def test_non_super_admin_delete_forbidden(self, admin_token):
        r = requests.delete(f"{BASE_URL}/api/admin/logo",
                            headers=_h(admin_token), timeout=10)
        assert r.status_code == 403, r.text

    def test_unauthenticated_put_forbidden(self):
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                         json={"logo_base64": TINY_PNG_DATAURL}, timeout=10)
        assert r.status_code in (401, 403), r.text


# ─────────────────────────── PDF with logo ──────────────────────────────────
class TestPdfWithLogo:
    def _find_or_skip_decision(self, user_token):
        """Find any existing decision for the regular user; skip if none."""
        if not user_token:
            pytest.skip("No regular user token")
        # Try common listing endpoints
        for path in ("/api/decisions", "/api/decisions/list"):
            r = requests.get(f"{BASE_URL}{path}",
                             headers={"Authorization": f"Bearer {user_token}"},
                             timeout=10)
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else (data.get("items") or data.get("decisions") or [])
                if items:
                    return items[0].get("id"), "dezider"
        # Try pros_cons
        r = requests.get(f"{BASE_URL}/api/pros-cons",
                         headers={"Authorization": f"Bearer {user_token}"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else (data.get("items") or [])
            if items:
                return items[0].get("id"), "pros_cons"
        # Try SWOT
        r = requests.get(f"{BASE_URL}/api/swot",
                         headers={"Authorization": f"Bearer {user_token}"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else (data.get("items") or [])
            if items:
                return items[0].get("id"), "swot"
        pytest.skip("No existing decision found for regular user")

    @pytest.fixture(scope="class", autouse=True)
    def _enable_skip_payment(self, super_token):
        """Flip admin global skip_payment_all_flows ON for this class so the
        regular user can download PDFs without an L1/L2 entitlement. Restore
        original setting on teardown."""
        get = requests.get(f"{BASE_URL}/api/admin/payment-settings",
                           headers=_h(super_token), timeout=10)
        original = bool((get.json() or {}).get("skip_payment_all_flows", False)) \
            if get.status_code == 200 else False
        requests.put(f"{BASE_URL}/api/admin/payment-settings",
                     json={"skip_payment_all_flows": True,
                           "skip_payment_reason": "iter49-logo-pdf-test"},
                     headers=_h(super_token), timeout=10)
        yield
        # Restore
        requests.put(f"{BASE_URL}/api/admin/payment-settings",
                     json={"skip_payment_all_flows": original,
                           "skip_payment_reason": "" if not original else "restore"},
                     headers=_h(super_token), timeout=10)

    def test_pdf_renders_with_logo_set(self, super_token, user_token):
        # Ensure logo is set
        r = requests.put(f"{BASE_URL}/api/admin/logo",
                        json={"logo_base64": TINY_PNG_DATAURL},
                        headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        decision_id, module = self._find_or_skip_decision(user_token)
        url = f"{BASE_URL}/api/reports/{module}/{decision_id}.pdf"
        r = requests.get(url,
                         headers={"Authorization": f"Bearer {user_token}"},
                         timeout=30)
        assert r.status_code == 200, f"PDF generation failed: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1000  # non-trivial PDF body

    def test_pdf_renders_after_logo_removed(self, super_token, user_token):
        # Remove logo
        r = requests.delete(f"{BASE_URL}/api/admin/logo",
                            headers=_h(super_token), timeout=10)
        assert r.status_code == 200, r.text
        decision_id, module = self._find_or_skip_decision(user_token)
        url = f"{BASE_URL}/api/reports/{module}/{decision_id}.pdf"
        r = requests.get(url,
                         headers={"Authorization": f"Bearer {user_token}"},
                         timeout=30)
        assert r.status_code == 200, f"PDF generation failed: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ─────────────────────────── Delete & cleanup ───────────────────────────────
class TestLogoDelete:
    def test_super_admin_deletes_logo(self, super_token):
        # Set then delete
        requests.put(f"{BASE_URL}/api/admin/logo",
                     json={"logo_base64": TINY_PNG_DATAURL},
                     headers=_h(super_token), timeout=15)
        r = requests.delete(f"{BASE_URL}/api/admin/logo",
                            headers=_h(super_token), timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("success") is True
        assert j.get("has_logo") is False

    def test_serve_logo_404_after_delete(self):
        r = requests.get(f"{BASE_URL}/api/appearance/logo", timeout=10)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    def test_appearance_has_logo_false_after_delete(self):
        r = requests.get(f"{BASE_URL}/api/appearance", timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j.get("has_logo") is False
        assert j.get("logo_url") is None
        # Regression intact
        assert j.get("font_family")
        assert j.get("company_name")
