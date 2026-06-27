"""Backend regression for Phase 3A (iter 170) — Catalog payout config (L0-L3)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "super@test.com"
ADMIN_PASSWORD = "SuperPass2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("session_token") or j.get("token") or j.get("access_token")
    assert tok, f"no session_token in login response: {j}"
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def health_node_id(auth_headers):
    # Try to find a node under la_health for override testing
    r = requests.get(f"{BASE_URL}/api/catalog/nodes?life_area_id=la_health",
                     headers=auth_headers, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"catalog/nodes unavailable: {r.status_code}")
    items = r.json().get("items", [])
    if not items:
        pytest.skip("no nodes under la_health")
    # Pick a deep (high level) node if possible
    items.sort(key=lambda x: -(x.get("level") or 0))
    return items[0]["node_id"]


# ---- GET /api/catalog/payout/config ----
class TestPayoutConfigShape:
    def test_get_config_returns_required_keys(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/catalog/payout/config",
                         headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ["global", "default", "template_steps", "nodes"]:
            assert key in data, f"missing key: {key}"
        assert isinstance(data["template_steps"], list)
        assert set(data["template_steps"]) == {
            "factors", "classification", "prioritization", "options", "assessment"
        }
        assert isinstance(data["nodes"], list)

    def test_default_has_expected_fields(self, auth_headers):
        data = requests.get(f"{BASE_URL}/api/catalog/payout/config",
                            headers=auth_headers, timeout=20).json()
        d = data["default"]
        for k in ["free_usage_count", "payment_min", "payment_max",
                  "karma_solution_store", "karma_reviewnet",
                  "karma_template_by_step"]:
            assert k in d, f"default missing {k}"


# ---- PUT /api/catalog/payout/config/global ----
class TestGlobalUpsert:
    def test_global_upsert_persists(self, auth_headers):
        payload = {"payment_min": 50, "payment_max": 800,
                   "karma_solution_store": 20, "karma_reviewnet": 5,
                   "free_usage_count": 3,
                   "karma_template_by_step": {
                       "factors": 5, "classification": 8,
                       "prioritization": 10, "options": 15, "assessment": 20}}
        r = requests.put(f"{BASE_URL}/api/catalog/payout/config/global",
                         headers=auth_headers, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        # Verify persistence via GET
        r2 = requests.get(f"{BASE_URL}/api/catalog/payout/config",
                          headers=auth_headers, timeout=20)
        g = r2.json()["global"]
        assert g["payment_max"] == 800
        assert g["payment_min"] == 50
        assert g["karma_template_by_step"]["assessment"] == 20

    def test_global_rejects_max_lt_min(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/catalog/payout/config/global",
                         headers=auth_headers,
                         json={"payment_min": 500, "payment_max": 100}, timeout=20)
        assert r.status_code == 400


# ---- PUT/DELETE /api/catalog/payout/config/node/{id} ----
class TestNodeOverride:
    def test_node_upsert_then_resolve_then_delete(self, auth_headers, health_node_id):
        # Upsert
        payload = {"payment_min": 25, "payment_max": 600,
                   "karma_solution_store": 30}
        r = requests.put(
            f"{BASE_URL}/api/catalog/payout/config/node/{health_node_id}",
            headers=auth_headers, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        resolved = r.json()
        assert resolved.get("payment_min") == 25
        assert resolved.get("payment_max") == 600

        # GET config — node should appear
        r2 = requests.get(f"{BASE_URL}/api/catalog/payout/config",
                          headers=auth_headers, timeout=20)
        nodes = r2.json()["nodes"]
        match = [n for n in nodes if n["node_id"] == health_node_id]
        assert match, "node override not listed"
        assert match[0]["payment_min"] == 25
        assert match[0].get("level") is not None
        assert match[0].get("node_name")

        # Resolve via dedicated endpoint
        r3 = requests.get(
            f"{BASE_URL}/api/catalog/payout/resolve/{health_node_id}",
            headers=auth_headers, timeout=20)
        assert r3.status_code == 200
        res = r3.json()
        assert res.get("payment_min") == 25
        assert "_provenance" in res, "missing provenance"

        # Delete
        r4 = requests.delete(
            f"{BASE_URL}/api/catalog/payout/config/node/{health_node_id}",
            headers=auth_headers, timeout=20)
        assert r4.status_code == 200
        assert r4.json().get("deleted") >= 1

        # GET — should no longer appear
        r5 = requests.get(f"{BASE_URL}/api/catalog/payout/config",
                          headers=auth_headers, timeout=20)
        nodes2 = r5.json()["nodes"]
        assert not [n for n in nodes2 if n["node_id"] == health_node_id]

    def test_node_404_for_unknown_id(self, auth_headers):
        r = requests.put(
            f"{BASE_URL}/api/catalog/payout/config/node/DOES_NOT_EXIST_xyz",
            headers=auth_headers, json={"payment_min": 1, "payment_max": 2},
            timeout=20)
        assert r.status_code == 404


# ---- POST /api/catalog/payout/preview ----
class TestPreviewEquation:
    def test_cash_payout_canonical_example(self, auth_headers):
        # min=100, max=1000, avg=4, ratings=1500
        # cash = 100 + 900 * (4/5) * (1500/3000) = 100 + 900*0.8*0.5 = 100+360 = 460
        # NOTE: global currently set to min=50 max=800 by earlier test -> use override via preview body cfg
        # Reset global to canonical for this assertion
        requests.put(f"{BASE_URL}/api/catalog/payout/config/global",
                     headers=auth_headers,
                     json={"payment_min": 100, "payment_max": 1000,
                           "karma_solution_store": 10, "karma_reviewnet": 5,
                           "free_usage_count": 3}, timeout=20)
        r = requests.post(f"{BASE_URL}/api/catalog/payout/preview",
                          headers=auth_headers,
                          json={"usage_type": "solution_store_paid",
                                "avg_rating": 4.0, "num_ratings": 1500},
                          timeout=20)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["reward_kind"] == "cash"
        # expected 460
        assert abs(out["cash_payout"] - 460.0) < 0.01, out

    def test_karma_canonical_example(self, auth_headers):
        # karma_solution_store=10, star=5 -> 10*(1+5/5)=20  (Note: brief said "karma 40 case" assuming karma_per_use=20 -> 40)
        r = requests.post(f"{BASE_URL}/api/catalog/payout/preview",
                          headers=auth_headers,
                          json={"usage_type": "reviewnet",
                                "star_rating": 5},
                          timeout=20)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["reward_kind"] == "karma"
        # karma_reviewnet from earlier set = 5 -> 5*(1+5/5) = 10
        assert out["karma"] == 10, out

    def test_preview_unknown_usage_type(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/catalog/payout/preview",
                          headers=auth_headers,
                          json={"usage_type": "garbage_type"}, timeout=20)
        assert r.status_code == 400
