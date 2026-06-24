"""
Iter 158 — ACM dashboard_tiles extensions + dashboard-layout tile_titles sync

Validates the changes introduced after the previous syntax-error rollback:

1. /api/dashboard-layout now returns `{sections, tile_titles}`; `tile_titles`
   defaults to `{}` when nothing has been saved.
2. PUT /api/admin/dashboard-layout accepts a `tile_titles` dict, persists it,
   drops blank values, and mirrors each `tile_id → label` into the ACM
   `dashboard_tiles` module (`dash_<tile_id>` feature_name becomes
   "Dashboard tile · <label>").
3. POST /api/admin/dashboard-layout/reset removes the saved layout and
   returns `tile_titles: {}`.
4. ACM seed is at v2026-06-24-03: total features == 145; dashboard_tiles
   module contains
     - dash_section_home_top   → "Home Page - Header"
     - dash_section_home_footer → "Home Page - Footer"
     - dash_orgs  (parent dash_section_execute_track)
     - dash_values (parent dash_section_execute_track)
     - dash_notifications (parent dash_section_home_footer)
     - dash_analytics     (parent dash_section_home_footer)
5. /api/acm/my-access exposes dash_orgs / dash_values / dash_notifications /
   dash_analytics in the features map.
6. PUT /api/admin/dashboard-layout requires admin role (403 otherwise).
"""

import os
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com"
).rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASSWORD = "SuperPass2026!"
NORMAL_EMAIL = "iter158_user@test.com"
NORMAL_PASSWORD = "UserPass2026!"


# ---------- helpers -----------------------------------------------------------

def _login(email: str, password: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )


def _auth(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    r = _login(SUPER_EMAIL, SUPER_PASSWORD)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, "session_token missing from admin login response"
    return tok


@pytest.fixture(scope="module")
def normal_user_token():
    r = _login(NORMAL_EMAIL, NORMAL_PASSWORD)
    if r.status_code == 200:
        return r.json().get("session_token")
    reg = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": NORMAL_EMAIL,
            "password": NORMAL_PASSWORD,
            "name": "Iter158 User",
            "full_name": "Iter158 User",
            "phone": "+919999900158",
        },
        timeout=20,
    )
    if reg.status_code in (200, 201):
        data = reg.json()
        if data.get("session_token"):
            return data["session_token"]
    r2 = _login(NORMAL_EMAIL, NORMAL_PASSWORD)
    assert r2.status_code == 200, (
        f"Could not login fresh user: {reg.status_code} {reg.text} / "
        f"{r2.status_code} {r2.text}"
    )
    return r2.json().get("session_token")


def _get_layout(tok):
    return requests.get(
        f"{BASE_URL}/api/dashboard-layout", headers=_auth(tok), timeout=20
    )


def _put_layout(tok, payload):
    return requests.put(
        f"{BASE_URL}/api/admin/dashboard-layout",
        headers=_auth(tok),
        json=payload,
        timeout=20,
    )


def _reset_layout(tok):
    return requests.post(
        f"{BASE_URL}/api/admin/dashboard-layout/reset",
        headers=_auth(tok),
        timeout=20,
    )


def _get_acm_matrix(tok):
    return requests.get(
        f"{BASE_URL}/api/acm/matrix", headers=_auth(tok), timeout=30
    )


def _get_my_access(tok):
    return requests.get(
        f"{BASE_URL}/api/acm/my-access", headers=_auth(tok), timeout=30
    )


def _dash_tiles_features(matrix_json):
    for m in matrix_json.get("modules", []):
        if m.get("module_id") == "dashboard_tiles":
            return {f["feature_id"]: f for f in (m.get("features") or [])}
    return {}


# ---------- 1. GET /api/dashboard-layout shape --------------------------------

class TestGetLayoutShape:
    def test_get_returns_sections_and_tile_titles(self, admin_token):
        # Ensure clean state
        _reset_layout(admin_token)
        r = _get_layout(admin_token)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert "sections" in body and isinstance(body["sections"], list)
        assert "tile_titles" in body, "tile_titles missing from layout response"
        assert body["tile_titles"] == {}, (
            f"tile_titles should default to empty dict, got {body['tile_titles']!r}"
        )


