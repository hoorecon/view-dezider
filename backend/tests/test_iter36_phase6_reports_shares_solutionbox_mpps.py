"""Iteration 36 — Backend regression for Phases 2-6:
  • REPORTS:        /api/reports/{module}/{id}.pdf + /info for
                    dezider, pros_cons, swot, solution_finder
                    (with admin skip-payment ON)
  • SOLUTION BOX:   /api/solution-box + /counts + ?type=solution_finder filter
                    + intake fields (acting_as_context, decision_type,
                    sub_area_name, scenario_title)
  • DECISIONS MPPS: PUT /api/decisions/{id} accepts mpps_by_option and
                    persists it (verified via subsequent GET).
  • SHARES create:  POST /api/shares — happy path 200 + ownership 404 +
                    missing recipient_email 400.
  • SHARES flow:    Owner shares to primary user; primary GET shared-with-me
                    lists it; POST /{token}/accept → 200; GET
                    /{token}/report.pdf → 200 application/pdf (FREE,
                    bypasses paywall even with skip_payment OFF).
  • SHARES ACL:     Third user (non-recipient) → 403 on /{token}/report.pdf.

Cleanup: deletes test docs and restores admin payment-settings to original.
"""

import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")

OWNER_EMAIL = "veales.vedic.decisions@gmail.com"
OWNER_PASSWORD = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"   # recipient
USER_PASSWORD = "HardenPass2026!"

REPORT_MODULES = ["dezider", "pros_cons", "swot", "solution_finder"]


# ───────────────────────────── helpers ─────────────────────────────
def _login(email: str, password: str) -> dict:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _set_skip_payment(admin_h: dict, flag: bool, reason: str = "iter36-qa"):
    payload = {"skip_payment_all_flows": flag, "skip_payment_reason": reason if flag else ""}
    r = requests.put(
        f"{BASE_URL}/api/admin/payment-settings",
        json=payload, headers=admin_h, timeout=20,
    )
    assert r.status_code == 200, f"Set skip_payment={flag}: {r.status_code} {r.text}"
    assert bool(r.json().get("skip_payment_all_flows")) is flag


# ───────────────────────────── fixtures ─────────────────────────────
@pytest.fixture(scope="module")
def owner_session():
    s = _login(OWNER_EMAIL, OWNER_PASSWORD)
    return {"token": s["session_token"], "user_id": s["user_id"], "h": _hdr(s["session_token"])}


@pytest.fixture(scope="module")
def admin_session():
    s = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": s["session_token"], "user_id": s["user_id"], "h": _hdr(s["session_token"])}


@pytest.fixture(scope="module")
def user_session():
    s = _login(USER_EMAIL, USER_PASSWORD)
    return {
        "token": s["session_token"], "user_id": s["user_id"],
        "email": s["email"], "h": _hdr(s["session_token"]),
    }


@pytest.fixture(scope="module")
def third_user_session():
    """Register a fresh throwaway account for the 403 access-control test."""
    email = f"TEST_iter36_third_{uuid.uuid4().hex[:8]}@example.com"
    password = "ThirdUser2026!"
    # Try register
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Iter36 Third"},
        timeout=20,
    )
    if r.status_code not in (200, 201):
        # Some apps use /signup; try as fallback
        r2 = requests.post(
            f"{BASE_URL}/api/auth/signup",
            json={"email": email, "password": password, "name": "Iter36 Third"},
            timeout=20,
        )
        assert r2.status_code in (200, 201), (
            f"Register fallback failed: {r.status_code}/{r.text[:120]} | "
            f"{r2.status_code}/{r2.text[:120]}"
        )
        body = r2.json()
    else:
        body = r.json()
    token = body.get("session_token") or body.get("access_token") or body.get("token")
    assert token, f"No token in register response: {body}"
    return {"token": token, "email": email, "h": _hdr(token)}


@pytest.fixture(scope="module")
def original_toggle(admin_session):
    r = requests.get(
        f"{BASE_URL}/api/admin/payment-settings",
        headers=admin_session["h"], timeout=20,
    )
    assert r.status_code == 200, r.text
    original = bool(r.json().get("skip_payment_all_flows", False))
    yield original
    # Restore
    _set_skip_payment(admin_session["h"], original, reason="restore_after_iter36")


