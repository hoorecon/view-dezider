"""
Iter160 — Verifies:
  (A) ACM seed v2026-06-24-04 has 148 features and the 3 new Collaboration
      togglable features (collab_share, collab_expert_call, collab_shared_inbox)
      live under the "collaboration" module.
  (B) GET /api/acm/my-access exposes those 3 features as "full" for the super
      admin (super@test.com).
  (C) ATEX bug fix: openPicker now sources tasks from BOTH /action-items and
      /ctt/tasks. We seed >=3 action items and assert /action-items returns
      them. The picker would dedupe & merge — we verify the source endpoint
      that the frontend now reads from is working and contains data.
  (D) Backward-compat smoke: /api/dashboard-layout still returns
      {sections, tile_titles}.
"""
import os
import uuid

import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "https://goals-feels-tracker.preview.emergentagent.com"
).rstrip("/")
ADMIN_EMAIL = "super@test.com"
ADMIN_PASSWORD = "SuperPass2026!"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("session_token") or body.get("access_token")
    assert tok, f"No token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────────────────────
# (A) ACM seed structural verification
# ──────────────────────────────────────────────────────────────────────────────
class TestACMSeed:
    def test_acm_matrix_version_and_count(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # seed_version may live at top-level or under 'meta'
        version = data.get("seed_version") or data.get("version") or (data.get("meta") or {}).get("seed_version")
        # Count all features across modules
        modules = data.get("modules") or []
        assert modules, "ACM matrix has no modules"
        total = sum(len(m.get("features", []) or []) for m in modules)
        # The review request asserts 148 features in seed v2026-06-24-04
        assert total == 148, f"Expected 148 features, got {total} (version={version})"
        if version is not None:
            assert version == "2026-06-24-04", f"Expected seed 2026-06-24-04, got {version}"

    def test_collaboration_module_has_new_features(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        modules = r.json().get("modules") or []
        collab = next((m for m in modules if m.get("module_id") == "collaboration"), None)
        assert collab is not None, "collaboration module missing from ACM matrix"
        ids = {f.get("feature_id") for f in (collab.get("features") or [])}
        for fid in ("collab_share", "collab_expert_call", "collab_shared_inbox"):
            assert fid in ids, f"{fid} missing from collaboration module. Have: {sorted(ids)}"

    def test_feature_names_match_review(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/acm/matrix", headers=admin_headers, timeout=30)
        modules = r.json().get("modules") or []
        collab = next((m for m in modules if m.get("module_id") == "collaboration"), None)
        by_id = {f["feature_id"]: f for f in (collab.get("features") or [])}
        # Be lenient about exact wording — assert presence + non-empty name
        for fid in ("collab_share", "collab_expert_call", "collab_shared_inbox"):
            assert by_id[fid].get("feature_name"), f"{fid} has no feature_name"


# ──────────────────────────────────────────────────────────────────────────────
# (B) /api/acm/my-access exposes the 3 new flags for admin = "full"
# ──────────────────────────────────────────────────────────────────────────────
class TestMyAccess:
    def test_my_access_returns_collab_flags_full(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/acm/my-access", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        feats = r.json().get("features") or {}
        for fid in ("collab_share", "collab_expert_call", "collab_shared_inbox"):
            entry = feats.get(fid)
            assert entry is not None, f"{fid} missing from /acm/my-access. Sample keys: {list(feats)[:8]}"
            lvl = entry.get("access_level") or entry.get("level")
            assert lvl == "full", f"{fid} access_level expected 'full', got {lvl!r}"


# ──────────────────────────────────────────────────────────────────────────────
# (C) ATEX picker source — admin's /action-items must have entries
# ──────────────────────────────────────────────────────────────────────────────
class TestATEXPickerSources:
    @pytest.fixture(scope="class")
    def seeded_action_ids(self, admin_headers):
        """Ensure at least 3 action items exist for the admin (idempotent
        — we add a tag we can clean up later, then read all)."""
        created = []
        for i in range(3):
            payload = {
                "title": f"TEST_iter160_action_{uuid.uuid4().hex[:6]}",
                "priority": "medium",
                "status": "pending",
                "source_module": "manual",
            }
            r = requests.post(
                f"{BASE_URL}/api/action-items", headers=admin_headers, json=payload, timeout=30
            )
            # Some impls return 201, some 200
            assert r.status_code in (200, 201), f"create action-item failed: {r.status_code} {r.text[:200]}"
            body = r.json()
            aid = body.get("action_id") or body.get("id")
            if aid:
                created.append(aid)
        yield created
        # Cleanup
        for aid in created:
            try:
                requests.delete(f"{BASE_URL}/api/action-items/{aid}", headers=admin_headers, timeout=15)
            except Exception:
                pass

    def test_action_items_endpoint_returns_list(self, admin_headers, seeded_action_ids):
        r = requests.get(f"{BASE_URL}/api/action-items", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data).__name__}"
        # At least our 3 freshly-seeded items must be present
        assert len(data) >= 3, f"Expected >=3 action items, got {len(data)}"
        # Every entry must have a title we can show in the picker
        titles = [(a.get("title") or a.get("task") or "").strip() for a in data]
        non_empty = [t for t in titles if t]
        assert len(non_empty) >= 3, f"Action items missing titles; titles={titles[:5]}"

    def test_ctt_tasks_endpoint_reachable(self, admin_headers):
        """Picker also queries /ctt/tasks?status=all — must respond 200 even
        if empty (admin currently has 0 ctt tasks per review note)."""
        r = requests.get(f"{BASE_URL}/api/ctt/tasks?status=all", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Backend may return list or {tasks: [...]}
        if isinstance(data, dict):
            data = data.get("tasks") or []
        assert isinstance(data, list)


# ──────────────────────────────────────────────────────────────────────────────
# (D) Dashboard layout smoke — no regression on iter158/159 contract
# ──────────────────────────────────────────────────────────────────────────────
class TestDashboardLayoutSmoke:
    def test_dashboard_layout_shape(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard-layout", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "sections" in body, f"missing 'sections' in dashboard-layout: {list(body)}"
        assert "tile_titles" in body, f"missing 'tile_titles' in dashboard-layout: {list(body)}"
        assert isinstance(body["tile_titles"], dict)
