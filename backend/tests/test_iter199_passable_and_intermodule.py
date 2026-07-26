"""
Iter-199: Inter-module Integrations
- GET /api/integrations/passable-values (text + percent aggregation)
- POST /api/pros-cons/{id}/options with sf_ref persists
- POST /api/ctt/tasks + PUT with classification_ref
- GET /api/gem-pm/nodes/all?types=deliverable,work_package filter
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "super@test.com", "password": "SuperPass2026!"},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Seed helpers ──

@pytest.fixture(scope="module")
def seed_decision(h):
    """POST a Decision with 2 options (one with worth_percentage > 0)."""
    title = f"TEST_iter199_decision_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{BASE_URL}/api/decisions", headers=h,
                      json={"title": title, "context": "iter199 seed"}, timeout=30)
    assert r.status_code in (200, 201), f"create decision {r.status_code} {r.text}"
    did = r.json().get("id") or r.json().get("decision_id")
    assert did, r.text
    # Add options via update
    opt1 = {"id": str(uuid.uuid4()), "name": "iter199-opt-A", "worth_percentage": 72}
    opt2 = {"id": str(uuid.uuid4()), "name": "iter199-opt-B", "worth_percentage": 0}
    u = requests.put(f"{BASE_URL}/api/decisions/{did}", headers=h,
                     json={"options": [opt1, opt2]}, timeout=30)
    assert u.status_code == 200, f"update decision {u.status_code} {u.text}"
    return {"id": did, "title": title, "opt_names": [opt1["name"], opt2["name"]]}


# ═════ 1. GET /api/integrations/passable-values ═════

class TestPassableValues:
    def test_returns_shape(self, h):
        r = requests.get(f"{BASE_URL}/api/integrations/passable-values",
                         headers=h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "values" in d and "count" in d
        assert isinstance(d["values"], list)
        assert d["count"] == len(d["values"])

    def test_contains_option_text_and_worth_pct(self, h, seed_decision):
        # give store a moment
        time.sleep(0.5)
        r = requests.get(f"{BASE_URL}/api/integrations/passable-values",
                         headers=h, timeout=30)
        assert r.status_code == 200
        vals = r.json()["values"]
        option_texts = [v for v in vals
                        if v.get("kind") == "text"
                        and v.get("category") == "Option Name"
                        and v.get("value") == "iter199-opt-A"]
        assert option_texts, f"missing text Option Name for seeded option; sample: {vals[:5]}"
        pcts = [v for v in vals
                if v.get("kind") == "percent"
                and v.get("category") == "Case-1 Worth %"
                and "iter199-opt-A" in (v.get("source") or "")]
        assert pcts, "missing Case-1 Worth % for seeded option"
        # Also each item must have module, link, ref_id
        item = option_texts[0]
        assert item.get("module") == "MYDEZIDER"
        assert item.get("link", "").startswith("/decision/")
        assert item.get("ref_id") == seed_decision["id"]

    def test_smart_goal_link_shape(self, h):
        """SMART Goal items (if any) must have link '/tools/solution-finder?id=...'."""
        r = requests.get(f"{BASE_URL}/api/integrations/passable-values",
                         headers=h, timeout=30)
        assert r.status_code == 200
        vals = r.json()["values"]
        goals = [v for v in vals if v.get("category") == "SMART Goal"]
        for g in goals:
            assert g.get("kind") == "text"
            assert g.get("link", "").startswith("/tools/solution-finder?id=")
            assert g.get("module") == "SOLUTION_FINDER"


# ═════ 2. Pros&Cons option with sf_ref ═════

class TestProsConsSfRef:
    def test_add_option_with_sf_ref_persists(self, h):
        # Create analysis
        r = requests.post(f"{BASE_URL}/api/pros-cons", headers=h,
                          json={"title": f"TEST_iter199_pc_{uuid.uuid4().hex[:6]}"},
                          timeout=30)
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        # Add option with sf_ref
        payload = {"name": "From SF", "sf_ref": {"entry_id": "test123",
                                                  "label": "My SMART Goal"}}
        r2 = requests.post(f"{BASE_URL}/api/pros-cons/{aid}/options",
                           headers=h, json=payload, timeout=30)
        assert r2.status_code == 200, r2.text
        opt = r2.json().get("option") or {}
        assert opt.get("sf_ref", {}).get("entry_id") == "test123", \
            f"sf_ref not persisted in POST response: {opt}"
        # GET analysis and confirm
        r3 = requests.get(f"{BASE_URL}/api/pros-cons/{aid}", headers=h, timeout=30)
        assert r3.status_code == 200
        opts = r3.json().get("options") or []
        found = next((o for o in opts if o.get("name") == "From SF"), None)
        assert found is not None, opts
        assert found.get("sf_ref", {}).get("entry_id") == "test123", \
            f"sf_ref lost after GET: {found}"


# ═════ 3. CTT tasks with classification_ref + gem-pm nodes filter ═════

class TestCttClassificationRef:
    def test_create_task_with_classification_ref(self, h):
        payload = {
            "task": f"TEST_iter199_task_{uuid.uuid4().hex[:6]}",
            "classification_ref": {"type": "goal", "ref_id": "g1", "label": "My Goal"},
        }
        r = requests.post(f"{BASE_URL}/api/ctt/tasks", headers=h,
                          json=payload, timeout=30)
        assert r.status_code == 200, r.text
        task = r.json()
        tid = task.get("task_id")
        assert tid, task
        cr = task.get("classification_ref") or {}
        assert cr.get("type") == "goal"
        assert cr.get("ref_id") == "g1"
        assert cr.get("label") == "My Goal"

        # GET to verify persistence
        g = requests.get(f"{BASE_URL}/api/ctt/tasks/{tid}", headers=h, timeout=30)
        assert g.status_code == 200
        assert g.json().get("classification_ref", {}).get("ref_id") == "g1"

        # PUT to null
        u = requests.put(f"{BASE_URL}/api/ctt/tasks/{tid}", headers=h,
                        json={"classification_ref": None}, timeout=30)
        assert u.status_code == 200, u.text
        # Reads back with null / missing
        assert u.json().get("classification_ref") in (None, {}), u.json()


class TestGemPmNodesAllFilter:
    def test_types_filter(self, h):
        # Ensure endpoint returns 200 and only requested types
        r = requests.get(
            f"{BASE_URL}/api/gem-pm/nodes/all?types=deliverable,work_package",
            headers=h, timeout=30)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row.get("node_type") in ("deliverable", "work_package"), row

    def test_no_filter_returns_list(self, h):
        r = requests.get(f"{BASE_URL}/api/gem-pm/nodes/all",
                         headers=h, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
