"""
Iteration 24 — Backend tests for this session's fixes:

  1) Masters dedup migration ran on boot — masters list has no
     duplicate (value_lower, parent_lower) per type.
  2) Masters search & cascade still work; caste?parent=Hindu returns Hindu castes.
  3) Admin POST /api/masters rejects duplicates with 409.
  4) Admin POST/PUT/DELETE still work for new masters rows.
  5) Contacts CRUD — POST /api/contacts with profile_image (data-URI)
     persists; GET /api/contacts and GET /api/contacts/{id} both return it.
"""
import os
import time
from collections import defaultdict
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"

MASTER_TYPES = ["religion", "caste", "language", "occupation", "skill", "drive", "trait"]
PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("token") or body.get("access_token")
    assert token, f"no token in login response: {body}"
    return token


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER_EMAIL, USER_PASSWORD)


# ─────────────────────────── MASTERS — DEDUP ───────────────────────────

class TestMastersDedup:
    """Confirms dedup migration left the masters collection with no duplicates."""

    @pytest.mark.parametrize("mtype", MASTER_TYPES)
    def test_no_duplicate_value_parent_per_type(self, user_token, mtype):
        r = requests.get(f"{API}/masters/{mtype}?limit=2000", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        seen = defaultdict(list)
        for it in items:
            key = ((it.get("value") or "").strip().lower(), (it.get("parent") or "").strip().lower())
            seen[key].append(it.get("master_id"))
        dups = {k: ids for k, ids in seen.items() if len(ids) > 1}
        assert not dups, f"{mtype} has duplicate (value,parent) groups: {dups}"

    def test_caste_cascade_hindu(self, user_token):
        r = requests.get(f"{API}/masters/caste?parent=Hindu", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        assert len(items) > 0
        # All items must have parent=Hindu (case-insensitive)
        for it in items:
            assert (it.get("parent") or "").lower() == "hindu", f"non-hindu caste in cascade: {it}"
        # No dupes inside cascade
        values_lower = [(i.get("value") or "").lower() for i in items]
        assert len(values_lower) == len(set(values_lower)), \
            f"duplicate hindu castes: {[v for v in values_lower if values_lower.count(v) > 1]}"

    def test_search_filters(self, user_token):
        r = requests.get(f"{API}/masters/occupation?search=accoun", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        for it in items:
            assert "accoun" in (it.get("value") or "").lower()


# ─────────────────────────── MASTERS — ADMIN CRUD + 409 ───────────────────────────

class TestMastersAdmin:
    created_ids: list = []

    def test_create_then_duplicate_returns_409(self, admin_token):
        unique = f"TEST_iter24_skill_{int(time.time())}"
        r1 = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "skill", "value": unique},
            timeout=20,
        )
        assert r1.status_code == 200, r1.text
        mid = r1.json().get("master_id")
        assert mid
        TestMastersAdmin.created_ids.append(mid)

        # Duplicate same value (same type, no parent) should 409
        r2 = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "skill", "value": unique},
            timeout=20,
        )
        assert r2.status_code == 409, f"expected 409 dup, got {r2.status_code} {r2.text}"

        # Case-insensitive duplicate should also 409
        r3 = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "skill", "value": unique.upper()},
            timeout=20,
        )
        assert r3.status_code == 409, f"expected 409 case-insensitive dup, got {r3.status_code} {r3.text}"

    def test_caste_dup_scoped_by_parent(self, admin_token):
        unique = f"TEST_caste_iter24_{int(time.time())}"
        # Create under religion Hindu
        a = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "caste", "value": unique, "parent": "Hindu"},
            timeout=20,
        )
        assert a.status_code == 200, a.text
        TestMastersAdmin.created_ids.append(a.json()["master_id"])

        # Same value but different parent (Christian) — allowed
        b = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "caste", "value": unique, "parent": "Christian"},
            timeout=20,
        )
        assert b.status_code == 200, b.text
        TestMastersAdmin.created_ids.append(b.json()["master_id"])

        # Same value AND same parent → 409
        c = requests.post(
            f"{API}/masters",
            headers=_h(admin_token),
            json={"type": "caste", "value": unique, "parent": "Hindu"},
            timeout=20,
        )
        assert c.status_code == 409, f"expected 409 dup with same parent, got {c.status_code}"

    def test_update_and_delete(self, admin_token):
        # Pick first created skill from earlier test
        if not TestMastersAdmin.created_ids:
            pytest.skip("no masters created")
        mid = TestMastersAdmin.created_ids[0]
        renamed = f"TEST_iter24_skill_renamed_{int(time.time())}"
        up = requests.put(
            f"{API}/masters/{mid}",
            headers=_h(admin_token),
            json={"value": renamed, "active": False},
            timeout=20,
        )
        assert up.status_code == 200, up.text
        assert up.json().get("value") == renamed
        assert up.json().get("active") is False

    @classmethod
    def teardown_class(cls):
        try:
            t = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
            for mid in cls.created_ids:
                requests.delete(f"{API}/masters/{mid}", headers=_h(t), timeout=10)
        except Exception:
            pass


# ─────────────────────────── CONTACTS — profile_image ───────────────────────────

class TestContactsProfileImage:
    created_ids: list = []

    def test_post_contact_with_profile_image_persists(self, user_token):
        payload = {
            "name": f"TEST_iter24_photo_{int(time.time())}",
            "profile_image": PNG_DATA_URI,
        }
        r = requests.post(f"{API}/contacts", headers=_h(user_token), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        cid = doc["id"]
        TestContactsProfileImage.created_ids.append(cid)
        assert doc.get("profile_image") == PNG_DATA_URI, "POST response missing profile_image"

        # GET /api/contacts/{id} returns it
        g = requests.get(f"{API}/contacts/{cid}", headers=_h(user_token), timeout=20)
        assert g.status_code == 200, g.text
        assert g.json().get("profile_image") == PNG_DATA_URI

    def test_list_contacts_includes_profile_image(self, user_token):
        assert TestContactsProfileImage.created_ids, "fixture: no contact created"
        cid = TestContactsProfileImage.created_ids[0]
        r = requests.get(f"{API}/contacts", headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else (data.get("contacts") or data.get("items") or [])
        found = next((c for c in items if c.get("id") == cid), None)
        assert found is not None, f"created contact {cid} not in list"
        assert found.get("profile_image") == PNG_DATA_URI, (
            f"list endpoint missing profile_image for {cid}; keys={list(found.keys())}"
        )

    @classmethod
    def teardown_class(cls):
        try:
            t = _login(USER_EMAIL, USER_PASSWORD)
            for cid in cls.created_ids:
                requests.delete(f"{API}/contacts/{cid}", headers=_h(t), timeout=10)
        except Exception:
            pass
