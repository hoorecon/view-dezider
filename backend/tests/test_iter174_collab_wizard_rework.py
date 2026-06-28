"""Iter174 — Backend coverage for the New Collaboration wizard rework.

Validates POST /api/shared-steps/create for all three modules (decision,
pros_cons, solution_finder) accepts the new fields
(session_mode / auth_config / notify) and persists them.

Also verifies GET /api/shared-steps/{id}/review and GET /api/shared-steps/{id}
both succeed (no 500s) and the share doc carries the new fields.
"""
import os
import uuid
import pytest
import requests

def _resolve_base_url():
    u = os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    if u:
        return u.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for ln in f:
                if ln.strip().startswith("EXPO_PUBLIC_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip().strip('"').rstrip("/")
    except Exception:
        pass
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL is not set")


BASE_URL = _resolve_base_url()
API = f"{BASE_URL}/api"

OWNER = {"email": "super@test.com", "password": "SuperPass2026!"}
CONTRIB_EMAIL = "admin@test.com"

CREATED = {"decisions": [], "pros_cons": [], "solution_finders": [], "shared_steps": []}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def owner_headers():
    tok = _login(OWNER["email"], OWNER["password"])
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def decision_id(owner_headers):
    payload = {"title": f"TEST_iter174 Decision {uuid.uuid4().hex[:6]}",
               "context": "wizard rework test"}
    r = requests.post(f"{API}/decisions", json=payload, headers=owner_headers, timeout=30)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text[:200]}"
    did = r.json().get("id") or r.json().get("decision_id")
    CREATED["decisions"].append(did)
    return did


@pytest.fixture(scope="module")
def pros_cons_id(owner_headers):
    payload = {"title": f"TEST_iter174 P&C {uuid.uuid4().hex[:6]}",
               "topic": "Adopt new framework", "pros": [], "cons": []}
    r = requests.post(f"{API}/pros-cons", json=payload, headers=owner_headers, timeout=30)
    assert r.status_code in (200, 201), f"create P&C: {r.status_code} {r.text[:200]}"
    pid = r.json().get("id")
    CREATED["pros_cons"].append(pid)
    return pid


@pytest.fixture(scope="module")
def solution_finder_id(owner_headers):
    payload = {"title": f"TEST_iter174 SF {uuid.uuid4().hex[:6]}",
               "smart_goal": "Improve onboarding NPS to 70",
               "problem_statement": "Onboarding drop-off"}
    r = requests.post(f"{API}/solution-finders", json=payload, headers=owner_headers, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Solution finder create unavailable: {r.status_code} {r.text[:120]}")
    sid = r.json().get("entry_id") or r.json().get("id")
    CREATED["solution_finders"].append(sid)
    return sid


# ---------- Shared payload helpers ----------
def _create_share_payload(module, mid, step, session_mode="async", auth=None):
    return {
        "module": module,
        "module_id": mid,
        "step_number": step,
        "recipient_emails": [CONTRIB_EMAIL],
        "merge_mode": "equal",
        "session_mode": session_mode,
        "auth_config": auth or {"enabled_methods": ["email_otp"], "methods_required": 1, "verify_each_time": False},
        "notify": {"participants": True, "mode": True},
        "message": "wizard test invite",
    }


# ---------- Tests ----------
class TestWizardSharedStepCreate:
    def test_create_decision_share_async(self, owner_headers, decision_id):
        body = _create_share_payload("decision", decision_id, 7, session_mode="async")
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, f"decision share create: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "id" in data and data["id"]
        assert data.get("shared_count", 0) >= 1, f"shared_count expected >=1, got {data}"
        assert "link" in data
        CREATED["shared_steps"].append(data["id"])
        # GET share doc -> must carry session_mode + auth_config
        g = requests.get(f"{API}/shared-steps/{data['id']}", headers=owner_headers, timeout=30)
        assert g.status_code == 200, f"GET share: {g.status_code} {g.text[:200]}"
        share = g.json()
        assert share.get("session_mode") == "async"
        ac = share.get("auth_config") or {}
        assert "email_otp" in (ac.get("enabled_methods") or [])
        # /review must not 500
        rv = requests.get(f"{API}/shared-steps/{data['id']}/review", headers=owner_headers, timeout=30)
        assert rv.status_code == 200, f"/review: {rv.status_code} {rv.text[:200]}"
        rj = rv.json()
        assert rj.get("module") == "decision"
        assert rj.get("step_number") == 7

    def test_create_pros_cons_share_async(self, owner_headers, pros_cons_id):
        body = _create_share_payload("pros_cons", pros_cons_id, 3, session_mode="async")
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, f"P&C share create: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("shared_count", 0) >= 1
        assert "link" in data
        CREATED["shared_steps"].append(data["id"])
        g = requests.get(f"{API}/shared-steps/{data['id']}", headers=owner_headers, timeout=30)
        assert g.status_code == 200
        share = g.json()
        assert share.get("module") == "pros_cons"
        assert share.get("session_mode") == "async"
        assert share.get("auth_config", {}).get("enabled_methods") == ["email_otp"]
        rv = requests.get(f"{API}/shared-steps/{data['id']}/review", headers=owner_headers, timeout=30)
        assert rv.status_code == 200

    def test_create_solution_finder_share_async(self, owner_headers, solution_finder_id):
        body = _create_share_payload("solution_finder", solution_finder_id, 2, session_mode="async")
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, f"SF share create: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("shared_count", 0) >= 1
        assert "link" in data
        CREATED["shared_steps"].append(data["id"])
        g = requests.get(f"{API}/shared-steps/{data['id']}", headers=owner_headers, timeout=30)
        assert g.status_code == 200
        share = g.json()
        assert share.get("module") == "solution_finder"
        assert share.get("session_mode") == "async"
        rv = requests.get(f"{API}/shared-steps/{data['id']}/review", headers=owner_headers, timeout=30)
        assert rv.status_code == 200

    def test_create_live_sync_carries_session_mode(self, owner_headers, decision_id):
        body = _create_share_payload("decision", decision_id, 5, session_mode="live_sync",
                                     auth={"enabled_methods": [], "methods_required": 0, "verify_each_time": False})
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 200, f"live_sync create: {r.status_code} {r.text[:200]}"
        sid = r.json()["id"]
        CREATED["shared_steps"].append(sid)
        g = requests.get(f"{API}/shared-steps/{sid}", headers=owner_headers, timeout=30)
        assert g.status_code == 200
        assert g.json().get("session_mode") == "live_sync"

    def test_create_rejects_missing_recipients(self, owner_headers, decision_id):
        body = _create_share_payload("decision", decision_id, 1)
        body["recipient_emails"] = []
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 400, f"expected 400 when no recipients, got {r.status_code}"

    def test_create_rejects_missing_module_id(self, owner_headers):
        body = _create_share_payload("decision", None, 1)
        body.pop("module_id")
        r = requests.post(f"{API}/shared-steps/create", json=body, headers=owner_headers, timeout=30)
        assert r.status_code == 400


# ---------- Cleanup ----------
def teardown_module(_m):
    try:
        tok = _login(OWNER["email"], OWNER["password"])
        h = {"Authorization": f"Bearer {tok}"}
        for did in CREATED["decisions"]:
            requests.delete(f"{API}/decisions/{did}", headers=h, timeout=15)
        for pid in CREATED["pros_cons"]:
            requests.delete(f"{API}/pros-cons/{pid}", headers=h, timeout=15)
        for sid in CREATED["solution_finders"]:
            requests.delete(f"{API}/solution-finders/{sid}", headers=h, timeout=15)
    except Exception:
        pass
