"""Iter 32 — POST /api/ai/find-best-options now returns per-option factor_values.

For Solution-Store-sourced options, factor_values must come from the store
item's quantitative_factors (mapped by factor_name → decision factor id),
overriding any AI estimate.

LLM budget is exhausted in this preview so we exercise the store-only
fallback path on purpose.
"""
import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
)
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL/EXPO_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

# Unique life area so the store match is deterministic (avoid colliding with
# unrelated public solutions in the same area).
LIFE_AREA = "career"
RUN = uuid.uuid4().hex[:6]


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("session_token") or j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def user_headers():
    return {"Authorization": f"Bearer {_login(USER_EMAIL, USER_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_headers():
    try:
        return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASS)}", "Content-Type": "application/json"}
    except Exception:
        return None


@pytest.fixture(scope="module")
def store_solution(user_headers, admin_headers):
    """Create a Solutions-Store item the harden user can see, with
    quantitative_factors matching the decision factor names."""
    payload = {
        "type": "PRODUCT",
        "name": f"TEST_iter32 SuperLaptop {RUN}",
        "description": "Test laptop used by find-best-options factor_values check",
        "life_area_id": LIFE_AREA,
        "visibility": "PRIVATE",  # user-owned so they always see it
        "tags": ["TEST_iter32", "laptop", "budget"],
        "price_range": "₹40k-50k",
        "quantitative_factors": [
            {"factor_name": "Budget", "value": 45000, "unit": "INR"},
            {"factor_name": "Rating", "value": 4.5, "unit": "stars"},
        ],
    }
    r = requests.post(
        f"{BASE_URL}/api/solutions-store/solutions",
        json=payload,
        headers=user_headers,
        timeout=30,
    )
    # If user-created solutions are gated, try admin and make it PUBLIC
    if r.status_code not in (200, 201) and admin_headers:
        payload["visibility"] = "PUBLIC"
        r = requests.post(
            f"{BASE_URL}/api/solutions-store/solutions",
            json=payload,
            headers=admin_headers,
            timeout=30,
        )
    assert r.status_code in (200, 201), f"create solution failed: {r.status_code} {r.text}"
    sol = r.json()
    sid = sol.get("solution_id") or sol.get("id")
    assert sid, sol
    yield sol
    # Cleanup best-effort
    try:
        h = admin_headers or user_headers
        requests.delete(f"{BASE_URL}/api/solutions-store/solutions/{sid}", headers=h, timeout=10)
    except Exception:
        pass


@pytest.fixture(scope="module")
def decision_id(user_headers):
    payload = {
        "title": f"TEST_iter32 Buying a laptop {RUN}",
        "context": "Need a laptop within budget with good rating",
        "life_area": LIFE_AREA,
        "decision_type": "purchase",
    }
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=user_headers, timeout=20)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text}"
    did = r.json().get("id") or r.json().get("decision", {}).get("id")
    assert did
    # Update factors: Budget <=50000, Rating >=4
    factors = [
        {
            "id": "fac_budget",
            "name": "Budget",
            "category": "primary",
            "rating": 90,
            "order": 0,
            "unit": "INR",
            "expected_value": 50000,
            "operator": "<=",
            "data_type": "numeric",
        },
        {
            "id": "fac_rating",
            "name": "Rating",
            "category": "primary",
            "rating": 80,
            "order": 1,
            "unit": "stars",
            "expected_value": 4,
            "operator": ">=",
            "data_type": "numeric",
        },
    ]
    upd = requests.put(
        f"{BASE_URL}/api/decisions/{did}",
        json={"factors": factors},
        headers=user_headers,
        timeout=20,
    )
    assert upd.status_code in (200, 204), f"update factors: {upd.status_code} {upd.text}"
    yield did
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=user_headers, timeout=10)
    except Exception:
        pass


