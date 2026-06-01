"""
Iteration 33 — Solution Store bulk factor-value ingestion (Phase 2).

Covers:
  1. XLS template download (generic / prefilled / non-owner safety).
  2. Ingestion-token CRUD: generate / get / 403 for non-owners / 404 for missing.
  3. Webhook endpoint: pending submission, 401 missing, 401 invalid token, 400 empty.
  4. Google Sheet import: 400 helpful error on malformed; URL-coercion accepted but fetch may fail.
  5. XLS upload: openpyxl-built file -> pending_review with parsed_rows>=1; non-.xlsx -> 400.
  6. Admin review flow: list pending, approve -> values applied; reject -> no apply, 403 for non-admin.
  7. Ownership boundary: non-admin cannot create submission for other user's solution.
"""

import io
import os
import time
import uuid
import pytest
import requests
from openpyxl import Workbook

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "harden_1777921741@example.com"
OWNER_PASS = "HardenPass2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def owner_token():
    r = requests.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASS}, timeout=15)
    assert r.status_code == 200, f"owner login failed {r.status_code} {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed {r.status_code} {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def second_user_token():
    """A different non-admin user to test ownership boundaries."""
    email = f"TEST_owner_{int(time.time())}@example.com"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": "AutoPass2026!", "name": "TEST Owner"
    }, timeout=15)
    assert r.status_code in (200, 201), r.text[:200]
    return r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")


