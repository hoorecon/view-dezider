"""Phase A — share collaboration regression test.

Verifies:
  • POST /api/decisions/{id}/share-step accepts and persists `allow_reshare`
  • GET /api/shared-steps/received exposes `allow_reshare` to recipients
  • POST /api/shared-steps/{share_id}/reshare:
      - works when allow_reshare=True (recipient adds new email, invited_by set)
      - returns 403 when allow_reshare=False
  • POST /api/shared-steps/{share_id}/contribute accepts a `consolidated` field
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = ("admin@test.com", "AdminPass2026!")
RECIPIENT = ("super@test.com", "SuperPass2026!")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    j = r.json()
    return j.get("session_token") or j.get("token")


@pytest.fixture(scope="module")
def owner_token():
    return _login(*OWNER)


@pytest.fixture(scope="module")
def recipient_token():
    return _login(*RECIPIENT)


def _create_decision(token):
    h = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": f"TEST_iter145_{uuid.uuid4().hex[:6]}",
        "context": "phaseA reshare test",
        "factors": [{"id": "f1", "name": "Cost", "ftype": "negative"},
                    {"id": "f2", "name": "Quality", "ftype": "positive"}],
        "options": [{"id": "o1", "name": "Option A", "assessments": []},
                    {"id": "o2", "name": "Option B", "assessments": []}],
    }
    r = requests.post(f"{API}/decisions", json=payload, headers=h, timeout=20)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text}"
    return r.json()["id"]


_CREATED = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(owner_token):
    yield
    h = {"Authorization": f"Bearer {owner_token}"}
    for did in _CREATED:
        try:
            requests.delete(f"{API}/decisions/{did}", headers=h, timeout=10)
        except Exception:
            pass


def _share(owner_token, decision_id, allow_reshare, recipient_email):
    h = {"Authorization": f"Bearer {owner_token}"}
    payload = {
        "decision_id": decision_id,
        "step_number": 7,
        "recipient_emails": [recipient_email],
        "merge_mode": "equal",
        "message": f"TEST_iter145 reshare={allow_reshare}",
        "allow_reshare": allow_reshare,
    }
    r = requests.post(f"{API}/decisions/{decision_id}/share-step", json=payload, headers=h, timeout=20)
    assert r.status_code == 200, f"share-step: {r.status_code} {r.text}"
    return r.json()["id"]


# ---------- allow_reshare = TRUE ----------

def test_allow_reshare_true_flow(owner_token, recipient_token):
    did = _create_decision(owner_token)
    _CREATED.append(did)
    share_id = _share(owner_token, did, True, RECIPIENT[0])

    # Recipient — GET /shared-steps/received should show allow_reshare=True
    r = requests.get(f"{API}/shared-steps/received",
                     headers={"Authorization": f"Bearer {recipient_token}"}, timeout=20)
    assert r.status_code == 200
    mine = [s for s in r.json() if s["id"] == share_id]
    assert mine, "recipient should see the share"
    assert mine[0].get("allow_reshare") is True

    # Reshare by recipient with consolidated note (forwarded email)
    fwd_email = f"TEST_fwd_{uuid.uuid4().hex[:8]}@example.com".lower()
    rr = requests.post(f"{API}/shared-steps/{share_id}/reshare",
                       json={"recipient_emails": [fwd_email], "message": "please help"},
                       headers={"Authorization": f"Bearer {recipient_token}"}, timeout=20)
    assert rr.status_code == 200, f"reshare: {rr.status_code} {rr.text}"
    body = rr.json()
    assert body.get("added", 0) + body.get("invited", 0) == 1

    # Owner — GET /shared-steps/sent — verify pending_invites carries invited_by_name
    so = requests.get(f"{API}/shared-steps/sent",
                      headers={"Authorization": f"Bearer {owner_token}"}, timeout=20)
    assert so.status_code == 200
    owner_share = next((s for s in so.json() if s["id"] == share_id), None)
    assert owner_share is not None
    pend = [p for p in owner_share.get("pending_invites", []) if p.get("email") == fwd_email]
    assert pend, "forwarded invite should appear in pending_invites"
    assert pend[0].get("invited_by_name"), "invited_by_name must be set for transparency"

    # Contribute with `consolidated` field
    cr = requests.post(f"{API}/shared-steps/{share_id}/contribute",
                       json={"factors": [], "options": [], "assessments": {"o1_f1": 25},
                             "note": "TEST_iter145", "consolidated": "TEST_consolidated_note"},
                       headers={"Authorization": f"Bearer {recipient_token}"}, timeout=20)
    assert cr.status_code == 200, f"contribute: {cr.status_code} {cr.text}"

    # Verify contribution persisted with consolidated text
    so2 = requests.get(f"{API}/shared-steps/sent",
                       headers={"Authorization": f"Bearer {owner_token}"}, timeout=20)
    s2 = next(s for s in so2.json() if s["id"] == share_id)
    me_rec = next((r for r in s2.get("recipients", []) if r["email"] == RECIPIENT[0]), None)
    assert me_rec and me_rec.get("contribution", {}).get("consolidated") == "TEST_consolidated_note"


# ---------- allow_reshare = FALSE ----------

def test_allow_reshare_false_blocks_reshare(owner_token, recipient_token):
    did = _create_decision(owner_token)
    _CREATED.append(did)
    share_id = _share(owner_token, did, False, RECIPIENT[0])

    # Recipient should see allow_reshare=False
    r = requests.get(f"{API}/shared-steps/received",
                     headers={"Authorization": f"Bearer {recipient_token}"}, timeout=20)
    mine = next((s for s in r.json() if s["id"] == share_id), None)
    assert mine and mine.get("allow_reshare") is False

    # Attempt to reshare — must 403
    fwd_email = f"TEST_blocked_{uuid.uuid4().hex[:8]}@example.com"
    rr = requests.post(f"{API}/shared-steps/{share_id}/reshare",
                       json={"recipient_emails": [fwd_email], "message": "nope"},
                       headers={"Authorization": f"Bearer {recipient_token}"}, timeout=20)
    assert rr.status_code == 403, f"expected 403, got {rr.status_code} {rr.text}"


# ---------- non-recipient cannot reshare ----------

def test_non_recipient_cannot_reshare(owner_token):
    # Create a third user to attempt reshare without being a recipient
    third_email = f"TEST_third_{uuid.uuid4().hex[:8]}@example.com"
    third_pw = "ThirdPass2026!"
    reg = requests.post(f"{API}/auth/register",
                       json={"email": third_email, "password": third_pw, "name": "TEST third"},
                       timeout=20)
    if reg.status_code not in (200, 201):
        pytest.skip(f"could not register third user: {reg.status_code} {reg.text}")
    third_token = reg.json().get("token") or _login(third_email, third_pw)

    did = _create_decision(owner_token)
    _CREATED.append(did)
    share_id = _share(owner_token, did, True, RECIPIENT[0])  # shared with someone else

    rr = requests.post(f"{API}/shared-steps/{share_id}/reshare",
                       json={"recipient_emails": ["someone@example.com"]},
                       headers={"Authorization": f"Bearer {third_token}"}, timeout=20)
    assert rr.status_code == 403, f"non-recipient should be 403, got {rr.status_code}"
