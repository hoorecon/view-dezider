"""Backend tests for TEPFI Capabilities & Resources Index — overrides + dashboard.
Tests cover: dashboard enrichment, override upsert/delete, scope isolation,
per-user permission boundary, validation.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token") or r.json()["access_token"]


def _register_throwaway():
    email = f"tepfi_{int(time.time()*1000)}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "AutoPass2026!", "name": "TepfiTest"
    }, timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    return email, body.get("session_token") or body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def userB_headers():
    _, tok = _register_throwaway()
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tepfi_entry(admin_headers):
    """Create a TEPFI entry for the admin user with some scored cells."""
    matrix = {
        "time":           {"self": {"score": 6, "description": "", "notes": ""},
                           "micro": {"score": 5, "description": "", "notes": ""},
                           "macro": {"score": 4, "description": "", "notes": ""}},
        "effort":         {"self": {"score": 7, "description": "", "notes": ""},
                           "micro": {"score": 6, "description": "", "notes": ""},
                           "macro": {"score": 5, "description": "", "notes": ""}},
        "people":         {"self": {"score": 5, "description": "", "notes": ""},
                           "micro": {"score": 6, "description": "", "notes": ""},
                           "macro": {"score": 7, "description": "", "notes": ""}},
        "finance":        {"self": {"score": 4, "description": "", "notes": ""},
                           "micro": {"score": 5, "description": "", "notes": ""},
                           "macro": {"score": 6, "description": "", "notes": ""}},
        "infrastructure": {"self": {"score": 3, "description": "", "notes": ""},
                           "micro": {"score": 4, "description": "", "notes": ""},
                           "macro": {"score": 5, "description": "", "notes": ""}},
    }
    payload = {"title": "TEST_TEPFI_overrides", "life_area": "career", "matrix": matrix, "status": "active"}
    r = requests.post(f"{API}/tepfi/entries", headers=admin_headers, json=payload, timeout=15)
    assert r.status_code == 200, f"create entry: {r.status_code} {r.text}"
    entry = r.json()
    yield entry
    requests.delete(f"{API}/tepfi/entries/{entry['entry_id']}", headers=admin_headers, timeout=15)


@pytest.fixture(autouse=True)
def cleanup_overrides(admin_headers):
    """Best-effort clean up overrides created in tests before/after each test."""
    cells = ["effort_self", "effort_micro", "time_self", "people_macro"]
    for scope in ("all", "career"):
        for ck in cells:
            requests.delete(f"{API}/tepfi/overrides/{scope}/{ck}", headers=admin_headers, timeout=10)
    yield
    for scope in ("all", "career"):
        for ck in cells:
            requests.delete(f"{API}/tepfi/overrides/{scope}/{ck}", headers=admin_headers, timeout=10)


# 1a — dashboard returns enriched cell objects (auto/score/overridden/note)
class TestDashboardEnrichment:
    def test_overall_dashboard_cells_enriched(self, admin_headers, tepfi_entry):
        r = requests.get(f"{API}/tepfi/dashboard", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "all"
        cell = body["avg_matrix"]["time"]["self"]
        assert set(cell.keys()) >= {"auto", "score", "overridden", "note"}
        assert cell["overridden"] is False
        assert cell["auto"] == cell["score"]

    def test_scoped_dashboard_cells_enriched(self, admin_headers, tepfi_entry):
        r = requests.get(f"{API}/tepfi/dashboard?life_area=career", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["scope"] == "career"
        cell = body["avg_matrix"]["effort"]["self"]
        assert cell["overridden"] is False
        # career entry has effort_self=7
        assert cell["auto"] == 7.0


# 1b — PUT override on 'all' scope reflects in dashboard
class TestOverrideAll:
    def test_put_override_all_visible_in_dashboard(self, admin_headers, tepfi_entry):
        body = {"cell_key": "effort_self", "score": 9, "note": "expert"}
        r = requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers, json=body, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        d = requests.get(f"{API}/tepfi/dashboard", headers=admin_headers, timeout=15).json()
        cell = d["avg_matrix"]["effort"]["self"]
        assert cell["overridden"] is True
        assert cell["score"] == 9.0
        assert cell["note"] == "expert"


# 1c — scope isolation: all override vs career override on same cell_key
class TestScopeIsolation:
    def test_all_and_career_overrides_do_not_bleed(self, admin_headers, tepfi_entry):
        # All-scope override: 9
        r1 = requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers,
                          json={"cell_key": "people_macro", "score": 9, "note": "all"}, timeout=15)
        assert r1.status_code == 200
        # Career-scope override: 3
        r2 = requests.put(f"{API}/tepfi/overrides/career", headers=admin_headers,
                          json={"cell_key": "people_macro", "score": 3, "note": "career"}, timeout=15)
        assert r2.status_code == 200

        all_cell = requests.get(f"{API}/tepfi/dashboard", headers=admin_headers, timeout=15).json()["avg_matrix"]["people"]["macro"]
        career_cell = requests.get(f"{API}/tepfi/dashboard?life_area=career", headers=admin_headers, timeout=15).json()["avg_matrix"]["people"]["macro"]

        assert all_cell["score"] == 9.0 and all_cell["note"] == "all"
        assert career_cell["score"] == 3.0 and career_cell["note"] == "career"


# 1d — DELETE removes the override and dashboard reverts to auto
class TestDeleteOverride:
    def test_delete_override_reverts_to_auto(self, admin_headers, tepfi_entry):
        requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers,
                     json={"cell_key": "time_self", "score": 10, "note": "x"}, timeout=15)
        d_before = requests.get(f"{API}/tepfi/dashboard", headers=admin_headers, timeout=15).json()["avg_matrix"]["time"]["self"]
        assert d_before["overridden"] is True and d_before["score"] == 10.0

        rd = requests.delete(f"{API}/tepfi/overrides/all/time_self", headers=admin_headers, timeout=15)
        assert rd.status_code == 200
        assert rd.json().get("deleted", 0) == 1

        d_after = requests.get(f"{API}/tepfi/dashboard", headers=admin_headers, timeout=15).json()["avg_matrix"]["time"]["self"]
        assert d_after["overridden"] is False
        assert d_after["score"] == d_after["auto"]


# 1e — Per-user permission boundary
class TestPerUserIsolation:
    def test_user_b_cannot_see_user_a_overrides(self, admin_headers, userB_headers, tepfi_entry):
        requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers,
                     json={"cell_key": "effort_micro", "score": 8, "note": "A only"}, timeout=15)

        b = requests.get(f"{API}/tepfi/overrides?scope=all", headers=userB_headers, timeout=15)
        assert b.status_code == 200
        b_keys = [o.get("cell_key") for o in b.json().get("overrides", [])]
        assert "effort_micro" not in b_keys, f"User B saw user A's override: {b_keys}"

        b_dash = requests.get(f"{API}/tepfi/dashboard", headers=userB_headers, timeout=15).json()
        b_cell = b_dash["avg_matrix"]["effort"]["micro"]
        assert b_cell["overridden"] is False


# 1f — Validation edge cases
class TestValidation:
    def test_cell_key_empty_returns_400(self, admin_headers):
        r = requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers,
                         json={"cell_key": "", "score": 5}, timeout=15)
        assert r.status_code == 400

    def test_score_non_numeric_returns_400(self, admin_headers):
        r = requests.put(f"{API}/tepfi/overrides/all", headers=admin_headers,
                         json={"cell_key": "time_self", "score": "abc"}, timeout=15)
        assert r.status_code == 400


# 4 — Regression: /api/tepfi/entries CRUD
class TestEntriesCRUDRegression:
    def test_crud_entries_works(self, admin_headers):
        payload = {"title": "TEST_regression", "life_area": "finance",
                   "matrix": {"time": {"self": {"score": 5, "description": "", "notes": ""}}}}
        r = requests.post(f"{API}/tepfi/entries", headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200
        eid = r.json()["entry_id"]

        g = requests.get(f"{API}/tepfi/entries/{eid}", headers=admin_headers, timeout=15)
        assert g.status_code == 200
        assert g.json()["title"] == "TEST_regression"

        u = requests.put(f"{API}/tepfi/entries/{eid}", headers=admin_headers,
                         json={"title": "TEST_regression_v2"}, timeout=15)
        assert u.status_code == 200
        assert u.json()["title"] == "TEST_regression_v2"

        d = requests.delete(f"{API}/tepfi/entries/{eid}", headers=admin_headers, timeout=15)
        assert d.status_code == 200
        g2 = requests.get(f"{API}/tepfi/entries/{eid}", headers=admin_headers, timeout=15)
        assert g2.status_code == 404


# Metadata - sub-dimension list for Effort
class TestMetadata:
    def test_effort_subdimensions_returned(self, admin_headers):
        r = requests.get(f"{API}/tepfi/metadata", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["effort_sub_dimensions"] == [
            "attitude", "knowledge", "skills", "physical_health",
            "mental_state", "emotional_wellness", "energy_level", "action"
        ]
