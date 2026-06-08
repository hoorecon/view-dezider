"""P4 Partner Embed admin self-serve console + analytics tests."""
import os
import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://pros-cons-engine.preview.emergentagent.com").rstrip("/")
SLUG = "pmsbazaar-demo"

ADMIN = {"email": "admin@test.com", "password": "AdminPass2026!"}
ORG_MEMBER = {"email": "analyst@pmsbazaar-demo.com", "password": "PmsAnalyst2026!", "org_slug": "pmsbazaar-demo"}


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login resp: {r.json()}"
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def non_admin_headers():
    # try regular user route first for org member
    payloads = [
        ("/api/org-auth/login", ORG_MEMBER),
        ("/api/auth/login", {"email": ORG_MEMBER["email"], "password": ORG_MEMBER["password"]}),
    ]
    for url, body in payloads:
        r = requests.post(f"{BASE}{url}", json=body, timeout=20)
        if r.status_code == 200:
            j = r.json()
            tok = j.get("session_token") or j.get("token") or j.get("access_token")
            if tok:
                return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    pytest.skip("Could not log in non-admin user for RBAC check")


# ------------------------- partners list -------------------------
def test_partners_requires_admin():
    r = requests.get(f"{BASE}/api/embed/partners", timeout=20)
    assert r.status_code in (401, 403), f"expected 401/403 anon, got {r.status_code}"


