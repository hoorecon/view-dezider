"""
Regression tests for the refactored /app/backend/routes/decisions/ package.

Goal: verify that splitting the monolithic decisions.py into sub-modules
(crud, assessment, templates, admin, test123, assessment_modes, journal,
dashboard, sharing, mpps) did NOT change behaviour.

All endpoints are still mounted under /api and the public import contract
`from routes.decisions import router` is unchanged.
"""

import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://modal-responsive-fix.preview.emergentagent.com"
).rstrip("/")

REG_EMAIL = "harden_1777921741@example.com"
REG_PASS = "HardenPass2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"


# ─────────────────────────── helpers / fixtures ───────────────────────────

def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def user_token():
    return _login(REG_EMAIL, REG_PASS)


@pytest.fixture(scope="module")
def admin_token():
    try:
        return _login(ADMIN_EMAIL, ADMIN_PASS)
    except AssertionError:
        pytest.skip("admin@test.com login unavailable")


@pytest.fixture(scope="module")
def super_token():
    try:
        return _login(SUPER_EMAIL, SUPER_PASS)
    except AssertionError:
        pytest.skip("super admin login unavailable")


@pytest.fixture
def H(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ─────────────────────────── crud.py ───────────────────────────

class TestDecisionsCRUD:
    """POST/GET/PUT/DELETE/clone on /api/decisions"""

    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200

    def test_create_list_get_decision(self, H):
        payload = {"title": f"TEST_iter72_{uuid.uuid4().hex[:8]}",
                   "context": "regression test for refactor", "folder": ""}
        r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=H, timeout=20)
        assert r.status_code == 200, r.text
        did = r.json()["id"]

        # GET single
        g = requests.get(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)
        assert g.status_code == 200
        body = g.json()
        assert body["id"] == did and body["title"] == payload["title"]

        # LIST contains it
        lst = requests.get(f"{BASE_URL}/api/decisions", headers=H, timeout=20)
        assert lst.status_code == 200
        assert any(d["id"] == did for d in lst.json())

        # cleanup
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)

    def test_update_recomputes_worth_percentage(self, H):
        # Create
        create = requests.post(f"{BASE_URL}/api/decisions",
                               json={"title": f"TEST_iter72_worth_{uuid.uuid4().hex[:6]}",
                                     "context": "worth recompute", "folder": ""},
                               headers=H, timeout=20).json()
        did = create["id"]

        f1, f2 = str(uuid.uuid4()), str(uuid.uuid4())
        o1 = str(uuid.uuid4())
        factors = [
            {"id": f1, "name": "Cost", "category": "primary", "rating": 4, "order": 0},
            {"id": f2, "name": "Quality", "category": "primary", "rating": 6, "order": 1},
        ]
        options = [{
            "id": o1, "name": "OptA",
            "assessments": [
                {"factor_id": f1, "percentage": 50},
                {"factor_id": f2, "percentage": 100},
            ],
            "worth_percentage": 0.0,
        }]
        upd = requests.put(f"{BASE_URL}/api/decisions/{did}",
                           json={"factors": factors, "options": options},
                           headers=H, timeout=20)
        assert upd.status_code == 200, upd.text

        got = requests.get(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20).json()
        # 4/10 * 50 + 6/10 * 100 = 20 + 60 = 80
        assert got["options"][0]["worth_percentage"] == 80.0, got["options"][0]

        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)

    def test_delete_moves_to_trash(self, H):
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_del_{uuid.uuid4().hex[:6]}",
                                  "context": "x", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        d = requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)
        assert d.status_code == 200
        # GET should now 404 (trashed → moved out of decisions collection or hidden)
        g = requests.get(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)
        assert g.status_code == 404, g.text

    def test_clone_decision(self, H):
        # Setup source with factors+options
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_src_{uuid.uuid4().hex[:6]}",
                                  "context": "clone source", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        f1 = str(uuid.uuid4())
        requests.put(f"{BASE_URL}/api/decisions/{did}",
                     json={"factors": [{"id": f1, "name": "F1", "category": "primary",
                                        "rating": 5, "order": 0}],
                           "options": [{"id": str(uuid.uuid4()), "name": "O1",
                                        "assessments": [{"factor_id": f1, "percentage": 80}],
                                        "worth_percentage": 0}]},
                     headers=H, timeout=20)

        c = requests.post(f"{BASE_URL}/api/decisions/{did}/clone",
                          json={"title": "TEST_iter72_clone", "clone_level": "options"},
                          headers=H, timeout=20)
        assert c.status_code == 200, c.text
        new_id = c.json()["id"]
        new_d = requests.get(f"{BASE_URL}/api/decisions/{new_id}", headers=H, timeout=20).json()
        assert new_d["title"] == "TEST_iter72_clone"
        assert len(new_d["factors"]) == 1 and len(new_d["options"]) == 1

        for x in (did, new_id):
            requests.delete(f"{BASE_URL}/api/decisions/{x}", headers=H, timeout=20)