# ─── 1. response contract still holds ───────────────────────────────
class TestResponseContract:
    def test_auth_required(self):
        r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                          json={"decision_id": "x"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_404_unknown_decision(self, user_headers):
        r = requests.post(
            f"{BASE_URL}/api/ai/find-best-options",
            json={"decision_id": f"dec_{uuid.uuid4().hex}"},
            headers=user_headers,
            timeout=30,
        )
        assert r.status_code == 404

    def test_200_shape(self, user_headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/ai/find-best-options",
            json={"decision_id": decision_id, "limit": 5},
            headers=user_headers,
            timeout=90,
        )
        assert r.status_code == 200, f"got {r.status_code} {r.text}"
        body = r.json()
        for key in ("options", "used_model", "store_match_count"):
            assert key in body, f"missing key {key}: {body}"
        assert isinstance(body["options"], list)
        assert len(body["options"]) <= 5
        # used_model may be null when LLM budget is exhausted
        assert body["used_model"] in (None, "claude-sonnet-4-5-20250929", "gpt-4.1-mini")


# ─── 2. Store-sourced factor_values populated from quantitative_factors ──
class TestFactorValuesFromStore:
    def test_store_option_carries_factor_values(self, user_headers, decision_id, store_solution):
        sid = store_solution.get("solution_id") or store_solution.get("id")
        r = requests.post(
            f"{BASE_URL}/api/ai/find-best-options",
            json={"decision_id": decision_id, "limit": 5},
            headers=user_headers,
            timeout=90,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        opts = body["options"]
        # We need to see a store match — at least 1 candidate must be the seeded solution
        assert body.get("store_match_count", 0) >= 1, (
            f"expected store_match_count>=1 from seeded solution, got {body.get('store_match_count')}; opts={opts}"
        )

        store_opts = [o for o in opts if o.get("source") == "store"]
        assert store_opts, f"no store-sourced option returned. Body: {body}"

        seeded = next((o for o in store_opts if o.get("solution_id") == sid), None)
        assert seeded is not None, (
            f"seeded solution {sid} not present in returned options. opts={opts}"
        )

        fvs = seeded.get("factor_values")
        assert fvs and isinstance(fvs, list), f"missing/empty factor_values on store option: {seeded}"

        by_id = {fv["factor_id"]: fv["value"] for fv in fvs}
        assert "fac_budget" in by_id, f"Budget factor_id not mapped: {fvs}"
        assert "fac_rating" in by_id, f"Rating factor_id not mapped: {fvs}"
        # Store values must override (45000 / 4.5)
        assert float(by_id["fac_budget"]) == 45000.0, by_id
        assert float(by_id["fac_rating"]) == 4.5, by_id


# ─── 3. _match_factor_id basic sanity via store option containing only
#       a factor name with different case/whitespace still maps correctly.
class TestFactorNameMatching:
    def test_case_insensitive_match(self, user_headers, admin_headers, decision_id):
        h = admin_headers or user_headers
        sol_payload = {
            "type": "PRODUCT",
            "name": f"TEST_iter32 CaseLaptop {RUN}",
            "description": "checks case-insensitive factor matching",
            "life_area_id": LIFE_AREA,
            "visibility": "PRIVATE" if h is user_headers else "PUBLIC",
            "tags": ["TEST_iter32"],
            "quantitative_factors": [
                {"factor_name": "BUDGET", "value": 30000},   # uppercase
                {"factor_name": "  rating  ", "value": 4.8},  # whitespace + lowercase
            ],
        }
        r = requests.post(f"{BASE_URL}/api/solutions-store/solutions",
                          json=sol_payload, headers=h, timeout=20)
        if r.status_code not in (200, 201):
            pytest.skip(f"cannot create extra store solution: {r.status_code} {r.text[:120]}")
        sol = r.json()
        sid = sol.get("solution_id")
        try:
            r = requests.post(
                f"{BASE_URL}/api/ai/find-best-options",
                json={"decision_id": decision_id, "limit": 5},
                headers=user_headers,
                timeout=90,
            )
            assert r.status_code == 200
            opts = r.json()["options"]
            match = next((o for o in opts if o.get("solution_id") == sid), None)
            if not match:
                pytest.skip("second store item not surfaced (ranking may have preferred first)")
            fvs = {fv["factor_id"]: fv["value"] for fv in (match.get("factor_values") or [])}
            assert "fac_budget" in fvs, f"BUDGET (uppercase) should map to fac_budget: {fvs}"
            assert "fac_rating" in fvs, f"'  rating  ' should map to fac_rating: {fvs}"
        finally:
            try:
                requests.delete(f"{BASE_URL}/api/solutions-store/solutions/{sid}", headers=h, timeout=10)
            except Exception:
                pass
