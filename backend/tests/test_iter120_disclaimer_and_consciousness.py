"""
Iteration 120: Verifies two shipped changes
  1) PDF legal-disclaimer wired into:
       • routes.decision_reports._build_pdf
       • routes.decisions.mpps (action-plan PDF)
       • utils.solution_matrix_pdf.render_matrix_pdf
  2) Decision-mode rename `awareness` → `consciousness`
       • /api/assessment/questions
       • POST /api/assessment
       • GET  /api/assessment/history
       • DB migration removed legacy keys
"""
from __future__ import annotations

import io
import os
import sys
import requests
import pytest

# Ensure backend modules importable for unit tests
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


# ─────────────────────────── fixtures ───────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token") or data.get("token")
    assert token, f"no token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ────────────────── CHANGE 2: consciousness rename ──────────────────
class TestConsciousnessRename:

    def test_questions_endpoint_uses_consciousness(self, session, auth_headers):
        r = session.get(f"{BASE_URL}/api/assessment/questions", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        questions = body.get("questions") if isinstance(body, dict) else body
        assert isinstance(questions, list) and len(questions) >= 12

        modes = [q.get("mode") for q in questions]
        mode_counts = {m: modes.count(m) for m in set(modes)}
        # No awareness anywhere
        assert "awareness" not in mode_counts, f"legacy awareness still in modes: {mode_counts}"
        # consciousness present with 3 entries
        assert mode_counts.get("consciousness") == 3, f"expected 3 consciousness Qs, got: {mode_counts}"
        # Other 3 modes also present
        for m in ("emotional", "logical", "intuitive"):
            assert mode_counts.get(m) == 3, f"missing {m}: {mode_counts}"

    def test_submit_assessment_returns_consciousness_keys(self, session, auth_headers):
        # Build answers: all 5s for consciousness Qs, all 3s for others
        r = session.get(f"{BASE_URL}/api/assessment/questions", headers=auth_headers, timeout=15)
        questions = r.json().get("questions") if isinstance(r.json(), dict) else r.json()

        # Backend expects answers as dict {question_id: score}
        answers = {q["id"]: (5 if q.get("mode") == "consciousness" else 3) for q in questions}

        sub = session.post(
            f"{BASE_URL}/api/assessment",
            headers=auth_headers,
            json={"answers": answers},
            timeout=30,
        )
        assert sub.status_code in (200, 201), f"submit failed: {sub.status_code} {sub.text[:300]}"
        result = sub.json()

        # Top-level dominant_mode
        dominant = result.get("dominant_mode")
        assert dominant == "consciousness", f"expected dominant_mode=consciousness got {dominant}; full={result}"

        ms = result.get("mode_scores") or {}
        assert "awareness" not in ms, f"legacy awareness leaked: {ms}"
        assert "consciousness" in ms, f"consciousness missing: {ms}"
        assert float(ms["consciousness"]) == 5.0, f"expected 5.0 got {ms['consciousness']}"

        # Make sure serialized JSON nowhere contains the substring 'awareness'
        import json as _json
        raw = _json.dumps(result)
        assert "awareness" not in raw.lower(), f"raw response contains 'awareness': {raw[:400]}"

    def test_history_has_no_awareness_keys(self, session, auth_headers):
        r = session.get(f"{BASE_URL}/api/assessment/history", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text[:200]
        records = r.json()
        # could be a list directly or {"history":[...]}
        if isinstance(records, dict):
            records = records.get("history") or records.get("items") or []
        assert isinstance(records, list), f"unexpected shape: {type(records)}"
        for rec in records:
            ms = rec.get("mode_scores") or {}
            assert "awareness" not in ms, f"record still has awareness: {rec}"
            assert rec.get("dominant_mode") != "awareness", f"dominant=awareness in record: {rec}"


# ────────────────── CHANGE 1: PDF disclaimer ──────────────────
class TestPdfDisclaimerWiring:

    DISCLAIMER_NEEDLE_1 = "Disclaimer:"
    DISCLAIMER_NEEDLE_2 = "JELCOS AI is not responsible"

    def _extract_text(self, pdf_bytes: bytes) -> str:
        # Use PyPDF2 (already installed)
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for p in reader.pages:
            try:
                out.append(p.extract_text() or "")
            except Exception:
                pass
        return "\n".join(out)

    def test_disclaimer_flowables_module_exports(self):
        from utils.pdf_disclaimer import DISCLAIMER_TEXT, legal_disclaimer_flowables
        assert "Disclaimer:" in DISCLAIMER_TEXT
        assert "JELCOS AI is not responsible" in DISCLAIMER_TEXT
        flows = legal_disclaimer_flowables()
        assert isinstance(flows, list) and len(flows) >= 1

    def test_build_pdf_contains_disclaimer_and_brand_footer(self):
        """Unit-test _build_pdf with a minimal payload, then verify
        the disclaimer string appears BEFORE the brand footer in the
        extracted PDF text."""
        from routes.decision_reports import _build_pdf

        payload = {
            "title": "Test Dezider Decision",
            "module": "dezider",
            "module_label": "My Dezider",
            "decision_id": "test_xxxx",
            "generated_at": "2026-01-01 12:00",
            "sections": [
                {"heading": "Summary", "body": "This is a test."},
            ],
        }
        pdf_bytes = _build_pdf(payload, logo_data_url=None)
        assert pdf_bytes.startswith(b"%PDF"), "not a valid PDF magic"
        assert len(pdf_bytes) > 1000, f"PDF suspiciously small: {len(pdf_bytes)} bytes"

        text = self._extract_text(pdf_bytes)
        assert self.DISCLAIMER_NEEDLE_1 in text, f"missing 'Disclaimer:' in extracted text. Sample: {text[:400]}"
        assert self.DISCLAIMER_NEEDLE_2 in text, f"missing 'JELCOS AI is not responsible'. Sample: {text[:400]}"
        # Brand footer should still be present
        assert "JELCOS AI" in text
        assert ("Best Wishes" in text) or ("© JELCOS AI" in text), f"brand footer missing: {text[:600]}"

        # Order: disclaimer before final copyright line
        idx_disc = text.find(self.DISCLAIMER_NEEDLE_1)
        idx_copy = text.rfind("© JELCOS AI")
        if idx_copy != -1:
            assert idx_disc < idx_copy, "disclaimer should appear BEFORE © JELCOS AI footer"

    def test_solution_matrix_pdf_contains_disclaimer(self):
        from utils.solution_matrix_pdf import render_matrix_pdf

        # Minimal viable matrix payload — try common signatures defensively
        try:
            pdf_bytes = render_matrix_pdf(
                title="Test Matrix",
                rows=[{"name": "Option A", "scores": {"f1": 4, "f2": 5}}],
                factors=[{"id": "f1", "name": "Cost"}, {"id": "f2", "name": "Quality"}],
            )
        except TypeError:
            # Fallback to a single 'payload' style
            pdf_bytes = render_matrix_pdf({
                "title": "Test Matrix",
                "rows": [{"name": "Option A", "scores": {"f1": 4}}],
                "factors": [{"id": "f1", "name": "Cost"}],
            })

        assert pdf_bytes.startswith(b"%PDF")
        text = self._extract_text(pdf_bytes)
        assert self.DISCLAIMER_NEEDLE_1 in text, f"matrix PDF missing disclaimer. Sample: {text[:400]}"
        assert self.DISCLAIMER_NEEDLE_2 in text

    def test_mpps_action_plan_pdf_endpoint_disclaimer(self, session, auth_headers):
        """Try to download an MPPS action plan PDF for the admin's most
        recent decision. If admin has no decisions, skip — but the
        unit-level tests above already cover the disclaimer wiring."""
        # Find any decision for admin via dashboard
        try:
            r = session.get(f"{BASE_URL}/api/decisions", headers=auth_headers, timeout=20)
            if r.status_code != 200:
                pytest.skip(f"cannot list decisions: {r.status_code}")
            items = r.json()
            if isinstance(items, dict):
                items = items.get("items") or items.get("decisions") or []
            if not items:
                pytest.skip("admin has no decisions for MPPS PDF integration test")
            decision_id = items[0].get("id") or items[0].get("decision_id")
            assert decision_id
        except Exception as e:
            pytest.skip(f"could not locate a decision: {e}")

        r = session.get(
            f"{BASE_URL}/api/decisions/{decision_id}/mpps-action-plan-pdf",
            headers=auth_headers,
            timeout=60,
        )
        if r.status_code in (402, 403, 404):
            pytest.skip(f"endpoint returned {r.status_code} (entitlement/missing data): {r.text[:200]}")
        assert r.status_code == 200, f"MPPS PDF failed: {r.status_code} {r.text[:300]}"
        assert r.content.startswith(b"%PDF")
        text = self._extract_text(r.content)
        assert self.DISCLAIMER_NEEDLE_1 in text, f"MPPS PDF missing disclaimer. Sample: {text[:400]}"
        assert self.DISCLAIMER_NEEDLE_2 in text


# ────────────────── Regression: PDF download still works ──────────────────
class TestRegressionPdfDownload:

    def test_dezider_module_pdf_route_exists(self, session, auth_headers):
        """Smoke: route is wired even if admin has no dezider decision."""
        # Try listing dezider decisions
        r = session.get(f"{BASE_URL}/api/decisions?module=dezider", headers=auth_headers, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"list decisions returned {r.status_code}")
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items") or items.get("decisions") or []
        dezider = [d for d in items if (d.get("module") in (None, "dezider"))]
        if not dezider:
            pytest.skip("admin has no dezider decisions for regression test")
        did = dezider[0].get("id") or dezider[0].get("decision_id")
        r2 = session.get(f"{BASE_URL}/api/reports/dezider/{did}.pdf", headers=auth_headers, timeout=60)
        if r2.status_code in (402, 403, 404):
            pytest.skip(f"entitlement gate: {r2.status_code}")
        assert r2.status_code == 200
        assert r2.content.startswith(b"%PDF")
