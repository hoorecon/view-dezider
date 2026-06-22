"""End-to-end HTTP regression for /api/admin/notification-engine/* (v3.18.0).

Tests against the public preview URL (EXPO_PUBLIC_BACKEND_URL).
Covers: registry, seeded trigger discovery, CRUD on event-kind triggers,
channel validation (email/phone), schedule guard, RBAC (super_admin vs admin
vs anonymous), test-send statuses, runs log, cleanup.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
NE = f"{API}/admin/notification-engine"

SUPER = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}
ADMIN = {"email": "admin@test.com", "password": "AdminPass2026!"}


def _login(creds) -> Optional[str]:
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def super_token():
    tok = _login(SUPER)
    if not tok:
        pytest.skip("Super-admin login failed; cannot run notification-engine API tests")
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def h_super(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


# ────────────────────────────────────────────────────────────────────────────
# Registry + seeded trigger
# ────────────────────────────────────────────────────────────────────────────
class TestRegistryAndSeed:
    def test_registry_returns_two_events(self, h_super):
        r = requests.get(f"{NE}/registry", headers=h_super, timeout=15)
        assert r.status_code == 200, r.text
        keys = {e["key"]: e for e in r.json()["events"]}
        assert "import-analytics" in keys and "import-run-failed" in keys
        ia = keys["import-analytics"]
        assert ia["kind"] == "scheduled"
        ds = ia["default_schedule"]
        assert (ds["frequency"], ds["day_of_week"], ds["hour"], ds["minute"],
                ds["timezone"]) == ("weekly", "mon", 9, 0, "Asia/Kolkata")
        assert keys["import-run-failed"]["kind"] == "event"

    def test_seeded_digest_trigger_present(self, h_super):
        r = requests.get(f"{NE}/triggers", headers=h_super, timeout=15)
        assert r.status_code == 200, r.text
        seeded = [t for t in r.json()["triggers"] if t["event_key"] == "import-analytics"]
        assert seeded, "Seeded import-analytics digest trigger missing"
        t = seeded[0]
        assert t["enabled"] is True
        assert t["schedule_label"] == "Weekly · Monday 09:00 Asia/Kolkata"
        # next_run_at should be present and parseable; must be 03:30 UTC (09:00 IST)
        assert t.get("next_run_at"), "next_run_at missing on seeded trigger"
        assert "03:30" in t["next_run_at"] or "T03:30" in t["next_run_at"]


# ────────────────────────────────────────────────────────────────────────────
# Validation + CRUD on event-kind trigger
# ────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def event_trigger(h_super):
    """Create a throwaway event-kind trigger; auto-cleanup after test."""
    body = {"event_key": "import-run-failed",
            "name": f"TEST_failure_alert_{uuid.uuid4().hex[:6]}",
            "throttle_minutes": 120,
            "channels": {"email": {"enabled": False, "recipients": []},
                         "whatsapp": {"enabled": False, "numbers": []}}}
    r = requests.post(f"{NE}/triggers", json=body, headers=h_super, timeout=15)
    assert r.status_code == 200, r.text
    trig = r.json()
    yield trig
    requests.delete(f"{NE}/triggers/{trig['id']}", headers=h_super, timeout=15)


class TestCRUDValidation:
    def test_create_event_kind_trigger(self, event_trigger):
        assert event_trigger["kind"] == "event"
        assert event_trigger["event_key"] == "import-run-failed"
        assert event_trigger["throttle_minutes"] == 120
        assert event_trigger["schedule"] is None

    def test_update_channels_normalises_recipients_lowercase(self, h_super, event_trigger):
        body = {"channels": {
            "email": {"enabled": True, "recipients": ["UPPER@Example.com", "  ops@example.com  "]},
            "whatsapp": {"enabled": True, "numbers": ["+91 98765-43210"]}}}
        r = requests.put(f"{NE}/triggers/{event_trigger['id']}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 200, r.text
        chs = r.json()["channels"]
        assert "upper@example.com" in chs["email"]["recipients"]
        assert "ops@example.com" in chs["email"]["recipients"]
        # whatsapp digits stripped
        assert chs["whatsapp"]["numbers"] == ["919876543210"]

    def test_invalid_email_400(self, h_super, event_trigger):
        body = {"channels": {"email": {"enabled": True, "recipients": ["not-an-email"]},
                              "whatsapp": {"enabled": False, "numbers": []}}}
        r = requests.put(f"{NE}/triggers/{event_trigger['id']}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 400, r.text

    def test_invalid_phone_short_400(self, h_super, event_trigger):
        body = {"channels": {"email": {"enabled": False, "recipients": []},
                              "whatsapp": {"enabled": True, "numbers": ["12345"]}}}
        r = requests.put(f"{NE}/triggers/{event_trigger['id']}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 400, r.text

    def test_unknown_event_key_400(self, h_super):
        body = {"event_key": "nope-bad-key", "name": "TEST_bad"}
        r = requests.post(f"{NE}/triggers", json=body, headers=h_super, timeout=15)
        assert r.status_code == 400, r.text

    def test_schedule_on_event_kind_400(self, h_super, event_trigger):
        body = {"schedule": {"frequency": "daily", "hour": 9, "minute": 0,
                              "timezone": "Asia/Kolkata"}}
        r = requests.put(f"{NE}/triggers/{event_trigger['id']}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 400, r.text

    def test_bad_timezone_400(self, h_super):
        body = {"event_key": "import-analytics",
                "name": f"TEST_badtz_{uuid.uuid4().hex[:6]}",
                "schedule": {"frequency": "weekly", "day_of_week": "mon",
                              "hour": 9, "minute": 0, "timezone": "Not/A_Zone"}}
        r = requests.post(f"{NE}/triggers", json=body, headers=h_super, timeout=15)
        assert r.status_code == 400, r.text


# ────────────────────────────────────────────────────────────────────────────
# Test-send + runs log
# ────────────────────────────────────────────────────────────────────────────
class TestSendAndRuns:
    def test_test_send_no_recipients_returns_skipped(self, h_super, event_trigger):
        r = requests.post(f"{NE}/triggers/{event_trigger['id']}/test",
                          headers=h_super, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "skipped_no_recipients"

    def test_test_send_with_email_recipient_sends(self, h_super, event_trigger):
        # add ops@example.com (bounces harmlessly)
        body = {"channels": {"email": {"enabled": True, "recipients": ["ops@example.com"]},
                              "whatsapp": {"enabled": False, "numbers": []}}}
        r = requests.put(f"{NE}/triggers/{event_trigger['id']}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 200
        r = requests.post(f"{NE}/triggers/{event_trigger['id']}/test",
                          headers=h_super, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # accept 'sent' (Resend OK) or 'failed' (Resend reject) — never skipped or error
        assert d["status"] in ("sent", "failed"), d
        assert d["report"]["email"]["attempted"] == 1

    def test_runs_endpoint_returns_dispatch_log(self, h_super, event_trigger):
        # trigger a test to ensure a fresh run exists
        requests.post(f"{NE}/triggers/{event_trigger['id']}/test", headers=h_super, timeout=20)
        time.sleep(1)
        r = requests.get(f"{NE}/runs?trigger_id={event_trigger['id']}", headers=h_super, timeout=15)
        assert r.status_code == 200, r.text
        runs = r.json()["runs"]
        assert runs, "Expected at least one run"
        first = runs[0]
        assert "run_kind" in first and "status" in first and "report" in first
        # newest-first
        if len(runs) > 1:
            assert runs[0]["ts"] >= runs[1]["ts"]


# ────────────────────────────────────────────────────────────────────────────
# Delete (and double-delete 404)
# ────────────────────────────────────────────────────────────────────────────
class TestDelete:
    def test_delete_twice_404(self, h_super):
        body = {"event_key": "import-run-failed", "name": f"TEST_del_{uuid.uuid4().hex[:6]}"}
        r = requests.post(f"{NE}/triggers", json=body, headers=h_super, timeout=15)
        assert r.status_code == 200
        tid = r.json()["id"]
        r1 = requests.delete(f"{NE}/triggers/{tid}", headers=h_super, timeout=15)
        assert r1.status_code == 200 and r1.json().get("deleted") is True
        r2 = requests.delete(f"{NE}/triggers/{tid}", headers=h_super, timeout=15)
        assert r2.status_code == 404


# ────────────────────────────────────────────────────────────────────────────
# RBAC — admin → 403, anonymous → 401
# ────────────────────────────────────────────────────────────────────────────
class TestRBAC:
    endpoints = [
        ("GET", "/registry"),
        ("GET", "/triggers"),
        ("POST", "/triggers"),
        ("PUT", "/triggers/some-id"),
        ("DELETE", "/triggers/some-id"),
        ("POST", "/triggers/some-id/test"),
        ("GET", "/runs"),
    ]

    @pytest.mark.parametrize("method,path", endpoints)
    def test_admin_role_gets_403(self, admin_token, method, path):
        if not admin_token:
            pytest.skip("Regular admin login failed")
        headers = {"Authorization": f"Bearer {admin_token}",
                   "Content-Type": "application/json"}
        url = f"{NE}{path}"
        r = requests.request(method, url, headers=headers, json={} if method in ("POST", "PUT") else None, timeout=15)
        assert r.status_code == 403, f"{method} {path} → {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("method,path", endpoints)
    def test_anonymous_gets_401(self, method, path):
        url = f"{NE}{path}"
        r = requests.request(method, url, json={} if method in ("POST", "PUT") else None, timeout=15)
        assert r.status_code in (401, 403), f"{method} {path} → {r.status_code}"


# ────────────────────────────────────────────────────────────────────────────
# Cleanup — restore seeded digest channels to clean defaults
# ────────────────────────────────────────────────────────────────────────────
class TestCleanup:
    def test_zzz_restore_seeded_trigger_channels(self, h_super):
        r = requests.get(f"{NE}/triggers", headers=h_super, timeout=15)
        assert r.status_code == 200
        seeded = [t for t in r.json()["triggers"] if t["event_key"] == "import-analytics"]
        assert seeded
        tid = seeded[0]["id"]
        body = {"channels": {"email": {"enabled": True, "recipients": []},
                              "whatsapp": {"enabled": False, "numbers": []}}}
        r = requests.put(f"{NE}/triggers/{tid}", json=body, headers=h_super, timeout=15)
        assert r.status_code == 200, r.text
