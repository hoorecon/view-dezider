"""Iteration 26 — Phase 2 'From ASM' picker backend endpoint test.

Coverage:
  - POST /api/solution-finders (create SF)
  - POST /api/solution-matrices (create ASM linked to SF via linked_from_sf_*)
  - GET  /api/solution-finders/{entry_id}/asm-entries (NEW endpoint)
  - Regression: GET/PUT/DELETE on /api/solution-finders, /api/solution-matrices

All tests run against the public preview URL (EXPO_PUBLIC_BACKEND_URL).
"""
import os
import time
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"No token in response: {r.json()}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_ids(auth_headers):
    """Holds all created entity ids for teardown."""
    state = {"sf_ids": [], "asm_ids": []}
    yield state
    # Teardown
    for aid in state["asm_ids"]:
        try:
            requests.delete(f"{BASE_URL}/api/solution-matrices/{aid}", headers=auth_headers, timeout=15)
        except Exception:
            pass
    for sid in state["sf_ids"]:
        try:
            requests.delete(f"{BASE_URL}/api/solution-finders/{sid}", headers=auth_headers, timeout=15)
        except Exception:
            pass


# --- Health smoke ---
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200


# --- Create SF ---
def test_create_sf(auth_headers, created_ids):
    payload = {
        "area_of_life": "TEST_career",
        "smart_goal": "TEST_iter26 SF for ASM Phase 2",
        "concerns": [
            {"concern_id": "c1", "text": "TEST_primary concern 1", "is_primary": True, "order": 0}
        ],
        "root_causes": [
            {"rca_id": "r1", "concern_id": "c1", "text": "TEST_root cause 1", "order": 0}
        ],
        "solutions": [
            {"sol_id": "s1", "rca_id": "r1", "text": "TEST_solution 1"}
        ],
        "schema_version": 2,
    }
    r = requests.post(f"{BASE_URL}/api/solution-finders", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["entry_id"]
    assert data["smart_goal"] == payload["smart_goal"]
    created_ids["sf_ids"].append(data["entry_id"])


# --- Create ASM linked to SF (solution level) ---
def test_create_asm_linked_solution(auth_headers, created_ids):
    assert created_ids["sf_ids"], "Need an SF id first"
    sf_id = created_ids["sf_ids"][0]
    payload = {
        "area_of_life": "TEST_career",
        "smart_goal": "[ASM]-SL TEST_solution 1",
        "linked_from_sf_entry_id": sf_id,
        "linked_from_sf_source": "solution",
        "linked_from_sf_source_id": "s1",
        "linked_from_sf_label": "[ASM]-SL TEST_solution 1",
        "solution_category": {
            "completely_solvable": True,
            "partially_solvable": False,
            "not_solvable": False,
            "patience_period": True,
            "accept_let_go": False,
            "surrender_trust": False,
            "surrender_ignore": False,
            "surrender_involve": False,
        },
        "solution_sources": {
            "from_self": "Practice daily",
            "from_wellwisher": "",
            "from_experienced": "Ask a senior",
            "from_expert": "",
            "from_coach": "",
        },
    }
    r = requests.post(f"{BASE_URL}/api/solution-matrices", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["entry_id"]
    assert data["linked_from_sf_entry_id"] == sf_id
    assert data["linked_from_sf_source"] == "solution"
    assert data["linked_from_sf_source_id"] == "s1"
    created_ids["asm_ids"].append(data["entry_id"])


# --- Create ASM linked to SF at all_concerns level (deep ALL_CONCERNS) ---
def test_create_asm_linked_all_concerns(auth_headers, created_ids):
    sf_id = created_ids["sf_ids"][0]
    payload = {
        "area_of_life": "TEST_career",
        "smart_goal": "[ASM]-OL TEST_overall analysis",
        "linked_from_sf_entry_id": sf_id,
        "linked_from_sf_source": "all_concerns",
        "linked_from_sf_source_id": "ALL_CONCERNS",
        "solution_category": {
            "completely_solvable": False,
            "partially_solvable": True,
            "not_solvable": False,
        },
        "solution_sources": {
            "from_self": "Reflect",
            "from_coach": "Hire coach",
        },
    }
    r = requests.post(f"{BASE_URL}/api/solution-matrices", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["linked_from_sf_source_id"] == "ALL_CONCERNS"
    created_ids["asm_ids"].append(data["entry_id"])


# --- GET /api/solution-finders/{entry_id}/asm-entries (NEW) ---
def test_asm_entries_endpoint(auth_headers, created_ids):
    sf_id = created_ids["sf_ids"][0]
    # small wait to let writes settle
    time.sleep(0.5)
    r = requests.get(f"{BASE_URL}/api/solution-finders/{sf_id}/asm-entries",
                     headers=auth_headers, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list), f"Expected list, got: {type(items)}"
    assert len(items) >= 2, f"Expected >=2 linked ASM entries, got {len(items)}: {items}"

    # Validate response shape per request:
    required_keys = {"entry_id", "title", "source", "source_id", "categories", "sources", "updated_at"}
    for it in items:
        missing = required_keys - set(it.keys())
        assert not missing, f"Missing keys {missing} in item {it}"
        assert isinstance(it["categories"], list)
        assert isinstance(it["sources"], list)

    # Find the solution-level entry and verify category/source summaries
    sol_entries = [x for x in items if x["source"] == "solution" and x["source_id"] == "s1"]
    assert len(sol_entries) >= 1, "Solution-level link not found"
    sol = sol_entries[0]
    # Two truthy categories from our payload
    assert "completely_solvable" in sol["categories"]
    assert "patience_period" in sol["categories"]
    # Two non-empty sources
    assert "from_self" in sol["sources"]
    assert "from_experienced" in sol["sources"]

    # ALL_CONCERNS entry
    all_entries = [x for x in items if x["source_id"] == "ALL_CONCERNS"]
    assert len(all_entries) >= 1, "ALL_CONCERNS-level link not found"
    assert "partially_solvable" in all_entries[0]["categories"]
    assert "from_coach" in all_entries[0]["sources"]


def test_asm_entries_404_for_unknown(auth_headers):
    r = requests.get(f"{BASE_URL}/api/solution-finders/does-not-exist-xyz/asm-entries",
                     headers=auth_headers, timeout=20)
    assert r.status_code == 404


# --- Regression: SF GET single + PUT ---
def test_sf_get_and_put(auth_headers, created_ids):
    sf_id = created_ids["sf_ids"][0]
    r = requests.get(f"{BASE_URL}/api/solution-finders/{sf_id}", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["entry_id"] == sf_id

    r = requests.put(f"{BASE_URL}/api/solution-finders/{sf_id}",
                     json={"smart_goal": "TEST_iter26 SF updated"},
                     headers=auth_headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["smart_goal"] == "TEST_iter26 SF updated"


# --- Regression: solution-matrix CRUD ---
def test_asm_list_and_get(auth_headers, created_ids):
    r = requests.get(f"{BASE_URL}/api/solution-matrices", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    aid = created_ids["asm_ids"][0]
    r = requests.get(f"{BASE_URL}/api/solution-matrices/{aid}", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    assert r.json()["entry_id"] == aid


# --- Auth: missing token returns 401/403 ---
def test_asm_entries_requires_auth(created_ids):
    sf_id = created_ids["sf_ids"][0] if created_ids["sf_ids"] else "any"
    r = requests.get(f"{BASE_URL}/api/solution-finders/{sf_id}/asm-entries", timeout=15)
    assert r.status_code in (401, 403)
