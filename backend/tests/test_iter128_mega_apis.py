"""Iteration 128 mega-feature tests.

Covers:
  - 7×7 Org Matrix (Custom Orgs, Divisions, Drivers, Assess, Due)
  - ATEX Estimation (SCC mandatory, math, AI suggest fallback)
  - 6 LeGs Goal Setting (L3 division required, tree, cascade delete, action conversion)
  - Referral Bonus Designer (config, simulate, profile/cash opt-in, ledger)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"

# Primary test (non-admin) user
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


# ─── Fixtures ────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="session")
def user_token():
    # Register a fresh user to keep tests isolated
    email = f"iter128_{int(time.time())}@example.com"
    pw = "Iter128Pass2026!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Iter128 Tester"}, timeout=30)
    if r.status_code in (200, 201):
        tok = r.json().get("session_token") or r.json().get("token")
        if tok:
            return tok
    # Fallback to primary
    r = requests.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"fallback user login failed: {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ─── 7×7 ORG MATRIX ──────────────────────────────────────────────
class TestSevenSeven:
    """7×7 Custom Orgs + Masters + Assessment"""

    def test_divisions_seeded_in_order(self, user_token):
        r = requests.get(f"{API}/seven-seven/divisions", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        rows = r.json()["divisions"]
        assert len(rows) >= 7, f"expected >=7 divisions, got {len(rows)}"
        # check ordering
        orders = [d["order"] for d in rows[:7]]
        assert orders == sorted(orders), f"divisions not sorted by order: {orders}"
        assert all(d.get("platform_default") is True for d in rows[:7]), "first 7 should be platform_default"

    def test_drivers_grouped_team_systems_strategy(self, user_token):
        r = requests.get(f"{API}/seven-seven/drivers", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        drivers = r.json()["drivers"]
        cats = {d["category"] for d in drivers}
        assert {"team", "systems", "strategy"}.issubset(cats), f"missing categories: {cats}"
        # count per category from seed: team=3, systems=2, strategy=2
        counts = {c: sum(1 for d in drivers if d["category"] == c) for c in cats}
        assert counts.get("team", 0) >= 3 and counts.get("systems", 0) >= 2 and counts.get("strategy", 0) >= 2

    def test_create_user_org_requires_life_area(self, user_token):
        # missing life_area → 422
        r = requests.post(f"{API}/seven-seven/orgs", headers=_h(user_token), json={"name": "TEST_OrgNoLA"}, timeout=30)
        assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}"

    def test_full_org_assess_due_flow(self, user_token):
        # 1. create org
        r = requests.post(f"{API}/seven-seven/orgs", headers=_h(user_token), json={
            "name": "TEST_Org_iter128", "org_type": "BUSINESS", "life_area": "business",
            "description": "iter128 test", "icon": "rocket", "color": "#4338CA"
        }, timeout=30)
        assert r.status_code == 200, r.text
        org = r.json()["user_org"]
        org_id = org["id"]
        assert org["life_area"] == "business"

        # 2. due_now should be True initially (no assessments yet)
        r = requests.get(f"{API}/seven-seven/assess/{org_id}/due", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["due_now"] is True
        assert r.json()["cadence_days"] == 14

        # 3. submit a cell score
        r = requests.post(f"{API}/seven-seven/assess", headers=_h(user_token), json={
            "user_org_id": org_id, "division_code": "solution_delivery",
            "driver_code": "capability", "scale_code": "up_to_mark", "remarks": "TEST_cell"
        }, timeout=30)
        assert r.status_code == 200, r.text
        assess = r.json()["assessment"]
        assert assess["division_code"] == "solution_delivery"

        # 4. fetch matrix
        r = requests.get(f"{API}/seven-seven/assess/{org_id}", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        m = r.json()
        assert m["total_assessments"] >= 1
        assert any(c["driver_code"] == "capability" for c in m["matrix"])

        # 5. due_now should be False now (just assessed)
        r = requests.get(f"{API}/seven-seven/assess/{org_id}/due", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        assert r.json()["due_now"] is False, f"due_now should be False right after assess: {r.json()}"
        assert r.json()["days_since_last"] == 0

        # Store for later tests
        pytest._iter128_org_id = org_id


# ─── ATEX ────────────────────────────────────────────────────────
class TestATEX:
    def test_estimate_without_scc_returns_400(self, user_token):
        r = requests.post(f"{API}/atex/estimate", headers=_h(user_token), json={
            "task_title": "Test no SCC",
            "synchronized_completion_criteria": "",
            "sub_tasks": [{"title": "x", "effort_minutes": 30}],
        }, timeout=30)
        assert r.status_code == 400, f"expected 400 SCC mandatory, got {r.status_code} {r.text[:200]}"
        assert "SCC" in r.text or "Synchronized" in r.text

    def test_estimate_math_and_end_date(self, user_token):
        payload = {
            "task_title": "TEST ATEX math",
            "task_priority": "P1",  # allows RC1, RC2
            "synchronized_completion_criteria": "All sub-tasks done, reviewer signs off",
            "sub_tasks": [
                {"title": "ST1", "effort_minutes": 120, "ip_level": "high"},
                {"title": "ST2", "effort_minutes": 60, "ip_level": "medium"},
            ],
            "minimal_buffer_pct": 10.0,
            "practical_break_minutes": 30,
            "risks": [
                {"category": "RC1", "description": "delay", "mitigation_minutes": 20, "contingency_minutes": 10},
                {"category": "RC3", "description": "black-swan", "mitigation_minutes": 60, "contingency_minutes": 0},  # filtered (P1 excludes RC3)
            ],
            "start_date": "2026-01-15",
            "work_hours_per_day": 8.0,
            "holidays_per_week": 1,
        }
        r = requests.post(f"{API}/atex/estimate", headers=_h(user_token), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()["calc"]
        # EE = 180
        assert c["effort_minutes"] == 180, c
        # MB = 10% of 180 = 18
        assert c["minimal_buffer_minutes"] == 18, c
        # PB = 30
        assert c["practical_break_minutes"] == 30
        # RM = 30 (RC1 only — 20+10)
        assert c["risk_buffer_minutes"] == 30, c
        # TT = 180+18+30+30 = 258
        assert c["total_timeline_minutes"] == 258, c
        # end_date set
        assert c["end_date"] is not None
        # risks_breakdown includes both with RC3 marked not applied
        applied = {rb["category"]: rb["applied"] for rb in c["risks_breakdown"]}
        assert applied.get("RC1") is True and applied.get("RC3") is False

    def test_ai_suggest_returns_structure(self, user_token):
        r = requests.post(f"{API}/atex/ai-suggest", headers=_h(user_token),
                          json={"task_title": "Build a landing page in 2 days"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "sub_tasks" in data and isinstance(data["sub_tasks"], list) and len(data["sub_tasks"]) >= 1
        assert "scc" in data
        assert "risks" in data


# ─── 6 LeGs ──────────────────────────────────────────────────────
class TestSixLegs:
    def _ensure_org(self, user_token):
        org_id = getattr(pytest, "_iter128_org_id", None)
        if org_id:
            return org_id
        r = requests.post(f"{API}/seven-seven/orgs", headers=_h(user_token), json={
            "name": "TEST_OrgSixLegs", "life_area": "business",
        }, timeout=30)
        assert r.status_code == 200, r.text
        org_id = r.json()["user_org"]["id"]
        pytest._iter128_org_id = org_id
        return org_id

    def test_l3_requires_division_code(self, user_token):
        org_id = self._ensure_org(user_token)
        # L3 without division_code → 400
        r = requests.post(f"{API}/six-legs/goals", headers=_h(user_token), json={
            "user_org_id": org_id, "level": "L3", "title": "TEST_L3 no div",
        }, timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_tree_and_cascade_delete_and_convert(self, user_token):
        org_id = self._ensure_org(user_token)
        # L1 root
        r = requests.post(f"{API}/six-legs/goals", headers=_h(user_token), json={
            "user_org_id": org_id, "level": "L1", "title": "TEST_L1 Revenue Target",
            "metric_label": "Revenue", "metric_target": "10M", "metric_unit": "INR",
        }, timeout=30)
        assert r.status_code == 200, r.text
        g1 = r.json()["goal"]
        # L2 child
        r = requests.post(f"{API}/six-legs/goals", headers=_h(user_token), json={
            "user_org_id": org_id, "level": "L2", "title": "TEST_L2 Customer", "parent_goal_id": g1["id"],
        }, timeout=30)
        assert r.status_code == 200, r.text
        g2 = r.json()["goal"]
        # L3 grandchild WITH division_code
        r = requests.post(f"{API}/six-legs/goals", headers=_h(user_token), json={
            "user_org_id": org_id, "level": "L3", "title": "TEST_L3 SD",
            "parent_goal_id": g2["id"], "division_code": "solution_delivery",
        }, timeout=30)
        assert r.status_code == 200, r.text
        g3 = r.json()["goal"]

        # tree
        r = requests.get(f"{API}/six-legs/goals/tree/{org_id}", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        tree_data = r.json()
        # find g1 in roots
        root = next((n for n in tree_data["tree"] if n["id"] == g1["id"]), None)
        assert root is not None, "g1 should be in tree roots"
        assert len(root["children"]) >= 1, "g1 should have at least one child"
        child = next((c for c in root["children"] if c["id"] == g2["id"]), None)
        assert child is not None and len(child["children"]) >= 1

        # convert to action
        r = requests.post(f"{API}/six-legs/goals/{g3['id']}/convert-to-action", headers=_h(user_token),
                          json={"recurrence_type": "one_time", "priority": "high"}, timeout=30)
        assert r.status_code == 200, r.text
        ai = r.json()["action_item"]
        assert ai["source_module"] == "GOAL_SETTER"
        assert ai["source_id"] == g3["id"]

        # delete g1 cascades
        r = requests.delete(f"{API}/six-legs/goals/{g1['id']}", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        # verify g2/g3 also gone
        r = requests.get(f"{API}/six-legs/goals?user_org_id={org_id}", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        ids = {g["id"] for g in r.json()["goals"]}
        assert g1["id"] not in ids and g2["id"] not in ids and g3["id"] not in ids, "cascade failed"


# ─── REFERRAL ────────────────────────────────────────────────────
class TestReferral:
    def test_config_defaults(self, user_token):
        r = requests.get(f"{API}/referral/config", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        cfg = r.json()
        assert cfg["l1_pct_first"] == 20.0
        assert cfg["l2_pct_first"] == 10.0
        assert cfg["l3_pct_first"] == 5.0
        assert cfg["subsequent_multiplier"] == 0.5
        assert cfg["alos_days"] == 365
        assert cfg["karma_inr_value"] == 10.0
        assert cfg["karma_points_per_unit"] == 100
        assert cfg["coupon_default_pct"] == 20.0
        assert cfg["coupon_validity_days"] == 90
        assert cfg["split_cash"] == 40.0
        assert cfg["split_coupon"] == 30.0
        assert cfg["split_karma"] == 20.0
        assert cfg["split_special"] == 10.0
        assert cfg["cash_refund_window_days"] == 7

    def test_put_config_non_admin_403(self, user_token):
        r = requests.put(f"{API}/referral/config", headers=_h(user_token), json={"l1_pct_first": 25.0}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_simulate_l1_first_purchase(self, user_token):
        r = requests.post(f"{API}/referral/simulate", headers=_h(user_token), json={
            "purchase_amount_inr": 5000, "level": 1, "is_first_purchase": True,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # 20% of 5000 = 1000
        assert d["total_reward_inr"] == 1000.0, d
        assert d["applied_pct"] == 20.0
        # Split 40/30/20/10 of 1000
        br = d["breakdown"]
        assert br["cash_inr"] == 400.0, br
        assert br["coupon_value_inr"] == 300.0, br
        assert br["karma_value_inr"] == 200.0, br
        # 200 INR @ 100KP=10INR → 2000 KP
        assert br["karma_points"] == 2000, br
        assert br["special_access_value_inr"] == 100.0, br

    def test_simulate_highest_tier_zeros_special_and_2x_karma(self, user_token):
        r = requests.post(f"{API}/referral/simulate", headers=_h(user_token), json={
            "purchase_amount_inr": 5000, "level": 1, "is_first_purchase": True,
            "user_on_highest_tier": True,
        }, timeout=30)
        assert r.status_code == 200, r.text
        br = r.json()["breakdown"]
        assert br["special_access_value_inr"] == 0.0
        # Original karma 200 INR + 2× of special (100 INR × 2 = 200) = 400 INR
        # In points: 200 → 2000 KP; extra 200 INR × 2 = 400 INR → 4000 KP; total karma 6000 KP
        assert br["special_access_resolution"]["strategy"] == "fallback_2x_karma"
        assert br["karma_points"] >= 4000  # at least 2× karma added on top
        assert br["special_access_resolution"]["added_karma_points"] == 2000  # 200INR × 100KP/10INR

    def test_simulate_subsequent_halves_rate(self, user_token):
        r = requests.post(f"{API}/referral/simulate", headers=_h(user_token), json={
            "purchase_amount_inr": 5000, "level": 1, "is_first_purchase": False,
            "referrer_since_days": 30,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # 20% × 0.5 = 10% of 5000 = 500
        assert d["applied_pct"] == 10.0, d
        assert d["total_reward_inr"] == 500.0, d

    def test_profile_cash_opt_in_requires_upi_or_bank(self, user_token):
        # opt_in_cash=True but no UPI nor bank trio → 400
        r = requests.put(f"{API}/referral/me/profile", headers=_h(user_token), json={
            "opt_in_cash": True, "upi_id": "", "bank_acct_number": "", "ifsc_code": "", "bank_acct_name": "",
        }, timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_profile_cash_opt_in_with_upi_only(self, user_token):
        r = requests.put(f"{API}/referral/me/profile", headers=_h(user_token), json={
            "opt_in_cash": True, "upi_id": "tester@upi",
        }, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_ledger_returns_keys(self, user_token):
        r = requests.get(f"{API}/referral/me/ledger", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("karma_balance", "coupons", "special_access_entitlements", "cash_ledger", "credits"):
            assert k in d, f"missing key {k} in ledger"
