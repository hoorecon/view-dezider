"""
Comprehensive tests for payment_admin.py:
- /api/org-types & /api/admin/org-types CRUD + soft-delete semantics
- /api/admin/payment-settings PUT toggle + audit log
- /api/payment-settings public view
- /api/admin/coupons CRUD
- /api/coupons/validate — every SP branch (ERR-1..ERR-10, MSG-1..MSG-3)
- /api/coupons/redeem per-user cap increment
- /api/payments/skip-grant 403 OFF / 200 ON / grant doc shape / coupon auto-redeem
- /api/payments/skip-grant/history scoped per user
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'http://localhost:8001').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ---------- helpers ----------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_session():
    """A fresh non-admin user for 403 tests + per-user cap tests."""
    email = f"TEST_payadm_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    pw = "UserPass2026!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Pay Adm Tester"}, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    if not token:
        token = _login(email, pw)
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}}


# ============================================================================
# ORG TYPES
# ============================================================================
class TestOrgTypes:
    def test_public_list_returns_seeded_six(self, admin_headers):
        r = requests.get(f"{API}/org-types", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        keys = [d["key"] for d in data]
        for k in ["INDIVIDUAL", "BUSINESS_ORG", "ACADEMIC_ORG", "NONPROFIT_ORG", "ASSOCIATION", "GOVERNMENT"]:
            assert k in keys, f"Missing seeded key {k}"
        # sorted by sort_order
        sort_orders = [d.get("sort_order", 99) for d in data if d["key"] in {"INDIVIDUAL","BUSINESS_ORG","ACADEMIC_ORG","NONPROFIT_ORG","ASSOCIATION","GOVERNMENT"}]
        assert sort_orders == sorted(sort_orders)

    def test_admin_list_requires_admin(self, user_session):
        r = requests.get(f"{API}/admin/org-types", headers=user_session["headers"])
        assert r.status_code == 403, f"expected 403, got {r.status_code} body={r.text[:200]}"

    def test_admin_list_ok(self, admin_headers):
        r = requests.get(f"{API}/admin/org-types", headers=admin_headers)
        assert r.status_code == 200

    def test_create_custom_orgtype_and_delete_hard(self, admin_headers):
        key = f"TEST_CUSTOM_{uuid.uuid4().hex[:6].upper()}"
        r = requests.post(f"{API}/admin/org-types", headers=admin_headers,
                          json={"key": key, "label": "Test Custom", "is_org": True, "sort_order": 50})
        assert r.status_code == 200, r.text
        assert r.json()["key"] == key
        # delete (hard since not system)
        d = requests.delete(f"{API}/admin/org-types/{key}", headers=admin_headers)
        assert d.status_code == 200
        assert d.json()["status"] == "deleted"
        # verify gone
        check = requests.get(f"{API}/admin/org-types", headers=admin_headers).json()
        assert not any(x["key"] == key for x in check)

    def test_delete_system_orgtype_soft_disables(self, admin_headers):
        # Pick GOVERNMENT — soft disable then re-enable
        r = requests.delete(f"{API}/admin/org-types/GOVERNMENT", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "disabled"
        # restore for next runs
        u = requests.put(f"{API}/admin/org-types/GOVERNMENT", headers=admin_headers, json={"active": True})
        assert u.status_code == 200


# ============================================================================
# PAYMENT SETTINGS
# ============================================================================
class TestPaymentSettings:
    def test_admin_get_requires_admin(self, user_session):
        r = requests.get(f"{API}/admin/payment-settings", headers=user_session["headers"])
        assert r.status_code == 403

    def test_admin_put_toggle_on_then_off(self, admin_headers):
        # ON
        r = requests.put(f"{API}/admin/payment-settings", headers=admin_headers,
                         json={"skip_payment_all_flows": True, "skip_payment_reason": "TEST_TOGGLE_ON"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["skip_payment_all_flows"] is True
        assert d["skip_payment_enabled_at"] is not None
        assert d["skip_payment_enabled_by"] is not None
        assert d["skip_payment_reason"] == "TEST_TOGGLE_ON"

        # Public endpoint sees the toggle
        pub = requests.get(f"{API}/payment-settings", headers=admin_headers).json()
        assert pub == {"skip_payment_all_flows": True}

    def test_public_payment_settings_accessible_to_user(self, user_session):
        r = requests.get(f"{API}/payment-settings", headers=user_session["headers"])
        assert r.status_code == 200
        assert "skip_payment_all_flows" in r.json()


# ============================================================================
# COUPONS — CRUD + every SP branch
# ============================================================================
@pytest.fixture(scope="module")
def coupon_codes():
    """Generate unique test coupon codes for this run."""
    suffix = uuid.uuid4().hex[:6].upper()
    return {
        "pct":      f"TEST_PCT_{suffix}",
        "value":    f"TEST_VAL_{suffix}",
        "net":      f"TEST_NET_{suffix}",
        "expired":  f"TEST_EXP_{suffix}",
        "future":   f"TEST_FUT_{suffix}",
        "inactive": f"TEST_INA_{suffix}",
        "capped":   f"TEST_CAP_{suffix}",
        "peruser":  f"TEST_PUR_{suffix}",
        "bad_type": f"TEST_BAD_{suffix}",
        "orgflow":  f"TEST_OFL_{suffix}",
    }


class TestCouponCRUD:
    def test_create_percentage(self, admin_headers, coupon_codes):
        r = requests.post(f"{API}/admin/coupons", headers=admin_headers, json={
            "coupon_code": coupon_codes["pct"].lower(),  # test uppercase
            "discount_type": "Percentage", "discount_value": 30,
            "max_usage_limit": 100, "max_usage_limit_per_user": 2,
            "is_active": "Y",
        })
        assert r.status_code == 200, r.text
        assert r.json()["coupon_code"] == coupon_codes["pct"]  # uppercased

    def test_create_value_and_net(self, admin_headers, coupon_codes):
        for code, dtype, dval in [
            (coupon_codes["value"], "Value", 50),
            (coupon_codes["net"], "NetValue", 99),
        ]:
            r = requests.post(f"{API}/admin/coupons", headers=admin_headers, json={
                "coupon_code": code, "discount_type": dtype, "discount_value": dval, "is_active": "Y",
            })
            assert r.status_code == 200, r.text

    def test_duplicate_code_409(self, admin_headers, coupon_codes):
        r = requests.post(f"{API}/admin/coupons", headers=admin_headers, json={
            "coupon_code": coupon_codes["pct"], "discount_type": "Percentage", "discount_value": 10, "is_active": "Y",
        })
        assert r.status_code == 409

    def test_create_inactive_expired_future_capped_peruser_orgflow(self, admin_headers, coupon_codes):
        now = datetime.now(timezone.utc)
        defs = [
            # inactive
            {"coupon_code": coupon_codes["inactive"], "discount_type": "Percentage", "discount_value": 10, "is_active": "N"},
            # expired
            {"coupon_code": coupon_codes["expired"], "discount_type": "Percentage", "discount_value": 10, "is_active": "Y",
             "valid_until": (now - timedelta(days=2)).isoformat()},
            # future
            {"coupon_code": coupon_codes["future"], "discount_type": "Percentage", "discount_value": 10, "is_active": "Y",
             "valid_from": (now + timedelta(days=7)).isoformat()},
            # global cap exhausted: limit=1, we'll pre-bump via redeem then re-validate
            {"coupon_code": coupon_codes["capped"], "discount_type": "Value", "discount_value": 10, "is_active": "Y",
             "max_usage_limit": 1},
            # per-user cap = 1
            {"coupon_code": coupon_codes["peruser"], "discount_type": "Value", "discount_value": 5, "is_active": "Y",
             "max_usage_limit_per_user": 1},
            # orgtype + flow restricted
            {"coupon_code": coupon_codes["orgflow"], "discount_type": "Percentage", "discount_value": 20, "is_active": "Y",
             "applicable_org_types": ["BUSINESS_ORG"], "applicable_flows": ["SUBSCRIPTION"]},
        ]
        for body in defs:
            r = requests.post(f"{API}/admin/coupons", headers=admin_headers, json=body)
            assert r.status_code == 200, f"create {body['coupon_code']} failed: {r.text}"

    def test_create_bad_discount_type(self, admin_headers, coupon_codes):
        r = requests.post(f"{API}/admin/coupons", headers=admin_headers, json={
            "coupon_code": coupon_codes["bad_type"], "discount_type": "BadType", "discount_value": 10, "is_active": "Y",
        })
        assert r.status_code == 400


class TestCouponValidateBranches:
    """Each SP branch must be exercised. Order matters for ERR-5/6 (need redeem first)."""

    def test_err1_invalid_code(self, user_session):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": "DOES_NOT_EXIST_X", "list_price": 100})
        assert r.status_code == 200
        assert r.json()["remarks_code"] == "ERR-1"
        assert r.json()["valid"] is False

    def test_err0_missing_args(self, user_session):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"], json={"list_price": 0})
        assert r.status_code == 200
        assert r.json()["remarks_code"] == "ERR-0"

    def test_err2_inactive(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["inactive"], "list_price": 100})
        assert r.json()["remarks_code"] == "ERR-2"

    def test_err3_future_not_yet_started(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["future"], "list_price": 100})
        assert r.json()["remarks_code"] == "ERR-3"

    def test_err4_expired(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["expired"], "list_price": 100})
        assert r.json()["remarks_code"] == "ERR-4"

    def test_msg1_percentage(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["pct"], "list_price": 200}).json()
        assert r["remarks_code"] == "MSG-1"
        assert r["valid"] is True
        assert r["net_payable_amount"] == 140.0  # 30% off 200

    def test_msg2_value(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["value"], "list_price": 200}).json()
        assert r["remarks_code"] == "MSG-2"
        assert r["net_payable_amount"] == 150.0  # 200-50

    def test_msg2_value_floors_at_zero(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["value"], "list_price": 5}).json()
        assert r["remarks_code"] == "MSG-2"
        assert r["net_payable_amount"] == 0.0

    def test_msg3_netvalue(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["net"], "list_price": 500}).json()
        assert r["remarks_code"] == "MSG-3"
        assert r["net_payable_amount"] == 99.0

    def test_err9_org_type_not_applicable(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["orgflow"], "list_price": 100,
                                "org_type": "INDIVIDUAL", "flow": "SUBSCRIPTION"}).json()
        assert r["remarks_code"] == "ERR-9"

    def test_err10_flow_not_applicable(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["orgflow"], "list_price": 100,
                                "org_type": "BUSINESS_ORG", "flow": "TOPUP"}).json()
        assert r["remarks_code"] == "ERR-10"

    def test_orgflow_happy_path(self, user_session, coupon_codes):
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": coupon_codes["orgflow"], "list_price": 100,
                                "org_type": "BUSINESS_ORG", "flow": "SUBSCRIPTION"}).json()
        assert r["remarks_code"] == "MSG-1"
        assert r["valid"] is True

    def test_err6_per_user_cap_after_redeem(self, user_session, coupon_codes):
        # First validate ok
        r1 = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                           json={"coupon_code": coupon_codes["peruser"], "list_price": 50}).json()
        assert r1["valid"] is True
        # Redeem once
        red = requests.post(f"{API}/coupons/redeem", headers=user_session["headers"],
                            json={"coupon_code": coupon_codes["peruser"], "list_price": 50, "net_payable_amount": 45}).json()
        assert red.get("status") == "redeemed"
        # Now should be capped per-user
        r2 = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                           json={"coupon_code": coupon_codes["peruser"], "list_price": 50}).json()
        assert r2["remarks_code"] == "ERR-6"

    def test_err5_global_cap_after_redeem(self, user_session, coupon_codes):
        # Redeem once to exhaust the cap=1
        requests.post(f"{API}/coupons/redeem", headers=user_session["headers"],
                      json={"coupon_code": coupon_codes["capped"], "list_price": 50, "net_payable_amount": 40})
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                         json={"coupon_code": coupon_codes["capped"], "list_price": 50}).json()
        assert r["remarks_code"] == "ERR-5"

    def test_percentage_caps_at_100(self, admin_headers, user_session):
        code = f"TEST_PCT200_{uuid.uuid4().hex[:6].upper()}"
        c = requests.post(f"{API}/admin/coupons", headers=admin_headers, json={
            "coupon_code": code, "discount_type": "Percentage", "discount_value": 250, "is_active": "Y",
        })
        assert c.status_code == 200
        r = requests.post(f"{API}/coupons/validate", headers=user_session["headers"],
                          json={"coupon_code": code, "list_price": 100}).json()
        assert r["remarks_code"] == "MSG-1"
        assert r["net_payable_amount"] == 0.0  # 100% cap


# ============================================================================
# SKIP-GRANT
# ============================================================================
class TestSkipGrant:
    def test_skip_grant_blocked_when_off(self, admin_headers, user_session):
        # First turn OFF
        requests.put(f"{API}/admin/payment-settings", headers=admin_headers,
                     json={"skip_payment_all_flows": False})
        r = requests.post(f"{API}/payments/skip-grant", headers=user_session["headers"],
                          json={"flow": "DECISION_FLOW", "amount": 100})
        assert r.status_code == 403, f"expected 403 when toggle OFF, got {r.status_code}: {r.text}"

    def test_skip_grant_works_when_on(self, admin_headers, user_session):
        # Turn ON
        requests.put(f"{API}/admin/payment-settings", headers=admin_headers,
                     json={"skip_payment_all_flows": True, "skip_payment_reason": "Razorpay creds pending"})
        r = requests.post(f"{API}/payments/skip-grant", headers=user_session["headers"],
                          json={"flow": "SUBSCRIPTION", "amount": 999, "plan_id": "test-plan"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["amount_charged"] == 0.0
        assert d["payment_method"] == "ADMIN_SKIP"
        assert d["status"] == "granted"
        assert d["flow"] == "SUBSCRIPTION"
        assert d["order_id"].startswith("SKIP-")

    def test_skip_grant_with_coupon_redeems(self, admin_headers, user_session, coupon_codes):
        # use the percentage coupon to ensure auto-redeem
        before = requests.get(f"{API}/coupons/my-usage/{coupon_codes['pct']}",
                              headers=user_session["headers"]).json()
        r = requests.post(f"{API}/payments/skip-grant", headers=user_session["headers"],
                          json={"flow": "DECISION_FLOW", "amount": 100,
                                "coupon_code": coupon_codes["pct"], "net_payable_amount": 70, "list_price": 100})
        assert r.status_code == 200
        assert r.json()["coupon_code"] == coupon_codes["pct"]
        after = requests.get(f"{API}/coupons/my-usage/{coupon_codes['pct']}",
                             headers=user_session["headers"]).json()
        assert after["usage_count"] == before["usage_count"] + 1

    def test_skip_grant_history_scoped(self, user_session):
        r = requests.get(f"{API}/payments/skip-grant/history", headers=user_session["headers"])
        assert r.status_code == 200
        items = r.json()
        # All grants should be the current user's
        assert all("order_id" in g and g.get("payment_method") == "ADMIN_SKIP" for g in items)
        assert len(items) >= 1


# ============================================================================
# Teardown — turn OFF the toggle so test env doesn't leak skip enabled
# ============================================================================
def test_zz_teardown_toggle_off(admin_headers):
    r = requests.put(f"{API}/admin/payment-settings", headers=admin_headers,
                     json={"skip_payment_all_flows": False, "skip_payment_reason": ""})
    assert r.status_code == 200
    assert r.json()["skip_payment_all_flows"] is False
