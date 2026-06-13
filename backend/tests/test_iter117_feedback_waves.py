"""Smoke tests for the June 2026 feedback waves (Wave 1 + Wave 2 + Wave 3).

Uses live HTTP against the running backend (port 8001) like the rest of the
iter-* test suite — keeps fixture conflicts out of the picture.

Coverage:
  1. Engine credit estimate (Wave 1 #1) — Fast vs Precise tiers differ.
  2. Blank-cell default % round-trip (Wave 2 #9, profile pref).
  3. Decision-level blank_default_pct field accepted on PUT /decisions/{id}.
  4. WhatsApp soft de-dup (Wave 3 #3b) — 409 then ack proceeds.
"""
import os
import time
import uuid
import asyncio

import requests
import pytest

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _register() -> tuple[str, str]:
    em = f"iter117_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": em, "password": "TestPass2026!", "name": "Iter117"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    return em, r.json()["session_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user():
    em, tok = _register()
    return {"email": em, "tok": tok}


# ── 1. Engine credit estimate (Wave 1 #1) ────────────────────────────
def test_import_estimate_fast_vs_precise(user):
    h = _h(user["tok"])
    fast = requests.get(f"{API}/ai-wallet/import-estimate",
                        params={"endpoint": "import", "pages": 1, "tier": "fast"},
                        headers=h, timeout=10)
    precise = requests.get(f"{API}/ai-wallet/import-estimate",
                           params={"endpoint": "import", "pages": 1, "tier": "precise"},
                           headers=h, timeout=10)
    assert fast.status_code == 200, fast.text
    assert precise.status_code == 200, precise.text
    fd, pd = fast.json(), precise.json()
    assert pd["estimate"] > fd["estimate"], (fd, pd)
    assert pd.get("tier_multiplier", 0) >= 1.5


def test_import_estimate_deep_import_tiered(user):
    h = _h(user["tok"])
    fast = requests.get(f"{API}/ai-wallet/import-estimate",
                        params={"endpoint": "deep_import", "pages": 5, "tier": "fast"},
                        headers=h, timeout=10)
    precise = requests.get(f"{API}/ai-wallet/import-estimate",
                           params={"endpoint": "deep_import", "pages": 5, "tier": "precise"},
                           headers=h, timeout=10)
    assert fast.status_code == 200 and precise.status_code == 200
    assert precise.json()["estimate"] > fast.json()["estimate"]


# ── 2. Blank-cell default %, profile pref (Wave 2 #9) ────────────────
def test_blank_default_pct_round_trip(user):
    h = _h(user["tok"])
    r = requests.get(f"{API}/decisions/preferences/blank-default-pct", headers=h, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["blank_default_pct"] == 5  # default fallback

    r = requests.put(f"{API}/decisions/preferences/blank-default-pct",
                     json={"blank_default_pct": 12}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["blank_default_pct"] == 12

    r = requests.get(f"{API}/decisions/preferences/blank-default-pct", headers=h, timeout=10)
    assert r.json()["blank_default_pct"] == 12

    r = requests.put(f"{API}/decisions/preferences/blank-default-pct",
                     json={"blank_default_pct": 250}, headers=h, timeout=10)
    assert r.status_code == 400  # out of range

    r = requests.put(f"{API}/decisions/preferences/blank-default-pct",
                     json={"blank_default_pct": 0}, headers=h, timeout=10)
    assert r.status_code == 200
    assert r.json()["blank_default_pct"] == 0  # opt-out


def test_decision_blank_default_pct_field(user):
    h = _h(user["tok"])
    r = requests.post(f"{API}/decisions",
                      json={"title": "iter117 decision", "context": "ctx"},
                      headers=h, timeout=10)
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    r = requests.put(f"{API}/decisions/{did}",
                     json={"blank_default_pct": 7}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/decisions/{did}", headers=h, timeout=10)
    assert r.json().get("blank_default_pct") == 7


# ── 3. WhatsApp soft de-dup (Wave 3 #3b) ─────────────────────────────
def test_whatsapp_soft_dedup_409_then_ack():
    """Mark user A's WhatsApp number verified, then user B attempts to claim it.
    First call must return 409 with `whatsapp_already_linked`; the follow-up
    with acknowledge_duplicate=true must NOT return 409 (200, or any other
    non-409 error like UltraMsg-not-configured, is acceptable).
    """
    # Patch db directly using the same connection the backend uses.
    from core.database import db  # imported lazily to avoid pollution

    n_raw = f"99{int(time.time()) % 10**8:08d}"[:10]
    number = "91" + n_raw

    # User A — created via HTTP, then DB-patched to "verified".
    em_a, tok_a = _register()  # noqa: F841
    asyncio.get_event_loop().run_until_complete(
        db.users.update_one(
            {"email": em_a},
            {"$set": {"whatsapp_number": number, "whatsapp_verified": True}},
        )
    )

    # User B — fresh registration.
    em_b, tok_b = _register()
    h = _h(tok_b)

    r = requests.post(f"{API}/auth/whatsapp/send-otp",
                      json={"phone_number": n_raw}, headers=h, timeout=10)
    assert r.status_code == 409, r.text
    body = r.json().get("detail")
    assert isinstance(body, dict) and body.get("code") == "whatsapp_already_linked", body
    assert body.get("linked_email_hint"), body

    # Acknowledge → no longer 409.
    r2 = requests.post(f"{API}/auth/whatsapp/send-otp",
                       json={"phone_number": n_raw, "acknowledge_duplicate": True},
                       headers=h, timeout=10)
    assert r2.status_code != 409, r2.text