# Seed module docs OWNED BY THE OWNER (super_admin).
# Each fixture also cleans up best-effort.
def _seed_dezider(owner_h: dict) -> str:
    r = requests.post(
        f"{BASE_URL}/api/decisions",
        json={
            "title": f"TEST_iter36_Dez_{uuid.uuid4().hex[:8]}",
            "context": "iter36 dezider report seed",
            "life_area": "career",
            "decision_type": "Need",
        },
        headers=owner_h, timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    return r.json().get("id") or r.json().get("decision_id")


def _seed_pros_cons(owner_h: dict) -> str:
    r = requests.post(
        f"{BASE_URL}/api/pros-cons",
        json={
            "title": f"TEST_iter36_PnC_{uuid.uuid4().hex[:8]}",
            "context": "iter36 pros_cons report seed",
            "life_area": "career",
            "decision_type": "career",
        },
        headers=owner_h, timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    return r.json().get("id")


def _seed_swot(owner_h: dict) -> str:
    r = requests.post(
        f"{BASE_URL}/api/swot",
        json={
            "title": f"TEST_iter36_Swot_{uuid.uuid4().hex[:8]}",
            "context": "iter36 swot seed",
        },
        headers=owner_h, timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    return r.json().get("id") or r.json().get("swot_id")


def _seed_solution_finder(owner_h: dict) -> str:
    r = requests.post(
        f"{BASE_URL}/api/solution-finders",
        json={
            "area_of_life": "career",
            "smart_goal": f"TEST_iter36_SF_{uuid.uuid4().hex[:8]}",
            "concerns": [
                {"concern_id": "c1", "text": "Concern A", "is_primary": True, "order": 1}
            ],
            "root_causes": [{"rca_id": "r1", "concern_id": "c1", "text": "Cause", "order": 1}],
            "solutions": [{"sol_id": "s1", "rca_id": "r1", "text": "Solution X",
                           "capabilities": [], "resources": []}],
            "risks": [], "mitigations": [], "contingencies": [],
            "action_plan_items": [],
        },
        headers=owner_h, timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return body.get("entry_id") or body.get("id")


@pytest.fixture(scope="module")
def seeded(owner_session):
    h = owner_session["h"]
    ids = {
        "dezider": _seed_dezider(h),
        "pros_cons": _seed_pros_cons(h),
        "swot": _seed_swot(h),
        "solution_finder": _seed_solution_finder(h),
    }
    yield ids
    # Best-effort cleanup
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{ids['dezider']}", headers=h, timeout=10)
    except Exception:
        pass
    try:
        requests.delete(f"{BASE_URL}/api/pros-cons/{ids['pros_cons']}", headers=h, timeout=10)
    except Exception:
        pass
    try:
        requests.delete(f"{BASE_URL}/api/swot/{ids['swot']}", headers=h, timeout=10)
    except Exception:
        pass
    try:
        requests.delete(f"{BASE_URL}/api/solution-finders/{ids['solution_finder']}",
                        headers=h, timeout=10)
    except Exception:
        pass


# ────────────────────────── REPORTS (skip-payment ON) ──────────────────────────
class TestReportsAllModules:
    """With skip_payment ON, /info → unlocked=true; .pdf → 200 + application/pdf
    for ALL 4 modules: dezider, pros_cons, swot, solution_finder."""

    def test_aa_enable_skip_payment(self, admin_session, original_toggle):
        _set_skip_payment(admin_session["h"], True)

    @pytest.mark.parametrize("module", REPORT_MODULES)
    def test_ab_info_unlocked(self, owner_session, seeded, module):
        did = seeded[module]
        r = requests.get(
            f"{BASE_URL}/api/reports/{module}/{did}/info",
            headers=owner_session["h"], timeout=20,
        )
        assert r.status_code == 200, f"{module} /info: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("unlocked") is True, f"{module} unlocked must be true: {body}"

    @pytest.mark.parametrize("module", REPORT_MODULES)
    def test_ac_pdf_200(self, owner_session, seeded, module):
        did = seeded[module]
        r = requests.get(
            f"{BASE_URL}/api/reports/{module}/{did}.pdf",
            headers=owner_session["h"], timeout=45,
        )
        assert r.status_code == 200, (
            f"{module} .pdf expected 200, got {r.status_code}: {r.text[:300]}"
        )
        ctype = r.headers.get("content-type", "")
        assert ctype.startswith("application/pdf"), f"{module} wrong content-type: {ctype}"
        assert r.content[:4] == b"%PDF", f"{module} body is not a PDF"


# ────────────────────────── SOLUTION BOX ──────────────────────────
class TestSolutionBox:
    """Validate aggregated list, counts, type filter, and intake-field exposure."""

    def test_aa_list_includes_intake_fields_and_solution_finder(self, owner_session, seeded):
        r = requests.get(
            f"{BASE_URL}/api/solution-box",
            headers=owner_session["h"], timeout=20,
        )
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) > 0, "Expected non-empty solution-box"

        # Every item should expose the 4 intake-field keys (values may be None)
        intake_keys = {"acting_as_context", "decision_type", "sub_area_name", "scenario_title"}
        sample = items[0]
        missing = intake_keys - set(sample.keys())
        assert not missing, f"Missing intake keys on first item: {missing} (have {list(sample.keys())})"

        # Solution-finder items should be present (we seeded one)
        sf_items = [i for i in items if i.get("type") == "solution_finder"]
        assert sf_items, "Expected at least one solution_finder item in /api/solution-box"

    def test_ab_counts_includes_solution_finder(self, owner_session, seeded):
        r = requests.get(
            f"{BASE_URL}/api/solution-box/counts",
            headers=owner_session["h"], timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        by_type = body.get("by_type") or {}
        assert "solution_finder" in by_type, f"'solution_finder' missing in by_type: {by_type}"
        assert by_type["solution_finder"] >= 1, f"Expected >=1 solution_finder: {by_type}"
        assert body.get("total") == sum(by_type.values())

    def test_ac_filter_by_solution_finder(self, owner_session, seeded):
        r = requests.get(
            f"{BASE_URL}/api/solution-box?type=solution_finder",
            headers=owner_session["h"], timeout=20,
        )
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        for it in items:
            assert it.get("type") == "solution_finder", f"Filter leaked non-SF: {it}"


# ────────────────────────── DECISIONS MPPS persistence ──────────────────────────
class TestDecisionsMppsByOption:
    """PUT /api/decisions/{id} with mpps_by_option must persist + be returned on GET."""

    def test_aa_create_and_update_mpps_by_option(self, owner_session):
        h = owner_session["h"]
        # Create a fresh decision
        r = requests.post(
            f"{BASE_URL}/api/decisions",
            json={"title": f"TEST_iter36_MPPS_{uuid.uuid4().hex[:8]}", "context": "mpps test"},
            headers=h, timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        did = r.json().get("id") or r.json().get("decision_id")
        assert did

        option_id = "opt-1"
        mpps_payload = {
            option_id: [
                {
                    "factor_id": "f1",
                    "original_percentage": 30,
                    "projected_percentage": 80,
                    "improvement_plan": "x",
                }
            ]
        }
        try:
            up = requests.put(
                f"{BASE_URL}/api/decisions/{did}",
                json={"mpps_by_option": mpps_payload},
                headers=h, timeout=20,
            )
            assert up.status_code == 200, f"PUT failed: {up.status_code} {up.text[:300]}"

            # GET and verify persistence
            g = requests.get(
                f"{BASE_URL}/api/decisions/{did}", headers=h, timeout=20,
            )
            assert g.status_code == 200, g.text
            doc = g.json()
            persisted = doc.get("mpps_by_option")
            assert persisted, f"mpps_by_option not persisted, got: {doc.keys()}"
            assert option_id in persisted, f"Option key missing: {persisted}"
            imps = persisted[option_id]
            assert isinstance(imps, list) and len(imps) == 1, f"Bad list: {imps}"
            entry = imps[0]
            assert entry.get("factor_id") == "f1"
            assert entry.get("original_percentage") == 30
            assert entry.get("projected_percentage") == 80
            assert entry.get("improvement_plan") == "x"
        finally:
            try:
                requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=h, timeout=10)
            except Exception:
                pass


# ────────────────────────── SHARES create (validation + 404 + happy) ──────────────────────────
class TestSharesCreate:
    """POST /api/shares basic happy path + ownership 404 + missing-email 400."""

    def test_aa_happy_path_returns_token_and_sent(self, owner_session, seeded):
        # Use a Resend test recipient — they sink the email but return 200
        r = requests.post(
            f"{BASE_URL}/api/shares",
            json={
                "module": "dezider",
                "decision_id": seeded["dezider"],
                "channel": "email",
                "recipient_email": "delivered@resend.dev",
            },
            headers=owner_session["h"], timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True, body
        assert isinstance(body.get("token"), str) and len(body["token"]) > 10
        # sent SHOULD be true when Resend is live; tolerate False if RESEND_API_KEY env-stripped
        # but the response shape (ok=true,token=str) is mandatory.
        # Per the request: assert sent:true
        assert body.get("sent") is True, f"Expected sent=true, got: {body}"

    def test_ab_unowned_decision_returns_404(self, user_session, seeded):
        # Primary user tries to share OWNER's decision (not owned by primary)
        r = requests.post(
            f"{BASE_URL}/api/shares",
            json={
                "module": "dezider",
                "decision_id": seeded["dezider"],
                "channel": "email",
                "recipient_email": "delivered@resend.dev",
            },
            headers=user_session["h"], timeout=20,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_ac_missing_recipient_email_for_email_channel_returns_400(self, owner_session, seeded):
        r = requests.post(
            f"{BASE_URL}/api/shares",
            json={
                "module": "dezider",
                "decision_id": seeded["dezider"],
                "channel": "email",
                # recipient_email intentionally omitted
            },
            headers=owner_session["h"], timeout=20,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"


# ────────────────────────── SHARES recipient flow ──────────────────────────
class TestSharesRecipientFlow:
    """Owner shares to USER_EMAIL → user lists, accepts, downloads PDF (free).
    The PDF endpoint must bypass paywall even when skip_payment is OFF.
    """

    @pytest.fixture(scope="class")
    def share_to_user(self, owner_session, seeded):
        r = requests.post(
            f"{BASE_URL}/api/shares",
            json={
                "module": "pros_cons",  # use a different module than the happy-path one
                "decision_id": seeded["pros_cons"],
                "channel": "email",
                "recipient_email": USER_EMAIL,
            },
            headers=owner_session["h"], timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True and body.get("token")
        return body["token"]

    def test_aa_disable_skip_payment_for_free_share_path(self, admin_session, original_toggle):
        # Force OFF so we PROVE the share endpoint is FREE regardless of toggle
        _set_skip_payment(admin_session["h"], False)

    def test_ab_recipient_sees_share_in_shared_with_me(self, user_session, share_to_user):
        r = requests.get(
            f"{BASE_URL}/api/shares/shared-with-me",
            headers=user_session["h"], timeout=20,
        )
        assert r.status_code == 200, r.text
        items = r.json().get("items") or []
        tokens = {it.get("token") for it in items}
        assert share_to_user in tokens, (
            f"Expected token {share_to_user} in shared-with-me. Got tokens: {tokens}"
        )

    def test_ac_accept_share_returns_ok(self, user_session, share_to_user):
        r = requests.post(
            f"{BASE_URL}/api/shares/{share_to_user}/accept",
            headers=user_session["h"], timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("module") == "pros_cons"

    def test_ad_recipient_downloads_pdf_free(self, user_session, share_to_user):
        # skip_payment is OFF, but the share endpoint must bypass the paywall.
        r = requests.get(
            f"{BASE_URL}/api/shares/{share_to_user}/report.pdf",
            headers=user_session["h"], timeout=45,
        )
        assert r.status_code == 200, (
            f"Recipient PDF expected 200 (FREE), got {r.status_code}: {r.text[:300]}"
        )
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            f"Wrong content-type: {r.headers.get('content-type')}"
        assert r.content[:4] == b"%PDF", "Body is not a valid PDF"

    def test_ae_third_user_forbidden(self, third_user_session, share_to_user):
        """Third user whose email/phone doesn't match and hasn't accepted → 403."""
        r = requests.get(
            f"{BASE_URL}/api/shares/{share_to_user}/report.pdf",
            headers=third_user_session["h"], timeout=30,
        )
        assert r.status_code == 403, (
            f"Third user expected 403, got {r.status_code}: {r.text[:300]}"
        )
