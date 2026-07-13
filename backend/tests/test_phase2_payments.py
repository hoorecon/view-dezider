"""
Phase 2 Payments backend tests.

Covers:
  * DELETE /api/hos/templates/{id} — admin path, author path (CUSTOM_BLANK), 403 for non-author on AUTHORIZED_STANDARD, deletion_log audit row.
  * POST /api/hos/admin/templates/bulk-delete — admin only (title_prefix), idempotent second call.
  * GET /api/store/admin/l4-queue — admin / non-admin / status filter.
  * GET /api/store/admin/experts-pick-list — admin / non-admin.
  * POST /api/store/admin/l4-queue/{id}/assign — moves awaiting_assignment → in_progress.
  * PUT /api/store/admin/l4-queue/{id}/status — delivered / cancelled / 400 invalid.
"""
import os
import re
import uuid
import requests
import pytest
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://repo-blueprint-1.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _login(email: str, pwd: str) -> dict:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    return r.json()


def H(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _now():
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_session():
    d = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": d["session_token"], "user_id": d["user_id"], "name": d.get("name", "")}


@pytest.fixture(scope="session")
def user_session():
    d = _login(USER_EMAIL, USER_PASSWORD)
    return {"token": d["session_token"], "user_id": d["user_id"], "name": d.get("name", "")}


@pytest.fixture(scope="session")
def mongo_db():
    cl = MongoClient(MONGO_URL)
    db = cl[DB_NAME]
    yield db
    cl.close()


# ─────────────────────────────────────────────────────────────────────
# 1. DELETE /api/hos/templates/{id}
# ─────────────────────────────────────────────────────────────────────
class TestTemplateDelete:
    def _insert_template(self, mongo_db, **overrides):
        tid = f"TEST_TPL_{uuid.uuid4().hex[:8]}"
        doc = {
            "id": tid,
            "title": f"TEST_{tid}",
            "description": "phase2 test",
            "source_type": overrides.get("source_type", "CUSTOM_BLANK"),
            "approval_status": overrides.get("approval_status", "pending"),
            "created_by_user_id": overrides.get("created_by_user_id"),
            "created_at": _now(),
        }
        doc.update({k: v for k, v in overrides.items() if k not in doc})
        mongo_db.hos_decision_templates.insert_one(doc)
        return tid

    def test_admin_delete_template_200_and_get_404(self, admin_session, mongo_db):
        tid = self._insert_template(mongo_db, source_type="AUTHORIZED_STANDARD",
                                    approval_status="approved")
        r = requests.delete(f"{API}/hos/templates/{tid}", headers=H(admin_session["token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("deleted") is True
        assert body.get("template_id") == tid

        # GET → 404
        g = requests.get(f"{API}/hos/templates/{tid}", headers=H(admin_session["token"]), timeout=15)
        assert g.status_code == 404, g.text

        # deletion_log row exists
        log = mongo_db.hos_template_deletion_log.find_one({"template_id": tid})
        assert log is not None
        assert log.get("deleted_by_role") in ("admin", "author")

    def test_author_can_delete_own_custom_blank_pending(self, user_session, mongo_db):
        tid = self._insert_template(
            mongo_db,
            source_type="CUSTOM_BLANK",
            approval_status="pending",
            created_by_user_id=user_session["user_id"],
        )
        r = requests.delete(f"{API}/hos/templates/{tid}", headers=H(user_session["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("deleted") is True

    def test_non_admin_cannot_delete_authorized_standard(self, user_session, mongo_db):
        tid = self._insert_template(
            mongo_db,
            source_type="AUTHORIZED_STANDARD",
            approval_status="approved",
            created_by_user_id="someone_else",
        )
        r = requests.delete(f"{API}/hos/templates/{tid}", headers=H(user_session["token"]), timeout=15)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        # Cleanup
        mongo_db.hos_decision_templates.delete_one({"id": tid})

    def test_delete_nonexistent_404(self, admin_session):
        r = requests.delete(
            f"{API}/hos/templates/DOES_NOT_EXIST_{uuid.uuid4().hex[:6]}",
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 2. POST /api/hos/admin/templates/bulk-delete
# ─────────────────────────────────────────────────────────────────────
class TestBulkDelete:
    def test_bulk_delete_by_title_prefix(self, admin_session, mongo_db):
        prefix = f"TEST_BULK_{uuid.uuid4().hex[:6]}_"
        # Insert 3 templates with the prefix
        ids = []
        for i in range(3):
            tid = f"{prefix}{i}"
            mongo_db.hos_decision_templates.insert_one({
                "id": tid,
                "title": f"{prefix}item_{i}",
                "source_type": "CUSTOM_BLANK",
                "approval_status": "pending",
                "created_at": _now(),
            })
            ids.append(tid)

        # First call deletes 3
        r = requests.post(
            f"{API}/hos/admin/templates/bulk-delete",
            json={"title_prefix": prefix},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deleted_count"] == 3, body
        matched_ids = {m["id"] for m in body["matched"]}
        assert set(ids) == matched_ids

        # Second call → idempotent (0)
        r2 = requests.post(
            f"{API}/hos/admin/templates/bulk-delete",
            json={"title_prefix": prefix},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["deleted_count"] == 0
        assert r2.json()["matched"] == []

    def test_non_admin_bulk_delete_forbidden(self, user_session):
        r = requests.post(
            f"{API}/hos/admin/templates/bulk-delete",
            json={"title_prefix": "TEST_"},
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# 3. L4 queue
# ─────────────────────────────────────────────────────────────────────
class TestL4Queue:
    @pytest.fixture
    def expert_id(self, mongo_db):
        eid = f"TEST_EXP_{uuid.uuid4().hex[:8]}"
        mongo_db.experts.insert_one({
            "expert_id": eid,
            "name": "Test Expert Phase2",
            "specializations": ["career", "swot"],
            "rating_avg": 4.7,
            "is_online": True,
            "status": "active",
            "created_at": _now(),
        })
        yield eid
        mongo_db.experts.delete_one({"expert_id": eid})

    @pytest.fixture
    def delivery_id(self, admin_session, mongo_db):
        did = f"test_d_{uuid.uuid4().hex[:8]}"
        mongo_db.expert_deliveries.insert_one({
            "id": did,
            "order_id": f"test_o_{uuid.uuid4().hex[:6]}",
            "user_id": admin_session["user_id"],
            "sku_code": "L4",
            "status": "awaiting_assignment",
            "module": "swot",
            "decision_id": f"TEST_SWOT_{uuid.uuid4().hex[:6]}",
            "created_at": _now(),
        })
        yield did
        mongo_db.expert_deliveries.delete_one({"id": did})

    def test_l4_queue_admin_shape(self, admin_session, delivery_id):
        r = requests.get(f"{API}/store/admin/l4-queue", headers=H(admin_session["token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert "counts" in body
        assert "statuses" in body
        assert set(body["statuses"]) >= {"awaiting_assignment", "in_progress", "delivered", "cancelled"}
        ids_in_queue = [i["id"] for i in body["items"]]
        assert delivery_id in ids_in_queue

    def test_l4_queue_filter_by_status(self, admin_session, delivery_id):
        r = requests.get(
            f"{API}/store/admin/l4-queue",
            params={"status": "awaiting_assignment"},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        for it in items:
            assert it["status"] == "awaiting_assignment"

    def test_l4_queue_invalid_status_400(self, admin_session):
        r = requests.get(
            f"{API}/store/admin/l4-queue",
            params={"status": "garbage_status"},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 400

    def test_l4_queue_non_admin_403(self, user_session):
        r = requests.get(f"{API}/store/admin/l4-queue", headers=H(user_session["token"]), timeout=15)
        assert r.status_code == 403

    def test_experts_pick_list_admin(self, admin_session, expert_id):
        r = requests.get(
            f"{API}/store/admin/experts-pick-list",
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        experts = r.json().get("experts") or []
        eids = [e["expert_id"] for e in experts]
        assert expert_id in eids
        # Sorted by rating_avg desc (None coerced to -inf for comparison)
        ratings = [(e.get("rating_avg") if e.get("rating_avg") is not None else -1) for e in experts]
        assert ratings == sorted(ratings, reverse=True), f"Not sorted desc: {ratings}"

    def test_experts_pick_list_non_admin_403(self, user_session):
        r = requests.get(
            f"{API}/store/admin/experts-pick-list",
            headers=H(user_session["token"]),
            timeout=15,
        )
        assert r.status_code == 403

    def test_assign_moves_to_in_progress(self, admin_session, delivery_id, expert_id):
        r = requests.post(
            f"{API}/store/admin/l4-queue/{delivery_id}/assign",
            json={"expert_id": expert_id, "sla_hours": 48, "admin_notes": "phase2 test assign"},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "in_progress"
        assert d["expert_id"] == expert_id
        assert d.get("expert_name")
        assert d.get("assigned_at")
        assert d.get("due_at")

    def test_status_delivered(self, admin_session, delivery_id, expert_id):
        # First assign
        requests.post(
            f"{API}/store/admin/l4-queue/{delivery_id}/assign",
            json={"expert_id": expert_id, "sla_hours": 48},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        # Mark delivered
        r = requests.put(
            f"{API}/store/admin/l4-queue/{delivery_id}/status",
            json={"status": "delivered", "deliverable_url": "https://example.com/report.pdf",
                  "deliverable_note": "All done"},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "delivered"
        assert d.get("delivered_at")
        assert d.get("deliverable_url") == "https://example.com/report.pdf"

    def test_status_cancelled(self, admin_session, mongo_db):
        # Make a fresh delivery
        did = f"test_d_cancel_{uuid.uuid4().hex[:6]}"
        mongo_db.expert_deliveries.insert_one({
            "id": did,
            "order_id": f"test_o_{uuid.uuid4().hex[:6]}",
            "user_id": admin_session["user_id"],
            "sku_code": "L4",
            "status": "awaiting_assignment",
            "module": "swot",
            "decision_id": f"TEST_SWOT_{uuid.uuid4().hex[:6]}",
            "created_at": _now(),
        })
        try:
            r = requests.put(
                f"{API}/store/admin/l4-queue/{did}/status",
                json={"status": "cancelled"},
                headers=H(admin_session["token"]),
                timeout=15,
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "cancelled"
            assert r.json().get("cancelled_at")
        finally:
            mongo_db.expert_deliveries.delete_one({"id": did})

    def test_status_invalid_400(self, admin_session, delivery_id):
        r = requests.put(
            f"{API}/store/admin/l4-queue/{delivery_id}/status",
            json={"status": "bogus_status"},
            headers=H(admin_session["token"]),
            timeout=15,
        )
        assert r.status_code == 400, r.text
