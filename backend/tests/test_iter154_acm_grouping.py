"""Iter 154 — verify background-boot health, ACM grouping (dashboard_tiles), and
'Apply to all user types' bulk edit on PUT /api/acm/feature/{id}."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"

EXPECTED_AUDIENCES = {
    "unit_tester", "integration_tester", "alpha", "beta",
    "free", "trial", "paid_starter", "paid_pro",
    "paid_enterprise", "paid_api",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


@pytest.fixture(scope="module")
def super_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    assert tok, f"no token in {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


# ── Health & request handling after background boot ─────────────────────────
class TestHealthAndAuth:
    def test_health_live_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/health/live")
        assert r.status_code == 200, r.text

    def test_auth_me_after_login(self, super_token):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {super_token}"})
        assert r.status_code == 200, r.text
        assert r.json().get("email") == SUPER_EMAIL

    def test_acm_my_access(self, super_token):
        r = requests.get(f"{BASE_URL}/api/acm/my-access",
                         headers={"Authorization": f"Bearer {super_token}"})
        assert r.status_code == 200, r.text

    def test_action_items_list(self, super_token):
        r = requests.get(f"{BASE_URL}/api/action-items",
                         headers={"Authorization": f"Bearer {super_token}"})
        assert r.status_code == 200, r.text


# ── ACM Matrix shape & dashboard_tiles grouping ─────────────────────────────
class TestACMMatrixGrouping:
    @pytest.fixture(scope="class")
    def matrix(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=auth_headers)
        assert r.status_code == 200, r.text
        return r.json()

    @pytest.fixture(scope="class")
    def dashboard_tiles(self, matrix):
        mods = matrix["modules"]
        mod = next((m for m in mods if m["module_id"] == "dashboard_tiles"), None)
        assert mod, "dashboard_tiles module missing"
        return mod

    def test_seed_version(self, auth_headers):
        # seed_version persisted in acm_meta after seed. We surface it via /api/acm/seed
        # — but we can also infer it indirectly. Try meta endpoint if available.
        # Fallback: probe acm_meta via direct request if there's an endpoint; otherwise
        # just check that the new grouping exists (covered in next tests).
        # If there's an explicit endpoint, use it.
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=auth_headers)
        assert r.status_code == 200
        # presence of dash_section_problem_solvers is our smoke for 2026-06-24-01
        feats = next(m for m in r.json()["modules"]
                     if m["module_id"] == "dashboard_tiles")["features"]
        ids = {f["feature_id"] for f in feats}
        assert "dash_section_problem_solvers" in ids, \
            "Expected dash_section_problem_solvers (seed 2026-06-24-01) missing"

    def test_section_problem_solvers_present(self, dashboard_tiles):
        sec = next((f for f in dashboard_tiles["features"]
                    if f["feature_id"] == "dash_section_problem_solvers"), None)
        assert sec, "dash_section_problem_solvers section missing"
        assert sec.get("is_section") is True
        assert "Problem Solvers" in sec["feature_name"]

    def test_emotional_gatekeeper_parent(self, dashboard_tiles):
        tile = next((f for f in dashboard_tiles["features"]
                     if f["feature_id"] == "dash_emotional_gatekeeper"), None)
        assert tile, "dash_emotional_gatekeeper tile missing"
        assert tile.get("parent_feature_id") == "dash_section_decision_kickstarters"

    def test_conflict_breaker_parent(self, dashboard_tiles):
        tile = next((f for f in dashboard_tiles["features"]
                     if f["feature_id"] == "dash_conflict_breaker"), None)
        assert tile, "dash_conflict_breaker tile missing"
        assert tile.get("parent_feature_id") == "dash_section_problem_solvers"

    def test_solution_finder_parent(self, dashboard_tiles):
        tile = next((f for f in dashboard_tiles["features"]
                     if f["feature_id"] == "dash_solution_finder"), None)
        assert tile, "dash_solution_finder tile missing"
        assert tile.get("parent_feature_id") == "dash_section_problem_solvers"

    def test_swot_appears_once(self, dashboard_tiles):
        swot = [f for f in dashboard_tiles["features"]
                if f["feature_id"] == "dash_swot"]
        assert len(swot) == 1, f"dash_swot appears {len(swot)} times, expected 1"

    def test_nine_sections_present(self, dashboard_tiles):
        sections = [f for f in dashboard_tiles["features"] if f.get("is_section")]
        assert len(sections) == 9, f"expected 9 sections, got {len(sections)}"
        sec_ids = {s["feature_id"] for s in sections}
        expected = {
            "dash_section_self_discovery", "dash_section_decision_kickstarters",
            "dash_section_problem_solvers", "dash_section_goals_manifestation",
            "dash_section_execute_track", "dash_section_reflection_awareness",
            "dash_section_collaboration_mgmt", "dash_section_solution_space",
            "dash_section_more_tools",
        }
        assert sec_ids == expected, f"missing sections: {expected - sec_ids}"


# ── Apply to all user types bulk edit ───────────────────────────────────────
class TestApplyToAllUserTypes:
    """Pick a non-critical feature, snapshot it, set Read+quota=5 for ALL audiences,
    verify the matrix reflects it, then restore the snapshot."""

    TARGET = "dash_more_tools_placeholder"  # safe non-critical tile; we'll auto-pick

    def _get_module(self, auth_headers, module_id="dashboard_tiles"):
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=auth_headers)
        assert r.status_code == 200, r.text
        return next(m for m in r.json()["modules"] if m["module_id"] == module_id)

    def test_bulk_apply_all_audiences(self, auth_headers):
        mod = self._get_module(auth_headers)
        # Pick a tile (child, not a section) that exists. Prefer dash_swot per spec context.
        tile = next((f for f in mod["features"]
                     if f["feature_id"] == "dash_swot"), None)
        assert tile, "dash_swot not found to test bulk-apply"
        original_access = tile.get("access") or {}
        original_stage = tile.get("release_stage")

        new_rule = {"level": "read", "quota": 5}
        body = {
            "release_stage": original_stage or "ga_free",
            "access": {aud: new_rule for aud in EXPECTED_AUDIENCES},
        }
        r = requests.put(f"{BASE_URL}/api/acm/feature/dash_swot",
                         headers=auth_headers, json=body)
        assert r.status_code == 200, r.text

        # Re-fetch and verify every audience is now read/5
        mod2 = self._get_module(auth_headers)
        tile2 = next(f for f in mod2["features"] if f["feature_id"] == "dash_swot")
        for aud in EXPECTED_AUDIENCES:
            entry = (tile2.get("access") or {}).get(aud)
            assert entry, f"audience {aud} missing after bulk apply"
            assert entry["level"] == "read", f"{aud}: level={entry['level']}, expected read"
            assert entry["quota"] == 5, f"{aud}: quota={entry['quota']}, expected 5"

        # ── Restore original (best-effort) ──
        if original_access:
            restore_body = {
                "release_stage": original_stage or "ga_free",
                "access": original_access,
            }
            rr = requests.put(f"{BASE_URL}/api/acm/feature/dash_swot",
                              headers=auth_headers, json=restore_body)
            assert rr.status_code == 200, f"restore failed: {rr.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
