"""
Iter 81 — Partner Embed Foundation (P0) backend tests.

Covers:
  * Org login fix: org-login token MUST authenticate downstream /api/auth/me
  * Admin-configurable per-partner OTP toggle (via embed config)
  * verify-otp tz datetime fix (no 500)
  * Public embed config (no auth) + 404 on unknown slug
  * Admin config CRUD + non-admin 403 + partners list
  * Legal gate for scraping
  * Enum validation (branding_mode / auth_mode / billing_mode / enabled_flows)
  * Regression smoke: /api/health, normal email/password login, /auth/me
"""
from __future__ import annotations

import os
import uuid
import pytest
import requests

# Public preview URL (used by mobile/web client). Falls back to localhost for
# Kubernetes-internal runs.
BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"

ORG_SLUG = "pmsbazaar-demo"
ORG_MEMBER_EMAIL = "analyst@pmsbazaar-demo.com"
ORG_MEMBER_PASSWORD = "PmsAnalyst2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


# ---------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------
class _NoCookieClient:
    """Thin wrapper around requests that NEVER persists cookies between
    calls — critical because /auth/me reads `session_token` from cookies
    BEFORE the Authorization header. A regular requests.Session() would
    silently authenticate every request as whichever user logged in last.
    """

    def _kwargs(self, kwargs):
        kwargs.setdefault("timeout", 30)
        kwargs["cookies"] = {}
        kwargs.setdefault("headers", {}).setdefault("Content-Type", "application/json")
        return kwargs

    def get(self, url, **kwargs):
        return requests.get(url, **self._kwargs(kwargs))

    def post(self, url, **kwargs):
        return requests.post(url, **self._kwargs(kwargs))

    def put(self, url, **kwargs):
        return requests.put(url, **self._kwargs(kwargs))


@pytest.fixture(scope="session")
def http():
    return _NoCookieClient()


@pytest.fixture(scope="session")
def admin_token(http) -> str:
    r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no admin token in response: {r.json()}"
    return tok


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _baseline_config() -> dict:
    """The frictionless baseline state we want the demo left in."""
    return {
        "allowed_origins": ["pmsbazaar.com", "www.pmsbazaar.com"],
        "branding_mode": "white_label",
        "enabled_flows": ["mydezider", "pros_cons", "screener"],
        "theme": {
            "primary_color": "#7B1E3B",
            "accent_color": "#C9A227",
            "logo_uri": None,
            "font_family": None,
            "hide_powered_by": False,
        },
        "auth_mode": "frictionless",
        "otp_required": False,
        "expose_dev_code": True,
        "screener_pricing": {
            "base_credits": 1.0,
            "per_candidate": 0.01,
            "per_finalist": 0.1,
            "per_factor": 0.05,
            "billing_mode": "end_user",
        },
        "ingestion": {
            "api_enabled": False,
            "api_endpoint": None,
            "api_auth_header": None,
            "csv_sheet_enabled": True,
            "scrape_enabled": False,
            "scrape_legal_ack": False,
            "scrape_terms_ack": False,
        },
    }


# ---------------------------------------------------------------
# regression smoke
# ---------------------------------------------------------------
class TestRegressionSmoke:
    def test_health(self, http):
        r = http.get(f"{API}/health")
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "ok"

    def test_admin_login_and_me(self, http, admin_token):
        r = http.get(f"{API}/auth/me", headers=_auth_headers(admin_token))
        assert r.status_code == 200, f"/auth/me failed for admin: {r.status_code} {r.text}"
        body = r.json()
        # Admin user payload should expose email
        assert (body.get("email") or body.get("user", {}).get("email")) == ADMIN_EMAIL