# ---------- 2. PUT tile_titles persists + drops blanks + ACM sync -------------

class TestPutTileTitles:
    def test_put_tile_titles_persists_and_drops_blanks(self, admin_token):
        # Snapshot current sections so we don't change structure.
        sections = _get_layout(admin_token).json()["sections"]
        payload = {
            "sections": sections,
            "tile_titles": {
                "orgs": "My Companies",
                "values": "  Personal Values  ",  # whitespace trimmed
                "notifications": "",               # dropped (blank)
                "analytics": "Folder Insights",
                "not_a_real_tile": "Phantom",      # accepted but harmless
            },
        }
        try:
            r = _put_layout(admin_token, payload)
            assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("ok") is True
            tt = body.get("tile_titles") or {}
            assert tt.get("orgs") == "My Companies"
            assert tt.get("values") == "Personal Values", (
                f"expected trimmed 'Personal Values', got {tt.get('values')!r}"
            )
            assert tt.get("analytics") == "Folder Insights"
            assert "notifications" not in tt, "blank value should be dropped"

            # GET should round-trip the persisted titles
            g = _get_layout(admin_token).json()
            assert g.get("tile_titles", {}).get("orgs") == "My Companies"
            assert g.get("tile_titles", {}).get("values") == "Personal Values"
            assert "notifications" not in g.get("tile_titles", {})
        finally:
            # Restore clean defaults for downstream tests
            _reset_layout(admin_token)

    def test_put_tile_titles_syncs_acm_feature_names(self, admin_token):
        # Baseline ACM label before
        before = _get_acm_matrix(admin_token).json()
        feats_before = _dash_tiles_features(before)
        assert "dash_orgs" in feats_before, "dash_orgs feature missing from ACM"
        original_label = feats_before["dash_orgs"].get("feature_name")

        sections = _get_layout(admin_token).json()["sections"]
        try:
            r = _put_layout(
                admin_token,
                {"sections": sections, "tile_titles": {"orgs": "My Companies"}},
            )
            assert r.status_code == 200

            after = _get_acm_matrix(admin_token).json()
            feats_after = _dash_tiles_features(after)
            expected = "Dashboard tile · My Companies"
            assert feats_after["dash_orgs"].get("feature_name") == expected, (
                f"Expected ACM dash_orgs feature_name to be {expected!r}, "
                f"got {feats_after['dash_orgs'].get('feature_name')!r}"
            )

            # Other tiles should remain untouched
            assert feats_after["dash_values"].get("feature_name") == feats_before[
                "dash_values"
            ].get("feature_name"), "dash_values feature_name should not have changed"
        finally:
            # Reset clears tile_titles, but does NOT restore the previous ACM
            # label automatically. Restore the original ACM label so other
            # tests/iterations see a clean matrix.
            _reset_layout(admin_token)
            if original_label and original_label != "Dashboard tile · My Companies":
                # Re-seed/refresh via cache to make sure tests don't bleed.
                requests.post(
                    f"{BASE_URL}/api/acm/refresh-cache",
                    headers=_auth(admin_token),
                    timeout=20,
                )


# ---------- 3. POST reset clears layout & tile_titles -------------------------

class TestResetClearsTileTitles:
    def test_reset_returns_empty_tile_titles(self, admin_token):
        # Seed something first
        sections = _get_layout(admin_token).json()["sections"]
        _put_layout(
            admin_token,
            {"sections": sections, "tile_titles": {"orgs": "TEMP_NAME"}},
        )
        r = _reset_layout(admin_token)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("tile_titles") == {}, (
            f"reset must return tile_titles: {{}}, got {body.get('tile_titles')!r}"
        )
        # GET should also reflect the empty tile_titles
        g = _get_layout(admin_token).json()
        assert g.get("tile_titles") == {}


# ---------- 4. ACM seed v2026-06-24-03 — 145 features + new ids --------------