# ─────────────────────────── templates.py ───────────────────────────

class TestTemplates:
    def test_template_lifecycle(self, H):
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_tpl_src_{uuid.uuid4().hex[:6]}",
                                  "context": "tpl source", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        save = requests.post(f"{BASE_URL}/api/decisions/{did}/save-as-template",
                             json={"name": "TEST_iter72_tpl", "template_type": "options",
                                   "visibility": "private", "shared_with": []},
                             headers=H, timeout=20)
        assert save.status_code == 200, save.text
        tid = save.json()["id"]

        # List
        lst = requests.get(f"{BASE_URL}/api/templates", headers=H, timeout=20)
        assert lst.status_code == 200
        body = lst.json()
        assert "my_templates" in body
        assert any(t["id"] == tid for t in body["my_templates"])

        # Update
        upd = requests.put(f"{BASE_URL}/api/templates/{tid}",
                           json={"name": "TEST_iter72_tpl_renamed", "template_type": "options",
                                 "visibility": "private", "shared_with": []},
                           headers=H, timeout=20)
        assert upd.status_code == 200, upd.text

        # Use
        use = requests.post(f"{BASE_URL}/api/templates/{tid}/use",
                            json={"title": "TEST_iter72_tpl_used"}, headers=H, timeout=20)
        assert use.status_code == 200, use.text
        used_id = use.json()["id"]

        # Delete
        d = requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=H, timeout=20)
        assert d.status_code == 200

        for x in (did, used_id):
            requests.delete(f"{BASE_URL}/api/decisions/{x}", headers=H, timeout=20)


# ─────────────────────────── admin.py ───────────────────────────

class TestAdmin:
    def test_admin_promote_demote_forbidden_for_non_root(self, admin_token):
        Ha = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{BASE_URL}/api/admin/promote",
                          json={"email": "noone@example.com", "role": "admin"},
                          headers=Ha, timeout=20)
        assert r.status_code == 403, r.text
        r2 = requests.post(f"{BASE_URL}/api/admin/demote",
                           json={"email": "noone@example.com"}, headers=Ha, timeout=20)
        assert r2.status_code == 403
        r3 = requests.post(f"{BASE_URL}/api/admin/setup", headers=Ha, timeout=20)
        assert r3.status_code == 403

    def test_admin_users_list(self, super_token):
        Hs = {"Authorization": f"Bearer {super_token}"}
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=Hs, timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_super_admin_can_call_promote_route(self, super_token):
        # Verify the route exists & runs end-to-end (target user not found → 404
        # is the expected outcome). Anything other than 401/403/500 means the
        # route is wired correctly post-refactor.
        Hs = {"Authorization": f"Bearer {super_token}"}
        r = requests.post(f"{BASE_URL}/api/admin/promote",
                          json={"email": f"nobody_{uuid.uuid4().hex[:6]}@example.com",
                                "role": "admin"},
                          headers=Hs, timeout=20)
        assert r.status_code in (404, 400), f"unexpected: {r.status_code} {r.text}"


# ─────────────────────────── test123.py ───────────────────────────

class TestTest123:
    def test_test123_full_lifecycle(self, H):
        r = requests.post(f"{BASE_URL}/api/test123",
                          json={"situation": "TEST_iter72 quick decision"},
                          headers=H, timeout=20)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        g = requests.get(f"{BASE_URL}/api/test123/{sid}", headers=H, timeout=20)
        assert g.status_code == 200

        lst = requests.get(f"{BASE_URL}/api/test123", headers=H, timeout=20)
        assert lst.status_code == 200 and isinstance(lst.json(), list)

        u = requests.put(f"{BASE_URL}/api/test123/{sid}",
                         json={"title": "TEST_iter72_t123"}, headers=H, timeout=20)
        assert u.status_code == 200, u.text

        d = requests.delete(f"{BASE_URL}/api/test123/{sid}", headers=H, timeout=20)
        assert d.status_code == 200


# ─────────────────────────── assessment_modes.py ───────────────────────────

