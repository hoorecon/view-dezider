"""
Iter 155 — Dashboard Layout admin-editable config

Tests the new GET /api/dashboard-layout, PUT /api/admin/dashboard-layout
and POST /api/admin/dashboard-layout/reset endpoints.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASSWORD = "SuperPass2026!"
TESTING_EMAIL = "veales.testing@gmail.com"


def _login(email: str, password: str):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login(SUPER_EMAIL, SUPER_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, "session_token missing in admin login response"
    return tok


@pytest.fixture(scope="module")
def normal_user_token():
    """Register a fresh non-admin user (or login if exists) and return its token."""
    email = "iter155_user@test.com"
    password = "UserPass2026!"
    # Try login first
    r = _login(email, password)
    if r.status_code == 200:
        return r.json().get("session_token")
    # Else register via signup
    reg = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Iter155 User",
            "full_name": "Iter155 User",
            "phone": "+919999900155",
        },
        timeout=20,
    )
    # registration may auto-login or require explicit login
    if reg.status_code in (200, 201):
        data = reg.json()
        if data.get("session_token"):
            return data["session_token"]
    r2 = _login(email, password)
    assert r2.status_code == 200, f"Could not login fresh user: {reg.status_code} {reg.text} / {r2.status_code} {r2.text}"
    return r2.json().get("session_token")


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---- GET /api/dashboard-layout ----
class TestGetDashboardLayout:
    def test_unauth_get_rejected(self):
        r = requests.get(f"{BASE_URL}/api/dashboard-layout", timeout=20)
        assert r.status_code in (401, 403), f"Unauth GET should be rejected, got {r.status_code}"

    def test_admin_get_returns_9_default_sections(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/dashboard-layout", headers=_auth(admin_token), timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        secs = body.get("sections")
        assert isinstance(secs, list) and len(secs) >= 9, f"Expected >=9 sections, got {secs}"
        ids = [s.get("id") for s in secs]
        for expected in [
            "self_discovery", "decision_kickstarters", "problem_solvers",
            "goals_manifestation", "execute_track", "reflection_awareness",
            "collaboration_mgmt", "solution_space", "more_tools",
        ]:
            assert expected in ids, f"Missing section id {expected}; got {ids}"
        # Each section has id/name/emoji/tiles
        for s in secs:
            assert "id" in s and "name" in s and "tiles" in s
            assert isinstance(s["tiles"], list)

    def test_normal_user_can_get(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("Could not provision normal user")
        r = requests.get(f"{BASE_URL}/api/dashboard-layout", headers=_auth(normal_user_token), timeout=20)
        assert r.status_code == 200, f"Normal user GET failed: {r.status_code} {r.text}"
        assert len(r.json().get("sections", [])) >= 9


# ---- PUT /api/admin/dashboard-layout ----
class TestPutDashboardLayout:
    def test_non_admin_put_forbidden(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("Could not provision normal user")
        # Build a minimal payload
        payload = {"sections": [{"id": "x", "emoji": "X", "name": "X", "tiles": []}]}
        r = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            headers=_auth(normal_user_token),
            json=payload,
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403 for non-admin PUT, got {r.status_code} {r.text}"

    def test_admin_put_rename_and_move_persists(self, admin_token):
        # 1) Snapshot current layout
        baseline = requests.get(
            f"{BASE_URL}/api/dashboard-layout", headers=_auth(admin_token), timeout=20
        ).json()["sections"]

        # 2) Build modified version: rename 'More Tools', move 'inbox' from more_tools → self_discovery,
        #    and swap position of first two sections
        mutated = [{**s, "tiles": list(s.get("tiles", []))} for s in baseline]
        # rename more_tools
        for s in mutated:
            if s["id"] == "more_tools":
                s["name"] = "TEST_RENAMED_MORE"
        # move inbox
        moved_tile = "inbox"
        for s in mutated:
            if s["id"] == "more_tools" and moved_tile in s["tiles"]:
                s["tiles"].remove(moved_tile)
        for s in mutated:
            if s["id"] == "self_discovery":
                if moved_tile not in s["tiles"]:
                    s["tiles"].append(moved_tile)
        # swap first two sections
        if len(mutated) >= 2:
            mutated[0], mutated[1] = mutated[1], mutated[0]

        # 3) PUT
        r = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            headers=_auth(admin_token),
            json={"sections": mutated},
            timeout=20,
        )
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True

        # 4) GET to verify persistence
        re_fetch = requests.get(
            f"{BASE_URL}/api/dashboard-layout", headers=_auth(admin_token), timeout=20
        ).json()["sections"]
        try:
            id_to_name = {s["id"]: s["name"] for s in re_fetch}
            assert id_to_name.get("more_tools") == "TEST_RENAMED_MORE", (
                f"Rename did not persist: {id_to_name.get('more_tools')}"
            )
            # inbox moved
            self_disc = next(s for s in re_fetch if s["id"] == "self_discovery")
            more_tools = next(s for s in re_fetch if s["id"] == "more_tools")
            assert moved_tile in self_disc["tiles"], "moved tile missing from self_discovery"
            assert moved_tile not in more_tools["tiles"], "moved tile still in more_tools"
            # order swap persisted
            assert re_fetch[0]["id"] == mutated[0]["id"] and re_fetch[1]["id"] == mutated[1]["id"], (
                f"Order swap did not persist; got [{re_fetch[0]['id']},{re_fetch[1]['id']}]"
            )
        finally:
            # 5) Reset to defaults to keep the system clean for downstream tests
            reset = requests.post(
                f"{BASE_URL}/api/admin/dashboard-layout/reset",
                headers=_auth(admin_token),
                timeout=20,
            )
            assert reset.status_code == 200

    def test_admin_put_bad_payload_rejected(self, admin_token):
        # Empty list
        r = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            headers=_auth(admin_token),
            json={"sections": []},
            timeout=20,
        )
        assert r.status_code == 400
        # Missing sections
        r2 = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            headers=_auth(admin_token),
            json={},
            timeout=20,
        )
        assert r2.status_code == 400


# ---- POST /api/admin/dashboard-layout/reset ----
class TestResetDashboardLayout:
    def test_non_admin_reset_forbidden(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("Could not provision normal user")
        r = requests.post(
            f"{BASE_URL}/api/admin/dashboard-layout/reset",
            headers=_auth(normal_user_token),
            timeout=20,
        )
        assert r.status_code == 403

    def test_admin_reset_restores_defaults(self, admin_token):
        # First mutate
        mutated = [{"id": "self_discovery", "emoji": "X", "name": "MUTATED", "tiles": ["pna"]}]
        r = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            headers=_auth(admin_token),
            json={"sections": mutated},
            timeout=20,
        )
        assert r.status_code == 200
        # Reset
        r2 = requests.post(
            f"{BASE_URL}/api/admin/dashboard-layout/reset",
            headers=_auth(admin_token),
            timeout=20,
        )
        assert r2.status_code == 200
        # GET should now have defaults again (9 sections)
        r3 = requests.get(
            f"{BASE_URL}/api/dashboard-layout", headers=_auth(admin_token), timeout=20
        ).json()["sections"]
        ids = [s["id"] for s in r3]
        for expected in [
            "self_discovery", "decision_kickstarters", "problem_solvers",
            "goals_manifestation", "execute_track", "reflection_awareness",
            "collaboration_mgmt", "solution_space", "more_tools",
        ]:
            assert expected in ids
