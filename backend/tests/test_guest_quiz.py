"""Guest Decision-Style Quiz — public endpoints (matches project's HTTP-style tests)."""
import os
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")


def test_guest_questions_public_returns_16():
    r = requests.get(f"{BASE_URL}/api/quiz/questions", timeout=15)
    assert r.status_code == 200
    qs = r.json().get("questions", [])
    assert len(qs) == 16
    modes = {}
    for q in qs:
        modes[q["mode"]] = modes.get(q["mode"], 0) + 1
    assert modes == {"emotional": 4, "logical": 4, "intuitive": 4, "consciousness": 4}


def test_guest_submit_public_returns_token_without_leaking_result():
    body = {
        "answers": {f"q{i}": 3 for i in range(1, 17)},
        "name": "Guest User", "email": "guest@example.com",
        "whatsapp": "+911234567890", "gender": "Other",
    }
    r = requests.post(f"{BASE_URL}/api/quiz/guest-submit", json=body, timeout=15)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload.get("quiz_token"), payload
    # A guest response must never leak the result — that's what unlocks after sign-in.
    assert "dominant_mode" not in payload
    assert "mode_scores" not in payload


def test_guest_claim_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/quiz/claim",
        json={"quiz_token": "does-not-matter"}, timeout=15,
    )
    assert r.status_code in (401, 403), r.status_code
