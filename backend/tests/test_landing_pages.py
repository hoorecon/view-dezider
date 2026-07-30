"""Custom landing pages CRUD tests."""
import os
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")


def test_seeded_tps_landing_page_is_public():
    r = requests.get(f"{BASE_URL}/api/lp/tps", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("slug") == "tps"
    assert "Sangamam" in body.get("title", "")
    assert len(body.get("html", "")) > 100
    assert len(body.get("css", "")) > 100
    assert body.get("active") is True


def test_unknown_slug_returns_404():
    r = requests.get(f"{BASE_URL}/api/lp/this-slug-does-not-exist", timeout=15)
    assert r.status_code == 404


def test_admin_list_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/landing-pages", timeout=15)
    assert r.status_code in (401, 403)


def test_admin_create_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/admin/landing-pages",
        json={"slug": "xyz", "title": "X"}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_admin_update_requires_auth():
    r = requests.put(
        f"{BASE_URL}/api/admin/landing-pages/tps",
        json={"active": False}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_admin_delete_requires_auth():
    r = requests.delete(f"{BASE_URL}/api/admin/landing-pages/tps", timeout=15)
    assert r.status_code in (401, 403)


def test_reserved_slugs_covered():
    """The list of reserved slugs must include the critical Expo route
    prefixes so admin can never create /admin, /api, /quiz etc."""
    from routes.landing_pages import RESERVED_SLUGS
    for critical in ("admin", "api", "auth", "quiz", "tools", "prr"):
        assert critical in RESERVED_SLUGS


def test_generate_from_template_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/admin/landing-pages/generate-from-template",
        json={"ribbon": "TEST"}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_template_renderer_produces_html_and_css():
    """Direct call to the renderer — verifies structure without needing auth."""
    from routes.landing_pages import EventTemplateData, _render_event_template
    d = EventTemplateData(
        ribbon="HELLO",
        details=[{"icon": "📅", "label": "Date", "value": "1 Aug", "highlight": False}],
        chips=[{"emoji": "🧠", "text": "AI Powered"}],
    )
    r = _render_event_template(d)
    assert "HELLO" in r["html"]
    assert "AI Powered" in r["html"]
    assert "lp-wrap" in r["css"]
    # HTML-escape check: script tags in inputs must be escaped
    d_evil = EventTemplateData(ribbon="<script>alert(1)</script>")
    r_evil = _render_event_template(d_evil)
    assert "<script>alert(1)</script>" not in r_evil["html"]
    assert "&lt;script&gt;" in r_evil["html"]
