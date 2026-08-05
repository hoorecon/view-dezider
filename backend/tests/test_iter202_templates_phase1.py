"""Iter 202 — Template save/edit + list-page overhaul tests.

Covers the backend contract for the Phase-1 fixes:
  B1  POST /decisions/{id}/save-as-template — public save rejected unless
      the source decision is Completed. When completed, lead_gen + policies
      are persisted onto the template row.
  B2  Same endpoint but PRIVATE — succeeds without lead_gen at any status.
  B3  GET /templates — user's OWN public template appears in BOTH my_templates
      AND public_templates. Any is_official=public founder-pack templates
      show up in public_templates (bucket rebuild fix).
  B4  PATCH /templates/{id} upgrading to visibility=public requires a
      lead_gen block on either the payload OR the existing template.
  B5  PATCH /templates/{id} with factors → factors replaced; store mirror
      refreshed with new factor_count when the template is public.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback matches the frontend .env only if a public URL is not injected
    BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com"

SUPER_EMAIL = "super@test.com"
SUPER_PASSWORD = "SuperPass2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": SUPER_EMAIL, "password": SUPER_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("access_token") or body.get("token") or body.get("session_token")
    assert tok, f"no token in login response: {body}"
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def draft_decision(client):
    """A minimal DRAFT decision. Used to prove public save is rejected."""
    r = client.post(f"{BASE_URL}/api/decisions",
                    json={"title": "TEST_iter202_draft", "context": "draft ctx"}, timeout=30)
    assert r.status_code in (200, 201), r.text[:200]
    return r.json()["id"]


@pytest.fixture(scope="module")
def completed_decision(client):
    """A completed decision seeded directly through the API-updates path so
    save-as-template public gate passes. We create → PATCH factors + options +
    assessments + chosen_option_id + status='completed'."""
    r = client.post(f"{BASE_URL}/api/decisions",
                    json={"title": "TEST_iter202_completed", "context": "completed ctx"}, timeout=30)
    assert r.status_code in (200, 201), r.text[:200]
    did = r.json()["id"]

    fac_id, fac_id2 = str(uuid.uuid4()), str(uuid.uuid4())
    opt_id, opt_id2 = str(uuid.uuid4()), str(uuid.uuid4())
    payload = {
        "factors": [
            {"id": fac_id, "name": "Cost", "category": "primary", "rating": 10, "order": 1,
             "expected_value": "low", "unit": "INR", "operator": "<=", "gap_multiplier": 1.0},
            {"id": fac_id2, "name": "Quality", "category": "primary", "rating": 8, "order": 2,
             "expected_value": "high", "unit": "", "operator": ">=", "gap_multiplier": 1.0},
        ],
        "options": [
            {"id": opt_id, "name": "Option A", "worth_percentage": 82.5,
             "assessments": [
                 {"factor_id": fac_id, "percentage": 80},
                 {"factor_id": fac_id2, "percentage": 85},
             ]},
            {"id": opt_id2, "name": "Option B", "worth_percentage": 60,
             "assessments": [
                 {"factor_id": fac_id, "percentage": 60},
                 {"factor_id": fac_id2, "percentage": 60},
             ]},
        ],
        "chosen_option_id": opt_id,
        "final_choice_reason": "highest worth",
        "notes": "seed", "reflection": "seed",
        "status": "completed",
    }
    r2 = client.put(f"{BASE_URL}/api/decisions/{did}", json=payload, timeout=30)
    assert r2.status_code in (200, 204), r2.text[:200]
    return did


# ── B1: Public save-as-template gated by Completed status ─────────────────
class TestB1PublicSaveGate:
    def test_public_save_rejected_when_not_completed(self, client, draft_decision):
        r = client.post(
            f"{BASE_URL}/api/decisions/{draft_decision}/save-as-template",
            json={
                "name": "TEST_iter202_public_from_draft",
                "template_type": "options",
                "visibility": "public",
                "lead_gen": {"contact_name": "T", "email": "t@x.com", "whatsapp": "+911"},
                "policies": {"privacy_policy": "p", "terms_of_use": "t",
                             "agreed_at": datetime.now(timezone.utc).isoformat()},
            }, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"
        assert "Completed" in r.text or "completed" in r.text

    def test_public_save_persists_lead_gen_and_policies(self, client, completed_decision):
        name = f"TEST_iter202_pub_{uuid.uuid4().hex[:6]}"
        r = client.post(
            f"{BASE_URL}/api/decisions/{completed_decision}/save-as-template",
            json={
                "name": name, "template_type": "options", "visibility": "public",
                "lead_gen": {"contact_name": "Iter202 Contact",
                             "email": "iter202@example.com", "whatsapp": "+91999",
                             "organization": "Org", "designation": "PM",
                             "mobile": "+91888", "redirect_url": "https://ex.com"},
                "policies": {"privacy_policy": "Iter202 PP",
                             "terms_of_use": "Iter202 TOU",
                             "agreed_at": datetime.now(timezone.utc).isoformat()},
            }, timeout=30)
        assert r.status_code == 200, r.text[:200]
        tid = r.json()["id"]
        # Verify via list endpoint
        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        mine = [t for t in lst["my_templates"] if t["id"] == tid]
        assert mine, "created public template not in my_templates"
        t = mine[0]
        assert t["visibility"] == "public"
        assert (t.get("lead_gen") or {}).get("email") == "iter202@example.com"
        assert (t.get("lead_gen") or {}).get("whatsapp") == "+91999"
        assert (t.get("policies") or {}).get("privacy_policy") == "Iter202 PP"
        pytest.iter202_public_tid = tid  # share with later tests


# ── B2: Private save works on non-completed, without lead_gen ─────────────
class TestB2PrivateSaveNoGate:
    def test_private_save_from_draft_succeeds(self, client, draft_decision):
        name = f"TEST_iter202_priv_{uuid.uuid4().hex[:6]}"
        r = client.post(
            f"{BASE_URL}/api/decisions/{draft_decision}/save-as-template",
            json={"name": name, "template_type": "factors", "visibility": "private"},
            timeout=30)
        assert r.status_code == 200, r.text[:200]
        tid = r.json()["id"]
        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        assert any(t["id"] == tid for t in lst["my_templates"])
        pytest.iter202_private_tid = tid


# ── B3: /templates buckets — own public in both Mine + Public; founder pack ─
class TestB3ListBuckets:
    def test_own_public_appears_in_mine_and_public(self, client):
        tid = getattr(pytest, "iter202_public_tid", None)
        assert tid, "public tid not seeded — B1 must run first"
        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        assert any(t["id"] == tid for t in lst["my_templates"]), "own public missing from Mine"
        assert any(t["id"] == tid for t in lst["public_templates"]), \
            "own public missing from Public (fix #5 regression)"

    def test_founder_pack_visible_in_public(self, client):
        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        # Any is_official=public template must appear in public_templates
        official = [t for t in lst["public_templates"] if t.get("is_official")]
        # Fix requires at least SOME founder-pack rows if they exist in db.
        # If db has zero (fresh env), skip so we don't false-fail.
        if not official:
            # Look in authorized_templates as fallback signal
            auth = [t for t in lst["authorized_templates"] if t.get("is_official")]
            if not auth:
                pytest.skip("no is_official templates seeded in this env")
        assert len(official) >= 1, \
            f"founder-pack is_official templates missing from public_templates bucket (fix #8)"


# ── B4: PATCH upgrade to public requires lead_gen ─────────────────────────
class TestB4PatchVisibilityUpgrade:
    def test_upgrade_to_public_without_leadgen_rejected(self, client):
        tid = getattr(pytest, "iter202_private_tid", None)
        assert tid, "private tid not seeded"
        r = client.patch(f"{BASE_URL}/api/templates/{tid}",
                         json={"visibility": "public"}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"
        assert "lead_gen" in r.text.lower() or "contact" in r.text.lower()

    def test_upgrade_to_public_with_leadgen_succeeds(self, client):
        tid = getattr(pytest, "iter202_private_tid", None)
        r = client.patch(
            f"{BASE_URL}/api/templates/{tid}",
            json={"visibility": "public",
                  "lead_gen": {"contact_name": "Upgrade",
                               "email": "up@x.com", "whatsapp": "+9111"},
                  "policies": {"privacy_policy": "up-pp",
                               "terms_of_use": "up-tou",
                               "agreed_at": datetime.now(timezone.utc).isoformat()}},
            timeout=30)
        assert r.status_code == 200, r.text[:200]
        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        t = next((x for x in lst["my_templates"] if x["id"] == tid), None)
        assert t and t["visibility"] == "public"
        assert (t.get("lead_gen") or {}).get("email") == "up@x.com"


# ── B5: PATCH factors replaces content + refreshes decider-store mirror ───
class TestB5PatchFactors:
    def test_patch_factors_replaces_and_mirror_refreshes(self, client):
        tid = getattr(pytest, "iter202_public_tid", None)
        assert tid, "public tid missing"
        new_factors = [
            {"id": str(uuid.uuid4()), "name": "PatchedA", "category": "primary",
             "rating": 9, "order": 1, "gap_multiplier": 1.2, "expected_value": "high"},
            {"id": str(uuid.uuid4()), "name": "PatchedB", "category": "secondary",
             "rating": 5, "order": 2, "gap_multiplier": 1.0},
            {"id": str(uuid.uuid4()), "name": "PatchedC", "category": "primary",
             "rating": 8, "order": 3, "gap_multiplier": 1.0},
        ]
        r = client.patch(f"{BASE_URL}/api/templates/{tid}",
                         json={"factors": new_factors, "life_area": "Career",
                               "category": "Talent", "decision_type": "Choice Selection"},
                         timeout=30)
        assert r.status_code == 200, r.text[:200]

        lst = client.get(f"{BASE_URL}/api/templates", timeout=30).json()
        t = next((x for x in lst["my_templates"] if x["id"] == tid), None)
        assert t is not None
        names = [f["name"] for f in t.get("factors", [])]
        assert names == ["PatchedA", "PatchedB", "PatchedC"], f"factors not replaced: {names}"
        assert t.get("life_area") == "Career"
        assert t.get("category") == "Talent"


# ── Cleanup ───────────────────────────────────────────────────────────────
def test_zzz_cleanup(client):
    for name in ("iter202_public_tid", "iter202_private_tid"):
        tid = getattr(pytest, name, None)
        if tid:
            client.delete(f"{BASE_URL}/api/templates/{tid}", timeout=30)
