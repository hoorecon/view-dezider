"""Iteration 63 — Google Sheet assessment import (Phase 1).

Backend-only validation of:
  1) GET  /api/oauth/sheets/status  → 200, {connected: false} for unconnected user
  2) Pros & Cons gating:
        POST /api/pros-cons/{id}/assessment-gsheet            → 428 (Google not connected)
        POST /api/pros-cons/{id}/assessment-gsheet/import     → 400 (No Google Sheet linked)
  3) My Dezider gating:
        POST /api/decisions/{id}/assessment-gsheet            → 428
        POST /api/decisions/{id}/assessment-gsheet/import     → 400
  4) XLS regression after the build_value_matrix/parse_rows refactor:
        GET  /api/pros-cons/{id}/assessment-template          → 200 xlsx bytes
        GET  /api/decisions/{id}/assessment-template          → 200 xlsx bytes
        POST /api/pros-cons/{id}/assessment-import (multipart) → 200 {applied, rows}

Does NOT attempt real Google OAuth.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

import pytest
import requests


# /api routes are routed to the FastAPI backend through Kubernetes ingress.
BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ─── Shared fixtures ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session: requests.Session) -> str:
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"no token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# Helper: detach Google sheets if a previous run left tokens for this user.
@pytest.fixture(scope="module", autouse=True)
def ensure_disconnected(session: requests.Session, auth_headers: dict):
    try:
        session.post(f"{BASE_URL}/api/oauth/sheets/disconnect", headers=auth_headers, timeout=15)
    except Exception:
        pass


# ─── 1) OAuth status endpoint ───────────────────────────────────────
class TestSheetsStatus:
    def test_status_unauthenticated_rejected(self):
        # Fresh session to avoid leaking cookies from the authenticated module session.
        with requests.Session() as fresh:
            r = fresh.get(f"{BASE_URL}/api/oauth/sheets/status", timeout=15)
        # Should reject without a bearer token. 401 expected (403 acceptable too).
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"

    def test_status_authenticated_not_connected(self, session: requests.Session, auth_headers: dict):
        r = session.get(f"{BASE_URL}/api/oauth/sheets/status", headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert isinstance(body, dict), f"expected dict, got: {body!r}"
        # When user has never connected, the doc isn't in db.google_sheet_tokens →
        # core.google_sheets.get_status returns {"connected": False}.
        assert body.get("connected") is False, f"expected connected=False, got: {body}"


# ─── Helpers to seed minimal Pros & Cons / Decisions ────────────────
def _create_pros_cons(session: requests.Session, headers: dict) -> str:
    r = session.post(
        f"{BASE_URL}/api/pros-cons",
        headers=headers,
        json={"title": f"TEST_iter63_pc_{uuid.uuid4().hex[:8]}",
              "context": "Iteration-63 gsheet contract test"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"pros-cons create failed: {r.status_code} {r.text}"
    pid = r.json().get("id")
    assert pid, f"no id in response: {r.json()}"
    return pid


def _add_pc_option(session, headers, pid, name="Option A") -> str:
    r = session.post(f"{BASE_URL}/api/pros-cons/{pid}/options",
                     headers=headers, json={"name": name}, timeout=20)
    assert r.status_code in (200, 201), f"add option failed: {r.status_code} {r.text}"
    return r.json()["id"]


def _add_pc_factor(session, headers, pid, name="Cost") -> str:
    r = session.post(f"{BASE_URL}/api/pros-cons/{pid}/factors",
                     headers=headers, json={"name": name}, timeout=20)
    assert r.status_code in (200, 201), f"add factor failed: {r.status_code} {r.text}"
    return r.json()["id"]


def _create_decision(session: requests.Session, headers: dict) -> str:
    r = session.post(
        f"{BASE_URL}/api/decisions",
        headers=headers,
        json={"title": f"TEST_iter63_md_{uuid.uuid4().hex[:8]}",
              "context": "Iteration-63 gsheet contract test (My Dezider)"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"decision create failed: {r.status_code} {r.text}"
    did = r.json().get("id")
    assert did, f"no id in response: {r.json()}"
    return did


def _seed_decision_factor_and_option(session, headers, did):
    """My Dezider mutates factors/options via the whole-doc PUT endpoint."""
    factor_id = str(uuid.uuid4())
    option_id = str(uuid.uuid4())
    body = {
        "factors": [{
            "id": factor_id,
            "name": "Cost",
            "rating": 5,
            "expected_value": "Low",
            "unit": "INR",
        }],
        "options": [{
            "id": option_id,
            "name": "Option A",
            "assessments": [],
            "worth_percentage": 0.0,
        }],
    }
    r = session.put(f"{BASE_URL}/api/decisions/{did}", headers=headers, json=body, timeout=30)
    assert r.status_code in (200, 201), f"decision PUT failed: {r.status_code} {r.text}"
    return factor_id, option_id


# ─── 2) Pros & Cons gating ──────────────────────────────────────────
class TestProsConsGSheetGating:
    @pytest.fixture(scope="class")
    def pc_id(self, session: requests.Session, auth_headers: dict) -> str:
        pid = _create_pros_cons(session, auth_headers)
        _add_pc_option(session, auth_headers, pid)
        _add_pc_factor(session, auth_headers, pid)
        return pid

    def test_create_gsheet_requires_google_connect(self, session, auth_headers, pc_id):
        r = session.post(f"{BASE_URL}/api/pros-cons/{pc_id}/assessment-gsheet",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 428, f"expected 428 got {r.status_code}: {r.text}"
        detail = (r.json() or {}).get("detail", "")
        # Readable message → must mention "connect" or "Google".
        low = detail.lower()
        assert ("connect" in low) or ("google" in low), f"unfriendly detail: {detail!r}"

    def test_import_gsheet_without_link_400(self, session, auth_headers, pc_id):
        r = session.post(f"{BASE_URL}/api/pros-cons/{pc_id}/assessment-gsheet/import",
                         headers=auth_headers, json={}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        detail = (r.json() or {}).get("detail", "")
        assert "no google sheet linked" in detail.lower(), f"detail mismatch: {detail!r}"


# ─── 3) My Dezider gating ───────────────────────────────────────────
class TestMyDeziderGSheetGating:
    @pytest.fixture(scope="class")
    def md_id(self, session: requests.Session, auth_headers: dict) -> str:
        did = _create_decision(session, auth_headers)
        _seed_decision_factor_and_option(session, auth_headers, did)
        return did

    def test_create_gsheet_requires_google_connect(self, session, auth_headers, md_id):
        r = session.post(f"{BASE_URL}/api/decisions/{md_id}/assessment-gsheet",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 428, f"expected 428 got {r.status_code}: {r.text}"
        detail = (r.json() or {}).get("detail", "")
        low = detail.lower()
        assert ("connect" in low) or ("google" in low), f"unfriendly detail: {detail!r}"

    def test_import_gsheet_without_link_400(self, session, auth_headers, md_id):
        r = session.post(f"{BASE_URL}/api/decisions/{md_id}/assessment-gsheet/import",
                         headers=auth_headers, json={}, timeout=30)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        detail = (r.json() or {}).get("detail", "")
        assert "no google sheet linked" in detail.lower(), f"detail mismatch: {detail!r}"


# ─── 4) XLS regression — round-trip ─────────────────────────────────
class TestXlsRegression:
    @pytest.fixture(scope="class")
    def pc_with_data(self, session: requests.Session, auth_headers: dict):
        pid = _create_pros_cons(session, auth_headers)
        opt_id = _add_pc_option(session, auth_headers, pid, name="Option A")
        fac_id = _add_pc_factor(session, auth_headers, pid, name="Cost")
        return pid, opt_id, fac_id

    @pytest.fixture(scope="class")
    def md_with_data(self, session: requests.Session, auth_headers: dict):
        did = _create_decision(session, auth_headers)
        fid, oid = _seed_decision_factor_and_option(session, auth_headers, did)
        return did, fid, oid

    def test_pros_cons_template_download(self, session, auth_headers, pc_with_data):
        pid, _, _ = pc_with_data
        r = session.get(f"{BASE_URL}/api/pros-cons/{pid}/assessment-template",
                        headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"
        ctype = r.headers.get("content-type", "")
        assert "spreadsheet" in ctype or ctype.startswith(XLSX_MIME), f"bad content-type: {ctype}"
        assert len(r.content) > 1000, f"xlsx unexpectedly small: {len(r.content)} bytes"
        # XLSX = ZIP container → PK\x03\x04
        assert r.content[:2] == b"PK", "downloaded bytes do not look like xlsx (no PK header)"

    def test_decisions_template_download(self, session, auth_headers, md_with_data):
        did, _, _ = md_with_data
        r = session.get(f"{BASE_URL}/api/decisions/{did}/assessment-template",
                        headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text[:200]}"
        ctype = r.headers.get("content-type", "")
        assert "spreadsheet" in ctype or ctype.startswith(XLSX_MIME), f"bad content-type: {ctype}"
        assert len(r.content) > 1000, f"xlsx unexpectedly small: {len(r.content)} bytes"
        assert r.content[:2] == b"PK"

    def test_pros_cons_round_trip_import(self, session, auth_headers, pc_with_data):
        """Download the template and immediately re-upload it. Even with empty
        values it must parse cleanly (no exception) and return 200."""
        pid, _, _ = pc_with_data
        dl = session.get(f"{BASE_URL}/api/pros-cons/{pid}/assessment-template",
                         headers=auth_headers, timeout=30)
        assert dl.status_code == 200
        xlsx_bytes = dl.content

        # Multipart upload — must NOT inherit Content-Type=application/json from
        # the session, otherwise the multipart boundary header is dropped.
        files = {"file": ("assessment.xlsx", xlsx_bytes, XLSX_MIME)}
        up_headers = {"Authorization": auth_headers["Authorization"]}
        up = requests.post(
            f"{BASE_URL}/api/pros-cons/{pid}/assessment-import",
            headers=up_headers, files=files, timeout=60,
        )
        assert up.status_code == 200, f"import failed: {up.status_code} {up.text}"
        body = up.json()
        assert "applied" in body and "rows" in body, f"missing keys: {body}"
        assert isinstance(body["applied"], int)
        assert isinstance(body["rows"], int)
        # Empty template round-trip → rows can be 0 (no values filled) but call must succeed.
        assert body["applied"] >= 0
        assert body["rows"] >= 0
