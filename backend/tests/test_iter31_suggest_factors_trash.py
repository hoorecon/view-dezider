"""Iter 31 — POST /api/ai/suggest-factors + Trash CRUD regression + find-best-options regression.

Per review_request: graceful empty list with used_model:null is PASS when LLM
budget is exhausted in the preview.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no session_token in {r.json()}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def decision_id(auth_headers):
    payload = {
        "title": f"TEST_iter31 Buying a Laptop {uuid.uuid4().hex[:6]}",
        "context": "Need a laptop for software development and occasional gaming under ₹1L",
        "life_area": "career",
        "decision_type": "purchase",
    }
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code in (200, 201), f"create decision failed: {r.status_code} {r.text}"
    did = r.json().get("id") or r.json().get("decision", {}).get("id")
    assert did
    yield did
    # cleanup best-effort
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=auth_headers, timeout=10)
    except Exception:
        pass


# ---------- suggest-factors ----------
class TestSuggestFactors:
    def test_auth_required(self):
        r = requests.post(f"{BASE_URL}/api/ai/suggest-factors", json={"decision_id": "x"}, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_404_for_unknown_decision(self, auth_headers):
        bogus = f"dec_{uuid.uuid4().hex}"
        r = requests.post(
            f"{BASE_URL}/api/ai/suggest-factors",
            json={"decision_id": bogus},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"

    def test_success_or_graceful_empty(self, auth_headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/ai/suggest-factors",
            json={"decision_id": decision_id, "limit": 6},
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text}"
        data = r.json()
        assert "factors" in data and isinstance(data["factors"], list)
        assert "used_model" in data
        # Graceful empty path is acceptable per review spec
        if not data["factors"]:
            assert data["used_model"] is None, (
                f"empty factors but used_model={data['used_model']!r} (should be null when LLM unavailable)"
            )
            pytest.skip("LLM budget exhausted in preview — empty list returned (graceful path PASS).")
        # If non-empty, validate factor shape
        for f in data["factors"]:
            assert f.get("name")
            assert f.get("factor_type") in ("quantitative", "qualitative")
            assert f.get("category") in ("primary", "secondary")
            pr = f.get("priority")
            assert isinstance(pr, int) and 1 <= pr <= 10
            if "expected_value_pct" in f:
                assert 0 <= float(f["expected_value_pct"]) <= 100


# ---------- find-best-options regression ----------
class TestFindBestOptionsRegression:
    def test_returns_200(self, auth_headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/ai/find-best-options",
            json={"decision_id": decision_id, "limit": 4},
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text}"
        data = r.json()
        assert "options" in data and isinstance(data["options"], list)
        assert "used_model" in data


# ---------- trash CRUD ----------
class TestTrashCRUD:
    @pytest.fixture
    def pros_cons_id(self, auth_headers):
        # Create a pros_cons item to soft-delete
        payload = {
            "title": f"TEST_iter31_PC_{uuid.uuid4().hex[:6]}",
            "decision_title": "TEST iter31 pros_cons",
            "pros": [{"text": "fast"}],
            "cons": [{"text": "expensive"}],
        }
        r = requests.post(f"{BASE_URL}/api/pros-cons", json=payload, headers=auth_headers, timeout=20)
        if r.status_code not in (200, 201):
            # try alternative route shape
            r = requests.post(f"{BASE_URL}/api/pros_cons", json=payload, headers=auth_headers, timeout=20)
        assert r.status_code in (200, 201), f"create pros_cons failed: {r.status_code} {r.text}"
        pid = r.json().get("id") or r.json().get("pros_cons", {}).get("id")
        assert pid
        return pid

    def test_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/trash", timeout=10)
        assert r.status_code in (401, 403)

    def test_empty_trash_first(self, auth_headers):
        # Empty the trash to start from a clean baseline
        r = requests.delete(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=15)
        assert r.status_code == 200

    def test_soft_delete_appears_in_trash(self, auth_headers, pros_cons_id):
        # Soft-delete the pros_cons via DELETE
        r = requests.delete(f"{BASE_URL}/api/pros-cons/{pros_cons_id}", headers=auth_headers, timeout=15)
        if r.status_code == 404:
            r = requests.delete(f"{BASE_URL}/api/pros_cons/{pros_cons_id}", headers=auth_headers, timeout=15)
        assert r.status_code in (200, 204), f"delete pros_cons failed: {r.status_code} {r.text}"

        # GET /api/trash should contain it
        r = requests.get(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data.get("items", [])
        match = [i for i in items if "TEST_iter31_PC_" in (i.get("title") or "")]
        assert match, f"deleted pros_cons not found in trash items: {items}"
        ti = match[0]
        for key in ("trash_id", "module", "label", "title", "route", "deleted_at", "days_left"):
            assert key in ti, f"missing key {key} in {ti}"
        assert ti["module"] == "pros_cons"
        assert isinstance(ti["days_left"], int) and 0 <= ti["days_left"] <= 7

    def test_restore_returns_to_collection(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=15)
        items = r.json().get("items", [])
        match = [i for i in items if "TEST_iter31_PC_" in (i.get("title") or "")]
        assert match, "no trash item to restore"
        tid = match[0]["trash_id"]
        original_id = None  # we'll detect by listing pros_cons after restore

        r = requests.post(f"{BASE_URL}/api/trash/{tid}/restore", headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"restore failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("module") == "pros_cons"
        original_id = data.get("id")
        assert original_id

        # Verify the item now exists in pros_cons collection (via list or by id)
        r = requests.get(f"{BASE_URL}/api/pros-cons", headers=auth_headers, timeout=15)
        if r.status_code != 200:
            r = requests.get(f"{BASE_URL}/api/pros_cons", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        raw = r.json()
        pc_list = raw if isinstance(raw, list) else raw.get("items") or raw.get("pros_cons") or []
        ids = [p.get("id") for p in pc_list]
        assert original_id in ids, f"restored id {original_id} not in pros_cons list ({len(ids)} items)"

        # Cleanup: soft-delete + purge from trash
        requests.delete(f"{BASE_URL}/api/pros-cons/{original_id}", headers=auth_headers, timeout=10)
        requests.delete(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=10)

    def test_purge_one(self, auth_headers):
        # Create + soft-delete a fresh pros_cons, then permanently delete via DELETE /api/trash/{id}
        payload = {
            "title": f"TEST_iter31_PURGE_{uuid.uuid4().hex[:6]}",
            "decision_title": "purge",
            "pros": [{"text": "x"}],
            "cons": [{"text": "y"}],
        }
        r = requests.post(f"{BASE_URL}/api/pros-cons", json=payload, headers=auth_headers, timeout=15)
        if r.status_code not in (200, 201):
            r = requests.post(f"{BASE_URL}/api/pros_cons", json=payload, headers=auth_headers, timeout=15)
        pid = r.json().get("id")
        requests.delete(f"{BASE_URL}/api/pros-cons/{pid}", headers=auth_headers, timeout=10)

        r = requests.get(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=15)
        items = r.json().get("items", [])
        match = [i for i in items if "TEST_iter31_PURGE_" in (i.get("title") or "")]
        assert match
        tid = match[0]["trash_id"]
        r = requests.delete(f"{BASE_URL}/api/trash/{tid}", headers=auth_headers, timeout=10)
        assert r.status_code == 200

        # 404 on second delete
        r = requests.delete(f"{BASE_URL}/api/trash/{tid}", headers=auth_headers, timeout=10)
        assert r.status_code == 404

    def test_empty_trash_endpoint(self, auth_headers):
        r = requests.delete(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        r = requests.get(f"{BASE_URL}/api/trash", headers=auth_headers, timeout=10)
        assert r.json().get("items") == []
