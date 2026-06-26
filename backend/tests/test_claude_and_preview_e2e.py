"""Iter 162 — Live E2E for:
  • Claude.ai share-link conversation import (POST /api/url-analyze/decision/{id}/import)
  • Conversation PREVIEW (preview=true returns detected factors/options
    without mutating the decision)
  • CONFIRM (POST .../import/confirm merges a user-edited subset)

Wallet (402) is reported as a skip — NOT a regression.
A 422 with the bug-marker "Couldn't find clear decision factors/options"
is a REGRESSION and fails the test.
"""
import os
import time
import requests
import pytest

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL"))
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL / EXPO_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")

CLAUDE_URL = "https://claude.ai/share/4b324e58-3e3f-453a-8746-3af2b1a970e9"
CHATGPT_URL = "https://chatgpt.com/share/6a36d8d2-3b08-83e8-b67a-6dffa9cc9ffa"
EMAIL = "super@test.com"
PASSWORD = "SuperPass2026!"


# ── shared fixtures ──────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    tok = body.get("session_token") or body.get("access_token")
    assert tok, f"no session_token in login response: {body}"
    return tok


def _make_decision(session_token, title):
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {"title": title, "decision_type": "need",
               "context": "Iter162 review-before-merge regression test"}
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload,
                      headers=headers, timeout=30)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text[:300]}"
    d = r.json()
    did = d.get("id") or d.get("decision_id")
    assert did
    return did


def _cleanup(session_token, did):
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}",
                        headers={"Authorization": f"Bearer {session_token}"},
                        timeout=15)
    except Exception:
        pass


def _post_import(session_token, did, url, preview=False):
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {"url": url, "accepted": True, "eligibility_type": "own",
               "preview": preview}
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/url-analyze/decision/{did}/import",
        json=payload, headers=headers, timeout=240)
    print(f"[import url={url[:60]} preview={preview}] HTTP {r.status_code} in {time.time()-t0:.1f}s")
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:500]}
    return r.status_code, body


def _assert_not_old_422(status, body):
    if status == 422:
        detail = str(body.get("detail") or body)
        assert "Couldn't find clear decision factors/options" not in detail, (
            f"REGRESSION: old 422 bug message returned → {detail}")


def _get_decision(session_token, did):
    headers = {"Authorization": f"Bearer {session_token}"}
    r = requests.get(f"{BASE_URL}/api/decisions/{did}",
                     headers=headers, timeout=30)
    assert r.status_code == 200, f"GET decision: {r.status_code} {r.text[:300]}"
    return r.json()


# ── 1) Claude.ai conversation import — non-preview merge ─────────────────────
def test_claude_share_import_succeeds(session_token):
    did = _make_decision(session_token, "TEST iter162 claude import")
    try:
        status, body = _post_import(session_token, did, CLAUDE_URL, preview=False)
        if status == 402:
            pytest.skip(f"AI wallet exhausted (402) — not a regression: {body}")
        _assert_not_old_422(status, body)
        assert status == 200, f"expected 200, got {status}: {body}"
        assert body.get("mode") == "conversation", f"mode != conversation: {body}"
        assert int(body.get("options_added") or 0) >= 2, f"options_added low: {body}"
        assert int(body.get("factors_added") or 0) >= 2, f"factors_added low: {body}"
        d = _get_decision(session_token, did)
        assert len(d.get("factors") or []) >= 2
        assert len(d.get("options") or []) >= 2
    finally:
        _cleanup(session_token, did)


# ── 2) PREVIEW must NOT mutate the decision ──────────────────────────────────
def test_chatgpt_preview_does_not_mutate(session_token):
    """Use ChatGPT URL for preview (cheaper/faster, already verified working)
    so the assertion that preview is non-destructive is robust regardless of
    Claude/ScraperAPI weather."""
    did = _make_decision(session_token, "TEST iter162 preview no-mutate")
    try:
        before = _get_decision(session_token, did)
        b_facs = len(before.get("factors") or [])
        b_opts = len(before.get("options") or [])

        status, body = _post_import(session_token, did, CHATGPT_URL, preview=True)
        if status == 402:
            pytest.skip(f"AI wallet exhausted (402): {body}")
        _assert_not_old_422(status, body)
        assert status == 200, f"expected 200, got {status}: {body}"
        assert body.get("mode") == "conversation_preview", f"mode wrong: {body}"
        factors = body.get("factors") or []
        options = body.get("options") or []
        assert isinstance(factors, list) and len(factors) >= 2, f"factors empty: {body}"
        assert isinstance(options, list) and len(options) >= 2, f"options empty: {body}"

        # The decision must NOT have been touched.
        after = _get_decision(session_token, did)
        a_facs = len(after.get("factors") or [])
        a_opts = len(after.get("options") or [])
        assert a_facs == b_facs, f"preview MUTATED factors: {b_facs} → {a_facs}"
        assert a_opts == b_opts, f"preview MUTATED options: {b_opts} → {a_opts}"

        # Stash for the confirm test
        pytest.preview_payload = {"decision_id": did,
                                  "factors": factors, "options": options}
    except Exception:
        _cleanup(session_token, did)
        raise


# ── 3) CONFIRM merges only the user-edited subset (renames respected) ────────
def test_confirm_merges_user_edited_subset(session_token):
    payload = getattr(pytest, "preview_payload", None)
    if not payload:
        pytest.skip("preview test did not run / was skipped")
    did = payload["decision_id"]
    try:
        # User trims to first 2 options + first 2 factors, renames option[0]
        renamed_opt = "RENAMED-" + payload["options"][0][:30]
        opts_subset = [renamed_opt, payload["options"][1]]
        facs_subset = payload["factors"][:2]

        headers = {"Authorization": f"Bearer {session_token}"}
        r = requests.post(
            f"{BASE_URL}/api/url-analyze/decision/{did}/import/confirm",
            json={"factors": facs_subset, "options": opts_subset},
            headers=headers, timeout=60)
        print(f"[confirm] HTTP {r.status_code} body={r.text[:400]}")
        assert r.status_code == 200, f"confirm failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("mode") == "conversation_confirmed", body
        assert body.get("factors_added") == len(facs_subset), body
        assert body.get("options_added") == len(opts_subset), body

        # Decision now contains the renamed option + 2 factors
        d = _get_decision(session_token, did)
        opt_names = [o.get("name") for o in (d.get("options") or [])]
        fac_names = [f.get("name") for f in (d.get("factors") or [])]
        assert renamed_opt in opt_names, f"rename not respected: {opt_names}"
        assert payload["options"][1] in opt_names, f"subset missing: {opt_names}"
        # Ensure dropped option[2..] not present
        if len(payload["options"]) > 2:
            dropped = payload["options"][2]
            assert dropped not in opt_names, f"dropped option leaked in: {opt_names}"
        # factors subset present
        for f in facs_subset:
            assert f in fac_names, f"factor {f} not persisted: {fac_names}"
    finally:
        _cleanup(session_token, did)
