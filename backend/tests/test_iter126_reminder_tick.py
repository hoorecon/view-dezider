"""Iter126 — Lightweight verification that the notification_engine 60s tick
calls _av_appointment_tick() and causes `reminders_sent` to grow.

Strategy (to stay under 2 minutes of wall time):
- Schedule appointment 65s in the future with reminder_offsets_minutes=[1],
  so the fire_at = scheduled-60s = ~5s in the future.
- Use empty participants list so no WhatsApp/Email is attempted.
- Poll for up to ~80s (one tick cycle + slack); assert reminders_sent contains 1.
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@test.com", "password": "AdminPass2026!"},
               timeout=30)
    assert r.status_code == 200
    s.headers.update({"Authorization": f"Bearer {r.json()['session_token']}"})
    return s


def test_av_appointment_tick_fires(session):
    # Create a CB session to attach the appointment to
    r = session.post(f"{BASE_URL}/api/conflict-breaker/sessions",
                     json={"title": "TEST_iter126_tick"}, timeout=30)
    assert r.status_code == 200
    sid = r.json()["session_id"]

    # Schedule 70s out so reminder@1min fires ~10s from now
    sched = (datetime.now(timezone.utc) + timedelta(seconds=70)).isoformat()
    payload = {
        "module": "conflict-breaker",
        "decision_id": sid,
        "title": "TEST_tick_ping",
        "scheduled_at": sched,
        "duration_minutes": 5,
        "participants": [],  # empty -> no WA/email calls
        "reminder_offsets_minutes": [1],
    }
    r = session.post(f"{BASE_URL}/api/collab/appointment", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    appt_id = r.json()["appointment"]["appointment_id"]
    print(f"[TICK] Created appt {appt_id} scheduled at {sched}, fire ~10s")

    # Poll list endpoint up to ~80s for reminders_sent to include 1
    deadline = time.time() + 80
    seen = []
    while time.time() < deadline:
        g = session.get(
            f"{BASE_URL}/api/collab/appointments/conflict-breaker/{sid}",
            timeout=30,
        )
        if g.status_code == 200:
            for a in g.json().get("appointments", []):
                if a["appointment_id"] == appt_id:
                    seen = a.get("reminders_sent") or []
                    if 1 in seen:
                        print(f"[TICK PASS] reminders_sent={seen} after "
                              f"{int(time.time() - (deadline-80))}s")
                        # Cleanup
                        session.post(
                            f"{BASE_URL}/api/collab/appointment/{appt_id}/cancel",
                            timeout=30,
                        )
                        return
        time.sleep(5)

    # Cleanup before failing
    session.post(f"{BASE_URL}/api/collab/appointment/{appt_id}/cancel", timeout=30)
    pytest.fail(
        f"reminders_sent did not include 1 within 80s. Last seen={seen}. "
        f"Note: the apscheduler tick interval is 60s, so this may legitimately "
        f"miss if the tick window doesn't overlap. Re-run if flaky."
    )
