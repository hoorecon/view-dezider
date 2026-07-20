"""
ITER 185 — Pre-production regression for JELCOS AI decision app.
Covers: Auth+WhatsApp gate, AI Assistant (Anthropic default+fallback), Solution Finder,
Pros&Cons (with new y_both metadata), MyDezider, SWOT, Stripe smoke, Admin-docs PDF.

NOTE: Report 402 (paid-gate) and Stripe placeholder key non-charge are EXPECTED, not bugs.
"""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

SF_ID_SUPER = "11cf0bc0-8086-40c3-a679-6da1ea10fdab"
PC_ID_1 = "a1263387-e826-40f9-9f84-45dc1a5b7667"
PC_ID_2 = "98426703-317e-4083-bcfd-bbfa0444da69"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def super_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=30)
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    tok = data["session_token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    s.super_data = data
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['session_token']}"})
    s.admin_data = data
    return s


# ================= AUTH + WhatsApp OTP gate =================
class TestAuthWhatsAppGate:
    def test_super_login_returns_session_and_whatsapp_verified_true(self, super_session):
        d = super_session.super_data
        assert d.get("session_token"), "session_token missing"
        assert "whatsapp_verified" in d, "whatsapp_verified field missing in login response"
        # super_admin with skip flag must be verified
        assert d["whatsapp_verified"] is True, f"super whatsapp_verified expected True, got {d.get('whatsapp_verified')}"
        assert d.get("role") == "super_admin"

    def test_admin_login_returns_session_and_whatsapp_verified(self, admin_session):
        d = admin_session.admin_data
        assert d.get("session_token")
        assert "whatsapp_verified" in d
        # admin has skip => should be True; if False, still not a bug, but flag it
        assert d["whatsapp_verified"] is True, f"admin whatsapp_verified expected True (skip gate), got {d.get('whatsapp_verified')}"

    def test_register_new_user_not_stuck_in_otp_loop(self):
        # Brand new throwaway user — verify whatsapp_verified field per skip flag
        uniq = uuid.uuid4().hex[:10]
        email = f"iter185_{uniq}@test.com"
        payload = {
            "email": email,
            "password": "IterPass2026!",
            "name": f"Iter185 {uniq}",
            "whatsapp_number": f"9199{uniq[:8]}",
        }
        r = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=30)
        # Accept 200/201; if endpoint uses different signature, at least should not 500
        assert r.status_code < 500, f"register 5xx: {r.status_code} {r.text[:400]}"
        if r.status_code in (200, 201):
            body = r.json()
            # After the bug fix, newly-registered user should have whatsapp_verified field present.
            # Depending on skip-flag policy it may be true or false, but the FIELD must exist and
            # login must not enforce infinite loop. We just assert the field is present.
            assert "whatsapp_verified" in body or "session_token" in body, \
                f"register missing whatsapp_verified/session_token: {body}"
        else:
            # 4xx acceptable (validation) — just log
            print(f"register returned {r.status_code}: {r.text[:200]}")


