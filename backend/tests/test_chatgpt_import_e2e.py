"""Live E2E for the ChatGPT share-link import bug-fix.

Hits the deployed backend via EXPO_PUBLIC_BACKEND_URL:
  1) POST /api/auth/login  -> session_token
  2) POST /api/decisions   -> decision id
  3) POST /api/url-analyze/decision/{id}/import   -> expect 200 + mode=conversation
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL / EXPO_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")

SHARE_URL = "https://chatgpt.com/share/6a36d8d2-3b08-83e8-b67a-6dffa9cc9ffa"
EMAIL = "super@test.com"
PASSWORD = "SuperPass2026!"


@pytest.fixture(scope="module")
def session_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    tok = body.get("session_token") or body.get("access_token")
    assert tok, f"no session_token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def decision_id(session_token):
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {"title": "TEST chatgpt import",
               "decision_type": "need",
               "context": "Choosing which VC investor to approach for fundraising"}
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=headers, timeout=30)
    assert r.status_code in (200, 201), f"create decision failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    did = d.get("id") or d.get("decision_id")
    assert did, f"no id in decision response: {d}"
    yield did
    # best-effort cleanup
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=headers, timeout=15)
    except Exception:
        pass


def test_chatgpt_share_import_succeeds(session_token, decision_id):
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {"url": SHARE_URL, "accepted": True, "eligibility_type": "own"}
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/url-analyze/decision/{decision_id}/import",
        json=payload, headers=headers, timeout=180)
    elapsed = time.time() - t0
    print(f"\n[import] HTTP {r.status_code} in {elapsed:.1f}s")
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:500]}
    print(f"[import] body: {body}")

    # 402 = wallet ran out of credits — explicitly NOT a regression per spec.
    if r.status_code == 402:
        pytest.skip(f"AI wallet exhausted (402) — not a code regression: {body}")

    # 422 with the bug-marker string would be a regression of the fix.
    if r.status_code == 422:
        detail = str(body.get("detail") or body)
        assert "Couldn't find clear decision factors/options" not in detail, (
            f"REGRESSION: import returned the old 422 bug message → {detail}")

    assert r.status_code == 200, f"expected 200, got {r.status_code}: {body}"
    assert body.get("mode") == "conversation", f"expected mode=conversation, got {body}"
    assert int(body.get("options_added") or 0) >= 2, f"options_added too low: {body}"
    assert int(body.get("factors_added") or 0) >= 2, f"factors_added too low: {body}"
    assert int(body.get("item_count") or 0) >= 1, f"item_count too low: {body}"


def test_decision_persisted_after_import(session_token, decision_id):
    headers = {"Authorization": f"Bearer {session_token}"}
    r = requests.get(f"{BASE_URL}/api/decisions/{decision_id}", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET decision failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    factors = d.get("factors") or []
    options = d.get("options") or []
    print(f"[verify] factors={len(factors)} options={len(options)}")
    assert len(factors) >= 2, f"expected ≥2 factors persisted, got {len(factors)}"
    assert len(options) >= 2, f"expected ≥2 options persisted, got {len(options)}"
