"""
Iter82 — Partner Embed P1: widget + loader.js + demo-host + RN web embed route
Backend smoke for the widget delivery routes.
"""
import os
import json
from urllib.parse import quote
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://pros-cons-engine.preview.emergentagent.com"
SLUG = "pmsbazaar-demo"


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- Public config sanity ----------------
class TestPublicConfig:
    def test_public_config_pmsbazaar(self, client):
        r = client.get(f"{BASE_URL}/api/embed/public-config/{SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["theme"]["primary_color"] == "#7B1E3B"
        assert d["branding_mode"] == "white_label"
        assert "render_mode" in d
        assert "mydezider" in d["enabled_flows"]
        assert "pros_cons" in d["enabled_flows"]


# ---------------- Demo Host page ----------------
class TestDemoHost:
    def test_demo_host_returns_200_with_themed_compare(self, client):
        r = client.get(f"{BASE_URL}/api/embed/demo-host/{SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        body = r.text
        # Maroon theme present
        assert "#7B1E3B" in body
        # Sample compare items present
        assert "Money Grow" in body
        assert "Hem Securities" in body
        assert "Green Portfolio" in body
        # Help me Decide CTA
        assert "Help me Decide" in body
        assert 'id="decideBtn"' in body
        # Loader is wired in
        assert f"/api/embed/decision/{SLUG}/loader.js" in body
        # Iframe-safe header
        csp = r.headers.get("content-security-policy", "")
        assert "frame-ancestors *" in csp

    def test_demo_host_unknown_slug_404(self, client):
        r = client.get(f"{BASE_URL}/api/embed/demo-host/nope-xyz", timeout=15)
        assert r.status_code == 404


# ---------------- Loader JS ----------------
class TestLoaderJS:
    def test_loader_js_returns_javascript(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/loader.js", timeout=15)
        assert r.status_code == 200, r.text
        ctype = r.headers.get("content-type", "")
        assert "javascript" in ctype.lower(), f"Wrong content-type: {ctype}"
        js = r.text
        assert "window.Dezider" in js
        assert "dezider-modal" in js
        assert "dezider-frame" in js
        # Slug baked in
        assert SLUG in js


# ---------------- HTML widget (html_widget mode) ----------------
class TestHtmlWidget:
    def test_html_widget_pros_cons_renders(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/pros_cons", timeout=15)
        assert r.status_code == 200, r.text
        body = r.text
        assert "#7B1E3B" in body
        assert "Pros &amp; Cons" in body or "Pros & Cons" in body
        # Iframe-safe header
        csp = r.headers.get("content-security-policy", "")
        assert "frame-ancestors *" in csp

    def test_html_widget_carries_over_options(self, client):
        options = [{"name": "Money Grow", "attributes": {"1Y": "44%"}}]
        url = f"{BASE_URL}/api/embed/decision/{SLUG}/pros_cons?options={quote(json.dumps(options))}"
        r = client.get(url, timeout=15)
        assert r.status_code == 200, r.text
        body = r.text
        assert "Money Grow" in body
        assert "carried over" in body.lower()

    def test_html_widget_unknown_flow_404(self, client):
        r = client.get(f"{BASE_URL}/api/embed/decision/{SLUG}/nope", timeout=15)
        assert r.status_code == 404


# ---------------- RN web embed route (HTML shell from Expo) ----------------
class TestRnWebEmbedRoute:
    def test_embed_mydezider_route_returns_200_html_shell(self, client):
        """The RN web route (served by Expo) should respond with the SPA shell.
        The shell is JS-driven; data fetching happens client-side. Here we only
        assert the route is reachable and returns HTML (not 404)."""
        r = client.get(
            f"{BASE_URL}/embed/mydezider?partner={SLUG}", timeout=20,
            allow_redirects=True,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:300]}"
        ctype = r.headers.get("content-type", "")
        assert "text/html" in ctype.lower(), f"Unexpected content-type: {ctype}"
