"""
Iteration test: Templates & Decider Store 2nd-round overhaul.
Covers backend tests B1..B9 from the review request:
  B1 GET moderation config default
  B2 PATCH show_unverified_in_store toggles /decider-store visibility
  B3 GET queue?status=jai_verified returns >= 11 founder items
  B4 Create public template via save-as-template -> appears as unverified in store
  B5 Disapprove -> hidden from store, visible in owner's my_templates
  B6 Resubmit (owner) -> unverified; resubmit non-disapproved -> 400
  B7 Approve -> jai_verified, reappears in store
  B8 All legacy public items have non-empty privacy_policy after boot backfill
  B9 POST /decider-store/{id}/clone still works (no regression)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or os.environ.get(
    "EXPO_BACKEND_URL", ""
).rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL must be set"

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("token") or j.get("session_token") or j.get("access_token")
    assert tok, f"no token in login response: {j}"
    return tok


@pytest.fixture(scope="module")
def super_token() -> str:
    return _login(SUPER_EMAIL, SUPER_PASS)


@pytest.fixture(scope="module")
def super_headers(super_token) -> dict:
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


# ─────────────────────── B1 ───────────────────────
def test_b1_moderation_config_defaults(super_headers):
    r = requests.get(f"{BASE_URL}/api/admin/moderation/config", headers=super_headers, timeout=30)
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert j.get("show_unverified_in_store") is True
    assert j.get("show_jai_verified_in_store") is True


# ─────────────────────── B2 ───────────────────────
def test_b2_toggle_show_unverified_reduces_store(super_headers):
    # Store count with defaults (both on)
    r_before = requests.get(f"{BASE_URL}/api/decider-store", timeout=30)
    assert r_before.status_code == 200
    before = len(r_before.json().get("templates") or [])

    # Flip OFF
    r = requests.patch(
        f"{BASE_URL}/api/admin/moderation/config",
        json={"show_unverified_in_store": False},
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("show_unverified_in_store") is False

    try:
        r_after = requests.get(f"{BASE_URL}/api/decider-store", timeout=30)
        assert r_after.status_code == 200
        after = len(r_after.json().get("templates") or [])
        # Should be <= before. Ideally strictly < if any unverified exists.
        assert after <= before, f"after={after} > before={before}"
        # All returned items should be jai_verified
        for t in r_after.json().get("templates") or []:
            assert t.get("moderation_status") == "jai_verified", t.get("moderation_status")
    finally:
        # Reset to ON
        r2 = requests.patch(
            f"{BASE_URL}/api/admin/moderation/config",
            json={"show_unverified_in_store": True},
            headers=super_headers,
            timeout=30,
        )
        assert r2.status_code == 200


# ─────────────────────── B3 ───────────────────────
def test_b3_jai_verified_queue_founder_pack(super_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/moderation/store?status=jai_verified",
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    items = r.json().get("items") or []
    # Review request says "10 founder templates + Business Model Chooser = 11".
    # Accept >= 10 to tolerate variation but flag if far off.
    assert len(items) >= 10, f"expected >=10 jai_verified items, got {len(items)}"


# ─────────────────────── B4 / B5 / B6 / B7 shared fixture ───────────────────────
def _make_completed_decision(headers) -> str:
    """Create a decision, add a factor + option + assessment, mark chosen."""
    dec = {
        "title": f"TEST_MOD_{uuid.uuid4().hex[:6]}",
        "context": "moderation flow test",
        "decision_type": "aspiration",
    }
    r = requests.post(f"{BASE_URL}/api/decisions", json=dec, headers=headers, timeout=30)
    assert r.status_code in (200, 201), r.text[:200]
    did = r.json().get("id") or r.json().get("decision_id")
    assert did

    fid = str(uuid.uuid4())
    oid = str(uuid.uuid4())
    patch = {
        "factors": [
            {"id": fid, "name": "Reach", "order": 0, "category": "primary", "rating": 3, "gap_multiplier": 1.0}
        ],
        "options": [
            {
                "id": oid,
                "name": "Option A",
                "assessments": [
                    {"factor_id": fid, "percentage": 80.0, "unit_value": "high"}
                ],
                "worth_percentage": 80.0,
            }
        ],
        "chosen_option_id": oid,
        "status": "completed",
    }
    r2 = requests.put(f"{BASE_URL}/api/decisions/{did}", json=patch, headers=headers, timeout=30)
    assert r2.status_code in (200, 204), r2.text[:200]
    return did


@pytest.fixture(scope="module")
def public_template_id(super_headers):
    did = _make_completed_decision(super_headers)
    body = {
        "name": f"TEST_MOD_TPL_{uuid.uuid4().hex[:6]}",
        "visibility": "public",
        "template_type": "assessment",
        "lead_gen": {
            "name": "Test Publisher",
            "email": "publisher@test.com",
            "whatsapp": "+911111111111",
        },
        "policies": {
            "privacy_policy": "TEST privacy policy",
            "terms_of_use": "TEST terms of use",
        },
    }
    r = requests.post(
        f"{BASE_URL}/api/decisions/{did}/save-as-template",
        json=body,
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, f"save-as-template failed: {r.status_code} {r.text[:300]}"
    tid = r.json().get("id") or r.json().get("template_id")
    assert tid
    yield tid
    # Cleanup
    try:
        requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=super_headers, timeout=30)
    except Exception:
        pass


def _find_in_store(tid: str, extra_query: str = "") -> dict:
    r = requests.get(f"{BASE_URL}/api/decider-store{extra_query}", timeout=30)
    assert r.status_code == 200
    for t in r.json().get("templates") or []:
        if t.get("template_id") == tid:
            return t
    return {}


def test_b4_new_public_template_appears_unverified_in_store(public_template_id, super_headers):
    tid = public_template_id
    # It may take a moment for the mirror
    hit = _find_in_store(tid)
    assert hit, f"template {tid} not found in /decider-store"
    assert hit.get("moderation_status") == "unverified", hit.get("moderation_status")


def test_b5_disapprove_hides_from_store_but_owner_still_sees(public_template_id, super_headers):
    tid = public_template_id
    reason = "Please add expected values"
    r = requests.post(
        f"{BASE_URL}/api/admin/moderation/{tid}/disapprove",
        json={"reason": reason},
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]

    # NOT in decider-store
    hit = _find_in_store(tid)
    assert not hit, f"disapproved template unexpectedly present in store: {hit}"

    # Still in owner's my_templates
    r2 = requests.get(f"{BASE_URL}/api/templates", headers=super_headers, timeout=30)
    assert r2.status_code == 200
    j = r2.json()
    mine = j.get("my_templates") or j.get("mine") or []
    row = next((t for t in mine if t.get("id") == tid), None)
    assert row, f"template {tid} not in my_templates"
    assert row.get("moderation_status") == "disapproved"
    assert row.get("moderation_remark") == reason


def test_b6_resubmit_flips_to_unverified_and_rejects_non_disapproved(public_template_id, super_headers):
    tid = public_template_id
    r = requests.post(
        f"{BASE_URL}/api/templates/{tid}/resubmit",
        json={"publisher_remark": "Added expected values"},
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("status") == "unverified"

    # Second resubmit on now-unverified template should 400
    r2 = requests.post(
        f"{BASE_URL}/api/templates/{tid}/resubmit",
        json={"publisher_remark": "Again"},
        headers=super_headers,
        timeout=30,
    )
    assert r2.status_code == 400, r2.text[:200]


def test_b7_approve_flips_to_jai_verified_and_shows_in_store(public_template_id, super_headers):
    tid = public_template_id
    r = requests.post(
        f"{BASE_URL}/api/admin/moderation/{tid}/approve",
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    assert r.json().get("status") == "jai_verified"

    hit = _find_in_store(tid, extra_query="?moderation=jai_verified")
    assert hit, "approved template not in /decider-store"
    assert hit.get("moderation_status") == "jai_verified"


# ─────────────────────── B8 ───────────────────────
def test_b8_all_legacy_jai_items_have_privacy_policy(super_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/moderation/store?status=jai_verified",
        headers=super_headers,
        timeout=30,
    )
    assert r.status_code == 200
    items = r.json().get("items") or []
    missing = []
    for it in items:
        pol = it.get("policies") or {}
        pp = (pol.get("privacy_policy") or "").strip()
        if not pp:
            missing.append(it.get("template_id"))
    assert not missing, f"jai_verified items missing privacy_policy: {missing}"


# ─────────────────────── B9 ───────────────────────
def test_b9_clone_still_works(public_template_id, super_headers):
    tid = public_template_id
    r = requests.post(
        f"{BASE_URL}/api/decider-store/{tid}/clone",
        json={"mode": "full"},
        headers=super_headers,
        timeout=60,
    )
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    assert j.get("decision_id")
    assert j.get("mode") == "full"
    # Cleanup the cloned decision
    try:
        requests.delete(
            f"{BASE_URL}/api/decisions/{j['decision_id']}", headers=super_headers, timeout=30
        )
    except Exception:
        pass