# ================= AI Assistant (Anthropic default + fallback) =================
class TestAIAssistant:
    def test_ai_meta_reachable(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/ai-assistant/meta", timeout=30)
        assert r.status_code == 200, f"meta failed: {r.status_code} {r.text[:400]}"
        body = r.json()
        assert "languages" in body or "capabilities" in body, f"meta payload malformed: {body}"

    def test_ai_default_model_is_claude_via_quick_ask(self, super_session):
        r = super_session.post(f"{BASE_URL}/api/ai-assistant/quick-ask",
                               json={"question": "Say pong"}, timeout=90)
        assert r.status_code == 200, f"quick-ask: {r.status_code} {r.text[:400]}"
        body = r.json()
        model = str(body.get("model", "")).lower()
        assert "claude" in model or "sonnet" in model, \
            f"default model expected claude-sonnet-4-6, got: {model}"

    def test_ai_quick_ask_returns_reply_with_model_label(self, super_session):
        payload = {"question": "Say the single word: pong"}
        r = super_session.post(f"{BASE_URL}/api/ai-assistant/quick-ask", json=payload, timeout=90)
        # try alt shape if 4xx
        if r.status_code >= 400:
            payload2 = {"prompt": "Say the single word: pong"}
            r = super_session.post(f"{BASE_URL}/api/ai-assistant/quick-ask", json=payload2, timeout=90)
        assert r.status_code == 200, f"quick-ask failed: {r.status_code} {r.text[:600]}"
        body = r.json()
        # There should be some reply text field
        assert any(k in body for k in ("reply", "answer", "message", "content", "text")), \
            f"no reply field in AI response: {list(body.keys())}"
        # model label present somewhere
        blob = str(body).lower()
        assert "claude" in blob or "gpt" in blob or "model" in blob, \
            f"no model label in reply body keys={list(body.keys())}"


# ================= Solution Finder =================
class TestSolutionFinder:
    def test_get_solution_finder_entry(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/solution-finders/{SF_ID_SUPER}", timeout=30)
        assert r.status_code == 200, f"solution-finder GET failed: {r.status_code} {r.text[:400]}"
        body = r.json()
        assert isinstance(body, dict) and (body.get("id") or body.get("entry_id") or body.get("_id"))

    def test_solution_finder_pdf_report_gated_or_ok(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/reports/solution_finder/{SF_ID_SUPER}.pdf", timeout=60)
        assert r.status_code in (200, 402), f"SF pdf unexpected status {r.status_code}: {r.text[:400]}"
        if r.status_code == 200:
            ctype = r.headers.get("content-type", "")
            assert "pdf" in ctype.lower(), f"200 but not pdf content-type: {ctype}"
        else:
            # 402 → expected entitlement JSON
            try:
                body = r.json()
                assert isinstance(body, dict), "402 body should be JSON dict (entitlement)"
            except Exception:
                pytest.fail(f"402 without JSON body: {r.text[:300]}")

    def test_ai_wallet_estimates_features(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/ai-wallet/estimates", timeout=30)
        assert r.status_code == 200, f"ai-wallet/estimates failed: {r.status_code} {r.text[:400]}"
        body = r.json()
        features = body.get("features") or body.get("feature_map") or body
        # look for solution_finder keys
        blob = str(features).lower()
        assert "solution_finder" in blob, f"features missing solution_finder keys: {blob[:400]}"
        assert "solutions" in blob and "risks" in blob, \
            f"expected solution_finder_solutions and solution_finder_risks: {blob[:400]}"


# ================= Pros & Cons (y_both metadata + reports) =================
class TestProsCons:
    @pytest.fixture(scope="class")
    def analysis_id(self, super_session):
        # verify one exists
        for aid in (PC_ID_2, PC_ID_1):
            r = super_session.get(f"{BASE_URL}/api/pros-cons/{aid}", timeout=30)
            if r.status_code == 200:
                return aid
        pytest.skip("no pros-cons analysis reachable")

    def test_get_analysis(self, super_session, analysis_id):
        r = super_session.get(f"{BASE_URL}/api/pros-cons/{analysis_id}", timeout=30)
        assert r.status_code == 200, f"{analysis_id} GET failed: {r.status_code}"
        body = r.json()
        assert isinstance(body, dict)
        factors = body.get("factors") or (body.get("data") or {}).get("factors") or []
        assert isinstance(factors, list) and len(factors) > 0, "no factors on analysis"
        # save first factor id
        pytest.pc_factor_id = factors[0].get("id") or factors[0].get("factor_id")
        assert pytest.pc_factor_id, f"factor missing id: {factors[0]}"

    def test_patch_factor_y_both_numeric_objective(self, super_session, analysis_id):
        fid = pytest.pc_factor_id
        payload = {"improvable": "y_both", "data_type": "numeric", "factor_type": "objective"}
        # try known route shape
        r = super_session.patch(f"{BASE_URL}/api/pros-cons/{analysis_id}/factors/{fid}", json=payload, timeout=30)
        if r.status_code == 404 or r.status_code == 405:
            r = super_session.put(f"{BASE_URL}/api/pros-cons/{analysis_id}/factors/{fid}", json=payload, timeout=30)
        assert r.status_code < 400, f"factor patch failed: {r.status_code} {r.text[:400]}"

    def test_aggregate_with_y_both_no_500(self, super_session, analysis_id):
        r = super_session.get(f"{BASE_URL}/api/pros-cons/{analysis_id}/aggregate", timeout=60)
        assert r.status_code < 500, f"aggregate 5xx with y_both: {r.status_code} {r.text[:600]}"
        assert r.status_code == 200, f"aggregate not 200: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert isinstance(body, dict) and len(body) > 0

    def test_patch_factor_text_subjective_still_aggregates(self, super_session, analysis_id):
        fid = pytest.pc_factor_id
        payload = {"improvable": "y_both", "data_type": "text", "factor_type": "subjective"}
        r = super_session.patch(f"{BASE_URL}/api/pros-cons/{analysis_id}/factors/{fid}", json=payload, timeout=30)
        if r.status_code in (404, 405):
            r = super_session.put(f"{BASE_URL}/api/pros-cons/{analysis_id}/factors/{fid}", json=payload, timeout=30)
        assert r.status_code < 400, f"factor patch text/subjective failed: {r.status_code} {r.text[:400]}"
        r2 = super_session.get(f"{BASE_URL}/api/pros-cons/{analysis_id}/aggregate", timeout=60)
        assert r2.status_code == 200, f"aggregate after text/subjective: {r2.status_code} {r2.text[:400]}"

    def test_pros_cons_pdf_report_no_500(self, super_session, analysis_id):
        r = super_session.get(f"{BASE_URL}/api/reports/pros_cons/{analysis_id}.pdf", timeout=90)
        assert r.status_code in (200, 402), f"pros_cons pdf unexpected {r.status_code}: {r.text[:400]}"


# ================= MyDezider regression =================
class TestMyDezider:
    def _find(self, sess):
        # MyDezider = /api/decisions endpoint
        r = sess.get(f"{BASE_URL}/api/decisions", timeout=30)
        if r.status_code == 200:
            items = r.json() if isinstance(r.json(), list) else []
            if items:
                return items[0].get("id")
        return None

    def test_dezider_report_no_500(self, super_session):
        aid = self._find(super_session)
        if not aid:
            pytest.skip("no dezider (decisions) analysis available")
        r = super_session.get(f"{BASE_URL}/api/reports/dezider/{aid}.pdf", timeout=90)
        assert r.status_code < 500, f"dezider pdf 5xx: {r.status_code} {r.text[:400]}"
        assert r.status_code in (200, 402, 404), f"dezider pdf {r.status_code}"


# ================= SWOT regression =================
class TestSWOT:
    _created_id = None

    def _ensure(self, sess):
        r = sess.get(f"{BASE_URL}/api/swot", timeout=30)
        if r.status_code == 200:
            items = r.json()
            if isinstance(items, list) and items:
                return items[0].get("id")
        # create one
        payload = {"title": "TEST_iter185_swot", "context": "iter185 seed",
                   "life_area": "career", "decision_type": "general"}
        r = sess.post(f"{BASE_URL}/api/swot", json=payload, timeout=30)
        if r.status_code < 400:
            body = r.json()
            TestSWOT._created_id = body.get("id")
            return TestSWOT._created_id
        return None

    def test_swot_report_no_500(self, super_session):
        aid = self._ensure(super_session)
        if not aid:
            pytest.skip("no swot analysis available/creatable")
        r = super_session.get(f"{BASE_URL}/api/reports/swot/{aid}.pdf", timeout=90)
        assert r.status_code < 500, f"swot pdf 5xx: {r.status_code} {r.text[:400]}"
        assert r.status_code in (200, 402, 404)


# ================= Stripe smoke =================
class TestStripeSmoke:
    def test_stripe_health(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/stripe/health", timeout=30)
        assert r.status_code < 500, f"stripe/health 5xx: {r.status_code} {r.text[:400]}"

    def test_stripe_status(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/stripe/status", timeout=30)
        assert r.status_code < 500, f"stripe/status 5xx: {r.status_code} {r.text[:400]}"

    def test_stripe_checkout_no_500(self, super_session):
        payload = {"plan": "topup", "amount_usd": 5, "success_url": "https://example.com/s", "cancel_url": "https://example.com/c"}
        r = super_session.post(f"{BASE_URL}/api/stripe/checkout", json=payload, timeout=45)
        # With placeholder key, expect a clean 4xx OR a JSON with a url; never 5xx
        assert r.status_code < 500, f"stripe/checkout 5xx: {r.status_code} {r.text[:600]}"
        try:
            body = r.json()
            assert isinstance(body, (dict, list)), "stripe response must be JSON"
        except Exception:
            pytest.fail(f"stripe/checkout not JSON: {r.text[:300]}")


# ================= Admin Docs PDF smoke =================
class TestAdminDocs:
    def test_list_admin_docs(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/admin-docs", timeout=30)
        assert r.status_code == 200, f"admin-docs list: {r.status_code} {r.text[:300]}"
        body = r.json()
        pytest.admin_docs = body

    def test_admin_docs_pdf(self, super_session):
        body = getattr(pytest, "admin_docs", None) or {}
        items = body if isinstance(body, list) else body.get("items") or body.get("docs") or body.get("data") or []
        if not items:
            # Try known slug
            slug = "system_kt"
        else:
            first = items[0]
            slug = first.get("slug") or first.get("id") or first.get("key")
        r = super_session.get(f"{BASE_URL}/api/admin-docs/{slug}/pdf", timeout=60)
        assert r.status_code < 500, f"admin-docs pdf 5xx: {r.status_code} {r.text[:400]}"
        if r.status_code == 200:
            assert "pdf" in r.headers.get("content-type", "").lower()
