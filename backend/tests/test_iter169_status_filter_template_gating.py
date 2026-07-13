"""
Iter 169 — Phase-1 Solution Box status filter + Phase-2 Decision Template public gating.

Tests:
  - GET /api/solution-box returns progress_pct (int 0-100), progress_band, status on every item
  - status query param filters (draft, in_progress, completed, ip_low, ip_mid, ip_high)
  - POST /decisions/{id}/save-as-template public gating (NON-completed → 400, Private → 200)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")

EMAIL = "super@test.com"
PASSWORD = "SuperPass2026!"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    return body.get("token") or body.get("session_token") or body.get("access_token")


@pytest.fixture(scope="module")
def headers(auth_token):
    # Backend uses session_token cookie/bearer interchangeably
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ---------- Solution Box: shape + filter ----------

VALID_BANDS = {"draft", "ip_low", "ip_mid", "ip_high", "completed"}
VALID_STATUSES = {"draft", "in_progress", "completed"}


class TestSolutionBoxStatusShape:
    def test_every_item_has_progress_fields(self, headers):
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) > 0, "expected at least one solution-box item"
        for it in items:
            assert "progress_pct" in it, f"missing progress_pct on {it.get('id')}"
            assert "progress_band" in it, f"missing progress_band on {it.get('id')}"
            assert "status" in it, f"missing status on {it.get('id')}"
            assert isinstance(it["progress_pct"], int), f"progress_pct must be int, got {type(it['progress_pct'])}"
            assert 0 <= it["progress_pct"] <= 100
            assert it["progress_band"] in VALID_BANDS, f"bad band {it['progress_band']}"
            assert it["status"] in VALID_STATUSES, f"bad status {it['status']}"

    def test_band_status_consistency(self, headers):
        """progress_band == 'completed' must imply status == 'completed', etc."""
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, timeout=20)
        items = r.json()
        for it in items:
            b, s, p = it["progress_band"], it["status"], it["progress_pct"]
            if b == "completed":
                assert s == "completed" and p == 100, f"item {it['id']}: band=completed but status={s}, pct={p}"
            elif b == "draft":
                assert s == "draft", f"item {it['id']}: band=draft but status={s}"
            elif b in ("ip_low", "ip_mid", "ip_high"):
                assert s == "in_progress", f"item {it['id']}: band={b} but status={s}"
                if b == "ip_low":
                    assert p < 35
                elif b == "ip_mid":
                    assert 35 <= p <= 70
                elif b == "ip_high":
                    assert 70 < p < 100


class TestSolutionBoxStatusFilter:
    @pytest.mark.parametrize("band", ["ip_high", "ip_mid", "ip_low", "completed", "draft"])
    def test_band_filter_returns_only_matching(self, headers, band):
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, params={"status": band}, timeout=20)
        assert r.status_code == 200
        items = r.json()
        # Allow empty for narrow bands, but every returned item MUST match
        for it in items:
            assert it["progress_band"] == band, f"filter={band} returned band={it['progress_band']} id={it.get('id')}"

    def test_in_progress_returns_any_ip_band(self, headers):
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, params={"status": "in_progress"}, timeout=20)
        assert r.status_code == 200
        items = r.json()
        for it in items:
            assert it["status"] == "in_progress"
            assert it["progress_band"] in ("ip_low", "ip_mid", "ip_high")

    def test_no_param_returns_all(self, headers):
        r_all = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, timeout=20)
        assert r_all.status_code == 200
        all_count = len(r_all.json())
        # sum of bands should equal all (every item has exactly one band)
        total = 0
        for b in ("draft", "ip_low", "ip_mid", "ip_high", "completed"):
            r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, params={"status": b}, timeout=20)
            total += len(r.json())
        assert total == all_count, f"sum of band filters {total} != all {all_count}"


# ---------- Template public gating ----------

class TestTemplatePublicGating:
    def _find_decider(self, headers, completed: bool):
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, timeout=20)
        items = r.json()
        for it in items:
            if it.get("type") != "decider":
                continue
            if completed and it["status"] == "completed":
                return it
            if (not completed) and it["status"] != "completed":
                return it
        return None

    def test_non_completed_decider_public_blocked(self, headers):
        target = self._find_decider(headers, completed=False)
        if not target:
            pytest.skip("No non-completed decider found to test gating")
        body = {"name": "TEST_iter169_public_gate", "template_type": "options",
                "visibility": "public", "shared_with": []}
        r = requests.post(f"{BASE_URL}/api/decisions/{target['id']}/save-as-template",
                          headers=headers, json=body, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"
        detail = r.json().get("detail", "").lower()
        assert "complet" in detail, f"detail should mention completed: {detail}"

    def test_non_completed_decider_private_allowed(self, headers):
        target = self._find_decider(headers, completed=False)
        if not target:
            pytest.skip("No non-completed decider found")
        body = {"name": "TEST_iter169_private_ok", "template_type": "options",
                "visibility": "private", "shared_with": []}
        r = requests.post(f"{BASE_URL}/api/decisions/{target['id']}/save-as-template",
                          headers=headers, json=body, timeout=15)
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
        tid = r.json().get("id")
        assert tid
        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=headers, timeout=10)

    def test_completed_decider_public_allowed(self, headers):
        target = self._find_decider(headers, completed=True)
        if not target:
            pytest.skip("No completed decider in current data - skip positive case")
        body = {"name": "TEST_iter169_public_ok", "template_type": "options",
                "visibility": "public", "shared_with": []}
        r = requests.post(f"{BASE_URL}/api/decisions/{target['id']}/save-as-template",
                          headers=headers, json=body, timeout=15)
        assert r.status_code == 200, f"expected 200 for completed decider, got {r.status_code}: {r.text[:200]}"
        tid = r.json().get("id")
        if tid:
            requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=headers, timeout=10)


# ---------- VC pick reorder demo: ip_high ~75% ----------

class TestVCPickReorderDemo:
    def test_vc_pick_card_is_ip_high(self, headers):
        r = requests.get(f"{BASE_URL}/api/solution-box", headers=headers, timeout=20)
        items = r.json()
        match = next((it for it in items if "VC pick reorder" in (it.get("title") or "")), None)
        if not match:
            pytest.skip("'VC pick reorder demo' card not in user's data")
        assert match["status"] == "in_progress"
        assert match["progress_band"] == "ip_high", f"expected ip_high, got {match['progress_band']} ({match['progress_pct']}%)"
        assert 70 < match["progress_pct"] < 100
