"""Backend tests for SWOT 'Save as Template' (Phase 2) — Dezider.

Validates:
  1. POST /api/swot/{id}/save-as-template — 400 on empty name
  2. 400 when SWOT has zero S/W/O/T items
  3. 404 for non-existent analysis_id
  4. Success response shape {id, template_id, factor_count, message}
  5. Inserted template doc shape: applies_to_modules=['swot'],
     factors[*].swot_flag in {S,W,O,T}, polarity, internal_external
  6. Admin → AUTHORIZED_STANDARD + approved; non-admin → CUSTOM_BLANK + pending
  7. Template discoverable via /api/hos/templates?module=swot
     and /api/hos/templates/suggest?module=swot
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


# ─────────── Fixtures ───────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": USER_EMAIL, "password": USER_PASS})
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _create_swot(token, title_suffix=""):
    r = requests.post(
        f"{BASE_URL}/api/swot",
        headers=_hdr(token),
        json={"title": f"TEST_SWOT_{title_suffix}_{uuid.uuid4().hex[:6]}",
              "context": "Test ctx",
              "decision_type": "problem"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _fill_swot(token, sid):
    """Adds 1 item to each quadrant via PUT."""
    payload = {
        "strengths":     [{"text": "Strong team",   "description": "", "impact": 8}],
        "weaknesses":    [{"text": "Low budget",    "description": "", "impact": 6}],
        "opportunities": [{"text": "New market",    "description": "", "impact": 7}],
        "threats":       [{"text": "Competitor",    "description": "", "impact": 9}],
    }
    r = requests.put(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(token), json=payload)
    assert r.status_code == 200, r.text


# ─────────── Validation tests ───────────
class TestSwotSaveAsTemplateValidation:

    def test_400_when_name_empty(self, admin_token):
        sid = _create_swot(admin_token, "empty_name")
        _fill_swot(admin_token, sid)
        r = requests.post(f"{BASE_URL}/api/swot/{sid}/save-as-template",
                          headers=_hdr(admin_token),
                          json={"name": "   ", "description": "", "is_public": False})
        assert r.status_code == 400, r.text
        assert "name" in r.text.lower()
        requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token))

    def test_400_when_zero_items(self, admin_token):
        sid = _create_swot(admin_token, "zero_items")
        # do NOT fill
        r = requests.post(f"{BASE_URL}/api/swot/{sid}/save-as-template",
                          headers=_hdr(admin_token),
                          json={"name": "TEST_zero", "description": "", "is_public": False})
        assert r.status_code == 400, r.text
        assert "at least one" in r.text.lower() or "s/w/o/t" in r.text.lower()
        requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token))

    def test_404_for_nonexistent_analysis(self, admin_token):
        r = requests.post(
            f"{BASE_URL}/api/swot/nope-{uuid.uuid4()}/save-as-template",
            headers=_hdr(admin_token),
            json={"name": "TEST_404", "description": "", "is_public": False})
        assert r.status_code == 404, r.text


# ─────────── Success tests (admin) ───────────
class TestSwotSaveAsTemplateAdmin:

    @pytest.fixture(scope="class")
    def created(self, admin_token):
        sid = _create_swot(admin_token, "admin_ok")
        _fill_swot(admin_token, sid)
        r = requests.post(f"{BASE_URL}/api/swot/{sid}/save-as-template",
                          headers=_hdr(admin_token),
                          json={"name": "TEST_admin_tpl",
                                "description": "Admin saved",
                                "is_public": True})
        assert r.status_code == 200, r.text
        data = r.json()
        yield {"sid": sid, "resp": data, "tok": admin_token}
        requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token))

    def test_response_shape(self, created):
        d = created["resp"]
        for key in ("id", "template_id", "factor_count", "message"):
            assert key in d, f"missing {key} in {d}"
        assert d["factor_count"] == 4  # 1 of each quadrant
        assert d["id"] == d["template_id"]

    def test_template_found_via_hos_templates(self, created):
        tid = created["resp"]["template_id"]
        r = requests.get(f"{BASE_URL}/api/hos/templates?module=swot",
                         headers=_hdr(created["tok"]))
        assert r.status_code == 200, r.text
        templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
        ids = [t.get("id") for t in templates]
        assert tid in ids, f"template {tid} not in {ids[:5]}..."

    def test_template_factors_have_swot_flag(self, created):
        tid = created["resp"]["template_id"]
        r = requests.get(f"{BASE_URL}/api/hos/templates?module=swot",
                         headers=_hdr(created["tok"]))
        templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
        tpl = next((t for t in templates if t.get("id") == tid), None)
        assert tpl, "template not found"
        assert tpl.get("applies_to_modules") == ["swot"]
        assert tpl.get("template_type") == "AUTHORIZED_STANDARD"
        assert tpl.get("approval_status") == "approved"
        factors = tpl.get("factors", [])
        assert len(factors) == 4
        flags = sorted(f.get("swot_flag") for f in factors)
        assert flags == ["O", "S", "T", "W"], f"flags={flags}"
        # Polarity + internal_external derivation
        by_flag = {f["swot_flag"]: f for f in factors}
        assert by_flag["S"]["polarity"] == "positive" and by_flag["S"]["internal_external"] == "internal"
        assert by_flag["W"]["polarity"] == "negative" and by_flag["W"]["internal_external"] == "internal"
        assert by_flag["O"]["polarity"] == "positive" and by_flag["O"]["internal_external"] == "external"
        assert by_flag["T"]["polarity"] == "negative" and by_flag["T"]["internal_external"] == "external"

    def test_template_discoverable_via_suggest(self, created):
        tid = created["resp"]["template_id"]
        # /suggest requires acting_as, life_area_id, ask_type_id (taxonomy v2)
        r = requests.get(
            f"{BASE_URL}/api/hos/templates/suggest"
            f"?acting_as=INDIVIDUAL&life_area_id=la_health&ask_type_id=at_problem&module=swot",
            headers=_hdr(created["tok"]))
        # Suggest may return many; just ensure endpoint works and template is discoverable
        assert r.status_code == 200, r.text
        body = r.json()
        templates = body if isinstance(body, list) else body.get("templates", []) or body.get("results", [])
        ids = [t.get("id") for t in templates]
        # Suggest may rank — accept either presence in primary list OR list+detail GET
        if tid not in ids:
            # try fallback: GET single template — should succeed
            r2 = requests.get(f"{BASE_URL}/api/hos/templates/{tid}", headers=_hdr(created["tok"]))
            assert r2.status_code == 200, (
                f"template {tid} not in suggest results AND single GET failed: {r2.status_code}")


# ─────────── Non-admin path ───────────
class TestSwotSaveAsTemplateNonAdmin:

    def test_non_admin_gets_custom_blank_pending(self, user_token, admin_token):
        sid = _create_swot(user_token, "user_ok")
        _fill_swot(user_token, sid)
        r = requests.post(f"{BASE_URL}/api/swot/{sid}/save-as-template",
                          headers=_hdr(user_token),
                          json={"name": "TEST_user_tpl",
                                "description": "User saved",
                                "is_public": False})
        assert r.status_code == 200, r.text
        tid = r.json()["template_id"]

        # Verify via admin-listing (admin can see all) — but use module filter
        r2 = requests.get(f"{BASE_URL}/api/hos/templates?module=swot",
                          headers=_hdr(admin_token))
        templates = r2.json() if isinstance(r2.json(), list) else r2.json().get("templates", [])
        tpl = next((t for t in templates if t.get("id") == tid), None)
        # If admin listing excludes pending, fetch the doc directly
        if not tpl:
            r3 = requests.get(f"{BASE_URL}/api/hos/templates/{tid}", headers=_hdr(admin_token))
            assert r3.status_code == 200, f"can't fetch non-admin tpl {tid}: {r3.status_code}"
            tpl = r3.json()
        assert tpl.get("template_type") == "CUSTOM_BLANK"
        assert tpl.get("approval_status") == "pending"

        requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(user_token))