class TestACMSeed:
    @pytest.fixture(scope="class")
    def matrix(self, admin_token):
        r = _get_acm_matrix(admin_token)
        assert r.status_code == 200, f"matrix fetch failed: {r.status_code} {r.text}"
        return r.json()

    def test_total_features_is_145(self, matrix):
        total = matrix.get("total_features")
        assert total == 145, f"Expected total_features=145, got {total}"

    def test_dashboard_tiles_module_present(self, matrix):
        feats = _dash_tiles_features(matrix)
        assert feats, "dashboard_tiles module/features missing in ACM matrix"

    def test_home_top_renamed_header(self, matrix):
        feats = _dash_tiles_features(matrix)
        f = feats.get("dash_section_home_top")
        assert f, "dash_section_home_top missing in ACM dashboard_tiles"
        assert "Home Page - Header" in (f.get("feature_name") or ""), (
            f"Expected 'Home Page - Header' in feature_name, "
            f"got {f.get('feature_name')!r}"
        )

    def test_home_footer_section_added(self, matrix):
        feats = _dash_tiles_features(matrix)
        f = feats.get("dash_section_home_footer")
        assert f, "dash_section_home_footer missing — new footer section not added"
        assert "Home Page - Footer" in (f.get("feature_name") or "")

    def test_orgs_values_parented_to_execute_track(self, matrix):
        feats = _dash_tiles_features(matrix)
        for fid in ("dash_orgs", "dash_values"):
            assert fid in feats, f"{fid} missing in dashboard_tiles features"
            assert feats[fid].get("parent_feature_id") == "dash_section_execute_track", (
                f"{fid} parent_feature_id should be dash_section_execute_track, "
                f"got {feats[fid].get('parent_feature_id')!r}"
            )

    def test_notifications_analytics_parented_to_home_footer(self, matrix):
        feats = _dash_tiles_features(matrix)
        for fid in ("dash_notifications", "dash_analytics"):
            assert fid in feats, f"{fid} missing in dashboard_tiles features"
            assert feats[fid].get("parent_feature_id") == "dash_section_home_footer", (
                f"{fid} parent_feature_id should be dash_section_home_footer, "
                f"got {feats[fid].get('parent_feature_id')!r}"
            )


# ---------- 5. /api/acm/my-access exposes the four toggleable flags -----------

class TestMyAccessExposesNewFlags:
    def test_my_access_includes_new_flags(self, admin_token):
        r = _get_my_access(admin_token)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        features = r.json().get("features") or {}
        for fid in ("dash_orgs", "dash_values", "dash_notifications", "dash_analytics"):
            assert fid in features, (
                f"{fid} missing from /api/acm/my-access features map; "
                f"present keys (sample) = {list(features)[:20]}"
            )

    def test_my_access_includes_new_flags_for_normal_user(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("normal user token unavailable")
        r = _get_my_access(normal_user_token)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        features = r.json().get("features") or {}
        for fid in ("dash_orgs", "dash_values", "dash_notifications", "dash_analytics"):
            assert fid in features, f"{fid} missing from normal user my-access"


# ---------- 6. Non-admin write protection -------------------------------------

class TestAdminProtection:
    def test_non_admin_put_layout_403(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("normal user token unavailable")
        payload = {
            "sections": [{"id": "x", "emoji": "X", "name": "X", "tiles": []}],
            "tile_titles": {"orgs": "Hacked"},
        }
        r = _put_layout(normal_user_token, payload)
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"

    def test_non_admin_reset_layout_403(self, normal_user_token):
        if not normal_user_token:
            pytest.skip("normal user token unavailable")
        r = _reset_layout(normal_user_token)
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text}"

    def test_unauthed_put_layout_rejected(self):
        r = requests.put(
            f"{BASE_URL}/api/admin/dashboard-layout",
            json={"sections": [{"id": "x", "name": "X", "tiles": []}]},
            timeout=20,
        )
        assert r.status_code in (401, 403), (
            f"Unauth PUT should be rejected, got {r.status_code}"
        )
