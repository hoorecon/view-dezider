"""
Iteration 57 — SKU ↔ Solution mapping & entitlement gating

Tests:
- PUT /api/solutions-store/solutions/{id} accepts linked_sku_codes (uppercased)
- Owner/admin can set; non-owner regular user gets 403
- GET /api/solutions-store/solutions enriches with linked_sku_codes, unlock_skus, unlocked_via, is_locked
- is_locked=true for a regular non-entitled user when codes mapped; false for admin & creator
- GET detail returns same lock fields
- POST /api/solutions-store/apply-to-option blocks locked regular user (403),
  succeeds for admin/owner, succeeds after mapping cleared
- Clearing linked_sku_codes=[] makes is_locked=false for everyone
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data.get("session_token") or data.get("token") or data.get("access_token")


def _register_fresh_user():
    """The provided regular user already owns L1 — we MUST register a fresh
    user with zero entitlements to test the locked-view path correctly."""
    import time
    email = f"sku_lock_{int(time.time()*1000)}@example.com"
    password = "FreshPass2026!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": "SKU Lock Tester"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    if not tok:
        tok = _login(email, password)
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_token():
    return _register_fresh_user()


@pytest.fixture(scope="module")
def auth_admin(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_user(user_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def target_solution(auth_admin):
    """Pick an admin-visible authorized solution; ensure SKU catalog seeded."""
    # Trigger SKU catalog seed so L1-L4 exist
    requests.post(f"{API}/store/skus/seed", timeout=30)
    r = auth_admin.get(f"{API}/solutions-store/solutions", timeout=30)
    assert r.status_code == 200, f"List solutions failed: {r.status_code} {r.text}"
    sols = r.json()
    assert isinstance(sols, list) and len(sols) > 0, "Expected at least one solution"
    # Pick first authorized solution (not created by admin) so we can test admin bypass + non-owner gating
    sol = next((s for s in sols if s.get("is_authorized")), sols[0])
    sol_id = sol["solution_id"]
    yield sol_id
    # Teardown: clear mapping
    try:
        auth_admin.put(f"{API}/solutions-store/solutions/{sol_id}", json={"linked_sku_codes": []}, timeout=30)
    except Exception:
        pass


# -------------------- mapping CRUD --------------------

class TestSkuMappingUpdate:
    def test_admin_can_set_linked_sku_codes(self, auth_admin, target_solution):
        # use lowercase to verify uppercasing
        r = auth_admin.put(
            f"{API}/solutions-store/solutions/{target_solution}",
            json={"linked_sku_codes": ["l1"]},
            timeout=30,
        )
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
        # verify via GET
        g = auth_admin.get(f"{API}/solutions-store/solutions/{target_solution}", timeout=30)
        assert g.status_code == 200
        body = g.json()
        assert body.get("linked_sku_codes") == ["L1"], f"expected ['L1'], got {body.get('linked_sku_codes')}"
        # Admin should NOT see is_locked=true (bypass)
        assert body.get("is_locked") is False, f"admin should bypass lock, got is_locked={body.get('is_locked')}"
        # unlock_skus should be enriched
        assert isinstance(body.get("unlock_skus"), list) and len(body["unlock_skus"]) == 1
        assert body["unlock_skus"][0]["code"] == "L1"
        assert "name" in body["unlock_skus"][0]

    def test_non_owner_user_cannot_update(self, auth_user, target_solution):
        r = auth_user.put(
            f"{API}/solutions-store/solutions/{target_solution}",
            json={"linked_sku_codes": ["L2"]},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


# -------------------- listing + detail enrichment --------------------

class TestLockEnrichment:
    def test_regular_user_sees_locked(self, auth_user, target_solution):
        r = auth_user.get(f"{API}/solutions-store/solutions", timeout=30)
        assert r.status_code == 200
        sols = r.json()
        target = next((s for s in sols if s["solution_id"] == target_solution), None)
        assert target is not None, "target solution missing from user listing"
        assert target.get("linked_sku_codes") == ["L1"]
        assert target.get("is_locked") is True, f"regular user should see locked; got {target.get('is_locked')}"
        assert target.get("unlocked_via") is None
        assert isinstance(target.get("unlock_skus"), list) and len(target["unlock_skus"]) == 1
        # ensure unlock_sku has the badge fields
        sku0 = target["unlock_skus"][0]
        for key in ("code", "name", "badge_color", "price_paise"):
            assert key in sku0, f"unlock_skus missing key {key}"

    def test_detail_lock_fields_for_user(self, auth_user, target_solution):
        r = auth_user.get(f"{API}/solutions-store/solutions/{target_solution}", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("is_locked") is True
        assert body.get("linked_sku_codes") == ["L1"]
        assert isinstance(body.get("unlock_skus"), list)


# -------------------- apply-to-option gating --------------------

class TestApplyToOptionGating:
    def test_user_blocked_when_locked(self, auth_user, target_solution):
        r = auth_user.post(
            f"{API}/solutions-store/apply-to-option",
            json={"solution_id": target_solution},
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 locked, got {r.status_code} {r.text}"
        body = r.json()
        detail = body.get("detail", "")
        assert "lock" in detail.lower() or "purchase" in detail.lower(), f"expected lock message, got: {detail}"

    def test_admin_bypasses_lock(self, auth_admin, target_solution):
        r = auth_admin.post(
            f"{API}/solutions-store/apply-to-option",
            json={"solution_id": target_solution},
            timeout=30,
        )
        assert r.status_code == 200, f"admin should bypass: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("solution_id") == target_solution

    def test_clearing_mapping_unlocks_for_everyone(self, auth_admin, auth_user, target_solution):
        # Clear mapping
        clr = auth_admin.put(
            f"{API}/solutions-store/solutions/{target_solution}",
            json={"linked_sku_codes": []},
            timeout=30,
        )
        assert clr.status_code == 200

        # Verify listing for user: is_locked=False, codes=[]
        r = auth_user.get(f"{API}/solutions-store/solutions", timeout=30)
        assert r.status_code == 200
        target = next((s for s in r.json() if s["solution_id"] == target_solution), None)
        assert target is not None
        assert target.get("linked_sku_codes") == []
        assert target.get("is_locked") is False, f"after clearing, lock should be off; got {target.get('is_locked')}"

        # Apply-to-option should succeed now
        a = auth_user.post(
            f"{API}/solutions-store/apply-to-option",
            json={"solution_id": target_solution},
            timeout=30,
        )
        assert a.status_code == 200, f"user should succeed after clear: {a.status_code} {a.text}"


# -------------------- owner bypass --------------------

class TestOwnerBypass:
    """User-created solutions: creator should never see lock for own solution."""

    def test_owner_bypass(self, auth_user, auth_admin):
        # User creates a PRIVATE solution
        payload = {
            "type": "PRODUCT",
            "name": "TEST_owner_lock_bypass_sku_iter57",
            "description": "test",
            "visibility": "PRIVATE",
        }
        c = auth_user.post(f"{API}/solutions-store/solutions", json=payload, timeout=30)
        assert c.status_code == 200, f"create failed: {c.status_code} {c.text}"
        sol_id = c.json()["solution_id"]

        # User maps SKU on own solution (owner can update)
        u = auth_user.put(
            f"{API}/solutions-store/solutions/{sol_id}",
            json={"linked_sku_codes": ["L1"]},
            timeout=30,
        )
        assert u.status_code == 200, f"owner PUT failed: {u.status_code} {u.text}"

        # Detail as owner: is_locked should be False (owner bypass)
        d = auth_user.get(f"{API}/solutions-store/solutions/{sol_id}", timeout=30)
        assert d.status_code == 200
        body = d.json()
        assert body.get("linked_sku_codes") == ["L1"]
        assert body.get("is_locked") is False, f"owner should bypass lock; got {body.get('is_locked')}"

        # Owner can apply to option
        a = auth_user.post(
            f"{API}/solutions-store/apply-to-option",
            json={"solution_id": sol_id},
            timeout=30,
        )
        assert a.status_code == 200, f"owner apply failed: {a.status_code} {a.text}"

        # Cleanup
        auth_user.delete(f"{API}/solutions-store/solutions/{sol_id}", timeout=30)
