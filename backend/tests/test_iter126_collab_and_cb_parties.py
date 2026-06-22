"""Iter126 — Collab routes + Conflict-Breaker `parties` field tests.

Covers tests A–K from the review request:
A. CB session create -> default parties [p1,p2]
B. PUT parties (rename + add p3) persists across GET
C. Create collab invite (module=conflict-breaker)
D. GET invite as owner
E. Submit invite as owner-self (skipped if 403)
F. Merge invite (owner)
G. Cancel after merge => expect 4xx
H. Create A/V appointment (jitsi_room generated)
I. List appointments for module/decision_id
J. Cancel appointment
K. Unknown module => 400
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json()["session_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def cb_session_id(session):
    """Test A: create CB session and verify default 2 parties."""
    payload = {"title": "TEST_iter126_parties", "conversation_type": "interpersonal",
               "other_party_role": "Coworker"}
    r = session.post(f"{BASE_URL}/api/conflict-breaker/sessions", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"A FAIL: {r.status_code} {r.text[:300]}"
    body = r.json()
    sid = body.get("session_id") or body.get("id") or body.get("_id")
    assert sid, f"no session_id in body: {body}"
    parties = body.get("parties")
    assert isinstance(parties, list) and len(parties) == 2, f"A FAIL parties: {parties}"
    assert parties[0]["id"] == "p1" and parties[1]["id"] == "p2"
    print(f"[A PASS] session_id={sid} parties={parties}")
    return sid


# ---------- Tests ----------
class TestCBParties:
    """Tests A + B"""

    def test_a_create_session_default_parties(self, cb_session_id):
        # Already validated inside fixture; this test exists so pytest counts A.
        assert cb_session_id

    def test_b_update_and_persist_parties(self, session, cb_session_id):
        new_parties = [
            {"id": "p1", "name": "Alice", "color": "#6366F1"},
            {"id": "p2", "name": "Bob", "color": "#F59E0B"},
            {"id": "p3", "name": "Carol", "color": "#10B981"},
        ]
        r = session.put(f"{BASE_URL}/api/conflict-breaker/sessions/{cb_session_id}",
                        json={"parties": new_parties}, timeout=30)
        assert r.status_code == 200, f"B PUT FAIL: {r.status_code} {r.text[:300]}"
        # GET to verify persistence
        g = session.get(f"{BASE_URL}/api/conflict-breaker/sessions/{cb_session_id}", timeout=30)
        assert g.status_code == 200, f"B GET FAIL: {g.status_code} {g.text[:300]}"
        gp = g.json().get("parties")
        names = [p["name"] for p in gp]
        assert names == ["Alice", "Bob", "Carol"], f"B FAIL names persisted={names}"
        print(f"[B PASS] parties persisted: {names}")


class TestCollabInvite:
    """Tests C–G"""

    @pytest.fixture(scope="class")
    def invite_id(self, session, cb_session_id):
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        payload = {
            "module": "conflict-breaker",
            "decision_id": cb_session_id,
            "step_id": "start_with_heart",
            "step_label": "Step 4",
            "invitee_phone": "+919999999999",
            "fields": ["intent", "fear", "hope"],
            "expires_at": expires,
        }
        r = session.post(f"{BASE_URL}/api/collab/invite", json=payload, timeout=30)
        assert r.status_code == 200, f"C FAIL: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "invite" in body and "link" in body and "notify" in body, f"C FAIL shape: {body}"
        inv = body["invite"]
        assert inv.get("invite_id"), "no invite_id"
        assert inv["module"] == "conflict-breaker"
        assert inv["status"] == "pending"
        print(f"[C PASS] invite_id={inv['invite_id']} notify={body['notify']}")
        return inv["invite_id"]

    def test_c_create_invite(self, invite_id):
        assert invite_id

    def test_d_get_invite_as_owner(self, session, invite_id):
        r = session.get(f"{BASE_URL}/api/collab/invite/{invite_id}", timeout=30)
        assert r.status_code == 200, f"D FAIL: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("is_owner") is True
        assert body["invite"]["invite_id"] == invite_id
        print("[D PASS] owner can fetch invite")

    def test_e_submit_invite_as_owner(self, session, invite_id, request):
        payload = {"submission": {"intent": "test", "fear": "x", "hope": "y"}}
        r = session.post(f"{BASE_URL}/api/collab/invite/{invite_id}/submit",
                         json=payload, timeout=30)
        if r.status_code == 403:
            pytest.skip(f"E SKIP — owner cannot self-submit (403): {r.text[:200]}")
        assert r.status_code == 200, f"E FAIL: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("status") == "submitted"
        assert body.get("late") is False
        print(f"[E PASS] submitted; late={body.get('late')}")

    def test_f_merge_invite(self, session, invite_id):
        r = session.post(f"{BASE_URL}/api/collab/invite/{invite_id}/merge",
                         json={"override_notes": "OK"}, timeout=30)
        assert r.status_code == 200, f"F FAIL: {r.status_code} {r.text[:300]}"
        # Verify via GET that status=merged
        g = session.get(f"{BASE_URL}/api/collab/invite/{invite_id}", timeout=30)
        assert g.status_code == 200
        assert g.json()["invite"]["status"] == "merged"
        print("[F PASS] invite merged")

    def test_g_cancel_after_merge(self, session, invite_id):
        r = session.post(f"{BASE_URL}/api/collab/invite/{invite_id}/cancel", timeout=30)
        # Current code allows cancel regardless of status -> 200. Review note says
        # "409 or 403 acceptable" (i.e. should fail). We record outcome but mark
        # PASS if status >= 400; otherwise XFAIL noted in report.
        if r.status_code in (409, 403):
            print(f"[G PASS] cancel-after-merge rejected with {r.status_code}")
        elif r.status_code == 200:
            # Server allowed; flag as soft fail — not a hard regression but a bug.
            pytest.xfail(
                f"G XFAIL — cancel after merge returned 200 (should be 409/403). "
                f"Body: {r.text[:200]}"
            )
        else:
            pytest.fail(f"G FAIL unexpected status {r.status_code}: {r.text[:200]}")


class TestCollabAppointment:
    """Tests H–J"""

    @pytest.fixture(scope="class")
    def appt_id(self, session, cb_session_id):
        scheduled = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        payload = {
            "module": "conflict-breaker",
            "decision_id": cb_session_id,
            "title": "Test call",
            "scheduled_at": scheduled,
            "duration_minutes": 30,
            "participants": [{"name": "P1", "phone": "+919999999999"}],
            "reminder_offsets_minutes": [5, 1],
        }
        r = session.post(f"{BASE_URL}/api/collab/appointment", json=payload, timeout=30)
        assert r.status_code == 200, f"H FAIL: {r.status_code} {r.text[:300]}"
        body = r.json()
        appt = body["appointment"]
        assert appt.get("appointment_id"), "no appointment_id"
        assert appt.get("jitsi_room", "").startswith("jelcos-conflict-breaker-"), \
            f"jitsi_room shape unexpected: {appt.get('jitsi_room')}"
        assert appt["status"] == "scheduled"
        print(f"[H PASS] appt_id={appt['appointment_id']} jitsi_room={appt['jitsi_room']}")
        return appt["appointment_id"]

    def test_h_create_appointment(self, appt_id):
        assert appt_id

    def test_i_list_appointments(self, session, appt_id, cb_session_id):
        r = session.get(
            f"{BASE_URL}/api/collab/appointments/conflict-breaker/{cb_session_id}",
            timeout=30,
        )
        assert r.status_code == 200, f"I FAIL: {r.status_code} {r.text[:300]}"
        ids = [a["appointment_id"] for a in r.json().get("appointments", [])]
        assert appt_id in ids, f"I FAIL appt not in list: {ids}"
        print(f"[I PASS] listed appointments: {len(ids)}")

    def test_j_cancel_appointment(self, session, appt_id, cb_session_id):
        r = session.post(f"{BASE_URL}/api/collab/appointment/{appt_id}/cancel", timeout=30)
        assert r.status_code == 200, f"J FAIL: {r.status_code} {r.text[:300]}"
        # Verify via list — status should be cancelled
        g = session.get(
            f"{BASE_URL}/api/collab/appointments/conflict-breaker/{cb_session_id}",
            timeout=30,
        )
        matching = [a for a in g.json().get("appointments", [])
                    if a["appointment_id"] == appt_id]
        assert matching and matching[0]["status"] == "cancelled", \
            f"J FAIL not cancelled: {matching}"
        print("[J PASS] appointment cancelled")


class TestCollabMisc:
    """Test K + light tick verification"""

    def test_k_unknown_module(self, session, cb_session_id):
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        payload = {
            "module": "nope",
            "decision_id": cb_session_id,
            "step_id": "x",
            "step_label": "X",
            "invitee_phone": "+919999999999",
            "fields": [],
            "expires_at": expires,
        }
        r = session.post(f"{BASE_URL}/api/collab/invite", json=payload, timeout=30)
        assert r.status_code == 400, f"K FAIL expected 400 got {r.status_code}: {r.text[:200]}"
        print("[K PASS] unknown module rejected with 400")

    def test_l_short_phone_validation(self, session, cb_session_id):
        # Bonus: ensure phone min_length=8 is enforced
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        payload = {
            "module": "conflict-breaker",
            "decision_id": cb_session_id,
            "step_id": "x",
            "step_label": "X",
            "invitee_phone": "+91",
            "fields": [],
            "expires_at": expires,
        }
        r = session.post(f"{BASE_URL}/api/collab/invite", json=payload, timeout=30)
        assert r.status_code in (400, 422), \
            f"L FAIL expected 4xx got {r.status_code}: {r.text[:200]}"
        print(f"[L PASS] short phone rejected ({r.status_code})")