# ---------------------------------------------------------------
# Public embed config
# ---------------------------------------------------------------
class TestPublicEmbedConfig:
    def test_public_config_ok(self, http):
        r = http.get(f"{API}/embed/public-config/{ORG_SLUG}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("slug") == ORG_SLUG
        assert body.get("branding_mode") == "white_label"
        assert body["theme"]["primary_color"].upper() == "#7B1E3B"
        flows = body.get("enabled_flows") or []
        for f in ("mydezider", "pros_cons", "screener"):
            assert f in flows, f"flow {f} missing from public config: {flows}"

    def test_public_config_404_unknown(self, http):
        r = http.get(f"{API}/embed/public-config/does-not-exist-{uuid.uuid4().hex[:6]}")
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------
# Admin config CRUD + RBAC
# ---------------------------------------------------------------
class TestAdminConfigCRUD:
    def test_admin_get_config(self, http, admin_token):
        r = http.get(f"{API}/embed/config/{ORG_SLUG}", headers=_auth_headers(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("org", {}).get("slug") == ORG_SLUG

    def test_non_admin_get_config_403(self, http):
        # Org-login (frictionless) → token must NOT be able to read admin config
        login = http.post(
            f"{API}/org-auth/login",
            json={"org_slug": ORG_SLUG, "email": ORG_MEMBER_EMAIL, "password": ORG_MEMBER_PASSWORD},
        )
        assert login.status_code == 200, login.text
        tok = login.json().get("session_token")
        assert tok, f"frictionless login should return session_token: {login.json()}"
        r = http.get(f"{API}/embed/config/{ORG_SLUG}", headers=_auth_headers(tok))
        assert r.status_code == 403, f"expected 403 for non-admin, got {r.status_code}: {r.text}"

    def test_admin_list_partners_includes_demo(self, http, admin_token):
        r = http.get(f"{API}/embed/partners", headers=_auth_headers(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        slugs = [p.get("slug") for p in body.get("partners", [])]
        assert ORG_SLUG in slugs, f"{ORG_SLUG} not in partners list: {slugs}"


# ---------------------------------------------------------------
# CRITICAL: org login fix — org-login token authenticates downstream
# ---------------------------------------------------------------
class TestOrgLoginFixCritical:
    def test_org_login_frictionless_session_works_on_auth_me(self, http, admin_token):
        # Ensure frictionless state first
        put = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=_baseline_config(),
            headers=_auth_headers(admin_token),
        )
        assert put.status_code == 200, f"baseline PUT failed: {put.status_code} {put.text}"

        r = http.post(
            f"{API}/org-auth/login",
            json={"org_slug": ORG_SLUG, "email": ORG_MEMBER_EMAIL, "password": ORG_MEMBER_PASSWORD},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "authenticated", f"unexpected status: {body}"
        tok = body.get("session_token")
        assert tok and tok.startswith("session_"), f"bad token shape: {tok}"

        # The core bug: previously the token never authenticated /auth/me
        me = http.get(f"{API}/auth/me", headers=_auth_headers(tok))
        assert me.status_code == 200, (
            f"CRITICAL — org-login token failed /auth/me: {me.status_code} {me.text}"
        )
        me_body = me.json()
        email = me_body.get("email") or me_body.get("user", {}).get("email")
        assert email == ORG_MEMBER_EMAIL


# ---------------------------------------------------------------
# Admin OTP toggle + verify-otp datetime fix
# ---------------------------------------------------------------
class TestOTPToggleAndVerifyFix:
    def test_full_otp_path(self, http, admin_token):
        # Toggle OTP ON via admin config
        cfg = _baseline_config()
        cfg["auth_mode"] = "otp"
        cfg["otp_required"] = True
        cfg["expose_dev_code"] = True
        put = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert put.status_code == 200, put.text

        try:
            # Login should now require OTP
            r = http.post(
                f"{API}/org-auth/login",
                json={
                    "org_slug": ORG_SLUG,
                    "email": ORG_MEMBER_EMAIL,
                    "password": ORG_MEMBER_PASSWORD,
                },
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("status") == "otp_required", f"unexpected: {body}"
            vid = body.get("verification_id")
            dev_code = body.get("dev_code")
            assert vid, "no verification_id"
            assert dev_code and dev_code.isdigit() and len(dev_code) == 6, f"bad dev_code: {dev_code}"

            # verify-otp must not 500 (tz fix) and must return a working session_token
            v = http.post(
                f"{API}/org-auth/verify-otp",
                json={"verification_id": vid, "otp": dev_code},
            )
            assert v.status_code == 200, f"verify-otp failed: {v.status_code} {v.text}"
            vb = v.json()
            assert vb.get("status") == "authenticated"
            tok = vb.get("session_token")
            assert tok

            me = http.get(f"{API}/auth/me", headers=_auth_headers(tok))
            assert me.status_code == 200, f"/auth/me failed after OTP: {me.status_code} {me.text}"
        finally:
            # ALWAYS restore frictionless baseline so the demo stays usable.
            restore = http.put(
                f"{API}/embed/config/{ORG_SLUG}",
                json=_baseline_config(),
                headers=_auth_headers(admin_token),
            )
            assert restore.status_code == 200, f"restore failed: {restore.status_code} {restore.text}"


# ---------------------------------------------------------------
# Legal gate for scraping
# ---------------------------------------------------------------
class TestLegalGate:
    def test_scrape_enabled_without_acks_400(self, http, admin_token):
        cfg = _baseline_config()
        cfg["ingestion"]["scrape_enabled"] = True
        cfg["ingestion"]["scrape_legal_ack"] = False
        cfg["ingestion"]["scrape_terms_ack"] = False
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    def test_scrape_enabled_partial_ack_400(self, http, admin_token):
        cfg = _baseline_config()
        cfg["ingestion"]["scrape_enabled"] = True
        cfg["ingestion"]["scrape_legal_ack"] = True
        cfg["ingestion"]["scrape_terms_ack"] = False
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 400, r.text

    def test_scrape_enabled_both_acks_200_then_restore(self, http, admin_token):
        cfg = _baseline_config()
        cfg["ingestion"]["scrape_enabled"] = True
        cfg["ingestion"]["scrape_legal_ack"] = True
        cfg["ingestion"]["scrape_terms_ack"] = True
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 200, r.text
        # restore
        restore = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=_baseline_config(),
            headers=_auth_headers(admin_token),
        )
        assert restore.status_code == 200, restore.text


# ---------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------
class TestEnumValidation:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("branding_mode", "rainbow"),
            ("auth_mode", "telepathy"),
        ],
    )
    def test_invalid_top_level_enum(self, http, admin_token, field, value):
        cfg = _baseline_config()
        cfg[field] = value
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 400, f"expected 400 for {field}={value}, got {r.status_code}: {r.text}"

    def test_invalid_billing_mode(self, http, admin_token):
        cfg = _baseline_config()
        cfg["screener_pricing"]["billing_mode"] = "crypto"
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 400, r.text

    def test_invalid_enabled_flows(self, http, admin_token):
        cfg = _baseline_config()
        cfg["enabled_flows"] = ["mydezider", "tarot_reading"]
        r = http.put(
            f"{API}/embed/config/{ORG_SLUG}",
            json=cfg,
            headers=_auth_headers(admin_token),
        )
        assert r.status_code == 400, r.text


# ---------------------------------------------------------------
# Final teardown safety net — make sure baseline is restored at session end
# ---------------------------------------------------------------
def test_zz_restore_baseline_final(http, admin_token):
    r = http.put(
        f"{API}/embed/config/{ORG_SLUG}",
        json=_baseline_config(),
        headers=_auth_headers(admin_token),
    )
    assert r.status_code == 200, r.text
    pub = http.get(f"{API}/embed/public-config/{ORG_SLUG}")
    assert pub.status_code == 200
    body = pub.json()
    assert body.get("auth_mode") == "frictionless"
    assert body.get("otp_required") is False
