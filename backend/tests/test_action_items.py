"""
Universal Action-Item store tests (Phase B).

Covers /api/action-items CRUD, port-to-ctt, port-to-lifestyle, unport,
import-from-mpps, and stats/summary.
"""
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://voice-browse-epic.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token")
    assert token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_id(auth_headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200, r.text
    return r.json().get("user_id")


@pytest.fixture(scope="module")
def mongo_db():
    """Direct mongo access — to seed MPPS decision for import test + final cleanup."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    yield client[db_name]
    client.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup(mongo_db, user_id):
    """Remove TEST_ items at module teardown."""
    yield
    mongo_db.action_items.delete_many({"user_id": user_id, "title": {"$regex": "^TEST_"}})
    mongo_db.ctt_tasks.delete_many({"user_id": user_id, "task": {"$regex": "^TEST_"}})
    mongo_db.lifestyle_routines.delete_many({"user_id": user_id, "name": {"$regex": "^TEST_"}})
    mongo_db.decisions.delete_many({"user_id": user_id, "title": {"$regex": "^TEST_MPPS_"}})


# ────────────────────────────────────────────────────────────────────────────
# CRUD + ENUM VALIDATION
# ────────────────────────────────────────────────────────────────────────────

class TestCreate:
    def test_create_basic(self, auth_headers):
        payload = {
            "source_module": "MANUAL",
            "title": "TEST_basic_create_" + uuid.uuid4().hex[:6],
            "who": "Self",
            "by_when": "2026-06-30",
            "priority": "high",
        }
        r = requests.post(f"{BASE_URL}/api/action-items", json=payload, headers=auth_headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["title"] == payload["title"]
        assert data["priority"] == "high"
        assert data["status"] == "pending"
        assert data["progress_pct"] == 0
        assert data["recurrence_type"] == "one_time"
        assert data["ported_to"] is None
        assert "action_id" in data
        # GET to confirm persistence
        g = requests.get(f"{BASE_URL}/api/action-items/{data['action_id']}", headers=auth_headers, timeout=10)
        assert g.status_code == 200
        assert g.json()["title"] == payload["title"]

    def test_create_rejects_invalid_source(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "BOGUS_SRC", "title": "TEST_x"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_create_rejects_invalid_priority(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "TEST_x", "priority": "super"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_create_rejects_invalid_recurrence(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "TEST_x", "recurrence_type": "always"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_create_rejects_invalid_status(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "TEST_x", "status": "wibble"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_create_rejects_empty_title(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "   "},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400

    def test_create_recurring_defaults_frequency(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "TEST_recur_default", "recurrence_type": "recurring"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["recurrence_frequency"] == "weekly"

    def test_create_recurring_invalid_frequency(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/action-items",
            json={"source_module": "MANUAL", "title": "TEST_bad_freq",
                  "recurrence_type": "recurring", "recurrence_frequency": "lunar"},
            headers=auth_headers, timeout=10,
        )
        assert r.status_code == 400


# ────────────────────────────────────────────────────────────────────────────
# LIST + FILTERS
# ────────────────────────────────────────────────────────────────────────────

class TestListFilters:
    @pytest.fixture(scope="class", autouse=True)
    def seed(self, auth_headers):
        # Create 3 items with distinct source_module
        for src, title, prio in [("PROS_CONS", "TEST_pc_filter", "high"),
                                  ("SWOT",      "TEST_swot_filter", "low"),
                                  ("MANUAL",    "TEST_man_filter", "medium")]:
            requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": src, "title": title, "priority": prio,
                                "source_id": "FIXT_001", "source_subref": f"sub_{src}"},
                          headers=auth_headers, timeout=10)

    def test_filter_source_module(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/action-items?source_module=PROS_CONS",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert all(d["source_module"] == "PROS_CONS" for d in data)
        assert any(d["title"] == "TEST_pc_filter" for d in data)

    def test_filter_source_id_and_subref(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/action-items?source_id=FIXT_001&source_subref=sub_SWOT",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert all(d.get("source_subref") == "sub_SWOT" for d in data)

    def test_filter_priority_and_status(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/action-items?priority=high&status=pending",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert all(d["priority"] == "high" and d["status"] == "pending" for d in data)

    def test_filter_not_ported(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/action-items?not_ported=1",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert all(d.get("ported_to") is None for d in data)


# ────────────────────────────────────────────────────────────────────────────
# UPDATE + DELETE
# ────────────────────────────────────────────────────────────────────────────

class TestUpdateDelete:
    @pytest.fixture(scope="class")
    def created_id(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "MANUAL", "title": "TEST_update_target", "who": "Me"},
                          headers=auth_headers, timeout=10)
        return r.json()["action_id"]

    def test_partial_update(self, auth_headers, created_id):
        r = requests.put(f"{BASE_URL}/api/action-items/{created_id}",
                         json={"who": "TEST_partner", "by_when": "2026-12-01"},
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["who"] == "TEST_partner"
        assert r.json()["by_when"] == "2026-12-01"

    def test_done_status_autosets_progress(self, auth_headers, created_id):
        r = requests.put(f"{BASE_URL}/api/action-items/{created_id}",
                         json={"status": "done"},
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "done"
        assert body["progress_pct"] == 100

    def test_delete_soft_cancels(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "MANUAL", "title": "TEST_to_cancel"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        d = requests.delete(f"{BASE_URL}/api/action-items/{aid}", headers=auth_headers, timeout=10)
        assert d.status_code == 200
        # Item still exists but status == cancelled
        g = requests.get(f"{BASE_URL}/api/action-items/{aid}", headers=auth_headers, timeout=10)
        assert g.status_code == 200
        assert g.json()["status"] == "cancelled"

    def test_update_not_found(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/action-items/nonexistent_xxx",
                         json={"who": "x"}, headers=auth_headers, timeout=10)
        assert r.status_code == 404


# ────────────────────────────────────────────────────────────────────────────
# PORT TO CTT
# ────────────────────────────────────────────────────────────────────────────

class TestPortToCtt:
    def test_port_to_ctt_creates_task_and_links(self, auth_headers, mongo_db, user_id):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "PROS_CONS", "title": "TEST_port_ctt", "who": "Me",
                                "by_when": "2026-07-15", "priority": "high"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        p = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-ctt",
                          headers=auth_headers, timeout=10)
        assert p.status_code == 200, p.text
        body = p.json()
        assert body["action_item"]["ported_to"] == "CTT"
        assert body["action_item"]["ported_ref_id"] == body["ctt_task"]["task_id"]
        # Direct DB check
        task = mongo_db.ctt_tasks.find_one({"task_id": body["ctt_task"]["task_id"]})
        assert task is not None
        assert task["source_type"] == "ACTION_ITEM"
        assert task["source_id"] == aid

    def test_port_to_ctt_second_call_409(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "MANUAL", "title": "TEST_port_ctt_dup"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        p1 = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-ctt", headers=auth_headers, timeout=10)
        assert p1.status_code == 200
        p2 = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-ctt", headers=auth_headers, timeout=10)
        assert p2.status_code == 409


# ────────────────────────────────────────────────────────────────────────────
# PORT TO LIFESTYLE  (auto-upgrades one_time → recurring)
# ────────────────────────────────────────────────────────────────────────────

class TestPortToLifestyle:
    def test_port_to_lifestyle_autoupgrades_recurrence(self, auth_headers, mongo_db, user_id):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "PNA", "title": "TEST_port_lifestyle",
                                "who": "Me", "recurrence_type": "one_time"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        assert r.json()["recurrence_type"] == "one_time"
        p = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-lifestyle",
                          headers=auth_headers, timeout=10)
        assert p.status_code == 200, p.text
        body = p.json()
        assert body["action_item"]["ported_to"] == "LIFESTYLE"
        assert body["action_item"]["recurrence_type"] == "recurring"
        assert body["lifestyle_routine"]["source_type"] == "ACTION_ITEM"
        # DB cross-check
        routine = mongo_db.lifestyle_routines.find_one({"routine_id": body["lifestyle_routine"]["routine_id"]})
        assert routine is not None
        assert routine["source_id"] == aid

    def test_port_to_lifestyle_409_on_repeat(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "MANUAL", "title": "TEST_lifestyle_dup",
                                "recurrence_type": "recurring", "recurrence_frequency": "daily"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        p1 = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-lifestyle", headers=auth_headers, timeout=10)
        assert p1.status_code == 200
        p2 = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-lifestyle", headers=auth_headers, timeout=10)
        assert p2.status_code == 409


# ────────────────────────────────────────────────────────────────────────────
# UNPORT
# ────────────────────────────────────────────────────────────────────────────

class TestUnport:
    def test_unport_clears_link_but_preserves_downstream(self, auth_headers, mongo_db):
        r = requests.post(f"{BASE_URL}/api/action-items",
                          json={"source_module": "MANUAL", "title": "TEST_unport_item"},
                          headers=auth_headers, timeout=10)
        aid = r.json()["action_id"]
        p = requests.post(f"{BASE_URL}/api/action-items/{aid}/port-to-ctt", headers=auth_headers, timeout=10)
        assert p.status_code == 200
        task_id = p.json()["ctt_task"]["task_id"]

        u = requests.post(f"{BASE_URL}/api/action-items/{aid}/unport", headers=auth_headers, timeout=10)
        assert u.status_code == 200
        g = requests.get(f"{BASE_URL}/api/action-items/{aid}", headers=auth_headers, timeout=10)
        assert g.json()["ported_to"] is None
        assert g.json()["ported_ref_id"] is None
        # Downstream CTT row preserved
        assert mongo_db.ctt_tasks.find_one({"task_id": task_id}) is not None


# ────────────────────────────────────────────────────────────────────────────
# IMPORT-FROM-MPPS
# ────────────────────────────────────────────────────────────────────────────

class TestImportFromMpps:
    @pytest.fixture(scope="class")
    def seeded_decision(self, mongo_db, user_id):
        decision_id = "TEST_MPPS_" + uuid.uuid4().hex[:8]
        mongo_db.decisions.insert_one({
            "id": decision_id,
            "user_id": user_id,
            "title": "TEST_MPPS_decision_seed",
            "folder": "Career",
            "mpps_improvements": [
                {
                    "factor_id": "F1",
                    "action_items": [
                        {"task": "TEST_MPPS_item_alpha", "assignee_name": "Alice",
                         "assignee_email": "a@x.com", "deadline": "2026-09-01"},
                        {"task": "TEST_MPPS_item_beta",  "assignee_name": "Bob",
                         "deadline": "2026-10-15"},
                        {"task": "", "assignee_name": "Skip"},  # should skip empty
                    ],
                },
                {"factor_id": "F2", "action_items": [
                    {"task": "TEST_MPPS_item_gamma", "assignee_name": "Carol", "deadline": "2026-12-01"},
                ]},
            ],
        })
        yield decision_id

    def test_import_initial_count(self, auth_headers, seeded_decision):
        r = requests.post(f"{BASE_URL}/api/action-items/import-from-mpps/{seeded_decision}",
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Empty title should be skipped → 3 imported (alpha, beta, gamma)
        assert body["imported_count"] == 3
        labels = {it["title"] for it in body["imported"]}
        # New bracketed format: when the seed has no factor record / projected %,
        # title falls back to `[Factor] · <task>` (no rating, no delta).
        assert any("TEST_MPPS_item_alpha" in t for t in labels), labels
        assert any("TEST_MPPS_item_gamma" in t for t in labels), labels
        # life_area derived from decision.folder
        assert all(it["life_area"] == "Career" for it in body["imported"])

    def test_import_is_idempotent(self, auth_headers, seeded_decision):
        r = requests.post(f"{BASE_URL}/api/action-items/import-from-mpps/{seeded_decision}",
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["imported_count"] == 0

    def test_import_unknown_decision_404(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/action-items/import-from-mpps/nonexistent",
                          headers=auth_headers, timeout=10)
        assert r.status_code == 404


# ────────────────────────────────────────────────────────────────────────────
# STATS SUMMARY
# ────────────────────────────────────────────────────────────────────────────

class TestStatsSummary:
    def test_summary_shape_and_counts(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/action-items/stats/summary",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert "total" in body
        assert "by_status" in body
        assert "by_source" in body
        assert "by_ported" in body
        assert isinstance(body["total"], int)
        # We've created many items by this point
        assert body["total"] >= 1
        # by_status keys should be subset of allowed statuses
        for k in body["by_status"]:
            assert k in {"pending", "in_progress", "done", "blocked", "cancelled"}
