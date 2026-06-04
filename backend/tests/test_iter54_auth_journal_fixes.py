"""Iter54 — Backend tests for 5 fixes:
- /api/auth/login returns whatsapp_verified + whatsapp_number
- /api/journal/linkable-items returns the new 7-key shape (no solution_matrix)
- linkable-items returns 200 even when collections are empty
- linkable-items.decision is populated after creating a decision
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"
SUPER_EMAIL = "super@test.com"

EXPECTED_LINKABLE_KEYS = {
    "decision", "pros_cons", "swot", "solution_finder", "gem", "ctt", "lifestyle",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, password):
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    return r


# ============ Login response shape ============

def test_login_returns_whatsapp_fields_admin(session):
    r = _login(session, ADMIN_EMAIL, ADMIN_PASS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "whatsapp_verified" in data, f"missing whatsapp_verified key: {data}"
    assert "whatsapp_number" in data, f"missing whatsapp_number key: {data}"
    assert isinstance(data["whatsapp_verified"], bool)
    assert "session_token" in data


def test_login_returns_whatsapp_fields_regular_user(session):
    r = _login(session, USER_EMAIL, USER_PASS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "whatsapp_verified" in data
    assert "whatsapp_number" in data
    assert isinstance(data["whatsapp_verified"], bool)


# ============ linkable-items endpoint ============

def _auth_headers(s, email, password):
    r = _login(s, email, password)
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_linkable_items_keys_exact(session):
    headers = _auth_headers(requests.Session(), USER_EMAIL, USER_PASS)
    r = requests.get(f"{BASE_URL}/api/journal/linkable-items", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    keys = set(data.keys())
    assert keys == EXPECTED_LINKABLE_KEYS, (
        f"Expected exactly {EXPECTED_LINKABLE_KEYS}, got {keys}. "
        f"solution_matrix present? {'solution_matrix' in keys}"
    )
    assert "solution_matrix" not in keys
    # each value must be a list
    for k, v in data.items():
        assert isinstance(v, list), f"{k} is not a list"


def test_linkable_items_200_with_admin(session):
    """Even if admin has no items in many collections, must be 200 (not 500)."""
    headers = _auth_headers(requests.Session(), ADMIN_EMAIL, ADMIN_PASS)
    r = requests.get(f"{BASE_URL}/api/journal/linkable-items", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == EXPECTED_LINKABLE_KEYS


def test_linkable_items_decision_populated_after_create(session):
    s = requests.Session()
    headers = _auth_headers(s, USER_EMAIL, USER_PASS)
    title = f"TEST_iter54_{int(time.time())}"
    create = requests.post(
        f"{BASE_URL}/api/decisions",
        headers=headers,
        json={"title": title, "context": "iter54 testing", "folder": "Personal"},
    )
    assert create.status_code == 200, create.text
    decision_id = create.json()["id"]
    try:
        r = requests.get(f"{BASE_URL}/api/journal/linkable-items", headers=headers)
        assert r.status_code == 200, r.text
        decs = r.json()["decision"]
        assert any(d["id"] == decision_id for d in decs), (
            f"newly created decision {decision_id} not in linkable-items.decision list"
        )
        # title is populated
        found = next(d for d in decs if d["id"] == decision_id)
        assert found["title"] == title
    finally:
        # cleanup
        requests.delete(f"{BASE_URL}/api/decisions/{decision_id}", headers=headers)


# ============ Public route smoke (no auth) ============

def test_health_public():
    r = requests.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200


def test_linkable_items_requires_auth():
    r = requests.get(f"{BASE_URL}/api/journal/linkable-items")
    assert r.status_code in (401, 403)
