"""
Iter83 — RETEST of iter82 P1 bugs:
  FIX #1: Mixed-content / scheme — loader.js BAKED_ROOT must be https://,
          deriveRoot from document.currentScript must be present, and demo-host
          must reference loader via RELATIVE same-origin <script src>.
  FIX #2: org-auth login sets whatsapp_verified=true on the user and returns
          it; session token works on GET /api/auth/me and that endpoint also
          reports whatsapp_verified=true.
  REGRESSION: public-config 200, html_widget pros_cons 200 with HTTPS Start CTA,
              demo-host renders maroon themed compare with 3 sample cards.
"""
import os
import re
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
SLUG = "pmsbazaar-demo"
ORG_EMAIL = "analyst@pmsbazaar-demo.com"
ORG_PASSWORD = "PmsAnalyst2026!"


@pytest.fixture
def client():
    s = requests.Session()
    return s


# ---------------- FIX #1: scheme / mixed-content ----------------
class TestFix1LoaderScheme:
    def test_loader_js_has_https_baked_root_and_derive_root(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/loader.js", timeout=15)
        assert r.status_code == 200, r.text
        js = r.text
        # New code paths required by the fix
        assert "document.currentScript" in js, "loader.js missing document.currentScript-based ROOT derivation"
        assert "deriveRoot" in js, "loader.js missing deriveRoot() helper"
        # BAKED_ROOT must be an https URL, NOT the internal cluster host
        m = re.search(r'BAKED_ROOT\s*=\s*"([^"]+)"', js)
        assert m, "BAKED_ROOT literal not found"
        baked = m.group(1)
        assert baked.startswith("https://"), f"BAKED_ROOT must be https, got: {baked}"
        assert "emergentcf.cloud" not in baked, f"BAKED_ROOT must NOT be internal cluster URL: {baked}"
        # Sanity: window.Dezider still exposed
        assert "window.Dezider" in js

    def test_demo_host_loader_script_src_is_relative_same_origin(self, client):
        r = client.get(f"{BASE_URL}/api/embed/demo-host/{SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.text
        # The loader <script src=...> must be the RELATIVE path
        assert f'src="/api/embed/decision/{SLUG}/loader.js"' in body, \
            "demo-host loader <script> src must be relative same-origin path"
        # And it must NOT bake an absolute http:// host
        bad_http_hosts = re.findall(r'src="http://[^"]+/api/embed/decision/', body)
        assert not bad_http_hosts, f"demo-host still has http:// loader src(s): {bad_http_hosts}"
        # Verify decideBtn + theme stay intact
        assert 'id="decideBtn"' in body
        assert "#7B1E3B" in body  # maroon

    def test_html_widget_start_cta_is_https(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/pros_cons", timeout=15)
        assert r.status_code == 200
        body = r.text
        hrefs = re.findall(r'href="(https?://[^"]+/embed/[^"]+)"', body)
        assert hrefs, "no Start CTA href found in widget"
        for h in hrefs:
            assert h.startswith("https://"), f"Start CTA must be https, got: {h}"
            assert "emergentcf.cloud" not in h, f"CTA must not point to cluster host: {h}"


# ---------------- FIX #2: org-auth whatsapp_verified ----------------
class TestFix2OrgAuthWhatsAppVerified:
    def test_org_login_returns_whatsapp_verified_true(self, client):
        r = client.post(
            f"{BASE_URL}/api/org-auth/login",
            json={"org_slug": SLUG, "email": ORG_EMAIL, "password": ORG_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("status") == "authenticated"
        assert d.get("requires_otp") is False
        assert "session_token" in d
        user = d.get("user") or {}
        assert user.get("whatsapp_verified") is True, f"user.whatsapp_verified should be True, got: {user}"

    def test_session_token_works_on_auth_me_and_shows_verified(self, client):
        r = client.post(
            f"{BASE_URL}/api/org-auth/login",
            json={"org_slug": SLUG, "email": ORG_EMAIL, "password": ORG_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200
        token = r.json()["session_token"]

        me = client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert me.status_code == 200, me.text
        body = me.json()
        assert body.get("email") == ORG_EMAIL
        assert body.get("whatsapp_verified") is True, (
            f"/auth/me must show whatsapp_verified=true after org-auth login, got: {body}"
        )


# ---------------- REGRESSION ----------------
class TestRegression:
    def test_public_config_200(self, client):
        r = client.get(f"{BASE_URL}/api/embed/public-config/{SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["theme"]["primary_color"] == "#7B1E3B"
        assert d["branding_mode"] == "white_label"

    def test_demo_host_renders_themed_compare_3_cards(self, client):
        r = client.get(f"{BASE_URL}/api/embed/demo-host/{SLUG}", timeout=15)
        assert r.status_code == 200
        body = r.text
        assert "Money Grow" in body
        assert "Hem Securities" in body
        assert "Green Portfolio" in body
        # CSP iframe-safe
        assert "frame-ancestors *" in r.headers.get("content-security-policy", "")

    def test_html_widget_pros_cons_200(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/pros_cons", timeout=15)
        assert r.status_code == 200
        assert "#7B1E3B" in r.text

    def test_rn_web_embed_shell_reachable(self, client):
        r = client.get(
            f"{BASE_URL}/embed/mydezider?partner={SLUG}",
            timeout=20, allow_redirects=True,
        )
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "").lower()
