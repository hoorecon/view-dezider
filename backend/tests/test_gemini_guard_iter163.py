"""Iter 163 regression: Gemini share-link imports must be rejected FAST (no
fetch, no LLM call) with a 422 + guidance to use the 'Text' importer.

Flow:
 1. Login as super@test.com → session_token
 2. Create a TEST_ decision (Step 2 destination)
 3. POST /api/url-analyze/decision/{id}/import with the share.gemini.google URL
    → expect 422 within a few seconds, detail mentions Gemini + 'Text' import.
 4. Cleanup the decision.

Also asserts the helper `is_gemini_share_url` recognises the typical hosts.
"""
import os
import time
import pytest
import requests

import sys
sys.path.insert(0, "/app/backend")
from core.url_crawl import is_gemini_share_url, is_conversation_url  # noqa: E402

BASE_URL = (os.environ.get("EXPO_BACKEND_URL")
            or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
EMAIL = "super@test.com"
PASSWORD = "SuperPass2026!"
GEMINI_URL = "https://share.gemini.google/eOlCCzMAqeHt"


@pytest.fixture(scope="module")
def session_token() -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok, f"no session_token in response: {r.json()}"
    return tok


@pytest.fixture
def decision_id(session_token: str):
    h = {"Authorization": f"Bearer {session_token}"}
    payload = {"title": "TEST_iter163_gemini_guard", "context": "Iter 163 Gemini guard regression test.", "category": "personal"}
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=h, timeout=20)
    assert r.status_code in (200, 201), f"create decision failed: {r.status_code} {r.text[:200]}"
    did = r.json().get("id") or r.json().get("decision_id")
    assert did, f"no id in {r.json()}"
    yield did
    # cleanup best-effort
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=h, timeout=10)
    except Exception:
        pass


# ── unit: helper recognises gemini share hosts ───────────────────────────
def test_is_gemini_share_url_helper():
    assert is_gemini_share_url("https://share.gemini.google/eOlCCzMAqeHt") is True
    assert is_gemini_share_url("https://gemini.google.com/share/abc123") is True
    assert is_gemini_share_url("https://chatgpt.com/share/xyz") is False
    assert is_gemini_share_url("https://claude.ai/share/abc") is False
    # Helper says yes; conversation classifier also recognises it (caller order
    # matters — Gemini guard must run BEFORE the conversation branch).
    assert is_conversation_url("https://gemini.google.com/share/abc123") is True


# ── api: fast 422 + guidance, no long LLM wait ───────────────────────────
def test_gemini_share_import_returns_fast_422(session_token, decision_id):
    h = {"Authorization": f"Bearer {session_token}"}
    payload = {"url": GEMINI_URL, "accepted": True, "eligibility_type": "own"}
    t0 = time.time()
    r = requests.post(f"{BASE_URL}/api/url-analyze/decision/{decision_id}/import",
                      json=payload, headers=h, timeout=30)
    elapsed = time.time() - t0
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:300]}"
    # Must be a fast guard (no fetch, no LLM): well under typical fetch+LLM budget.
    assert elapsed < 10, f"Gemini guard too slow ({elapsed:.1f}s) — fetch/LLM may have run"
    detail = (r.json().get("detail") or "").lower()
    assert "gemini" in detail, f"detail should mention Gemini: {detail}"
    assert "text" in detail, f"detail should mention the 'Text' importer: {detail}"
