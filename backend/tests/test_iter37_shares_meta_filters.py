"""
Iteration 37 — Report-sharing meta (life_area + decision_type), Shared-with-me,
Solution Box regression, and shared report PDF.

Covers:
  - POST /api/shares for modules dezider, pros_cons, swot, solution_finder
    via EMAIL and WHATSAPP channels (8 shares total).
  - GET /api/shares/shared-with-me as a SECOND account (admin) — verifies
    new life_area + decision_type fields are populated.
  - Guards: wrong owner -> 404, missing recipient_email/phone -> 400.
  - Regression: GET /api/solution-box returns 200 + solution_finder type with
    intake fields. GET /api/reports/{module}/{id}.pdf returns 200 PDF.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "harden_1777921741@example.com"
OWNER_PASS = "HardenPass2026!"
RECIPIENT_EMAIL = "admin@test.com"
RECIPIENT_PASS = "AdminPass2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("session_token") or body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def owner_h():
    return {"Authorization": f"Bearer {_login(OWNER_EMAIL, OWNER_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def recip_h():
    return {"Authorization": f"Bearer {_login(RECIPIENT_EMAIL, RECIPIENT_PASS)}", "Content-Type": "application/json"}


# ---------- helpers to ensure the owner has at least one decision per module ----------

def _first_id(items):
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    if items and isinstance(items, list):
        d = items[0]
        return d.get("id") or d.get("entry_id") or d.get("decision_id")
    return None


def _ensure_dezider(h):
    r = requests.get(f"{API}/decisions", headers=h, timeout=20)
    if r.status_code == 200:
        rid = _first_id(r.json())
        if rid:
            return rid
    # create
    payload = {"title": "TEST_share_dezider", "context": "share test",
               "life_area": "career", "decision_type": "need"}
    r = requests.post(f"{API}/decisions", headers=h, json=payload, timeout=20)
    assert r.status_code in (200, 201), f"create dezider: {r.status_code} {r.text}"
    body = r.json()
    return body.get("id") or body.get("decision_id")


def _ensure_pros_cons(h):
    r = requests.get(f"{API}/pros-cons", headers=h, timeout=20)
    if r.status_code == 200:
        rid = _first_id(r.json())
        if rid:
            return rid
    payload = {"title": "TEST_share_pc", "context": "share test",
               "life_area": "career", "decision_type": "need"}
    r = requests.post(f"{API}/pros-cons", headers=h, json=payload, timeout=20)
    assert r.status_code in (200, 201), f"create pros_cons: {r.status_code} {r.text}"
    return r.json().get("id")


def _ensure_swot(h):
    r = requests.get(f"{API}/swot", headers=h, timeout=20)
    if r.status_code == 200:
        rid = _first_id(r.json())
        if rid:
            return rid
    payload = {"title": "TEST_share_swot", "context": "share test",
               "life_area": "career", "decision_type": "need"}
    r = requests.post(f"{API}/swot", headers=h, json=payload, timeout=20)
    assert r.status_code in (200, 201), f"create swot: {r.status_code} {r.text}"
    return r.json().get("id")


def _ensure_solution_finder(h):
    # solution-box gives us solution_finder type items
    r = requests.get(f"{API}/solution-box?type=solution_finder", headers=h, timeout=20)
    if r.status_code == 200:
        items = r.json()
        if isinstance(items, list) and items:
            return items[0].get("id")
    # try create
    payload = {"smart_goal": "TEST_share_sf goal", "area_of_life": "career", "decision_type": "need"}
    for path in ("/solution-finder", "/solution-finders"):
        r = requests.post(f"{API}{path}", headers=h, json=payload, timeout=20)
        if r.status_code in (200, 201):
            body = r.json()
            return body.get("entry_id") or body.get("id")
    pytest.skip("Could not ensure a solution_finder decision exists for owner")


@pytest.fixture(scope="module")
def decisions(owner_h):
    return {
        "dezider": _ensure_dezider(owner_h),
        "pros_cons": _ensure_pros_cons(owner_h),
        "swot": _ensure_swot(owner_h),
        "solution_finder": _ensure_solution_finder(owner_h),
    }


# ============================================================
# 1. POST /api/shares — Email + WhatsApp for all 4 modules
# ============================================================
@pytest.mark.parametrize("module", ["dezider", "pros_cons", "swot", "solution_finder"])
def test_create_email_share(owner_h, decisions, module):
    did = decisions[module]
    if not did:
        pytest.skip(f"no decision id for module {module}")
    payload = {
        "module": module, "decision_id": did, "channel": "email",
        "recipient_email": RECIPIENT_EMAIL, "recipient_name": "Admin Recipient",
    }
    r = requests.post(f"{API}/shares", headers=owner_h, json=payload, timeout=30)
    assert r.status_code == 200, f"{module} email share: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("token"), "missing token"
    assert body.get("link", "").endswith(body["token"]), "link should end with token"


@pytest.mark.parametrize("module", ["dezider", "pros_cons", "swot", "solution_finder"])
def test_create_whatsapp_share(owner_h, decisions, module):
    did = decisions[module]
    if not did:
        pytest.skip(f"no decision id for module {module}")
    payload = {
        "module": module, "decision_id": did, "channel": "whatsapp",
        "recipient_phone": "+919999000000", "recipient_name": "WA Recipient",
    }
    r = requests.post(f"{API}/shares", headers=owner_h, json=payload, timeout=30)
    assert r.status_code == 200, f"{module} wa share: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("token")


# ============================================================
# 2. Shared-with-me populates life_area + decision_type
# ============================================================
def test_shared_with_me_has_meta(recip_h):
    # Allow a beat for inserts to settle
    time.sleep(1.0)
    r = requests.get(f"{API}/shares/shared-with-me", headers=recip_h, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or []
    assert items, "recipient should see shared items"
    # New schema: every item must expose life_area + decision_type keys (may be null
    # when source doc never had them set — legacy rows). Modern shares for SF
    # *will* have life_area populated since solution-finder always carries
    # area_of_life. Solution_finder share should have life_area populated.
    for it in items:
        assert "life_area" in it
        assert "decision_type" in it
        assert "module" in it and "title" in it
    sf = [i for i in items if i.get("module") == "solution_finder"]
    if sf:
        assert sf[0].get("life_area"), f"SF share should have life_area populated: {sf[0]}"


# ============================================================
# 3. Guards
# ============================================================
def test_share_guard_not_owner(owner_h):
    payload = {
        "module": "dezider", "decision_id": f"bogus-{uuid.uuid4()}",
        "channel": "email", "recipient_email": RECIPIENT_EMAIL,
    }
    r = requests.post(f"{API}/shares", headers=owner_h, json=payload, timeout=20)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


def test_share_guard_missing_email(owner_h, decisions):
    did = decisions["dezider"]
    payload = {"module": "dezider", "decision_id": did, "channel": "email"}
    r = requests.post(f"{API}/shares", headers=owner_h, json=payload, timeout=20)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


def test_share_guard_missing_phone(owner_h, decisions):
    did = decisions["dezider"]
    payload = {"module": "dezider", "decision_id": did, "channel": "whatsapp"}
    r = requests.post(f"{API}/shares", headers=owner_h, json=payload, timeout=20)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


# ============================================================
# 4. Regressions
# ============================================================
def test_solution_box_lists_solution_finder(owner_h):
    r = requests.get(f"{API}/solution-box", headers=owner_h, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    sf = [i for i in items if i.get("type") == "solution_finder"]
    assert sf, "expected at least one solution_finder item in solution-box"
    # Intake fields should be present as keys (may be None)
    keys = sf[0].keys()
    for k in ("acting_as_context", "decision_type", "sub_area_name", "scenario_title"):
        assert k in keys, f"missing intake field {k} in {keys}"


def test_owned_decision_pdf(recip_h):
    # Reports endpoint requires entitlement; toggle admin skip_payment_all_flows
    # ON so admin (who owns the decision) can fetch the PDF, then restore.
    g = requests.get(f"{API}/admin/payment-settings", headers=recip_h, timeout=10)
    assert g.status_code == 200, g.text
    original = bool(g.json().get("skip_payment_all_flows", False))
    requests.put(
        f"{API}/admin/payment-settings", headers=recip_h, timeout=10,
        json={"skip_payment_all_flows": True, "skip_payment_reason": "iter37-qa"},
    )
    try:
        payload = {"title": "TEST_admin_pdf_iter37", "context": "pdf regression",
                   "life_area": "career", "decision_type": "need"}
        r = requests.post(f"{API}/decisions", headers=recip_h, json=payload, timeout=20)
        assert r.status_code in (200, 201), f"admin create decision: {r.status_code} {r.text}"
        did = r.json().get("id") or r.json().get("decision_id")
        assert did

        r = requests.get(f"{API}/reports/dezider/{did}.pdf", headers=recip_h, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        assert len(r.content) > 1000, "PDF body too small"
        requests.delete(f"{API}/decisions/{did}", headers=recip_h, timeout=10)
    finally:
        requests.put(
            f"{API}/admin/payment-settings", headers=recip_h, timeout=10,
            json={"skip_payment_all_flows": original, "skip_payment_reason": ""},
        )
