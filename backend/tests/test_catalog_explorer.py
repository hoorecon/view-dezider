"""
Tests for Central Catalog Manager — Explorer (lazy tree + role-gated CRUD).

Covers:
  - GET  /api/catalog-explorer/meta          (caps for super_admin / admin / user)
  - GET  /api/catalog-explorer/children      (lazy navigation at each level)
  - POST /api/catalog-explorer/scenarios     (role gate + create)
  - POST /api/catalog-explorer/decision-templates  (role gate + create)
  - POST /api/catalog-explorer/solution-templates  (role gate)
  - POST /api/catalog-explorer/solution-items      (admin can_store_crud)
  - DELETE scenario without cascade -> 409, with cascade -> 200
  - POST /api/catalog-explorer/seed-scenarios-from-templates
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL/EXPO_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}
ADMIN = {"email": "admin@test.com", "password": "AdminPass2026!"}
USER  = {"email": "harden_1777921741@example.com", "password": "HardenPass2026!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ── meta capabilities ───────────────────────────────────────────────────────
class TestMeta:
    def test_meta_super(self, super_token):
        r = requests.get(f"{API}/catalog-explorer/meta", headers=_h(super_token), timeout=15)
        assert r.status_code == 200, r.text
        caps = r.json().get("capabilities", {})
        assert caps.get("role") == "super_admin"
        assert caps.get("is_admin") is True
        assert caps.get("is_super_admin") is True
        assert caps.get("can_full_crud") is True
        assert caps.get("can_store_crud") is True

    def test_meta_admin(self, admin_token):
        r = requests.get(f"{API}/catalog-explorer/meta", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        caps = r.json().get("capabilities", {})
        assert caps.get("role") == "admin"
        assert caps.get("is_super_admin") is False
        assert caps.get("can_full_crud") is False
        assert caps.get("can_store_crud") is True

    def test_meta_user_forbidden(self, user_token):
        r = requests.get(f"{API}/catalog-explorer/meta", headers=_h(user_token), timeout=15)
        assert r.status_code == 403, r.text


# ── lazy children ───────────────────────────────────────────────────────────
class TestChildren:
    def test_root_life_areas(self, super_token):
        r = requests.get(f"{API}/catalog-explorer/children",
                         headers=_h(super_token),
                         params={"node_type": "catalog_node"}, timeout=15)
        assert r.status_code == 200, r.text
        kids = r.json().get("children", [])
        assert isinstance(kids, list) and len(kids) > 0, "no life areas seeded"
        for k in kids:
            assert k["node_type"] == "catalog_node"
        # store one for later subtests
        pytest.life_area_id = kids[0]["ctx"]["node_id"]

    def test_subarea_returns_orgtypes(self, super_token):
        # Drill into life area -> first sub area, then expand sub-area: should
        # return deeper catalog nodes + 7 org_type folders.
        la_id = getattr(pytest, "life_area_id", None)
        assert la_id, "life area id missing from prior test"

        r = requests.get(f"{API}/catalog-explorer/children",
                         headers=_h(super_token),
                         params={"node_type": "catalog_node", "node_id": la_id}, timeout=15)
        assert r.status_code == 200
        kids = r.json().get("children", [])
        # life area has sub-areas; pick first sub-area
        subs = [k for k in kids if k["node_type"] == "catalog_node"]
        assert subs, "no sub-areas under life area"
        sub_id = subs[0]["ctx"]["node_id"]
        pytest.sub_area_id = sub_id
        pytest.sub_area_life_area_id = subs[0]["ctx"].get("life_area_id")

        r2 = requests.get(f"{API}/catalog-explorer/children",
                          headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": sub_id}, timeout=15)
        assert r2.status_code == 200
        kids2 = r2.json().get("children", [])
        org_types = [k for k in kids2 if k["node_type"] == "org_type"]
        assert len(org_types) == 7, f"expected 7 org-type folders, got {len(org_types)}"

    def test_orgtype_returns_pnrag(self, super_token):
        sub_id = getattr(pytest, "sub_area_id", None)
        la_id = getattr(pytest, "sub_area_life_area_id", None)
        assert sub_id
        r = requests.get(f"{API}/catalog-explorer/children",
                         headers=_h(super_token),
                         params={"node_type": "org_type", "node_id": sub_id,
                                 "org_type": "individual", "life_area_id": la_id}, timeout=15)
        assert r.status_code == 200
        kids = r.json().get("children", [])
        keys = sorted([k["ctx"]["pnrag"] for k in kids])
        assert keys == sorted(["problem", "need", "risk", "aspiration", "general"]), keys


# ── role gating on writes ───────────────────────────────────────────────────
class TestRoleGates:
    def test_admin_cannot_create_scenario(self, admin_token):
        body = {"catalog_node_id": "x", "org_type": "individual", "pnrag": "general", "title": "T"}
        r = requests.post(f"{API}/catalog-explorer/scenarios", headers=_h(admin_token), json=body, timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_cannot_create_decision_template(self, admin_token):
        body = {"scenario_id": "x", "title": "T"}
        r = requests.post(f"{API}/catalog-explorer/decision-templates", headers=_h(admin_token), json=body, timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_cannot_create_solution_template(self, admin_token):
        body = {"scenario_id": "x", "title": "T"}
        r = requests.post(f"{API}/catalog-explorer/solution-templates", headers=_h(admin_token), json=body, timeout=15)
        assert r.status_code == 403, r.text

    def test_user_blocked_on_seed(self, user_token):
        r = requests.post(f"{API}/catalog-explorer/seed-scenarios-from-templates", headers=_h(user_token), timeout=20)
        assert r.status_code == 403, r.text


# ── full scenario lifecycle (super_admin) ───────────────────────────────────
class TestScenarioLifecycle:
    def test_full_lifecycle(self, super_token, admin_token):
        # Need a sub-area id
        r = requests.get(f"{API}/catalog-explorer/children",
                         headers=_h(super_token),
                         params={"node_type": "catalog_node"}, timeout=15)
        assert r.status_code == 200
        la = r.json()["children"][0]["ctx"]["node_id"]
        r2 = requests.get(f"{API}/catalog-explorer/children",
                          headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": la}, timeout=15)
        sub = next(k for k in r2.json()["children"] if k["node_type"] == "catalog_node")
        sub_id = sub["ctx"]["node_id"]

        # 1) create scenario as super_admin
        body = {
            "catalog_node_id": sub_id, "org_type": "individual",
            "pnrag": "general", "title": "TEST_lifecycle_scenario",
            "description": "Created by automated test",
        }
        r3 = requests.post(f"{API}/catalog-explorer/scenarios", headers=_h(super_token), json=body, timeout=15)
        assert r3.status_code == 200, r3.text
        scn = r3.json()
        scenario_id = scn["scenario_id"]
        assert scn["title"] == "TEST_lifecycle_scenario"

        # 2) create a decision template under it
        dt_body = {"scenario_id": scenario_id, "title": "TEST_dt", "decision_type": "yes_no"}
        r4 = requests.post(f"{API}/catalog-explorer/decision-templates", headers=_h(super_token), json=dt_body, timeout=15)
        assert r4.status_code == 200, r4.text
        dt = r4.json()
        assert dt["scenario_id"] == scenario_id

        # 2b) admin can create solution-item (auto-approved) under this scenario
        si_body = {"scenario_id": scenario_id, "name": "TEST_solution_item", "type": "PRODUCT",
                   "description": "auto-approved by admin"}
        r4b = requests.post(f"{API}/catalog-explorer/solution-items", headers=_h(admin_token), json=si_body, timeout=15)
        assert r4b.status_code == 200, r4b.text
        si = r4b.json()
        assert si.get("approval_status") == "approved"
        assert si.get("is_authorized") is True
        solution_id = si["solution_id"]

        # 3) DELETE scenario without cascade -> 409 (has children)
        r5 = requests.delete(f"{API}/catalog-explorer/scenarios/{scenario_id}",
                             headers=_h(super_token), timeout=15)
        assert r5.status_code == 409, f"expected 409 due to children, got {r5.status_code} {r5.text}"

        # 4) DELETE with cascade=true -> 200 + counts
        r6 = requests.delete(f"{API}/catalog-explorer/scenarios/{scenario_id}",
                             headers=_h(super_token), params={"cascade": "true"}, timeout=15)
        assert r6.status_code == 200, r6.text
        body = r6.json()
        assert body.get("success") is True
        assert body.get("deleted_decision_templates", 0) >= 1
        assert body.get("unlinked_store_items", 0) >= 1

        # cleanup: hard-delete the solution item we created (it was just unlinked)
        requests.delete(f"{API}/catalog-explorer/solution-items/{solution_id}",
                        headers=_h(admin_token), timeout=15)


# ── seed migration ──────────────────────────────────────────────────────────
class TestSeed:
    def test_seed_as_super_admin(self, super_token):
        r = requests.post(f"{API}/catalog-explorer/seed-scenarios-from-templates",
                          headers=_h(super_token), timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "scenarios_created" in d
        assert "skipped_existing" in d
        assert "templates_unmatched" in d

    def test_seed_as_admin_forbidden(self, admin_token):
        r = requests.post(f"{API}/catalog-explorer/seed-scenarios-from-templates",
                          headers=_h(admin_token), timeout=20)
        assert r.status_code == 403, r.text
