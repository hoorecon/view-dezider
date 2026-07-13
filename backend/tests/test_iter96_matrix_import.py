"""iter96 — verify Step-2 matrix import endpoints + Step-7 import-actuals-from-url.
Covers:
  - POST /api/decisions/{id}/import-actuals-from-url  (consent gate + happy path)
  - GET  /api/decisions/{id}/factor-matrix-template.xlsx
  - POST /api/decisions/{id}/import-matrix-file (CSV)
  - POST /api/decisions/{id}/import-matrix-sheet (validation)
"""
import io
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")

SUPER_ADMIN = {
    "email": "veales.vedic.decisions@gmail.com",
    "password": "Jelcos@Admin2026",
}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token returned: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def decision_id(headers):
    """Create a minimal decision with 2 options and 2 factors so we can hit
    import-actuals-from-url + factor-matrix-template + import-matrix-file."""
    payload = {
        "title": f"TEST_iter96_matrix_{int(time.time())}",
        "description": "Test decision for matrix import endpoints",
        "context": "Compare two phones for testing matrix import",
    }
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text[:200]}"
    did = r.json().get("id") or r.json().get("decision_id") or r.json().get("decision", {}).get("id")
    assert did, f"no decision id: {r.json()}"

    # Add 2 options + 2 factors. The decision API uses PATCH with options/factors arrays.
    upd = {
        "options": [
            {"id": "opt_test_a", "name": "Samsung Galaxy A57"},
            {"id": "opt_test_b", "name": "Oppo F9"},
        ],
        "factors": [
            {"id": "fac_test_disp", "name": "Display Size", "weight": 50, "data_type": "numeric"},
            {"id": "fac_test_bat", "name": "Battery", "weight": 50, "data_type": "numeric"},
        ],
    }
    r2 = requests.patch(f"{BASE_URL}/api/decisions/{did}", json=upd, headers=headers, timeout=20)
    # Some implementations use PUT instead
    if r2.status_code >= 400:
        r2 = requests.put(f"{BASE_URL}/api/decisions/{did}", json=upd, headers=headers, timeout=20)
    assert r2.status_code < 400, f"update decision: {r2.status_code} {r2.text[:200]}"

    yield did

    # cleanup
    requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=headers, timeout=15)


# ───────── factor-matrix-template (.xlsx) ─────────
class TestMatrixTemplate:
    def test_download_template_returns_xlsx(self, headers, decision_id):
        r = requests.get(
            f"{BASE_URL}/api/decisions/{decision_id}/factor-matrix-template.xlsx",
            headers={"Authorization": headers["Authorization"]},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        ct = r.headers.get("content-type", "")
        assert "spreadsheet" in ct or "xlsx" in ct or "octet-stream" in ct, f"ct={ct}"
        assert r.content[:2] == b"PK", "xlsx (zip) magic bytes missing"
        assert len(r.content) > 200


# ───────── import-matrix-file (CSV upload) ─────────
class TestMatrixImportFile:
    def test_csv_import_returns_counts(self, headers, decision_id):
        csv = (
            "Option,Display Size,Battery\n"
            "Samsung Galaxy A57,6.7,5000\n"
            "Oppo F9,6.3,3500\n"
        ).encode("utf-8")
        files = {"file": ("matrix.csv", io.BytesIO(csv), "text/csv")}
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-matrix-file",
            headers={"Authorization": headers["Authorization"]},
            files=files, timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        for k in ("factors_added", "options_added", "item_count", "factor_count"):
            assert k in data, f"missing key {k} in {data}"
        assert data["item_count"] == 2
        assert data["factor_count"] == 2

    def test_empty_file_rejected(self, headers, decision_id):
        files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-matrix-file",
            headers={"Authorization": headers["Authorization"]},
            files=files, timeout=15,
        )
        assert r.status_code == 422, f"{r.status_code} {r.text[:200]}"


# ───────── import-matrix-sheet (validation) ─────────
class TestMatrixImportSheet:
    def test_invalid_sheet_url_rejected(self, headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-matrix-sheet",
            json={"sheet_url": "not-a-sheet"}, headers=headers, timeout=15,
        )
        assert r.status_code == 422, f"{r.status_code} {r.text[:200]}"


# ───────── import-actuals-from-url (Step 7) ─────────
class TestImportActualsFromUrl:
    def test_consent_gate_rejects_without_accepted(self, headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-actuals-from-url",
            json={
                "url": "https://www.gsmarena.com/compare.php3?idPhone1=12345",
                "eligibility_type": "free_public",
                "accepted": False,
            },
            headers=headers, timeout=15,
        )
        assert r.status_code == 400, f"expected 400 consent gate, got {r.status_code} {r.text[:200]}"

    def test_invalid_eligibility_rejected(self, headers, decision_id):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-actuals-from-url",
            json={
                "url": "https://www.gsmarena.com/compare.php3?idPhone1=12345",
                "eligibility_type": "bogus_value",
                "accepted": True,
            },
            headers=headers, timeout=15,
        )
        assert r.status_code == 400, f"{r.status_code} {r.text[:200]}"

    def test_happy_path_returns_filled_cells_or_422(self, headers, decision_id):
        """Live URL fetch may be transient; accept 200 (with shape) OR 422
        (could-not-extract)."""
        r = requests.post(
            f"{BASE_URL}/api/decisions/{decision_id}/import-actuals-from-url",
            json={
                "url": "https://www.gsmarena.com/compare.php3?idPhone1=13405&idPhone2=9305",
                "eligibility_type": "free_public",
                "accepted": True,
            },
            headers=headers, timeout=60,
        )
        if r.status_code == 200:
            data = r.json()
            assert "filled_cells" in data, f"missing filled_cells in {data}"
            assert "matched_options" in data, f"missing matched_options in {data}"
            assert isinstance(data["filled_cells"], int)
            assert isinstance(data["matched_options"], int)
        else:
            # transient network / extractor miss is acceptable; ensure it's a
            # graceful 4xx not a 5xx
            assert r.status_code in (422, 400), f"unexpected status {r.status_code} {r.text[:200]}"
