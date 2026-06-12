"""
Iteration 106 — Org-Type Master + URL-Import Progress endpoint + FAMILY decision.

Covers:
  - GET /api/org-types: 7 active types incl. FAMILY, sort_order ordering, description present
  - Admin CRUD /api/admin/org-types: POST (create custom), PUT (update), DELETE (custom hard-delete)
  - Admin DELETE on a SYSTEM type soft-disables (not delete); re-enable via PUT active:true
  - POST /api/hos/decisions with acting_as_context=FAMILY -> 200
  - POST /api/hos/decisions with bogus acting_as_context -> 400 listing valid keys
  - GET /api/url-analyze/progress/{id} -> default {pct,label,status} when no doc
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE, "EXPO_PUBLIC_BACKEND_URL env not set"
BASE = BASE.rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no token in {r.json()}"
    return tok


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- GET /org-types ----------
class TestOrgTypesList:
    def test_list_public(self, H):
        r = requests.get(f"{BASE}/api/org-types", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        keys = [d["key"] for d in rows]
        for required in ["INDIVIDUAL", "FAMILY", "BUSINESS_ORG", "ACADEMIC_ORG",
                         "NONPROFIT_ORG", "ASSOCIATION", "GOVERNMENT"]:
            assert required in keys, f"missing {required} in {keys}"
        # FAMILY description + sort_order
        fam = next(d for d in rows if d["key"] == "FAMILY")
        assert "Family" in (fam.get("description") or "") or "household" in (fam.get("description") or "").lower()
        assert fam.get("sort_order") == 2
        # sorted by sort_order ascending
        sort_orders = [d.get("sort_order", 0) for d in rows]
        assert sort_orders == sorted(sort_orders), f"not sorted: {sort_orders}"


# ---------- Admin CRUD ----------
class TestAdminOrgTypesCRUD:
    CUSTOM_KEY = f"TESTFAM_{int(time.time())}"

    def test_create_custom(self, H):
        payload = {"key": self.CUSTOM_KEY, "label": "TEST Family Friend",
                   "icon": "leaf", "color": "#10B981",
                   "description": "auto test custom org type",
                   "is_org": False, "sort_order": 99}
        r = requests.post(f"{BASE}/api/admin/org-types", headers=H, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["key"] == self.CUSTOM_KEY
        assert doc["label"] == "TEST Family Friend"
        assert doc.get("is_system") is False

    def test_list_admin_includes_custom(self, H):
        r = requests.get(f"{BASE}/api/admin/org-types", headers=H, timeout=15)
        assert r.status_code == 200
        keys = [d["key"] for d in r.json()]
        assert self.CUSTOM_KEY in keys

    def test_update_custom(self, H):
        r = requests.put(f"{BASE}/api/admin/org-types/{self.CUSTOM_KEY}", headers=H,
                         json={"label": "TEST Family Renamed", "color": "#F43F5E",
                               "active": True, "description": "updated desc"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["label"] == "TEST Family Renamed"
        assert r.json()["color"] == "#F43F5E"

    def test_delete_custom_hard(self, H):
        r = requests.delete(f"{BASE}/api/admin/org-types/{self.CUSTOM_KEY}",
                            headers=H, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "deleted"
        # Confirm gone
        r2 = requests.get(f"{BASE}/api/admin/org-types", headers=H, timeout=15)
        assert self.CUSTOM_KEY not in [d["key"] for d in r2.json()]

    def test_delete_system_soft_disables(self, H):
        # Use FAMILY (system) — DELETE should disable; then PUT active=true to restore.
        target = "FAMILY"
        r = requests.delete(f"{BASE}/api/admin/org-types/{target}", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "disabled", r.text
        # Verify it's inactive in admin list
        r2 = requests.get(f"{BASE}/api/admin/org-types", headers=H, timeout=15)
        fam = next(d for d in r2.json() if d["key"] == target)
        assert fam.get("active") is False
        # Verify it's hidden from public list
        r3 = requests.get(f"{BASE}/api/org-types", headers=H, timeout=15)
        assert target not in [d["key"] for d in r3.json()]
        # Restore via PUT
        r4 = requests.put(f"{BASE}/api/admin/org-types/{target}",
                          headers=H, json={"active": True}, timeout=15)
        assert r4.status_code == 200
        assert r4.json().get("active") is True
        # Verify back in public list
        r5 = requests.get(f"{BASE}/api/org-types", headers=H, timeout=15)
        assert target in [d["key"] for d in r5.json()]


# ---------- Decision creation with FAMILY ----------
class TestDecisionFamilyContext:
    def test_create_decision_family(self, H):
        payload = {
            "title": "TEST family decision iter106",
            "acting_as_context": "FAMILY",
            "life_area_id": "la_personal",
            "ask_type_id": "at_choice",
        }
        r = requests.post(f"{BASE}/api/hos/decisions", headers=H, json=payload, timeout=20)
        assert r.status_code in (200, 201), f"FAMILY decision create failed: {r.status_code} {r.text}"
        body = r.json()
        # Try a few common id keys
        decision_id = body.get("decision_id") or body.get("id") or body.get("_id")
        assert decision_id, f"no decision id in {body}"

    def test_create_decision_bogus_org_type_rejected(self, H):
        payload = {
            "title": "TEST bogus org decision",
            "acting_as_context": "TOTALLY_BOGUS_KEY_XYZ",
            "life_area_id": "la_personal",
            "ask_type_id": "at_choice",
        }
        r = requests.post(f"{BASE}/api/hos/decisions", headers=H, json=payload, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        detail = (r.json().get("detail") or "").upper() if isinstance(r.json().get("detail"), str) else str(r.json())
        # Detail should list valid keys
        assert "FAMILY" in detail or "INDIVIDUAL" in detail, f"detail does not list valid keys: {detail}"


# ---------- URL-Import progress endpoint ----------
class TestUrlImportProgress:
    def test_progress_default_response(self, H):
        random_id = f"noexist_{uuid.uuid4().hex}"
        r = requests.get(f"{BASE}/api/url-analyze/progress/{random_id}",
                         headers=H, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "pct" in body and "label" in body and "status" in body
        # Default for missing doc
        assert body["label"] in ("Starting…", "Starting...", "Starting&hellip;") or "Starting" in body["label"]
        assert body["status"] == "running"
        assert isinstance(body["pct"], (int, float))
