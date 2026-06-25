"""Iter 129 — Deferred wires + Backend hardening regression suite.

Covers:
  - Contacts professional_roles[] multi-org persistence (POST + PUT, primary autoflag)
  - Solution Finder values_applied / values_violated arrays persistence
  - /referral/config gate (super_admin only — admin gets 403)
  - /seven-seven/assess master validation (unknown division/driver/scale → 400)
  - /six-legs/goals/{id}/convert-to-action datetime serialization
  - /referral/credit HMAC vs super_admin authorization
  - action_items SOURCE_MODULES accepts SOLUTION_FINDER, INSTANT_DEZIDER
"""
from __future__ import annotations

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"


# ───────── Auth helpers ─────────

def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _register_throwaway() -> tuple[str, str]:
    email = f"iter129_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "AutoPass2026!", "name": "Iter129 Tester"},
                      timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    return email, r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def super_token() -> str:
    return _login(SUPER_EMAIL, SUPER_PASS)


@pytest.fixture(scope="module")
def user_token() -> str:
    _, tok = _register_throwaway()
    return tok


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ═══════════════ Contacts: professional_roles[] multi-org ═══════════════

class TestContactsProfessionalRoles:
    def test_create_with_explicit_primary(self, user_token):
        body = {
            "name": "TEST_iter129_multi_org",
            "professional_roles": [
                {"organization": "JELCOS", "designation": "CEO", "is_primary": True},
                {"organization": "ACME", "designation": "Advisor", "is_primary": False},
            ],
        }
        r = requests.post(f"{API}/contacts", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        roles = doc.get("professional_roles") or []
        assert len(roles) == 2, f"expected 2 roles, got {roles}"
        # role_id stamped
        for role in roles:
            assert role.get("role_id"), f"role_id missing on {role}"
            assert role["role_id"].startswith("role_")
        # primary flag preserved
        jelcos = next(r for r in roles if r["organization"] == "JELCOS")
        assert jelcos["is_primary"] is True
        # cleanup
        requests.delete(f"{API}/contacts/{doc['id']}", headers=_h(user_token))

    def test_create_no_primary_auto_first(self, user_token):
        body = {
            "name": "TEST_iter129_auto_primary",
            "professional_roles": [
                {"organization": "FirstCo", "designation": "Mgr"},
                {"organization": "SecondCo", "designation": "Dir"},
            ],
        }
        r = requests.post(f"{API}/contacts", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        roles = doc.get("professional_roles") or []
        assert len(roles) == 2
        primaries = [x for x in roles if x["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["organization"] == "FirstCo", "first role should be auto-primary"
        requests.delete(f"{API}/contacts/{doc['id']}", headers=_h(user_token))

    def test_put_updates_professional_roles_array(self, user_token):
        # create
        r = requests.post(f"{API}/contacts",
                          json={"name": "TEST_iter129_put", "professional_roles": [
                              {"organization": "Old", "designation": "X", "is_primary": True}
                          ]},
                          headers=_h(user_token), timeout=20)
        assert r.status_code == 200
        cid = r.json()["id"]
        # update — replace array
        upd = {"professional_roles": [
            {"organization": "NewA", "designation": "A", "is_primary": True},
            {"organization": "NewB", "designation": "B", "is_primary": True},  # 2 primaries → only first kept
        ]}
        r2 = requests.put(f"{API}/contacts/{cid}", json=upd, headers=_h(user_token), timeout=20)
        assert r2.status_code == 200, r2.text
        roles = r2.json().get("professional_roles") or []
        orgs = [x["organization"] for x in roles]
        assert orgs == ["NewA", "NewB"], orgs
        primaries = [x for x in roles if x["is_primary"]]
        assert len(primaries) == 1 and primaries[0]["organization"] == "NewA", \
            "single-primary enforcement broken"
        requests.delete(f"{API}/contacts/{cid}", headers=_h(user_token))


# ═══════════════ Solution Finder values_applied / values_violated ═══════════════

class TestSolutionFinderValues:
    def test_create_persists_values_arrays(self, user_token):
        body = {
            "smart_goal": "TEST_iter129_sf_values",
            "values_applied": [{"principle_id": "x", "principle_name": "Integrity"}],
            "values_violated": [{"principle_id": "z", "principle_name": "Speed",
                                  "reason": "because"}],
            "linked_role_ids": ["role_aaa"],
        }
        r = requests.post(f"{API}/solution-finders", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        doc = r.json()
        eid = doc["entry_id"]
        # GET to verify persistence
        g = requests.get(f"{API}/solution-finders/{eid}", headers=_h(user_token), timeout=20)
        assert g.status_code == 200
        d = g.json()
        assert d.get("values_applied") == [{"principle_id": "x", "principle_name": "Integrity"}]
        violated = d.get("values_violated") or []
        assert len(violated) == 1
        assert violated[0]["principle_name"] == "Speed"
        assert violated[0]["reason"] == "because"
        assert d.get("linked_role_ids") == ["role_aaa"]


# ═══════════════ /referral/config — super_admin gate ═══════════════

class TestReferralConfigGate:
    def test_admin_role_now_blocked(self, admin_token):
        r = requests.put(f"{API}/referral/config", json={"alos_days": 365},
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 403, f"admin should be blocked, got {r.status_code} {r.text}"

    def test_super_admin_allowed(self, super_token):
        r = requests.put(f"{API}/referral/config", json={"alos_days": 365},
                         headers=_h(super_token), timeout=20)
        assert r.status_code == 200, f"super_admin should pass, got {r.status_code} {r.text}"
        assert r.json().get("ok") is True


# ═══════════════ /seven-seven/assess master validation ═══════════════

class TestSevenSevenAssess:
    @pytest.fixture(scope="class")
    def user_org_id(self, user_token):
        r = requests.post(f"{API}/seven-seven/orgs",
                          json={"name": "TEST_iter129_org", "life_area": "business",
                                "org_type": "BUSINESS"},
                          headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        return r.json()["user_org"]["id"]

    def test_unknown_division_code_400(self, user_token, user_org_id):
        body = {"user_org_id": user_org_id, "division_code": "nope",
                "driver_code": "PEOPLE", "scale_code": "up_to_mark"}
        r = requests.post(f"{API}/seven-seven/assess", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        assert "division" in r.text.lower()

    def test_unknown_driver_code_400(self, user_token, user_org_id):
        # fetch a real division
        d = requests.get(f"{API}/seven-seven/divisions", headers=_h(user_token), timeout=20).json()
        div_code = d["divisions"][0]["code"]
        body = {"user_org_id": user_org_id, "division_code": div_code,
                "driver_code": "GARBAGE", "scale_code": "up_to_mark"}
        r = requests.post(f"{API}/seven-seven/assess", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        assert "driver" in r.text.lower()

    def test_unknown_scale_code_400(self, user_token, user_org_id):
        d = requests.get(f"{API}/seven-seven/divisions", headers=_h(user_token), timeout=20).json()
        dr = requests.get(f"{API}/seven-seven/drivers", headers=_h(user_token), timeout=20).json()
        body = {"user_org_id": user_org_id, "division_code": d["divisions"][0]["code"],
                "driver_code": dr["drivers"][0]["code"], "scale_code": "no_such_scale"}
        r = requests.post(f"{API}/seven-seven/assess", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        assert "scale" in r.text.lower()

    def test_valid_masters_200(self, user_token, user_org_id):
        d = requests.get(f"{API}/seven-seven/divisions", headers=_h(user_token), timeout=20).json()
        dr = requests.get(f"{API}/seven-seven/drivers", headers=_h(user_token), timeout=20).json()
        sc = requests.get(f"{API}/seven-seven/scale", headers=_h(user_token), timeout=20).json()
        body = {"user_org_id": user_org_id, "division_code": d["divisions"][0]["code"],
                "driver_code": dr["drivers"][0]["code"], "scale_code": sc["scale"][0]["code"]}
        r = requests.post(f"{API}/seven-seven/assess", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, f"expected 200, got {r.status_code} {r.text}"
        a = r.json().get("assessment")
        assert a and a.get("id")


# ═══════════════ /six-legs convert-to-action datetime serialization ═══════════════

class TestSixLegsConvertDatetime:
    def test_convert_returns_iso_strings(self, user_token):
        # need an org
        r0 = requests.post(f"{API}/seven-seven/orgs",
                           json={"name": "TEST_iter129_sl_org", "life_area": "career",
                                 "org_type": "BUSINESS"},
                           headers=_h(user_token), timeout=20)
        assert r0.status_code == 200, r0.text
        org_id = r0.json()["user_org"]["id"]
        # create a goal
        r1 = requests.post(f"{API}/six-legs/goals",
                           json={"user_org_id": org_id, "level": "L1",
                                 "title": "TEST_iter129 leg goal", "owner_name": "Tester",
                                 "target_date": "2026-12-31"},
                           headers=_h(user_token), timeout=20)
        assert r1.status_code == 200, r1.text
        gid = r1.json()["goal"]["id"]
        # convert
        r2 = requests.post(f"{API}/six-legs/goals/{gid}/convert-to-action",
                           json={"recurrence_type": "one_time", "priority": "high"},
                           headers=_h(user_token), timeout=20)
        assert r2.status_code == 200, f"convert failed: {r2.status_code} {r2.text}"
        ai = r2.json().get("action_item")
        assert ai, "no action_item in response"
        # critical: created_at/updated_at must be JSON-serialised ISO strings,
        # not a raw datetime repr or null
        for k in ("created_at", "updated_at"):
            v = ai.get(k)
            assert isinstance(v, str) and "T" in v, \
                f"{k} should be ISO string, got {type(v).__name__}={v!r}"


# ═══════════════ /referral/credit HMAC vs admin gate ═══════════════

class TestReferralCreditAuth:
    def _payload(self):
        return {"referrer_user_id": "user_fake", "referee_user_id": "user_fakeree",
                "purchase_amount_inr": 1000.0, "level": 1, "is_first_purchase": True}

    def test_non_admin_no_hmac_403(self, user_token):
        r = requests.post(f"{API}/referral/credit", json=self._payload(),
                          headers=_h(user_token), timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
        assert "hmac" in r.text.lower() or "verification" in r.text.lower()

    def test_super_admin_succeeds(self, super_token):
        r = requests.post(f"{API}/referral/credit", json=self._payload(),
                          headers=_h(super_token), timeout=20)
        assert r.status_code == 200, f"super_admin should succeed, got {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("credit_id")
        assert body.get("breakdown")


# ═══════════════ action_items SOURCE_MODULES expansion ═══════════════

class TestActionItemsNewSources:
    def test_solution_finder_source_accepted(self, user_token):
        body = {"source_module": "SOLUTION_FINDER", "title": "TEST_iter129 SF source",
                "priority": "medium", "recurrence_type": "one_time"}
        r = requests.post(f"{API}/action-items", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source_module"] == "SOLUTION_FINDER"
        assert d["action_id"]

    def test_instant_dezider_source_accepted(self, user_token):
        body = {"source_module": "INSTANT_DEZIDER", "title": "TEST_iter129 ID source",
                "priority": "medium", "recurrence_type": "one_time"}
        r = requests.post(f"{API}/action-items", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["source_module"] == "INSTANT_DEZIDER"

    def test_garbage_source_rejected(self, user_token):
        body = {"source_module": "BOGUS_MODULE", "title": "TEST_iter129 bogus",
                "priority": "medium", "recurrence_type": "one_time"}
        r = requests.post(f"{API}/action-items", json=body, headers=_h(user_token), timeout=20)
        assert r.status_code == 400
