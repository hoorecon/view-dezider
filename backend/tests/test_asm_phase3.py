"""
Phase 3 — ASM↔Solution Finder unification backend tests.

Coverage:
  - ACM unlock: solution_matrix_orgtype_{org,govt,nature} → 'full' for free user.
  - ACM version = 2026-06-02-05.
  - ASM CRUD (create/list/get/update/delete) with Title-only save.
  - POST /api/solution-matrices/{entry_id}/push-action-plan
      fans into action_items + ctt_tasks + lifestyle_routines as flagged.
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


# ─────────── ACM checks ───────────

class TestACMUnlock:
    """ACM seed version + Org/Govt/Nature columns should be 'full' for free."""

    def test_my_access_includes_orgtype_features_full(self, auth_headers):
        r = requests.get(f"{API}/acm/my-access", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        feats = data["features"]
        for fid in (
            "solution_matrix_orgtype_individual",
            "solution_matrix_orgtype_org",
            "solution_matrix_orgtype_govt",
            "solution_matrix_orgtype_nature",
        ):
            assert fid in feats, f"feature {fid} missing"
            assert feats[fid]["access_level"] == "full", (
                f"{fid} expected 'full', got {feats[fid]}"
            )

    def test_check_single_feature_org(self, auth_headers):
        r = requests.get(
            f"{API}/acm/check/solution_matrix_orgtype_org",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["access_level"] == "full"
        assert body["allowed"] is True

    def test_acm_seed_version(self, auth_headers):
        # ACM seed version is exposed indirectly via admin /matrix → we hit DB-backed acm_meta
        # through a public-ish path: re-login as admin and call /api/acm/seed admin only.
        # Use admin creds for this single assertion.
        ar = requests.post(
            f"{API}/auth/login",
            json={"email": "admin@test.com", "password": "AdminPass2026!"},
            timeout=15,
        )
        if ar.status_code != 200:
            pytest.skip(f"admin login unavailable: {ar.status_code}")
        atok = ar.json()["session_token"]
        # POST seed force=false returns the current stored seed_version
        s = requests.post(
            f"{API}/acm/seed",
            headers={"Authorization": f"Bearer {atok}"},
            timeout=20,
        )
        assert s.status_code == 200, s.text
        assert s.json().get("seed_version") == "2026-06-02-05", s.json()


# ─────────── ASM CRUD + push-action-plan ───────────

class TestSolutionMatrixCRUDAndPush:
    created_ids = []

    @classmethod
    def teardown_class(cls):
        # best-effort cleanup
        try:
            r = requests.post(
                f"{API}/auth/login",
                json={"email": USER_EMAIL, "password": USER_PASS},
                timeout=10,
            )
            if r.status_code == 200:
                tok = r.json()["session_token"]
                h = {"Authorization": f"Bearer {tok}"}
                for eid in cls.created_ids:
                    requests.delete(f"{API}/solution-matrices/{eid}", headers=h, timeout=10)
        except Exception:
            pass

    def test_create_title_only(self, auth_headers):
        """Save should work with only smart_goal (Title) — no area_of_life required."""
        payload = {
            "smart_goal": f"TEST_phase3_{uuid.uuid4().hex[:8]}",
            "matrix_mode": "advanced",
        }
        r = requests.post(f"{API}/solution-matrices", json=payload, headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "entry_id" in body
        assert body["smart_goal"] == payload["smart_goal"]
        assert body.get("area_of_life", "") == ""
        TestSolutionMatrixCRUDAndPush.created_ids.append(body["entry_id"])

    def test_list_contains_created(self, auth_headers):
        r = requests.get(f"{API}/solution-matrices", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        entries = r.json()
        assert isinstance(entries, list)
        ids = [e["entry_id"] for e in entries]
        for eid in self.created_ids:
            assert eid in ids

    def test_get_single(self, auth_headers):
        eid = self.created_ids[0]
        r = requests.get(f"{API}/solution-matrices/{eid}", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["entry_id"] == eid

    def test_update_persists(self, auth_headers):
        eid = self.created_ids[0]
        new_title = f"TEST_phase3_updated_{uuid.uuid4().hex[:6]}"
        r = requests.put(
            f"{API}/solution-matrices/{eid}",
            json={"smart_goal": new_title},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # verify with GET
        g = requests.get(f"{API}/solution-matrices/{eid}", headers=auth_headers, timeout=15)
        assert g.status_code == 200
        assert g.json()["smart_goal"] == new_title

    def test_push_action_plan_fans_out(self, auth_headers):
        """Push 3 items: one CTT-only, one Lifestyle-only, one both."""
        eid = self.created_ids[0]
        items = [
            {"text": "SELF · Aggregate · Time: TEST_phase3 plan ctt-only",
             "push_ctt": True, "push_lifestyle": False},
            {"text": "MICRO · Aggregate · Energy: TEST_phase3 plan life-only",
             "push_ctt": False, "push_lifestyle": True},
            {"text": "MACRO · Aggregate · People: TEST_phase3 plan both",
             "push_ctt": True, "push_lifestyle": True},
        ]
        r = requests.post(
            f"{API}/solution-matrices/{eid}/push-action-plan",
            json={"items": items},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pushed_to_action_center"] == 3
        assert body["pushed_to_ctt"] == 2
        assert body["pushed_to_lifestyle"] == 2

        # Verify action_items show up via the Action Center API (if exposed)
        ai = requests.get(f"{API}/action-items", headers=auth_headers, timeout=15)
        if ai.status_code == 200:
            arr = ai.json() if isinstance(ai.json(), list) else ai.json().get("items", [])
            sm = [a for a in arr if a.get("source_module") == "solution_matrix"
                  and a.get("source_id") == eid]
            assert len(sm) >= 3, f"expected >=3 action_items from this entry, got {len(sm)}"

    def test_push_with_empty_items_returns_zero(self, auth_headers):
        eid = self.created_ids[0]
        r = requests.post(
            f"{API}/solution-matrices/{eid}/push-action-plan",
            json={"items": []},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pushed_to_action_center"] == 0
        assert body["pushed_to_ctt"] == 0
        assert body["pushed_to_lifestyle"] == 0

    def test_push_unknown_entry_404(self, auth_headers):
        r = requests.post(
            f"{API}/solution-matrices/nonexistent-{uuid.uuid4().hex}/push-action-plan",
            json={"items": [{"text": "x", "push_ctt": False, "push_lifestyle": False}]},
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 404, r.text

    def test_delete_round_trip(self, auth_headers):
        # create a throwaway to delete
        c = requests.post(
            f"{API}/solution-matrices",
            json={"smart_goal": f"TEST_phase3_del_{uuid.uuid4().hex[:6]}"},
            headers=auth_headers,
            timeout=15,
        )
        assert c.status_code == 200
        eid = c.json()["entry_id"]
        d = requests.delete(f"{API}/solution-matrices/{eid}", headers=auth_headers, timeout=15)
        assert d.status_code == 200, d.text
        g = requests.get(f"{API}/solution-matrices/{eid}", headers=auth_headers, timeout=15)
        assert g.status_code == 404
