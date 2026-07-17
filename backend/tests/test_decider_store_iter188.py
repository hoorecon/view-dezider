"""Iter 188 — The Decider Store: public + admin + clone tests.

Runs against the public preview URL derived from frontend/.env (EXPO_PUBLIC_BACKEND_URL).
"""
import base64
import os
import pytest
import requests

# Resolve BASE_URL from frontend .env (EXPO_PUBLIC_BACKEND_URL)
def _base_url() -> str:
    env_path = "/app/frontend/.env"
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")

BASE_URL = _base_url()
API = f"{BASE_URL}/api"
XLSX_PATH = "/app/backend/scripts/data/Business_Model_Assessments.xlsx"

ADMIN_EMAIL = "super@test.com"
ADMIN_PASS = "SuperPass2026!"


# ── Fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_headers(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC (no auth)
# ══════════════════════════════════════════════════════════════════════════
class TestPublicNoAuth:
    def test_list_store_no_auth(self, s):
        r = s.get(f"{API}/decider-store", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data and isinstance(data["templates"], list)
        # find seeded bmp
        bmp = next((t for t in data["templates"] if t.get("template_id") == "bmp-55-patterns"), None)
        assert bmp is not None, "bmp-55-patterns not found in public list"
        assert bmp["title"] == "The 55 Business Model Patterns"
        assert bmp["factor_count"] == 10
        assert bmp["option_count"] == 54
        assert bmp["pricing_type"] == "free"
        assert set(bmp["allowed_clone_modes"]) == {"full", "values_only"}

    def test_meta_categories(self, s):
        r = s.get(f"{API}/decider-store/meta", timeout=30)
        assert r.status_code == 200
        data = r.json()
        keys = [c["key"] for c in data.get("categories", [])]
        assert "Financial" in keys, f"expected 'Financial' in categories, got {keys}"

    def test_bmp_detail_no_auth(self, s):
        r = s.get(f"{API}/decider-store/bmp-55-patterns", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data.get("factors", [])) == 10
        assert len(data.get("options", [])) == 54
        # ensure no mongo _id leaked
        assert "_id" not in data

    def test_import_template_xlsx_no_auth(self, s):
        r = s.get(f"{API}/decider-store/import-template.xlsx", timeout=30)
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "").lower()
        assert len(r.content) > 500

    def test_public_detail_404_for_missing(self, s):
        r = s.get(f"{API}/decider-store/does-not-exist-xxx", timeout=30)
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# ADMIN: import excel / create / update / authorize / delete
# ══════════════════════════════════════════════════════════════════════════
class TestAdminFlow:
    _created_id = None

    def test_import_excel_non_admin_gets_403(self):
        # Minimal payload — we only need to verify auth guard, not parse
        r = requests.post(f"{API}/decider-store/import/excel",
                          json={"file_b64": "AA=="}, timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_import_excel_admin_ok(self, s, admin_headers):
        with open(XLSX_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = s.post(f"{API}/decider-store/import/excel", json={"file_b64": b64},
                   headers=admin_headers, timeout=60)
        assert r.status_code == 200, f"import failed {r.status_code} {r.text[:200]}"
        data = r.json()
        assert len(data["factors"]) == 10
        assert len(data["options"]) == 54
        # stash for next test
        TestAdminFlow._parsed = data

    def test_create_authorize_update_delete(self, s, admin_headers):
        parsed = getattr(TestAdminFlow, "_parsed", None)
        assert parsed is not None, "prior import test must have set _parsed"
        # CREATE
        body = {
            "title": "TEST_BMP_iter188",
            "subtitle": "test",
            "description": "test template",
            "category": "Financial",
            "decision_type": "aspiration",
            "pricing_type": "free",
            "allowed_clone_modes": ["full", "values_only"],
            "factors": parsed["factors"],
            "options": parsed["options"],
        }
        r = s.post(f"{API}/decider-store", json=body, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        created = r.json()
        assert created["status"] == "authorized"
        assert created["is_public"] is True
        tid = created["template_id"]
        TestAdminFlow._created_id = tid

        # GET public (should now be visible)
        r = s.get(f"{API}/decider-store/{tid}", timeout=30)
        assert r.status_code == 200
        assert r.json()["title"] == "TEST_BMP_iter188"

        # UPDATE — change classification of first factor to mandatory / priority 5
        updated_factors = parsed["factors"][:]
        updated_factors[0] = {**updated_factors[0], "category": "mandatory", "priority": 5}
        r = s.put(f"{API}/decider-store/{tid}", json={"factors": updated_factors},
                  headers=admin_headers, timeout=30)
        assert r.status_code == 200

        # verify GET reflects update
        r = s.get(f"{API}/decider-store/{tid}", timeout=30)
        assert r.status_code == 200
        f0 = r.json()["factors"][0]
        assert f0.get("category") == "mandatory"
        assert f0.get("priority") == 5

        # AUTHORIZE (idempotent)
        r = s.post(f"{API}/decider-store/{tid}/authorize", headers=admin_headers, timeout=30)
        assert r.status_code == 200

        # DELETE
        r = s.delete(f"{API}/decider-store/{tid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # GET now → 404
        r = s.get(f"{API}/decider-store/{tid}", timeout=30)
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# CLONE → MyDezider decision prefill
# ══════════════════════════════════════════════════════════════════════════
class TestCloneFlow:
    def test_clone_full(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/clone",
                   json={"mode": "full"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        did = data["decision_id"]
        assert data["factors"] == 10
        assert data["options"] == 54

        # fetch decision
        r = s.get(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        dec = r.json()
        assert len(dec["factors"]) == 10
        assert len(dec["options"]) == 54
        f0 = dec["factors"][0]
        # FULL: category present (primary/mandatory) and rating comes from priority
        assert f0["category"] in ("primary", "mandatory", "optional")
        # Assessments include unit_value like "Solo, Startup (40%)" and percentage=None
        opt0 = dec["options"][0]
        assert len(opt0["assessments"]) > 0
        a0 = opt0["assessments"][0]
        assert a0.get("percentage") is None
        assert isinstance(a0.get("unit_value"), str) and len(a0["unit_value"]) > 0

    def test_clone_values_only(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/clone",
                   json={"mode": "values_only"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        did = data["decision_id"]
        r = s.get(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        dec = r.json()
        f0 = dec["factors"][0]
        # values_only → category=='' rating==0
        assert f0["category"] == "", f"expected empty category, got {f0.get('category')!r}"
        assert f0["rating"] == 0, f"expected rating==0, got {f0.get('rating')!r}"
        # options+assessments still present
        assert len(dec["options"]) == 54
        assert len(dec["options"][0]["assessments"]) > 0

    def test_clone_requires_auth(self):
        # Use fresh session with no cookies/auth
        r = requests.post(f"{API}/decider-store/bmp-55-patterns/clone",
                          json={"mode": "full"}, timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_paid_template_returns_402(self, s, admin_headers):
        # create a paid template, then attempt clone
        with open(XLSX_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = s.post(f"{API}/decider-store/import/excel", json={"file_b64": b64},
                   headers=admin_headers, timeout=60)
        assert r.status_code == 200
        parsed = r.json()
        body = {
            "title": "TEST_PAID_iter188",
            "category": "Financial",
            "decision_type": "aspiration",
            "pricing_type": "paid",
            "price_paise": 49900,
            "currency": "INR",
            "creator_split_pct": 70,
            "allowed_clone_modes": ["full"],
            "factors": parsed["factors"],
            "options": parsed["options"],
        }
        r = s.post(f"{API}/decider-store", json=body, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        tid = r.json()["template_id"]
        try:
            r = s.post(f"{API}/decider-store/{tid}/clone",
                       json={"mode": "full"}, headers=admin_headers, timeout=30)
            assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text[:200]}"
            body = r.json().get("detail") or {}
            assert body.get("price_paise") == 49900
        finally:
            s.delete(f"{API}/decider-store/{tid}", headers=admin_headers, timeout=30)


# ══════════════════════════════════════════════════════════════════════════
# NEGATIVE (non-admin permissions)
# ══════════════════════════════════════════════════════════════════════════
class TestNegative:
    def test_admin_all_requires_admin(self):
        r = requests.get(f"{API}/decider-store/admin/all", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"
