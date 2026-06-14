"""
Seed an AIM session with addictions, irritations, commitments,
and a hand-crafted breakthrough_report including `advised_items`
— so we can frontend-test the P0 (Find a solution) + P1 (Action Center
deep-link) flows WITHOUT burning real LLM credits.

Usage: python /app/test_reports/seed_aim_iter109.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from core.database import db  # noqa: E402
import requests  # noqa: E402

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
BASE = os.environ.get("EXPO_BACKEND_URL", "http://localhost:8001").rstrip("/")


def login():
    r = requests.post(
        f"{BASE}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token"), j


async def seed():
    tok, login_payload = login()
    user_id = login_payload.get("user", {}).get("user_id") or login_payload.get("user_id")
    if not user_id:
        # look up
        me = requests.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
        user_id = me.get("user_id")
    print(f"logged in as user_id={user_id}")

    hdr = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    # 1) Create AIM session
    s = requests.post(
        f"{BASE}/api/emotional-gatekeeper/sessions",
        json={"session_type": "aim", "title": "TEST_iter109_seeded"},
        headers=hdr,
    ).json()
    sid = s["id"]
    print(f"session={sid}")

    # 2) Save addictions+irritations
    requests.post(
        f"{BASE}/api/emotional-gatekeeper/aim/{sid}/save",
        json={
            "addictions": [
                {
                    "area_of_life": "health",
                    "addiction": "TEST_late_night_snacking",
                    "negative_impact_pct": 80,
                    "corrective_actions": "Stop snacking after 9pm",
                    "triggering_situations": "boredom",
                    "negative_impact": "poor sleep + weight gain",
                },
                {
                    "area_of_life": "career",
                    "addiction": "TEST_doomscrolling",
                    "negative_impact_pct": 50,
                },
            ],
            "irritations": [
                {
                    "area_of_life": "relationships",
                    "irritation": "TEST_messy_kitchen",
                    "irritation_pct": 65,
                    "probable_reaction": "snap at family",
                    "negative_impact": "tense evenings",
                },
            ],
        },
        headers=hdr,
    ).raise_for_status()

    # 3) Commitments
    for ctype, txt in [
        ("immediate", "TEST do the kitchen sweep tonight"),
        ("7_day", "TEST cook 3 dinners this week"),
        ("30_day", "TEST hit gym 3x/week"),
    ]:
        requests.post(
            f"{BASE}/api/emotional-gatekeeper/sessions/{sid}/commitments",
            json={"commitment_type": ctype, "commitment_text": txt, "reminder_enabled": False},
            headers=hdr,
        ).raise_for_status()

    # 4) Hand-seed a breakthrough_reports doc with `advised_items`
    now = datetime.now(timezone.utc).isoformat()
    report_doc = {
        "id": f"BR-{uuid.uuid4().hex[:8].upper()}",
        "session_id": sid,
        "user_id": user_id,
        "report": {
            "report_title": "TEST Breakthrough Report (seeded)",
            "breakthrough_score": 7,
            "sections": [
                {"title": "Pattern", "content": "You snack late at night when stressed."},
                {"title": "Insight", "content": "Snacking is a cope, not a craving."},
            ],
            "advised_items": [
                {
                    "kind": "addiction",
                    "label": "Late-night snacking",
                    "why": "It disrupts sleep and undermines your health goals.",
                    "life_area": "health",
                },
                {
                    "kind": "irritation",
                    "label": "Messy kitchen",
                    "why": "Resentment leaks into the rest of your evening.",
                    "life_area": "relationships",
                },
            ],
        },
        "created_at": now,
    }
    await db.breakthrough_reports.update_one(
        {"session_id": sid}, {"$set": report_doc}, upsert=True
    )
    # Also flip session to completed so the report card renders
    await db.breakthrough_sessions.update_one(
        {"id": sid}, {"$set": {"status": "completed", "updated_at": now}}
    )
    print(f"SEEDED session_id={sid}")
    print(f"OPEN: /tools/eg-session?sessionId={sid}")


if __name__ == "__main__":
    asyncio.run(seed())
