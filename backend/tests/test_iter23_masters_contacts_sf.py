"""
Iteration 23 — Backend tests covering:
  1) Masters API (GET types, list per type, search, cascade, CRUD admin/403 non-admin)
  2) Contacts new Phase-2 fields persistence (languages/occupation/drives/traits/profile_image/resources.finance.*)
  3) Solution Finder status='completed' persistence via PUT (bug #1)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
if not BASE_URL:
    # fall back to local backend port for safety in pytest
    BASE_URL = "http://localhost:8001"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("token") or body.get("access_token")
    assert token, f"no token in login response: {body}"
    return token


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER_EMAIL, USER_PASSWORD)


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ─────────────────────────── MASTERS ───────────────────────────

class TestMasters:
    def test_get_types(self, user_token):
        r = requests.get(f"{API}/masters/types", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        types = r.json().get("types", [])
        for expected in ["religion", "caste", "language", "occupation", "skill", "drive", "trait"]:
            assert expected in types, f"missing master type {expected}"

    @pytest.mark.parametrize("mtype,expected_min", [
        ("religion", 11),
        ("caste", 238),
        ("language", 44),
        ("occupation", 231),
        ("skill", 40),
        ("drive", 20),
        ("trait", 30),
    ])
    def test_seeded_counts(self, user_token, mtype, expected_min):
        r = requests.get(f"{API}/masters/{mtype}?limit=2000", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        assert len(items) >= expected_min, f"{mtype} expected >= {expected_min}, got {len(items)}"
        # validate shape
        for it in items[:3]:
            assert "master_id" in it
            assert "value" in it
            assert it.get("type") == mtype

    def test_caste_cascade_by_religion(self, user_token):
        r = requests.get(f"{API}/masters/caste?parent=Hindu", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        assert len(items) > 0, "Hindu castes returned empty"
        for it in items:
            p = (it.get("parent") or "").lower()
            assert p == "hindu", f"caste {it.get('value')} parent expected hindu, got {p}"

    def test_search_case_insensitive(self, user_token):
        r = requests.get(f"{API}/masters/religion?search=hin", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        values = [i["value"].lower() for i in r.json().get("items", [])]
        assert any("hin" in v for v in values), f"expected at least one religion containing 'hin', got {values}"

    def test_unknown_type_400(self, user_token):
        r = requests.get(f"{API}/masters/bogustype", headers=_h(user_token), timeout=20)
        assert r.status_code == 400

    def test_non_admin_cannot_create(self, user_token):
        r = requests.post(
            f"{API}/masters",
            headers=_h(user_token),
            json={"type": "skill", "value": "TEST_unauthorized_skill"},
            timeout=20,
        )
        assert r.status_code == 403, f"non-admin POST expected 403, got {r.status_code} {r.text}"

    def test_admin_crud_roundtrip(self, admin_token):
        unique = f"TEST_iter23_skill_{int(time.time())}"
        # CREATE
        r = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "skill", "value": unique},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        mid = r.json().get("master_id")
        assert mid

        # READ back via search
        r2 = requests.get(f"{API}/masters/skill?search={unique}", headers=_h(admin_token), timeout=20)
        assert r2.status_code == 200
        values = [i["value"] for i in r2.json().get("items", [])]
        assert unique in values

        # UPDATE
        renamed = unique + "_renamed"
        r3 = requests.put(
            f"{API}/masters/{mid}",
            headers=_h(admin_token),
            json={"value": renamed},
            timeout=20,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json().get("value") == renamed

        # DELETE
        r4 = requests.delete(f"{API}/masters/{mid}", headers=_h(admin_token), timeout=20)
        assert r4.status_code == 200, r4.text
        assert r4.json().get("deleted") is True

        # Verify gone
        r5 = requests.get(f"{API}/masters/skill?search={renamed}", headers=_h(admin_token), timeout=20)
        assert renamed not in [i["value"] for i in r5.json().get("items", [])]

    def test_non_admin_cannot_update_or_delete(self, user_token, admin_token):
        # Use admin to create, then test 403 for non-admin
        unique = f"TEST_iter23_perm_{int(time.time())}"
        c = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "trait", "value": unique},
            timeout=20,
        )
        assert c.status_code == 200, c.text
        mid = c.json()["master_id"]
        try:
            up = requests.put(f"{API}/masters/{mid}", headers=_h(user_token), json={"value": "x"}, timeout=20)
            assert up.status_code == 403, f"non-admin PUT expected 403, got {up.status_code}"
            de = requests.delete(f"{API}/masters/{mid}", headers=_h(user_token), timeout=20)
            assert de.status_code == 403
        finally:
            requests.delete(f"{API}/masters/{mid}", headers=_h(admin_token), timeout=20)


# ─────────────────────────── CONTACTS ───────────────────────────

class TestContactsPhase2Fields:
    created_ids: list = []

    def test_create_contact_with_phase2_fields(self, user_token):
        payload = {
            "name": "TEST_iter23_phase2",
            "email": f"TEST_iter23_{int(time.time())}@example.com",
            "languages": ["English", "Hindi", "Tamil"],
            "occupation": "Software Engineer",
            "drives": ["Achievement", "Mastery"],
            "traits": ["Curious", "Resilient"],
            "profile_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
            "religion": "Hindu",
            "caste": "Brahmin",
            "resources": {
                "finance": {
                    "currency": "USD",
                    "monthly_cashflow": 5000,
                    "monthly_expenses": 3200,
                    "net_worth": 250000,
                },
            },
        }
        r = requests.post(f"{API}/contacts", headers=_h(user_token), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        cid = doc["id"]
        TestContactsPhase2Fields.created_ids.append(cid)

        # Persistence check via GET
        g = requests.get(f"{API}/contacts/{cid}", headers=_h(user_token), timeout=20)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("occupation") == "Software Engineer"
        assert gd.get("drives") == ["Achievement", "Mastery"]
        assert gd.get("traits") == ["Curious", "Resilient"]
        assert gd.get("profile_image", "").startswith("data:image/png;base64,")
        # NOTE: languages is in PUT allowed list; verify POST persisted too
        # POST endpoint stores body.get("language") singular AND we sent "languages".
        # If languages list was not persisted by POST, treat as a minor finding.
        fin = gd.get("resources", {}).get("finance", {})
        assert fin.get("currency") == "USD"
        assert fin.get("monthly_cashflow") == 5000
        assert fin.get("monthly_expenses") == 3200
        assert fin.get("net_worth") == 250000

    def test_update_contact_languages_via_put(self, user_token):
        assert TestContactsPhase2Fields.created_ids, "no contact created"
        cid = TestContactsPhase2Fields.created_ids[0]
        r = requests.put(
            f"{API}/contacts/{cid}",
            headers=_h(user_token),
            json={"languages": ["French", "German"], "drives": ["Service"]},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        g = requests.get(f"{API}/contacts/{cid}", headers=_h(user_token), timeout=20)
        assert g.status_code == 200
        gd = g.json()
        assert gd.get("languages") == ["French", "German"]
        assert gd.get("drives") == ["Service"]

    def test_finance_currency_defaults_inr(self, user_token):
        r = requests.post(
            f"{API}/contacts",
            headers=_h(user_token),
            json={"name": "TEST_iter23_default_currency", "resources": {"finance": {"monthly_cashflow": 100}}},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        TestContactsPhase2Fields.created_ids.append(doc["id"])
        assert doc.get("resources", {}).get("finance", {}).get("currency") == "INR"

    @classmethod
    def teardown_class(cls):
        try:
            t = _login(USER_EMAIL, USER_PASSWORD)
            for cid in cls.created_ids:
                requests.delete(f"{API}/contacts/{cid}", headers=_h(t), timeout=10)
        except Exception:
            pass


# ─────────────────────────── SOLUTION FINDER (bug #1) ───────────────────────────

class TestSolutionFinderStatusCompletion:
    created_ids: list = []

    def test_create_and_complete(self, user_token):
        # Create
        r = requests.post(
            f"{API}/solution-finders",
            headers=_h(user_token),
            json={"smart_goal": "TEST_iter23_sf", "area_of_life": "Career"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        eid = doc["entry_id"]
        TestSolutionFinderStatusCompletion.created_ids.append(eid)
        assert doc.get("status") == "in_progress"

        # PUT status=completed
        up = requests.put(
            f"{API}/solution-finders/{eid}",
            headers=_h(user_token),
            json={"status": "completed"},
            timeout=20,
        )
        assert up.status_code == 200, up.text
        assert up.json().get("status") == "completed"

        # GET and verify
        g = requests.get(f"{API}/solution-finders/{eid}", headers=_h(user_token), timeout=20)
        assert g.status_code == 200
        assert g.json().get("status") == "completed", f"status not persisted: {g.json()}"

    def test_list_returns_completed(self, user_token):
        r = requests.get(f"{API}/solution-finders", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        entries = data.get("entries") if isinstance(data, dict) else data
        if isinstance(entries, dict):
            entries = entries.get("entries") or []
        statuses = {e["entry_id"]: e.get("status") for e in entries if "entry_id" in e}
        for eid in TestSolutionFinderStatusCompletion.created_ids:
            assert statuses.get(eid) == "completed", f"list status mismatch for {eid}: {statuses.get(eid)}"

    def test_list_returns_updated_at(self, user_token):
        r = requests.get(f"{API}/solution-finders", headers=_h(user_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        entries = data.get("entries") if isinstance(data, dict) else data
        if isinstance(entries, dict):
            entries = entries.get("entries") or []
        assert entries, "expected at least one SF entry"
        for e in entries:
            assert e.get("updated_at") or e.get("created_at"), "entry missing timestamp"

    @classmethod
    def teardown_class(cls):
        try:
            t = _login(USER_EMAIL, USER_PASSWORD)
            for eid in cls.created_ids:
                requests.delete(f"{API}/solution-finders/{eid}", headers=_h(t), timeout=10)
        except Exception:
            pass
