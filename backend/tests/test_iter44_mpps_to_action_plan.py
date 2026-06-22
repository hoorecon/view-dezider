"""
Iteration 44 — MyDezider MPPS → Action Plan auto-push, with bracketed title format.

Verifies:
  * Title format: `[Factor Name - <projected%>] · <action text or improvement_plan> · [+<delta>%]`
  * Realistic rating = MPPS projected_percentage
  * Delta = projected_percentage - original_percentage (or explicit delta_percentage if present)
  * Idempotency on mpps_key (stable factor_id|task|deadline)
  * Self-heal: existing item's title is updated when projected/delta change
  * GET filter by source_module + source_id returns the imported items
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json().get("session_token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_id(auth_headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    return r.json().get("user_id")


@pytest.fixture(scope="module")
def mongo_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    yield client[db_name]
    client.close()


@pytest.fixture(scope="module")
def seeded_decision(mongo_db, user_id):
    decision_id = "TEST_MPPS_FMT_" + uuid.uuid4().hex[:8]
    mongo_db.decisions.insert_one({
        "id": decision_id,
        "user_id": user_id,
        "title": "TEST_MPPS_FMT_Job_Switch",
        "folder": "Career",
        "factors": [
            {"id": "F_SAL", "name": "Salary & Compensation"},
            {"id": "F_GRO", "name": "Career Growth Opportunities"},
            {"id": "F_LOC", "name": "Location Flexibility"},  # used for delta=0 case
        ],
        "mpps_improvements": [
            {
                "factor_id": "F_SAL",
                "original_percentage": 70,
                "projected_percentage": 90,
                "improvement_plan": "Negotiate salary increase after 6 months + annual bonus structure",
                "action_items": [],
            },
            {
                "factor_id": "F_GRO",
                "original_percentage": 60,
                "projected_percentage": 85,
                "improvement_plan": "Request mentorship program, lead client project, and attend industry conferences",
                "action_items": [],
            },
            {
                "factor_id": "F_LOC",
                "original_percentage": 80,
                "projected_percentage": 80,  # delta = 0 → should omit delta block
                "improvement_plan": "Maintain current hybrid arrangement",
                "action_items": [],
            },
        ],
    })
    yield decision_id
    # Teardown
    mongo_db.decisions.delete_one({"id": decision_id})
    mongo_db.action_items.delete_many({"user_id": user_id, "source_id": decision_id})


# Helper to fetch all items for the seeded decision via API
def _list_items(headers, decision_id):
    r = requests.get(
        f"{BASE_URL}/api/action-items?source_module=MYDEZIDER_MPPS&source_id={decision_id}",
        headers=headers, timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── Format & content ──────────────────────────────────────────────────────
class TestMppsBracketedFormat:
    def test_import_creates_bracketed_titles(self, auth_headers, seeded_decision):
        r = requests.post(
            f"{BASE_URL}/api/action-items/import-from-mpps/{seeded_decision}",
            headers=auth_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["imported_count"] == 3, body

        titles = {it["title"] for it in body["imported"]}

        expected_salary = "[Salary & Compensation - 90] · Negotiate salary increase after 6 months + annual bonus structure · [+20%]"
        expected_growth = "[Career Growth Opportunities - 85] · Request mentorship program, lead client project, and attend industry conferences · [+25%]"
        # delta = 0 → drop the delta block
        expected_loc = "[Location Flexibility - 80] · Maintain current hybrid arrangement"

        assert expected_salary in titles, f"Missing: {expected_salary}\nGot: {titles}"
        assert expected_growth in titles, f"Missing: {expected_growth}\nGot: {titles}"
        assert expected_loc in titles, f"Missing: {expected_loc}\nGot: {titles}"

        # All flagged as MPPS, correctly tagged
        for it in body["imported"]:
            assert it["source_module"] == "MYDEZIDER_MPPS"
            assert it["source_id"] == seeded_decision
            assert it.get("is_mpps") is True
            assert it.get("mpps_key")

    def test_list_endpoint_returns_imported(self, auth_headers, seeded_decision):
        items = _list_items(auth_headers, seeded_decision)
        assert len(items) >= 3
        titles = {i["title"] for i in items}
        assert any("[Salary & Compensation - 90]" in t for t in titles)
        assert any("[Career Growth Opportunities - 85]" in t for t in titles)


# ── Idempotency ───────────────────────────────────────────────────────────
class TestIdempotency:
    def test_second_import_does_not_duplicate(self, auth_headers, seeded_decision):
        # 1st call already done; this is the 2nd
        r = requests.post(
            f"{BASE_URL}/api/action-items/import-from-mpps/{seeded_decision}",
            headers=auth_headers, timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["imported_count"] == 0

        # Total remains exactly 3
        items = _list_items(auth_headers, seeded_decision)
        assert len(items) == 3, [i["title"] for i in items]


# ── Self-heal title on projected/delta change ─────────────────────────────
class TestSelfHeal:
    def test_title_updates_when_projected_changes(self, auth_headers, seeded_decision, mongo_db):
        # Bump Salary projected 90 → 95 (delta now 25)
        mongo_db.decisions.update_one(
            {"id": seeded_decision, "mpps_improvements.factor_id": "F_SAL"},
            {"$set": {"mpps_improvements.$.projected_percentage": 95}},
        )
        r = requests.post(
            f"{BASE_URL}/api/action-items/import-from-mpps/{seeded_decision}",
            headers=auth_headers, timeout=15,
        )
        assert r.status_code == 200
        # No new inserts
        assert r.json()["imported_count"] == 0

        items = _list_items(auth_headers, seeded_decision)
        titles = [i["title"] for i in items]
        # Old title gone, new healed title present
        assert not any("[Salary & Compensation - 90]" in t for t in titles), titles
        expected_new = "[Salary & Compensation - 95] · Negotiate salary increase after 6 months + annual bonus structure · [+25%]"
        assert expected_new in titles, titles
        # Still no duplicates
        assert len(items) == 3


# ── Explicit delta_percentage takes priority ──────────────────────────────
class TestExplicitDelta:
    def test_explicit_delta_field_is_used(self, auth_headers, mongo_db, user_id):
        did = "TEST_MPPS_EXP_" + uuid.uuid4().hex[:8]
        mongo_db.decisions.insert_one({
            "id": did,
            "user_id": user_id,
            "title": "TEST_MPPS_explicit_delta",
            "factors": [{"id": "FE", "name": "Work-Life Balance"}],
            "mpps_improvements": [{
                "factor_id": "FE",
                "projected_percentage": 75,
                "delta_percentage": 15,  # explicit, no original_percentage
                "improvement_plan": "Adopt no-meeting Fridays",
                "action_items": [],
            }],
        })
        try:
            r = requests.post(
                f"{BASE_URL}/api/action-items/import-from-mpps/{did}",
                headers=auth_headers, timeout=15,
            )
            assert r.status_code == 200, r.text
            assert r.json()["imported_count"] == 1
            t = r.json()["imported"][0]["title"]
            assert t == "[Work-Life Balance - 75] · Adopt no-meeting Fridays · [+15%]", t
        finally:
            mongo_db.decisions.delete_one({"id": did})
            mongo_db.action_items.delete_many({"user_id": user_id, "source_id": did})
