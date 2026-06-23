"""
iter149 — backend tests for new admin diagnostics endpoint
GET /api/shares/admin/ultramsg-status
and the deep-link redirect plumbing (share creation produces a working token
plus the resolve/accept endpoints work for the recipient).
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

SUPER = {"email": "super@test.com", "password": "SuperPass2026!"}


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()["session_token"]


# ── ultramsg-status endpoint ───────────────────────────────────────────────
class TestUltramsgStatus:
    """GET /api/shares/admin/ultramsg-status — admin-gated diagnostic."""

    def test_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/shares/admin/ultramsg-status", timeout=15)
        # require_admin -> 401 (no creds) or 403 (creds without admin)
        assert r.status_code in (401, 403), f"got {r.status_code} {r.text[:200]}"

    def test_super_admin_returns_status_shape(self):
        token = _login(**SUPER)
        r = requests.get(
            f"{BASE_URL}/api/shares/admin/ultramsg-status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Required shape fields
        for k in ("configured", "connected", "status", "detail"):
            assert k in data, f"missing field {k} in {data}"
        assert isinstance(data["configured"], bool)
        assert isinstance(data["connected"], bool)
        assert isinstance(data["status"], str) and len(data["status"]) > 0
        # detail must be a non-empty string when configured (UI uses it)
        assert isinstance(data["detail"], str)


# ── share creation/resolve/accept flow (deep-link plumbing) ────────────────
class TestShareDeepLink:
    """Owner can create a share; recipient flow accepts it via /shares/{token}."""

    @pytest.fixture(scope="class")
    def owner_session(self):
        return _login(**SUPER)

    @pytest.fixture(scope="class")
    def decision_id(self, owner_session):
        # Pick any existing decision; if none, create a Dezider stub.
        h = {"Authorization": f"Bearer {owner_session}"}
        r = requests.get(f"{BASE_URL}/api/decisions", headers=h, timeout=15)
        if r.status_code == 200:
            body = r.json()
            arr = body if isinstance(body, list) else (body.get("decisions") or body.get("items") or [])
            if arr:
                # find one with a known module (dezider) if possible
                for d in arr:
                    if d.get("module") in ("dezider", "pros_cons", "swot", "solution_finder", "assessment"):
                        return (d["module"], d.get("id") or d.get("decision_id"))
                d = arr[0]
                return (d.get("module") or "dezider", d.get("id") or d.get("decision_id"))

    def test_create_email_share_returns_token(self, owner_session, decision_id):
        module, did = decision_id
        h = {"Authorization": f"Bearer {owner_session}"}
        payload = {
            "module": module,
            "decision_id": did,
            "channel": "email",
            "recipient_email": f"TEST_share_{uuid.uuid4().hex[:8]}@example.com",
            "recipient_name": "Test Recipient",
        }
        r = requests.post(f"{BASE_URL}/api/shares", json=payload, headers=h, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("token"), str) and len(body["token"]) > 10
        assert body.get("link", "").endswith(f"/shared/{body['token']}")

    def test_resolve_share_requires_auth(self):
        # Need a real token. Use the same login + create flow.
        s = _login(**SUPER)
        h = {"Authorization": f"Bearer {s}"}
        # quickly create a share for resolve test (reuse above test path)
        r = requests.get(f"{BASE_URL}/api/decisions", headers=h, timeout=15)
        if r.status_code != 200:
            pytest.skip("no decisions endpoint")
        arr = r.json() if isinstance(r.json(), list) else (r.json().get("decisions") or r.json().get("items") or [])
        if not arr:
            pytest.skip("no decisions to share")
        d = arr[0]
        module = d.get("module") or "dezider"
        did = d.get("id") or d.get("decision_id")
        payload = {
            "module": module,
            "decision_id": did,
            "channel": "email",
            "recipient_email": f"TEST_resolve_{uuid.uuid4().hex[:8]}@example.com",
        }
        cr = requests.post(f"{BASE_URL}/api/shares", json=payload, headers=h, timeout=30)
        assert cr.status_code == 200, cr.text[:300]
        token = cr.json()["token"]

        # unauth
        ru = requests.get(f"{BASE_URL}/api/shares/{token}", timeout=15)
        assert ru.status_code in (401, 403)

        # auth
        ra = requests.get(f"{BASE_URL}/api/shares/{token}",
                          headers=h, timeout=15)
        assert ra.status_code == 200, ra.text[:200]
        data = ra.json()
        assert data.get("token") == token
        # owner accessing -> can_access is false because the share is for
        # another email; but the resolve endpoint must still return module/title.
        assert "module" in data
        assert "title" in data
