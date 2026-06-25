"""
Iteration 71 — Pros & Cons → Action Plan import.

Tests the NEW endpoint:
    POST /api/action-items/import-from-pros-cons/{analysis_id}

Mirrors the existing My Dezider MPPS → Action Plan import flow but pulls
from the FINALLY CHOSEN option's per-factor improvement deltas (Step 8
"Improvement %"). Only positive deltas should become action items.

Scenarios covered:
  1. Happy path: chosen option + positive improvement_pct → action_items inserted,
     correct title format, GET /api/action-items?source_module=PROS_CONS&source_id=...
     returns them.
  2. Idempotency: second POST returns imported_count == 0 and DB count unchanged.
  3. No chosen option (final_choice_option_id=null) → imported_count 0, reason
     'no_chosen_option'.
  4. Only positive deltas: improvement_pct == 0 factor must NOT create an item.
  5. Auth: 401 without bearer token.
  6. Regression: POST /api/action-items/import-from-mpps/{bogus} → 404 (route still alive).
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://modal-responsive-fix.preview.emergentagent.com"
).rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


# ───── helpers / fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": USER_EMAIL, "password": USER_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    assert token, f"no token in login resp: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def analysis(session):
    """Create a Pros & Cons analysis with 1 option and 2 factors, one positive delta, one zero delta."""
    # create analysis
    r = session.post(f"{BASE_URL}/api/pros-cons",
                     json={"title": f"TEST_iter71_{int(time.time())}", "context": "iter71 test"},
                     timeout=30)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]

    # add 1 option
    r = session.post(f"{BASE_URL}/api/pros-cons/{aid}/options",
                     json={"name": "TEST_OptA"}, timeout=30)
    assert r.status_code == 200, r.text
    opt_id = r.json()["id"]

    # add 2 factors
    r = session.post(f"{BASE_URL}/api/pros-cons/{aid}/factors",
                     json={"name": "TEST_Salary"}, timeout=30)
    assert r.status_code == 200, r.text
    f1_id = r.json()["id"]

    r = session.post(f"{BASE_URL}/api/pros-cons/{aid}/factors",
                     json={"name": "TEST_Commute"}, timeout=30)
    assert r.status_code == 200, r.text
    f2_id = r.json()["id"]

    # Set std_rating so realistic_rating exists (not strictly required for the import)
    for fid in (f1_id, f2_id):
        session.put(f"{BASE_URL}/api/pros-cons/{aid}/factors/{fid}",
                    json={"std_rating": 50}, timeout=30)

    # set assessments
    # factor1: positive improvement (30%) on assessment_pct 40 → projected 70%
    r = session.put(
        f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{f1_id}",
        json={"assessment_pct": 40, "improvement_pct": 30, "notes": "negotiate base"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    # factor2: zero improvement → must NOT yield action item
    r = session.put(
        f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{f2_id}",
        json={"assessment_pct": 80, "improvement_pct": 0},
        timeout=30,
    )
    assert r.status_code == 200, r.text

    yield {"id": aid, "option_id": opt_id, "f1": f1_id, "f2": f2_id}

    # cleanup: trash the analysis
    try:
        session.delete(f"{BASE_URL}/api/pros-cons/{aid}", timeout=15)
    except Exception:
        pass


def _set_chosen(session, aid, option_id):
    r = session.put(f"{BASE_URL}/api/pros-cons/{aid}/config",
                    json={"final_choice_option_id": option_id}, timeout=30)
    assert r.status_code == 200, r.text


def _list_pc_items(session, aid):
    r = session.get(
        f"{BASE_URL}/api/action-items",
        params={"source_module": "PROS_CONS", "source_id": aid},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ───── tests ─────────────────────────────────────────────────────────────

class TestProsConsImport:

    def test_01_happy_path_positive_delta_creates_item(self, session, analysis):
        # Set chosen option first
        _set_chosen(session, analysis["id"], analysis["option_id"])
        r = session.post(
            f"{BASE_URL}/api/action-items/import-from-pros-cons/{analysis['id']}",
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("imported_count", 0) >= 1, f"expected >=1 imported, got {data}"

        items = _list_pc_items(session, analysis["id"])
        # Only the positive-delta factor should have a corresponding action item
        assert len(items) == 1, f"expected 1 PROS_CONS item, got {len(items)}: {items}"
        item = items[0]
        # title format: '[<factor> - <projected%>] · <text> · [+<delta>%]'
        assert "TEST_Salary" in item["title"], item["title"]
        assert "[+30%]" in item["title"], item["title"]
        # projected = 40 + 30 = 70
        assert "70" in item["title"], item["title"]
        assert item["source_module"] == "PROS_CONS"
        assert item["source_id"] == analysis["id"]
        assert item.get("source_subref") == analysis["f1"]

    def test_02_zero_delta_did_not_create_item(self, session, analysis):
        items = _list_pc_items(session, analysis["id"])
        # f2 should NOT appear
        assert all(it.get("source_subref") != analysis["f2"] for it in items), \
            f"f2 (zero-delta) should not have been imported: {items}"

    def test_03_idempotent_repeat_import(self, session, analysis):
        before = len(_list_pc_items(session, analysis["id"]))
        r = session.post(
            f"{BASE_URL}/api/action-items/import-from-pros-cons/{analysis['id']}",
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("imported_count", 1) == 0, f"expected 0 on repeat, got {data}"
        after = len(_list_pc_items(session, analysis["id"]))
        assert after == before, f"item count changed on repeat import: {before} → {after}"

    def test_04_no_chosen_option_returns_reason(self, session, analysis):
        # Clear chosen option
        r = session.put(f"{BASE_URL}/api/pros-cons/{analysis['id']}/config",
                        json={"final_choice_option_id": None}, timeout=30)
        assert r.status_code == 200, r.text

        r = session.post(
            f"{BASE_URL}/api/action-items/import-from-pros-cons/{analysis['id']}",
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("imported_count") == 0, data
        assert data.get("reason") == "no_chosen_option", data
        # restore chosen option for later tests
        _set_chosen(session, analysis["id"], analysis["option_id"])

    def test_05_auth_required(self, analysis):
        bare = requests.Session()
        bare.headers.update({"Content-Type": "application/json"})
        r = bare.post(
            f"{BASE_URL}/api/action-items/import-from-pros-cons/{analysis['id']}",
            timeout=30,
        )
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text}"


class TestMppsRegression:

    def test_06_mpps_import_route_alive(self, session):
        """Bogus decision id → 404, proves the route still resolves."""
        bogus = f"nonexistent-{uuid.uuid4()}"
        r = session.post(
            f"{BASE_URL}/api/action-items/import-from-mpps/{bogus}",
            timeout=30,
        )
        # 404 expected for missing decision
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"