class TestModeAssessment:
    def test_questions(self, H):
        r = requests.get(f"{BASE_URL}/api/assessment/questions", headers=H, timeout=20)
        assert r.status_code == 200, r.text

    def test_history(self, H):
        r = requests.get(f"{BASE_URL}/api/assessment/history", headers=H, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ─────────────────────────── journal.py ───────────────────────────

class TestJournal:
    def test_journal_full_lifecycle(self, H):
        c = requests.post(f"{BASE_URL}/api/journal",
                          json={"decision_title": "TEST_iter72_j",
                                "decision_description": "desc"},
                          headers=H, timeout=20)
        assert c.status_code == 200, c.text
        jid = c.json()["id"]

        g = requests.get(f"{BASE_URL}/api/journal/{jid}", headers=H, timeout=20)
        assert g.status_code == 200

        lst = requests.get(f"{BASE_URL}/api/journal", headers=H, timeout=20)
        assert lst.status_code == 200 and isinstance(lst.json(), list)

        rem = requests.get(f"{BASE_URL}/api/journal/reminders", headers=H, timeout=20)
        assert rem.status_code == 200

        link = requests.get(f"{BASE_URL}/api/journal/linkable-items", headers=H, timeout=20)
        assert link.status_code == 200

        u = requests.put(f"{BASE_URL}/api/journal/{jid}",
                         json={"decision_title": "TEST_iter72_j_upd"},
                         headers=H, timeout=20)
        assert u.status_code == 200

        d = requests.delete(f"{BASE_URL}/api/journal/{jid}", headers=H, timeout=20)
        assert d.status_code == 200


# ─────────────────────────── dashboard.py ───────────────────────────

class TestDashboard:
    def test_stats(self, H):
        r = requests.get(f"{BASE_URL}/api/stats", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_folders(self, H):
        r = requests.get(f"{BASE_URL}/api/folders", headers=H, timeout=20)
        assert r.status_code == 200


# ─────────────────────────── sharing.py ───────────────────────────

class TestSharing:
    def test_received_sent_listings(self, H):
        rec = requests.get(f"{BASE_URL}/api/shared-steps/received", headers=H, timeout=20)
        assert rec.status_code == 200
        assert isinstance(rec.json(), list)
        snt = requests.get(f"{BASE_URL}/api/shared-steps/sent", headers=H, timeout=20)
        assert snt.status_code == 200
        assert isinstance(snt.json(), list)

    def test_share_step_no_valid_recipients_returns_400(self, H):
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_share_{uuid.uuid4().hex[:6]}",
                                  "context": "share", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        r = requests.post(f"{BASE_URL}/api/decisions/{did}/share-step",
                          json={"decision_id": did, "step_number": 2,
                                "recipient_emails": [f"ghost_{uuid.uuid4().hex[:8]}@nowhere.example"],
                                "merge_mode": "equal", "message": ""},
                          headers=H, timeout=20)
        # No matching users found → 400 as in original behaviour
        assert r.status_code == 400, r.text
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)


# ─────────────────────────── mpps.py ───────────────────────────

class TestMPPSDownloads:
    def test_csv_and_pdf(self, H):
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_mpps_{uuid.uuid4().hex[:6]}",
                                  "context": "mpps", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        # Seed minimal mpps data
        f1, o1 = str(uuid.uuid4()), str(uuid.uuid4())
        requests.put(f"{BASE_URL}/api/decisions/{did}",
                     json={"factors": [{"id": f1, "name": "F1", "category": "primary",
                                        "rating": 5, "order": 0}],
                           "options": [{"id": o1, "name": "O1",
                                        "assessments": [{"factor_id": f1, "percentage": 50}],
                                        "worth_percentage": 0}],
                           "mpps_option_id": o1,
                           "mpps_improvements": [{"factor_id": f1, "improvement_plan": "do x",
                                                  "tepfi_elements": ["T"], "tepfi_layer": "L1",
                                                  "original_percentage": 50,
                                                  "projected_percentage": 70,
                                                  "delta_percentage": 20,
                                                  "expected_value": "10", "expected_unit": "u",
                                                  "action_items": []}]},
                     headers=H, timeout=20)

        csv = requests.get(f"{BASE_URL}/api/decisions/{did}/mpps-action-plan",
                           headers=H, timeout=30)
        assert csv.status_code == 200, csv.text
        ctype = csv.headers.get("content-type", "")
        assert "csv" in ctype or "text" in ctype, ctype

        pdf = requests.get(f"{BASE_URL}/api/decisions/{did}/mpps-action-plan-pdf",
                           headers=H, timeout=30)
        assert pdf.status_code == 200, pdf.text[:300]
        assert "pdf" in pdf.headers.get("content-type", "").lower()

        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)


# ─────────────────────────── assessment.py (smoke) ───────────────────────────

class TestAssessmentTemplate:
    def test_xlsx_template(self, H):
        did = requests.post(f"{BASE_URL}/api/decisions",
                            json={"title": f"TEST_iter72_xls_{uuid.uuid4().hex[:6]}",
                                  "context": "xls", "folder": ""},
                            headers=H, timeout=20).json()["id"]
        f1, o1 = str(uuid.uuid4()), str(uuid.uuid4())
        requests.put(f"{BASE_URL}/api/decisions/{did}",
                     json={"factors": [{"id": f1, "name": "F1", "category": "primary",
                                        "rating": 5, "order": 0}],
                           "options": [{"id": o1, "name": "O1", "assessments": [],
                                        "worth_percentage": 0}]},
                     headers=H, timeout=20)
        r = requests.get(f"{BASE_URL}/api/decisions/{did}/assessment-template",
                         headers=H, timeout=30)
        # xlsx template should be 200 with spreadsheet content-type
        assert r.status_code == 200, r.text[:300]
        ctype = r.headers.get("content-type", "").lower()
        assert "spreadsheet" in ctype or "xls" in ctype or "octet-stream" in ctype, ctype
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=H, timeout=20)
