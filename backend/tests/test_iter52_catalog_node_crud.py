"""
Iteration 52 — Catalog NODE CRUD + level-gating + reparent + role gates.

Covers (new behaviour relative to iter 51):
  - POST /api/catalog-explorer/nodes              (super_admin)
  - PUT  /api/catalog-explorer/nodes/{node_id}    (rename)
  - DELETE /api/catalog-explorer/nodes/{node_id}  (with/without ?reparent=true)
  - L0 (life area) protection on PUT/DELETE → 403
  - Level gating in GET /children: L0 life areas → editable=false / deletable=false,
    L1 sub-areas → editable=true / deletable=true.
  - Role gating: plain admin can't create/edit/delete nodes (403)
  - Regression smoke: /meta capability matrix unchanged for super/admin/user;
    solution-items POST still works for plain admin.
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
USER = {"email": "harden_1777921741@example.com", "password": "HardenPass2026!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER)


# Helper: fetch root life areas + first sub-area (L1).
@pytest.fixture(scope="module")
def fixtures(super_token):
    r = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                     params={"node_type": "catalog_node"}, timeout=15)
    assert r.status_code == 200, r.text
    life_areas = r.json()["children"]
    assert len(life_areas) >= 1, "no life areas seeded"
    la = life_areas[0]
    la_id = la["ctx"]["node_id"]

    r2 = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                      params={"node_type": "catalog_node", "node_id": la_id}, timeout=15)
    assert r2.status_code == 200, r2.text
    children = r2.json()["children"]
    subs = [k for k in children if k["node_type"] == "catalog_node"]
    assert subs, f"life area {la_id} has no sub-areas"
    sub = subs[0]
    return {
        "la_node": la,
        "la_id": la_id,
        "sub_node": sub,
        "sub_id": sub["ctx"]["node_id"],
    }


# ── Level gating reflected in /children ────────────────────────────────────
class TestLevelGating:
    def test_l0_life_areas_not_editable_or_deletable(self, super_token):
        r = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                         params={"node_type": "catalog_node"}, timeout=15)
        assert r.status_code == 200, r.text
        kids = r.json()["children"]
        assert len(kids) >= 1
        for k in kids:
            assert k["editable"] is False, f"L0 {k['label']} editable should be False"
            assert k["deletable"] is False, f"L0 {k['label']} deletable should be False"
            assert k["ctx"].get("level") == 0

    def test_l1_subareas_editable_and_deletable(self, super_token, fixtures):
        r = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                         params={"node_type": "catalog_node", "node_id": fixtures["la_id"]}, timeout=15)
        assert r.status_code == 200, r.text
        kids = r.json()["children"]
        subs = [k for k in kids if k["node_type"] == "catalog_node"]
        assert subs, "no L1 sub-areas under life area"
        # Core fix: L1 sub-areas must be editable & deletable for super_admin.
        for s in subs:
            assert s["ctx"].get("level") == 1, f"sub-area level should be 1, got {s['ctx'].get('level')}"
            assert s["editable"] is True, f"L1 sub-area {s['label']} should be editable for super_admin"
            assert s["deletable"] is True, f"L1 sub-area {s['label']} should be deletable for super_admin"

    def test_l1_not_editable_for_plain_admin(self, admin_token, fixtures):
        r = requests.get(f"{API}/catalog-explorer/children", headers=_h(admin_token),
                         params={"node_type": "catalog_node", "node_id": fixtures["la_id"]}, timeout=15)
        assert r.status_code == 200, r.text
        kids = r.json()["children"]
        subs = [k for k in kids if k["node_type"] == "catalog_node"]
        assert subs
        for s in subs:
            assert s["editable"] is False, "plain admin must not see L1 as editable"
            assert s["deletable"] is False, "plain admin must not see L1 as deletable"


# ── L0 protection on writes ────────────────────────────────────────────────
class TestL0Protection:
    def test_put_l0_life_area_forbidden(self, super_token, fixtures):
        r = requests.put(f"{API}/catalog-explorer/nodes/{fixtures['la_id']}",
                         headers=_h(super_token), json={"name": "QA Hack"}, timeout=15)
        assert r.status_code == 403, f"expected 403 on L0 PUT, got {r.status_code} {r.text}"

    def test_delete_l0_life_area_forbidden(self, super_token, fixtures):
        r = requests.delete(f"{API}/catalog-explorer/nodes/{fixtures['la_id']}",
                            headers=_h(super_token), timeout=15)
        assert r.status_code == 403, f"expected 403 on L0 DELETE, got {r.status_code} {r.text}"


# ── Role gate: plain admin can't node-CRUD ─────────────────────────────────
class TestRoleGateOnNodes:
    def test_admin_cannot_create_node(self, admin_token, fixtures):
        body = {"parent_id": fixtures["sub_id"], "name": "QA Should Fail"}
        r = requests.post(f"{API}/catalog-explorer/nodes", headers=_h(admin_token), json=body, timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_cannot_update_node(self, admin_token, fixtures):
        r = requests.put(f"{API}/catalog-explorer/nodes/{fixtures['sub_id']}",
                         headers=_h(admin_token), json={"name": "QA Hack"}, timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_cannot_delete_node(self, admin_token, fixtures):
        r = requests.delete(f"{API}/catalog-explorer/nodes/{fixtures['sub_id']}",
                            headers=_h(admin_token), timeout=15)
        assert r.status_code == 403, r.text


# ── Full node CRUD lifecycle as super_admin ────────────────────────────────
class TestNodeCRUD:
    """Create an L2 folder under an L1 sub-area, rename it, then delete it."""

    def test_create_rename_delete(self, super_token, fixtures):
        # 1) Create under L1 sub-area → expect level 2
        body = {"parent_id": fixtures["sub_id"], "name": "TEST_QA Test Folder", "icon": ""}
        r = requests.post(f"{API}/catalog-explorer/nodes", headers=_h(super_token), json=body, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        node_id = data.get("node_id")
        assert node_id, data
        assert data.get("level") == 2, f"new node level should be 2, got {data.get('level')}"

        # 2) Verify it appears via /children with editable & deletable = true
        r2 = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": fixtures["sub_id"]}, timeout=15)
        assert r2.status_code == 200
        kids = [k for k in r2.json()["children"] if k["node_type"] == "catalog_node"]
        match = next((k for k in kids if k["id"] == node_id), None)
        assert match, f"new node {node_id} not found in children"
        assert match["editable"] is True
        assert match["deletable"] is True
        assert match["ctx"].get("level") == 2

        # 3) Rename it
        r3 = requests.put(f"{API}/catalog-explorer/nodes/{node_id}",
                          headers=_h(super_token), json={"name": "TEST_QA Renamed"}, timeout=15)
        assert r3.status_code == 200, r3.text
        assert r3.json().get("success") is True

        # 4) Verify rename persisted
        r4 = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": fixtures["sub_id"]}, timeout=15)
        match2 = next((k for k in r4.json()["children"] if k["id"] == node_id), None)
        assert match2 and match2["label"] == "TEST_QA Renamed", match2

        # 5) Delete (childless) → 200
        r5 = requests.delete(f"{API}/catalog-explorer/nodes/{node_id}",
                             headers=_h(super_token), timeout=15)
        assert r5.status_code == 200, r5.text
        assert r5.json().get("success") is True

        # 6) Confirm gone
        r6 = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": fixtures["sub_id"]}, timeout=15)
        gone = next((k for k in r6.json()["children"] if k["id"] == node_id), None)
        assert gone is None, "deleted node still listed"


# ── Reparent-on-delete behaviour ────────────────────────────────────────────
class TestReparent:
    def test_delete_with_children_blocks_then_reparent(self, super_token, fixtures):
        sub_id = fixtures["sub_id"]

        # Create parent under L1
        r = requests.post(f"{API}/catalog-explorer/nodes", headers=_h(super_token),
                          json={"parent_id": sub_id, "name": "TEST_QA Parent"}, timeout=15)
        assert r.status_code == 200, r.text
        parent_id = r.json()["node_id"]
        assert r.json()["level"] == 2

        # Create child under that parent
        r2 = requests.post(f"{API}/catalog-explorer/nodes", headers=_h(super_token),
                           json={"parent_id": parent_id, "name": "TEST_QA Child"}, timeout=15)
        assert r2.status_code == 200, r2.text
        child_id = r2.json()["node_id"]
        assert r2.json()["level"] == 3

        # DELETE parent WITHOUT reparent → 409
        r3 = requests.delete(f"{API}/catalog-explorer/nodes/{parent_id}",
                             headers=_h(super_token), timeout=15)
        assert r3.status_code == 409, f"expected 409, got {r3.status_code} {r3.text}"

        # DELETE parent WITH reparent=true → 200
        r4 = requests.delete(f"{API}/catalog-explorer/nodes/{parent_id}",
                             headers=_h(super_token), params={"reparent": "true"}, timeout=15)
        assert r4.status_code == 200, r4.text
        body = r4.json()
        assert body.get("success") is True
        assert body.get("reparented") is True
        assert body.get("moved_nodes", 0) >= 1

        # Verify child now sits under the original sub-area (lifted one level)
        r5 = requests.get(f"{API}/catalog-explorer/children", headers=_h(super_token),
                          params={"node_type": "catalog_node", "node_id": sub_id}, timeout=15)
        assert r5.status_code == 200
        kids = [k for k in r5.json()["children"] if k["node_type"] == "catalog_node"]
        moved = next((k for k in kids if k["id"] == child_id), None)
        assert moved is not None, f"child {child_id} not found under sub-area after reparent"
        assert moved["ctx"].get("parent_id") == sub_id, f"child parent_id should now be {sub_id}, got {moved['ctx'].get('parent_id')}"

        # Cleanup the lifted child
        rc = requests.delete(f"{API}/catalog-explorer/nodes/{child_id}",
                             headers=_h(super_token), timeout=15)
        assert rc.status_code == 200, rc.text


# ── Regression smoke ───────────────────────────────────────────────────────
class TestRegression:
    def test_meta_caps_unchanged(self, super_token, admin_token, user_token):
        r = requests.get(f"{API}/catalog-explorer/meta", headers=_h(super_token), timeout=15)
        assert r.status_code == 200
        c = r.json()["capabilities"]
        assert c["role"] == "super_admin" and c["can_full_crud"] and c["can_store_crud"]

        r2 = requests.get(f"{API}/catalog-explorer/meta", headers=_h(admin_token), timeout=15)
        assert r2.status_code == 200
        c2 = r2.json()["capabilities"]
        assert c2["role"] == "admin" and c2["can_full_crud"] is False and c2["can_store_crud"] is True

        r3 = requests.get(f"{API}/catalog-explorer/meta", headers=_h(user_token), timeout=15)
        assert r3.status_code == 403

    def test_super_admin_scenario_create_and_cascade_delete(self, super_token, fixtures):
        sub_id = fixtures["sub_id"]
        body = {"catalog_node_id": sub_id, "org_type": "individual",
                "pnrag": "general", "title": "TEST_iter52_scn"}
        r = requests.post(f"{API}/catalog-explorer/scenarios", headers=_h(super_token), json=body, timeout=15)
        assert r.status_code == 200, r.text
        scn_id = r.json()["scenario_id"]

        # add a decision template under it
        r2 = requests.post(f"{API}/catalog-explorer/decision-templates",
                           headers=_h(super_token),
                           json={"scenario_id": scn_id, "title": "TEST_iter52_dt"}, timeout=15)
        assert r2.status_code == 200, r2.text

        # delete without cascade → 409
        r3 = requests.delete(f"{API}/catalog-explorer/scenarios/{scn_id}",
                             headers=_h(super_token), timeout=15)
        assert r3.status_code == 409, r3.text

        # delete with cascade → 200
        r4 = requests.delete(f"{API}/catalog-explorer/scenarios/{scn_id}",
                             headers=_h(super_token), params={"cascade": "true"}, timeout=15)
        assert r4.status_code == 200, r4.text
        assert r4.json().get("deleted_decision_templates", 0) >= 1

    def test_admin_can_still_create_solution_item(self, super_token, admin_token, fixtures):
        # need a scenario first (created by super), then admin creates an item under it
        sub_id = fixtures["sub_id"]
        rs = requests.post(f"{API}/catalog-explorer/scenarios", headers=_h(super_token),
                           json={"catalog_node_id": sub_id, "org_type": "individual",
                                 "pnrag": "general", "title": "TEST_iter52_for_admin_item"}, timeout=15)
        assert rs.status_code == 200, rs.text
        scn_id = rs.json()["scenario_id"]

        ri = requests.post(f"{API}/catalog-explorer/solution-items", headers=_h(admin_token),
                           json={"scenario_id": scn_id, "name": "TEST_iter52_item", "type": "PRODUCT"}, timeout=15)
        assert ri.status_code == 200, ri.text
        item = ri.json()
        assert item.get("approval_status") == "approved"
        assert item.get("is_authorized") is True
        sol_id = item["solution_id"]

        # cleanup: cascade-delete the scenario, then hard-delete leftover item
        requests.delete(f"{API}/catalog-explorer/scenarios/{scn_id}",
                        headers=_h(super_token), params={"cascade": "true"}, timeout=15)
        requests.delete(f"{API}/catalog-explorer/solution-items/{sol_id}",
                        headers=_h(admin_token), timeout=15)
