"""Smoke tests for the OpenAI Free-Tier consent toggle (Wave 3 #4).

What the toggle does:
  - `allow_openai = true`            → OpenAI joins the provider fallback chain.
  - `openai_free_tier = true`        → OpenAI is moved to the FRONT of the chain
                                       AND the wallet charge is zeroed out
                                       (OpenAI bills $0 on data-sharing).

These tests only verify the round-trip + the metering chain ordering — they
do NOT trigger an actual OpenAI call (that would burn the user's tokens and
require a network-reachable key).
"""
import os
import time
import uuid
import asyncio
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _register() -> tuple[str, str]:
    em = f"iter119_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": em, "password": "TestPass2026!", "name": "Iter119"}, timeout=30)
    assert r.status_code in (200, 201), r.text
    return em, r.json()["session_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def test_consent_round_trip():
    _, tok = _register()
    h = _h(tok)
    # Default state: nothing set.
    r = requests.get(f"{API}/ai-wallet/provider-consent", headers=h, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["allow_openai"] is False
    assert d.get("openai_free_tier") is False

    # Toggle free-tier ON → backend MUST auto-enable allow_openai too.
    r = requests.put(f"{API}/ai-wallet/provider-consent",
                     json={"allow_openai": False, "openai_free_tier": True, "mode": "always"},
                     headers=h, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["allow_openai"] is True
    assert d["openai_free_tier"] is True
    assert d["mode"] == "always"

    # Read back persistently.
    r = requests.get(f"{API}/ai-wallet/provider-consent", headers=h, timeout=10)
    assert r.json()["openai_free_tier"] is True

    # Turn off allow_openai (frontend pattern resets free_tier too — backend
    # just persists what's posted).
    r = requests.put(f"{API}/ai-wallet/provider-consent",
                     json={"allow_openai": False, "openai_free_tier": False},
                     headers=h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["allow_openai"] is False
    assert d["openai_free_tier"] is False


def test_provider_chain_openai_first_when_free_tier():
    """Verify _build_chain puts OpenAI at the FRONT of the chain when
    openai_first=true (and at fallback positions otherwise)."""
    from core.ai_metering import _build_chain
    # All keys set in env (they are in this repo).
    base = _build_chain(allow_openai=True, openai_before_groq=False, openai_first=False)
    assert base.index("openai") > base.index("gemini"), base  # fallback position
    promoted = _build_chain(allow_openai=True, openai_before_groq=False, openai_first=True)
    assert promoted[0] == "openai", promoted  # FRONT


def test_consent_zero_charges_free_tier_path_via_helper():
    """The metering helper `user_consent` must return the persisted flag."""
    em, tok = _register()
    h = _h(tok)
    requests.put(f"{API}/ai-wallet/provider-consent",
                 json={"allow_openai": True, "openai_free_tier": True, "mode": "always"},
                 headers=h, timeout=10)

    from core.database import db
    from core.ai_metering import user_consent

    async def _read():
        u = await db.users.find_one({"email": em}, {"_id": 0, "user_id": 1})
        return await user_consent(u["user_id"])

    consent = asyncio.get_event_loop().run_until_complete(_read())
    assert consent.get("allow_openai") is True
    assert consent.get("openai_free_tier") is True
