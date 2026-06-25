"""Iteration 69 - June 2026 batch:
  A) Auto-create idempotent 'Self' contact on register
  B1) /api/solution-finders/ai/suggest-solutions (auth + 200/402 contract)
  B2) /api/solution-finders/ai/suggest-risks    (auth + 200/402 contract)
"""

import os
import time
import uuid
import pytest
import requests

# Use the public preview URL so we test what the user sees.
BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://modal-responsive-fix.preview.emergentagent.com"
).rstrip("/")

API = f"{BASE_URL}/api"


# ── Shared fixtures ───────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def fresh_user(session):
    """Register a brand-new throwaway @example.com user."""
    email = f"selftest_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": email,
        "password": "SelfTest2026!",
        "name": "Self Test User",
    }
    r = session.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("session_token", "").startswith("session_"), "no session_token returned"
    assert data.get("user_id"), "user_id missing"
    assert data.get("email") == email
    return {
        "email": email,
        "password": payload["password"],
        "user_id": data["user_id"],
        "token": data["session_token"],
    }


@pytest.fixture(scope="module")
def existing_user(session):
    """Primary test user from /app/memory/test_credentials.md."""
    r = session.post(
        f"{API}/auth/login",
        json={
            "email": "harden_1777921741@example.com",
            "password": "HardenPass2026!",
        },
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"existing user login unavailable: {r.status_code} {r.text[:120]}")
    return {"token": r.json()["session_token"], "user_id": r.json()["user_id"]}


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── BACKEND A — Self contact on register ──────────────────────────────────

class TestSelfContactOnRegister:
    def test_register_returns_session_token(self, fresh_user):
        assert fresh_user["token"].startswith("session_")

    def test_self_contact_auto_created(self, session, fresh_user):
        r = session.get(f"{API}/contacts", headers=_auth(fresh_user["token"]), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        contacts = body.get("contacts", [])
        self_rows = [c for c in contacts if c.get("is_self") is True]
        assert len(self_rows) == 1, f"expected exactly 1 self contact, got {len(self_rows)} (total={len(contacts)})"
        s = self_rows[0]
        # name / email pre-filled from user_doc
        assert s.get("name") == "Self Test User"
        assert s.get("email") == fresh_user["email"]
        assert s.get("user_id") == fresh_user["user_id"]

    def test_ensure_self_is_idempotent(self, session, fresh_user):
        # call POST /api/contacts/ensure-self twice; total still must be 1
        for _ in range(2):
            r = session.post(
                f"{API}/contacts/ensure-self", headers=_auth(fresh_user["token"]), timeout=30
            )
            assert r.status_code == 200, r.text
            assert r.json().get("is_self") is True

        r = session.get(f"{API}/contacts", headers=_auth(fresh_user["token"]), timeout=30)
        self_rows = [c for c in r.json().get("contacts", []) if c.get("is_self")]
        assert len(self_rows) == 1, f"duplicate self contact created: {len(self_rows)}"


# ── BACKEND B1 — suggest-solutions ────────────────────────────────────────

SUGGEST_SOL_BODY = {
    "area_of_life": "Career",
    "smart_goal": "Land a senior PM role at a SaaS company in 6 months.",
    "root_causes": [
        {
            "rca_id": "rca_a",
            "text": "Limited senior PM network in target industry",
            "concern_text": "Not enough warm intros",
            "existing": [],
        },
        {
            "rca_id": "rca_b",
            "text": "Portfolio lacks measurable B2B SaaS impact",
            "existing": [],
        },
    ],
}


class TestSuggestSolutions:
    URL = f"{API}/solution-finders/ai/suggest-solutions"

    def test_requires_auth(self):
        # Use a brand-new Session (no cookies leaked from register/login fixtures)
        r = requests.post(self.URL, json=SUGGEST_SOL_BODY, timeout=30)
        assert r.status_code == 401, f"expected 401 without auth, got {r.status_code} {r.text[:160]}"

    def test_authed_200_or_402_not_500(self, session, existing_user):
        r = session.post(
            self.URL, json=SUGGEST_SOL_BODY, headers=_auth(existing_user["token"]), timeout=90
        )
        assert r.status_code in (200, 402), (
            f"expected 200 or 402, got {r.status_code} {r.text[:200]}"
        )
        assert r.status_code != 500
        if r.status_code == 200:
            body = r.json()
            assert "suggestions" in body
            sugg = body["suggestions"]
            assert isinstance(sugg, dict)
            # Only requested rca_ids may appear
            for k, v in sugg.items():
                assert k in {"rca_a", "rca_b"}, f"unexpected rca_id {k}"
                assert isinstance(v, list)
                for item in v:
                    assert isinstance(item, str) and item.strip()
        else:
            assert "credit" in r.text.lower() or "wallet" in r.text.lower()

    def test_empty_rcas_returns_empty(self, session, existing_user):
        body = {**SUGGEST_SOL_BODY, "root_causes": []}
        r = session.post(self.URL, json=body, headers=_auth(existing_user["token"]), timeout=30)
        assert r.status_code == 200
        assert r.json() == {"suggestions": {}}


# ── BACKEND B2 — suggest-risks ────────────────────────────────────────────

SUGGEST_RISK_BODY = {
    "area_of_life": "Career",
    "smart_goal": "Land a senior PM role at a SaaS company in 6 months.",
    "solutions": [
        {
            "sol_id": "sol_a",
            "text": "Publish 2 case studies per month on LinkedIn",
            "existing_risks": [],
        },
        {
            "sol_id": "sol_b",
            "text": "Attend 1 SaaS meetup per week",
            "existing_risks": [],
        },
    ],
}


class TestSuggestRisks:
    URL = f"{API}/solution-finders/ai/suggest-risks"

    def test_requires_auth(self):
        # Use a brand-new Session (no cookies leaked from register/login fixtures)
        r = requests.post(self.URL, json=SUGGEST_RISK_BODY, timeout=30)
        assert r.status_code == 401, f"expected 401 without auth, got {r.status_code} {r.text[:160]}"

    def test_authed_200_or_402_not_500(self, session, existing_user):
        r = session.post(
            self.URL, json=SUGGEST_RISK_BODY, headers=_auth(existing_user["token"]), timeout=120
        )
        assert r.status_code in (200, 402), (
            f"expected 200 or 402, got {r.status_code} {r.text[:200]}"
        )
        assert r.status_code != 500
        if r.status_code == 200:
            body = r.json()
            sugg = body.get("suggestions")
            assert isinstance(sugg, dict)
            for k, risks in sugg.items():
                assert k in {"sol_a", "sol_b"}
                assert isinstance(risks, list)
                for risk in risks:
                    assert isinstance(risk, dict)
                    assert risk.get("name")
                    ip = risk.get("impact_pct")
                    pp = risk.get("probability_pct")
                    assert isinstance(ip, (int, float)) and 0 <= ip <= 100
                    assert isinstance(pp, (int, float)) and 0 <= pp <= 100
                    assert isinstance(risk.get("mitigations"), list)
                    assert isinstance(risk.get("contingencies"), list)

    def test_empty_solutions_returns_empty(self, session, existing_user):
        body = {**SUGGEST_RISK_BODY, "solutions": []}
        r = session.post(self.URL, json=body, headers=_auth(existing_user["token"]), timeout=30)
        assert r.status_code == 200
        assert r.json() == {"suggestions": {}}