def h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def owned_solution(owner_token):
    """Create a solution_store entry owned by the OWNER user."""
    payload = {
        "name": f"TEST Solution {uuid.uuid4().hex[:6]}",
        "type": "PRODUCT",
        "category": "PRODUCT",
        "description": "iter33 ingestion test",
        "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 1000, "unit": "INR", "data_type": "numeric"}
        ],
    }
    r = requests.post(f"{API}/solutions-store/solutions", headers=h(owner_token), json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create solution failed {r.status_code} {r.text[:300]}"
    sol = r.json()
    sid = sol.get("solution_id") or sol.get("id") or (sol.get("solution") or {}).get("solution_id")
    assert sid, f"no solution_id returned: {sol}"
    return sid


# ---------- 1. Template download ----------
class TestTemplate:
    def test_generic_template(self, owner_token):
        r = requests.get(f"{API}/solutions-store/factor-template.xlsx", headers=h(owner_token), timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert "spreadsheetml" in r.headers.get("content-type", "")
        assert len(r.content) > 500

    def test_prefilled_for_owner(self, owner_token, owned_solution):
        r = requests.get(
            f"{API}/solutions-store/factor-template.xlsx",
            params={"solution_id": owned_solution},
            headers=h(owner_token), timeout=15,
        )
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")

    def test_non_owner_gets_generic_no_leak(self, second_user_token, owned_solution):
        r = requests.get(
            f"{API}/solutions-store/factor-template.xlsx",
            params={"solution_id": owned_solution},
            headers=h(second_user_token), timeout=15,
        )
        # should still return a generic template (no leak), not 403
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")


# ---------- 2. Ingestion token ----------
class TestIngestionToken:
    def test_generate_token_as_owner(self, owner_token, owned_solution):
        r = requests.post(f"{API}/solutions-store/{owned_solution}/ingestion-token",
                          headers=h(owner_token), timeout=15)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["token"].startswith("sk_ing_")
        assert body["header_name"] == "X-Ingestion-Token"
        assert body["webhook_path"].endswith("/factor-values/webhook")
        assert "sample_payload" in body and "rows" in body["sample_payload"]

    def test_get_token_returns_current(self, owner_token, owned_solution):
        r = requests.get(f"{API}/solutions-store/{owned_solution}/ingestion-token",
                         headers=h(owner_token), timeout=15)
        assert r.status_code == 200
        assert r.json().get("token", "").startswith("sk_ing_")

    def test_non_owner_forbidden(self, second_user_token, owned_solution):
        r = requests.post(f"{API}/solutions-store/{owned_solution}/ingestion-token",
                          headers=h(second_user_token), timeout=15)
        assert r.status_code == 403

    def test_nonexistent_solution_404(self, owner_token):
        r = requests.post(f"{API}/solutions-store/does-not-exist-xyz/ingestion-token",
                          headers=h(owner_token), timeout=15)
        assert r.status_code == 404


# ---------- 3. Webhook ----------
class TestWebhook:
    @pytest.fixture(scope="class")
    def token(self, owner_token, owned_solution):
        r = requests.post(f"{API}/solutions-store/{owned_solution}/ingestion-token",
                          headers=h(owner_token), timeout=15)
        return r.json()["token"]

    def test_missing_header(self):
        r = requests.post(f"{API}/solutions-store/factor-values/webhook",
                          json={"rows": [{"factor_name": "X", "value": 1}]}, timeout=15)
        assert r.status_code == 401

    def test_invalid_token(self):
        r = requests.post(f"{API}/solutions-store/factor-values/webhook",
                          headers={"X-Ingestion-Token": "bad", "Content-Type": "application/json"},
                          json={"rows": [{"factor_name": "X", "value": 1}]}, timeout=15)
        assert r.status_code == 401

    def test_empty_rows(self, token):
        r = requests.post(f"{API}/solutions-store/factor-values/webhook",
                          headers={"X-Ingestion-Token": token, "Content-Type": "application/json"},
                          json={"rows": []}, timeout=15)
        assert r.status_code == 400

    def test_valid_webhook_creates_pending(self, token):
        r = requests.post(f"{API}/solutions-store/factor-values/webhook",
                          headers={"X-Ingestion-Token": token, "Content-Type": "application/json"},
                          json={"rows": [
                              {"factor_name": "Latency", "factor_type": "quantitative",
                               "value": 42, "unit": "ms"}
                          ]}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["status"] == "pending_review"
        assert len(body["submissions"]) >= 1


# ---------- 4. Google Sheet import ----------
class TestGSheet:
    def test_malformed_link_400(self, owner_token, owned_solution):
        r = requests.post(f"{API}/solutions-store/factor-values/import-gsheet",
                          headers=h(owner_token),
                          json={"sheet_url": "https://example.com/not-a-sheet", "solution_id": owned_solution},
                          timeout=20)
        assert r.status_code == 400
        assert "sheet" in r.json().get("detail", "").lower() or "csv" in r.json().get("detail", "").lower()

    def test_empty_url_400(self, owner_token, owned_solution):
        r = requests.post(f"{API}/solutions-store/factor-values/import-gsheet",
                          headers=h(owner_token),
                          json={"sheet_url": "", "solution_id": owned_solution}, timeout=20)
        assert r.status_code == 400


# ---------- 5. XLS upload ----------
def _build_xlsx(solution_id, factor_name="Bandwidth", value=99):
    wb = Workbook()
    ws = wb.active
    ws.title = "Factor Values"
    headers = ["solution_id", "factor_name", "factor_type", "value", "unit", "currency", "source_note", "effective_date"]
    for ci, hd in enumerate(headers, start=1):
        ws.cell(row=1, column=ci, value=hd)
    row = [solution_id, factor_name, "quantitative", value, "Mbps", None, "iter33 test", "2026-01-15"]
    for ci, v in enumerate(row, start=1):
        ws.cell(row=2, column=ci, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestXlsUpload:
    def test_upload_creates_pending(self, owner_token, owned_solution):
        buf = _build_xlsx(owned_solution, factor_name="Bandwidth", value=99)
        files = {"file": ("upload.xlsx", buf,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/solutions-store/factor-values/upload",
                          headers={"Authorization": f"Bearer {owner_token}"},
                          files=files, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("status") == "pending_review"
        assert body.get("parsed_rows", 0) >= 1
        assert len(body.get("submissions", [])) >= 1

    def test_non_xlsx_rejected(self, owner_token):
        files = {"file": ("data.txt", io.BytesIO(b"not an xlsx"), "text/plain")}
        r = requests.post(f"{API}/solutions-store/factor-values/upload",
                          headers={"Authorization": f"Bearer {owner_token}"},
                          files=files, timeout=15)
        assert r.status_code == 400

    def test_non_owner_cannot_upload_to_owned_solution(self, second_user_token, owned_solution):
        buf = _build_xlsx(owned_solution, factor_name="NotMine", value=5)
        files = {"file": ("upload.xlsx", buf,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/solutions-store/factor-values/upload",
                          headers={"Authorization": f"Bearer {second_user_token}"},
                          files=files, timeout=20)
        # No submissions should be created -> 400 with "Not your solution"
        assert r.status_code == 400
        assert "your" in r.json().get("detail", "").lower() or "not" in r.json().get("detail", "").lower()


# ---------- 6. Admin review flow ----------
class TestReviewFlow:
    def test_list_pending_as_admin(self, admin_token):
        r = requests.get(f"{API}/solutions-store/factor-submissions",
                         params={"status": "pending"},
                         headers=h(admin_token), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_non_admin_cannot_approve(self, owner_token, admin_token):
        # find a pending submission
        r = requests.get(f"{API}/solutions-store/factor-submissions",
                         params={"status": "pending"}, headers=h(admin_token), timeout=15)
        items = r.json().get("items", [])
        if not items:
            pytest.skip("No pending submissions to test non-admin approve")
        sub_id = items[0]["submission_id"]
        r = requests.post(f"{API}/solutions-store/factor-submissions/{sub_id}/approve",
                          headers=h(owner_token), timeout=15)
        assert r.status_code == 403

    def test_approve_applies_to_solution(self, owner_token, admin_token, owned_solution):
        # Create a fresh submission via upload
        unique_factor = f"TestFactor_{uuid.uuid4().hex[:6]}"
        buf = _build_xlsx(owned_solution, factor_name=unique_factor, value=77)
        files = {"file": ("upload.xlsx", buf,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        ru = requests.post(f"{API}/solutions-store/factor-values/upload",
                           headers={"Authorization": f"Bearer {owner_token}"},
                           files=files, timeout=20)
        assert ru.status_code == 200, ru.text[:200]
        sub_id = ru.json()["submissions"][0]["submission_id"]

        # approve as admin
        ra = requests.post(f"{API}/solutions-store/factor-submissions/{sub_id}/approve",
                           headers=h(admin_token), timeout=15)
        assert ra.status_code == 200, ra.text[:200]
        assert ra.json().get("status") == "approved"

        # verify solution has the new factor
        rs = requests.get(f"{API}/solutions-store/solutions/{owned_solution}",
                          headers=h(owner_token), timeout=15)
        assert rs.status_code == 200
        qfs = rs.json().get("quantitative_factors") or rs.json().get("solution", {}).get("quantitative_factors") or []
        names = [(qf.get("factor_name") or "").lower() for qf in qfs]
        assert unique_factor.lower() in names, f"factor not applied. Got: {names}"
        # value check
        found = next((qf for qf in qfs if (qf.get("factor_name") or "").lower() == unique_factor.lower()), None)
        assert found and found.get("value") == 77

    def test_reject_does_not_apply(self, owner_token, admin_token, owned_solution):
        unique_factor = f"ToReject_{uuid.uuid4().hex[:6]}"
        buf = _build_xlsx(owned_solution, factor_name=unique_factor, value=11)
        files = {"file": ("upload.xlsx", buf,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        ru = requests.post(f"{API}/solutions-store/factor-values/upload",
                           headers={"Authorization": f"Bearer {owner_token}"},
                           files=files, timeout=20)
        assert ru.status_code == 200
        sub_id = ru.json()["submissions"][0]["submission_id"]

        rr = requests.post(f"{API}/solutions-store/factor-submissions/{sub_id}/reject",
                           headers=h(admin_token),
                           json={"note": "test reject"}, timeout=15)
        assert rr.status_code == 200
        assert rr.json().get("status") == "rejected"

        rs = requests.get(f"{API}/solutions-store/solutions/{owned_solution}",
                          headers=h(owner_token), timeout=15)
        qfs = rs.json().get("quantitative_factors") or rs.json().get("solution", {}).get("quantitative_factors") or []
        names = [(qf.get("factor_name") or "").lower() for qf in qfs]
        assert unique_factor.lower() not in names, "rejected factor should NOT be applied"

    def test_non_admin_cannot_reject(self, owner_token, admin_token):
        r = requests.get(f"{API}/solutions-store/factor-submissions",
                         params={"status": "pending"}, headers=h(admin_token), timeout=15)
        items = r.json().get("items", [])
        if not items:
            pytest.skip("No pending submissions to test non-admin reject")
        sub_id = items[0]["submission_id"]
        r = requests.post(f"{API}/solutions-store/factor-submissions/{sub_id}/reject",
                          headers=h(owner_token), json={"note": "x"}, timeout=15)
        assert r.status_code == 403
