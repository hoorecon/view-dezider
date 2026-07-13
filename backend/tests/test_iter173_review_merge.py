"""Iter173 — per-step owner-side Review & Merge + AI Auto-Merge across all 3
modules (decision, pros_cons, solution_finder).

Covers:
 1. GET /shared-steps/{id}/review (owner-only) with sme/sme_domains/capability/resources.
 2. Contributions preserved after status=='merged'.
 3. POST /shared-steps/{id}/ai-merge (owner-only) — proposal+rationale+charged+provider+balance.
 4. POST /shared-steps/{id}/apply (owner-only) — writes merged fields, protects identity keys.
 5. Legacy weighted /merge for decision step-7.
 6. RBAC: contributor 403 on /review, /ai-merge, /apply.
 7. Admin tp_collab_ai_merge toggle disables AI merge → re-enable.
 8. SME enrichment from owner contact.

Runs against PROD-style external EXPO_PUBLIC_BACKEND_URL (uses /api prefix).
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "https://repo-blueprint-1.preview.emergentagent.com"
API = f"{BASE}/api"

OWNER = {"email": "super@test.com", "password": "SuperPass2026!"}
CONTRIB = {"email": "admin@test.com", "password": "AdminPass2026!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    r.raise_for_status()
    return r.json()["session_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def owner_tok():
    return _login(OWNER)


@pytest.fixture(scope="module")
def contrib_tok():
    return _login(CONTRIB)


# ── Helpers to build a fresh decision-share with one contribution ──
def _seed_decision_share(owner_tok, contrib_tok, merge_mode="equal"):
    dec = requests.post(f"{API}/decisions", headers=_h(owner_tok), json={
        "title": f"TEST_iter173 dec {uuid.uuid4().hex[:6]}", "context": "iter173",
    }, timeout=30).json()
    did = dec["id"]
    factors = [{"id": "f1", "name": "Cost", "category": "primary", "order": 1}]
    options = [{"id": "o1", "name": "Option A", "assessments": [
        {"factor_id": "f1", "percentage": 40, "assessment_mode": "custom", "unit_value": ""}]}]
    requests.put(f"{API}/decisions/{did}", headers=_h(owner_tok),
                 json={"factors": factors, "options": options}, timeout=30)
    sh = requests.post(f"{API}/decisions/{did}/share-step", headers=_h(owner_tok), json={
        "decision_id": did, "step_number": 7,
        "recipient_emails": [CONTRIB["email"]],
        "merge_mode": merge_mode, "message": "iter173 share",
    }, timeout=30)
    assert sh.status_code == 200, sh.text
    share_id = sh.json()["id"]
    # Contributor opens + contributes
    requests.post(f"{API}/shared-steps/{share_id}/open", headers=_h(contrib_tok), timeout=30)
    c = requests.post(f"{API}/shared-steps/{share_id}/contribute", headers=_h(contrib_tok), json={
        "assessments": {"o1_f1": 80}, "note": "iter173 contribution"}, timeout=30)
    assert c.status_code == 200, c.text
    return did, share_id


# ── 1. /review (owner) returns owner+contributions with SME/capability fields ──
class TestReviewEndpoint:
    def test_review_owner_only(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(owner_tok), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "owner" in body and body["owner"] is not None
        assert "contributions" in body and len(body["contributions"]) == 1
        c = body["contributions"][0]
        for k in ("user_id", "name", "email", "sme", "sme_domains", "capability", "resources", "data", "note"):
            assert k in c, f"missing key {k}"
        # cleanup
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)

    def test_review_rbac_contributor_403(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(contrib_tok), timeout=30)
        assert r.status_code == 403, r.text
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)


# ── 2. SME enrichment via owner contact ──
class TestSMEEnrichment:
    def test_sme_capability_from_contact(self, owner_tok, contrib_tok):
        # Create contact for admin@test.com flagged as SME · Finance
        # First get/clean existing
        contacts = requests.get(f"{API}/contacts", headers=_h(owner_tok), timeout=30).json()
        for c in contacts if isinstance(contacts, list) else []:
            if (c.get("email") or "").lower() == CONTRIB["email"]:
                requests.delete(f"{API}/contacts/{c['id']}", headers=_h(owner_tok), timeout=30)
        create_r = requests.post(f"{API}/contacts", headers=_h(owner_tok), json={
            "name": "TEST iter173 SME contact", "email": CONTRIB["email"],
            "is_sme": True, "sme_domains": ["Finance"], "relationship": "Colleague",
        }, timeout=30)
        assert create_r.status_code in (200, 201), create_r.text
        contact_id = create_r.json().get("id")

        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(owner_tok), timeout=30)
        body = r.json()
        c = body["contributions"][0]
        assert c.get("sme") is True, f"sme not propagated: {c}"
        assert "Finance" in (c.get("capability") or ""), f"capability missing finance: {c}"

        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)
        if contact_id:
            requests.delete(f"{API}/contacts/{contact_id}", headers=_h(owner_tok), timeout=30)


# ── 3. /ai-merge + balance/charge/provider; rbac; admin toggle ──
class TestAIMergeAndAdminToggle:
    def test_ai_merge_owner(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.post(f"{API}/shared-steps/{sid}/ai-merge", headers=_h(owner_tok),
                          json={}, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("proposal", "rationale", "charged", "provider", "balance"):
            assert k in body, f"missing {k}: {body}"
        assert (body.get("rationale") or "").strip(), "empty rationale"
        # contributions still visible
        rev = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(owner_tok), timeout=30).json()
        assert len(rev["contributions"]) == 1
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)

    def test_ai_merge_rbac_403(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.post(f"{API}/shared-steps/{sid}/ai-merge", headers=_h(contrib_tok),
                          json={}, timeout=30)
        assert r.status_code == 403, r.text
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)

    def test_admin_toggle_disables_ai_merge(self, owner_tok, contrib_tok):
        # Disable touchpoint
        d = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(owner_tok),
                         json={"tp_collab_ai_merge": False}, timeout=30)
        assert d.status_code == 200, d.text
        try:
            did, sid = _seed_decision_share(owner_tok, contrib_tok)
            r = requests.post(f"{API}/shared-steps/{sid}/ai-merge", headers=_h(owner_tok),
                              json={}, timeout=30)
            assert r.status_code == 403, f"expected 403 when disabled, got {r.status_code}: {r.text}"
            assert "disabled" in (r.json().get("detail") or "").lower()
            requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)
        finally:
            # Re-enable
            requests.put(f"{API}/admin/ai-wallet/config", headers=_h(owner_tok),
                         json={"tp_collab_ai_merge": True}, timeout=30)

        # And verify re-enabled works
        did2, sid2 = _seed_decision_share(owner_tok, contrib_tok)
        r2 = requests.post(f"{API}/shared-steps/{sid2}/ai-merge", headers=_h(owner_tok),
                           json={}, timeout=120)
        assert r2.status_code == 200, r2.text
        requests.delete(f"{API}/decisions/{did2}", headers=_h(owner_tok), timeout=30)


# ── 4. /apply writes merged fields + preserves contributions + RBAC ──
class TestApplyEndpoint:
    def test_apply_owner_persists_and_preserves(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        # Apply a faux merged options block
        merged = {
            "options": [{"id": "o1", "name": "Option A (merged)",
                         "assessments": [{"factor_id": "f1", "percentage": 70,
                                          "assessment_mode": "custom", "unit_value": ""}]}],
            # try to slip protected keys → must be stripped
            "id": "EVIL", "user_id": "EVIL", "_id": "EVIL",
        }
        r = requests.post(f"{API}/shared-steps/{sid}/apply", headers=_h(owner_tok),
                          json={"merged": merged, "method": "ai"}, timeout=30)
        assert r.status_code == 200, r.text
        # GET decision and verify
        d = requests.get(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30).json()
        assert d["id"] == did, "identity key clobbered!"
        opts = d.get("options") or []
        assert opts and opts[0].get("name") == "Option A (merged)", opts
        assert opts[0]["assessments"][0]["percentage"] == 70

        # Share status → 'merged' but contributions preserved
        rev = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(owner_tok), timeout=30).json()
        assert rev["status"] == "merged", rev
        assert len(rev["contributions"]) == 1
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)

    def test_apply_rbac_403(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok)
        r = requests.post(f"{API}/shared-steps/{sid}/apply", headers=_h(contrib_tok),
                          json={"merged": {"options": []}}, timeout=30)
        assert r.status_code == 403, r.text
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)


# ── 5. Legacy weighted /merge for decision step-7 ──
class TestLegacyMerge:
    def test_legacy_weighted_merge_step7(self, owner_tok, contrib_tok):
        did, sid = _seed_decision_share(owner_tok, contrib_tok, merge_mode="equal")
        r = requests.post(f"{API}/shared-steps/{sid}/merge", headers=_h(owner_tok),
                          json={"merge_mode": "equal"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "weights" in body and body["weights"]
        # owner=40, contrib=80 with equal weights → 60
        d = requests.get(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30).json()
        pct = d["options"][0]["assessments"][0]["percentage"]
        assert 55 <= pct <= 65, f"expected weighted ~60, got {pct}"
        # contributions still present after merge
        rev = requests.get(f"{API}/shared-steps/{sid}/review", headers=_h(owner_tok), timeout=30).json()
        assert len(rev["contributions"]) == 1
        requests.delete(f"{API}/decisions/{did}", headers=_h(owner_tok), timeout=30)


# ── 6. AI merge works for pros_cons + solution_finder shares ──
def _seed_clone_share(owner_tok, contrib_tok, module: str):
    if module == "pros_cons":
        create = requests.post(f"{API}/pros-cons", headers=_h(owner_tok), json={
            "title": f"TEST_iter173 PC {uuid.uuid4().hex[:6]}", "context": "iter173",
            "options": [{"id": "o1", "name": "Opt A", "pros": [{"id": "p1", "text": "good"}],
                         "cons": [{"id": "c1", "text": "bad"}]}],
        }, timeout=30)
        assert create.status_code in (200, 201), create.text
        mid = create.json()["id"]
    else:
        create = requests.post(f"{API}/solution-finders", headers=_h(owner_tok), json={
            "smart_goal": f"TEST_iter173 SF {uuid.uuid4().hex[:6]}",
            "concern": "iter173 concern",
        }, timeout=30)
        assert create.status_code in (200, 201), create.text
        mid = create.json().get("entry_id") or create.json().get("id")
    sh = requests.post(f"{API}/shared-steps/create", headers=_h(owner_tok), json={
        "module": module, "module_id": mid, "step_number": 2,
        "recipient_emails": [CONTRIB["email"]], "merge_mode": "equal",
    }, timeout=30)
    assert sh.status_code == 200, sh.text
    sid = sh.json()["id"]
    requests.post(f"{API}/shared-steps/{sid}/open", headers=_h(contrib_tok), timeout=30)
    requests.post(f"{API}/shared-steps/{sid}/contribute", headers=_h(contrib_tok),
                  json={"note": "iter173 pc/sf contribution"}, timeout=30)
    return mid, sid


class TestAIMergeMultiModule:
    def test_ai_merge_pros_cons(self, owner_tok, contrib_tok):
        mid, sid = _seed_clone_share(owner_tok, contrib_tok, "pros_cons")
        r = requests.post(f"{API}/shared-steps/{sid}/ai-merge", headers=_h(owner_tok),
                          json={}, timeout=120)
        assert r.status_code == 200, r.text
        assert "rationale" in r.json()
        requests.delete(f"{API}/pros-cons/{mid}", headers=_h(owner_tok), timeout=30)

    def test_ai_merge_solution_finder(self, owner_tok, contrib_tok):
        mid, sid = _seed_clone_share(owner_tok, contrib_tok, "solution_finder")
        r = requests.post(f"{API}/shared-steps/{sid}/ai-merge", headers=_h(owner_tok),
                          json={}, timeout=120)
        assert r.status_code == 200, r.text
        assert "rationale" in r.json()
        requests.delete(f"{API}/solution-finders/{mid}", headers=_h(owner_tok), timeout=30)