def test_partners_list_admin(admin_headers):
    r = requests.get(f"{BASE}/api/embed/partners", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "partners" in j and isinstance(j["partners"], list)
    slugs = [p["slug"] for p in j["partners"]]
    assert SLUG in slugs, f"pmsbazaar-demo missing from partners: {slugs}"


# ------------------------- GET config -------------------------
def test_get_config_admin(admin_headers):
    r = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "branding_mode" in j and "render_mode" in j and "enabled_flows" in j
    assert "screener_pricing" in j and "ingestion" in j


def test_get_config_anon_401():
    r = requests.get(f"{BASE}/api/embed/config/{SLUG}", timeout=20)
    assert r.status_code in (401, 403)


# ------------------------- Analytics -------------------------
def test_analytics_admin(admin_headers):
    r = requests.get(f"{BASE}/api/embed/analytics/{SLUG}", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "totals" in j and "recent_runs" in j
    t = j["totals"]
    for k in ("runs", "candidates_ranked", "end_user_credits", "partner_credits"):
        assert k in t, f"missing key {k} in analytics totals"


def test_analytics_anon_unauth():
    r = requests.get(f"{BASE}/api/embed/analytics/{SLUG}", timeout=20)
    assert r.status_code in (401, 403)


def test_analytics_non_admin_blocked(non_admin_headers):
    r = requests.get(f"{BASE}/api/embed/analytics/{SLUG}", headers=non_admin_headers, timeout=20)
    assert r.status_code in (401, 403), f"non-admin should not access analytics, got {r.status_code}"


def test_partners_non_admin_blocked(non_admin_headers):
    r = requests.get(f"{BASE}/api/embed/partners", headers=non_admin_headers, timeout=20)
    assert r.status_code in (401, 403)


# ------------------------- Edit + Save persists -------------------------
def _base_body(cfg):
    return {
        "allowed_origins": cfg.get("allowed_origins") or [],
        "branding_mode": cfg.get("branding_mode") or "white_label",
        "render_mode": cfg.get("render_mode") or "rn_web",
        "enabled_flows": cfg.get("enabled_flows") or ["mydezider", "pros_cons", "screener"],
        "theme": cfg.get("theme") or {},
        "auth_mode": cfg.get("auth_mode") or ("otp" if cfg.get("otp_required") else "frictionless"),
        "otp_required": bool(cfg.get("otp_required", False)),
        "expose_dev_code": bool(cfg.get("expose_dev_code", True)),
        "screener_pricing": cfg.get("screener_pricing") or {},
        "ingestion": cfg.get("ingestion") or {},
    }


def test_edit_save_per_finalist_persists(admin_headers):
    # GET current
    g = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    assert g.status_code == 200, g.text
    cfg = g.json()
    body = _base_body(cfg)
    body["screener_pricing"]["per_finalist"] = 0.2
    body["screener_pricing"]["billing_mode"] = "both"

    p = requests.put(f"{BASE}/api/embed/config/{SLUG}", json=body, headers=admin_headers, timeout=20)
    assert p.status_code == 200, p.text
    assert p.json().get("ok") is True

    g2 = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    cfg2 = g2.json()
    assert abs(float(cfg2["screener_pricing"]["per_finalist"]) - 0.2) < 1e-6
    assert cfg2["screener_pricing"]["billing_mode"] == "both"


# ------------------------- LEGAL GATE -------------------------
def test_legal_gate_blocks_save(admin_headers):
    g = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    cfg = g.json()
    body = _base_body(cfg)
    body["ingestion"] = {
        **(body["ingestion"] or {}),
        "scrape_enabled": True,
        "scrape_legal_ack": False,
        "scrape_terms_ack": False,
        "csv_sheet_enabled": True,
    }
    p = requests.put(f"{BASE}/api/embed/config/{SLUG}", json=body, headers=admin_headers, timeout=20)
    assert p.status_code == 400, f"expected 400 legal gate, got {p.status_code} {p.text}"


def test_legal_gate_passes_with_acks(admin_headers):
    g = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    cfg = g.json()
    body = _base_body(cfg)
    body["ingestion"] = {
        **(body["ingestion"] or {}),
        "scrape_enabled": True,
        "scrape_legal_ack": True,
        "scrape_terms_ack": True,
        "csv_sheet_enabled": True,
    }
    p = requests.put(f"{BASE}/api/embed/config/{SLUG}", json=body, headers=admin_headers, timeout=20)
    assert p.status_code == 200, p.text


# ------------------------- Restore demo state -------------------------
def test_zzz_restore_demo_state(admin_headers):
    """Always restore pmsbazaar-demo to the sane demo state."""
    g = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    cfg = g.json()
    body = _base_body(cfg)
    body["branding_mode"] = "white_label"
    body["render_mode"] = "rn_web"
    body["enabled_flows"] = ["mydezider", "pros_cons", "screener"]
    body["otp_required"] = False
    body["auth_mode"] = "frictionless"
    body["screener_pricing"] = {
        "base_credits": float(body["screener_pricing"].get("base_credits", 1.0)),
        "per_candidate": float(body["screener_pricing"].get("per_candidate", 0.01)),
        "per_finalist": float(body["screener_pricing"].get("per_finalist", 0.1)),
        "per_factor": float(body["screener_pricing"].get("per_factor", 0.05)),
        "billing_mode": "both",
    }
    body["ingestion"] = {
        "api_enabled": bool(body["ingestion"].get("api_enabled", False)),
        "api_endpoint": body["ingestion"].get("api_endpoint"),
        "api_auth_header": body["ingestion"].get("api_auth_header"),
        "csv_sheet_enabled": True,
        "scrape_enabled": False,
        "scrape_legal_ack": False,
        "scrape_terms_ack": False,
    }
    p = requests.put(f"{BASE}/api/embed/config/{SLUG}", json=body, headers=admin_headers, timeout=20)
    assert p.status_code == 200, p.text
    g2 = requests.get(f"{BASE}/api/embed/config/{SLUG}", headers=admin_headers, timeout=20)
    cfg2 = g2.json()
    assert cfg2["render_mode"] == "rn_web"
    assert cfg2["branding_mode"] == "white_label"
    assert cfg2["otp_required"] is False
    assert cfg2["screener_pricing"]["billing_mode"] == "both"
    assert cfg2["ingestion"]["scrape_enabled"] is False
    assert cfg2["ingestion"]["csv_sheet_enabled"] is True
    assert set(cfg2["enabled_flows"]) == {"mydezider", "pros_cons", "screener"}
