"""Iteration 59 — Pros&Cons AI-assess + XLS template export/import (Phase C).

Covers:
- POST /api/pros-cons/{aid}/factors/{fid}/ai-assess
- GET  /api/pros-cons/{aid}/assessment-template
- POST /api/pros-cons/{aid}/assessment-import
- GET  /api/decisions/{did}/assessment-template
- POST /api/decisions/{did}/assessment-import
- XLS round-trip integrity (export → reupload → values applied)
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
EMAIL = "harden_1777921741@example.com"
PASSWORD = "HardenPass2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Pros & Cons setup ──────────────────────────────────────────────
@pytest.fixture(scope="module")
def pc(auth):
    """Create P&C analysis with 1 option + 1 main factor (with sub-factor)."""
    ts = int(time.time())
    r = requests.post(f"{BASE_URL}/api/pros-cons", json={"title": f"TEST_iter59_xls_{ts}", "context": "ctx"}, headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]

    o = requests.post(f"{BASE_URL}/api/pros-cons/{aid}/options", json={"name": "OptA"}, headers=auth, timeout=15)
    assert o.status_code == 200
    oid = o.json()["id"]

    fm = requests.post(f"{BASE_URL}/api/pros-cons/{aid}/factors",
                       json={"name": "Salary", "expected_value": "100000", "unit": "INR"}, headers=auth, timeout=15)
    assert fm.status_code == 200
    main_fid = fm.json()["id"]

    fs = requests.post(f"{BASE_URL}/api/pros-cons/{aid}/factors",
                       json={"name": "Bonus", "expected_value": "10000", "unit": "INR", "parent_id": main_fid}, headers=auth, timeout=15)
    assert fs.status_code == 200
    sub_fid = fs.json()["id"]

    # Set std_rating ladder
    requests.post(f"{BASE_URL}/api/pros-cons/{aid}/factors/reorder",
                  json={"ordered_ids": [main_fid, sub_fid]}, headers=auth, timeout=15)

    yield {"aid": aid, "oid": oid, "main_fid": main_fid, "sub_fid": sub_fid}

    # cleanup
    requests.delete(f"{BASE_URL}/api/pros-cons/{aid}", headers=auth, timeout=15)


# ════════════════════════════════════════════════════════════════════
# AI assess
# ════════════════════════════════════════════════════════════════════
class TestAIAssess:
    def test_ai_assess_requires_actual(self, auth, pc):
        r = requests.post(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/factors/{pc['main_fid']}/ai-assess",
            json={"option_id": pc["oid"]}, headers=auth, timeout=30,
        )
        assert r.status_code == 400, r.text
        assert "actual" in r.text.lower()

    def test_ai_assess_returns_pct_and_persists(self, auth, pc):
        r = requests.post(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/factors/{pc['main_fid']}/ai-assess",
            json={"option_id": pc["oid"], "actual_value": "95000"},
            headers=auth, timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "assessment_pct" in body and 0 <= body["assessment_pct"] <= 100
        assert "cell_value" in body
        assert body.get("source") in ("ai", "ratio")

        # Persisted: GET analysis and check assessments cell
        g = requests.get(f"{BASE_URL}/api/pros-cons/{pc['aid']}", headers=auth, timeout=15).json()
        cell = g.get("assessments", {}).get(pc["oid"], {}).get(pc["main_fid"], {})
        assert cell.get("assessment_pct") == body["assessment_pct"]
        assert str(cell.get("actual_value")) == "95000"

    def test_ai_assess_404_bad_factor(self, auth, pc):
        r = requests.post(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/factors/nonexistent-id/ai-assess",
            json={"option_id": pc["oid"], "actual_value": "1"}, headers=auth, timeout=15,
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# Pros & Cons XLS export/import
# ════════════════════════════════════════════════════════════════════
class TestPCXls:
    def test_export_returns_xlsx(self, auth, pc):
        r = requests.get(f"{BASE_URL}/api/pros-cons/{pc['aid']}/assessment-template", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        assert "spreadsheetml" in r.headers.get("content-type", "")
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert len(r.content) > 500  # non-empty xlsx
        # xlsx magic bytes (zip)
        assert r.content[:2] == b"PK"

    def test_round_trip_import(self, auth, pc):
        # 1) seed a cell via PUT assessment
        put = requests.put(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/assessments/{pc['oid']}/{pc['sub_fid']}",
            json={"assessment_pct": 75, "actual_value": "9500"},
            headers=auth, timeout=15,
        )
        assert put.status_code == 200

        # 2) download template (now has the pre-filled cell)
        r = requests.get(f"{BASE_URL}/api/pros-cons/{pc['aid']}/assessment-template", headers=auth, timeout=30)
        assert r.status_code == 200
        xlsx_bytes = r.content

        # 3) re-upload the SAME bytes — round-trip
        files = {"file": ("template.xlsx", xlsx_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        imp = requests.post(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/assessment-import",
            files=files, headers=auth, timeout=30,
        )
        assert imp.status_code == 200, imp.text
        body = imp.json()
        assert "applied" in body and "rows" in body
        # at least the sub-factor cell we pre-filled should be applied
        assert body["applied"] >= 1

        # 4) verify the sub-factor cell is still 75/9500
        g = requests.get(f"{BASE_URL}/api/pros-cons/{pc['aid']}", headers=auth, timeout=15).json()
        cell = g.get("assessments", {}).get(pc["oid"], {}).get(pc["sub_fid"], {})
        assert cell.get("assessment_pct") == 75
        assert str(cell.get("actual_value")) == "9500"

    def test_import_rejects_garbage(self, auth, pc):
        files = {"file": ("bad.xlsx", b"not a real xlsx", "application/octet-stream")}
        r = requests.post(
            f"{BASE_URL}/api/pros-cons/{pc['aid']}/assessment-import",
            files=files, headers=auth, timeout=15,
        )
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════
# My Dezider XLS export/import
# ════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def md(auth):
    ts = int(time.time())
    r = requests.post(f"{BASE_URL}/api/decisions",
                      json={"title": f"TEST_iter59_md_{ts}", "context": "ctx"},
                      headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    # Seed factor + option directly via PUT (update_decision accepts options+factors)
    main_fid = "f-main-iter59"
    sub_fid = "f-sub-iter59"
    oid = "o-iter59"
    payload = {
        "factors": [
            {"id": main_fid, "name": "Cost", "category": "primary", "rating": 8,
             "order": 0, "expected_value": "1000", "unit": "INR"},
            {"id": sub_fid, "name": "Tax", "category": "primary", "rating": 5,
             "order": 1, "expected_value": "100", "unit": "INR", "parent_id": main_fid},
        ],
        "options": [{"id": oid, "name": "OptA", "assessments": [], "worth_percentage": 0}],
    }
    u = requests.put(f"{BASE_URL}/api/decisions/{did}", json=payload, headers=auth, timeout=15)
    assert u.status_code == 200, u.text

    yield {"did": did, "main_fid": main_fid, "sub_fid": sub_fid, "oid": oid}

    requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=auth, timeout=15)


class TestMDXls:
    def test_export_returns_xlsx(self, auth, md):
        r = requests.get(f"{BASE_URL}/api/decisions/{md['did']}/assessment-template", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        assert "spreadsheetml" in r.headers.get("content-type", "")
        assert r.content[:2] == b"PK"
        assert len(r.content) > 500

    def test_round_trip_import(self, auth, md):
        # seed via PUT decision (option assessment)
        existing = requests.get(f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15).json()
        opts = existing["options"]
        opts[0]["assessments"] = [
            {"factor_id": md["main_fid"], "percentage": 60, "unit_value": "900", "assessment_mode": "custom"},
            {"factor_id": md["sub_fid"], "percentage": 80, "unit_value": "80", "assessment_mode": "custom"},
        ]
        u = requests.put(f"{BASE_URL}/api/decisions/{md['did']}",
                         json={"factors": existing["factors"], "options": opts}, headers=auth, timeout=15)
        assert u.status_code == 200

        # download
        r = requests.get(f"{BASE_URL}/api/decisions/{md['did']}/assessment-template", headers=auth, timeout=30)
        assert r.status_code == 200
        xlsx = r.content

        # re-upload
        files = {"file": ("md.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        imp = requests.post(f"{BASE_URL}/api/decisions/{md['did']}/assessment-import",
                            files=files, headers=auth, timeout=30)
        assert imp.status_code == 200, imp.text
        body = imp.json()
        assert body.get("applied", 0) >= 2

        # verify via GET
        g = requests.get(f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15).json()
        opt = g["options"][0]
        by_fid = {a["factor_id"]: a for a in opt["assessments"]}
        assert by_fid[md["main_fid"]]["percentage"] == 60
        assert str(by_fid[md["main_fid"]]["unit_value"]) == "900"
        assert by_fid[md["sub_fid"]]["percentage"] == 80
        assert str(by_fid[md["sub_fid"]]["unit_value"]) == "80"
        # worth recomputed (non-zero, since main factor cell exists)
        assert opt.get("worth_percentage", 0) > 0

    def test_import_rejects_garbage(self, auth, md):
        files = {"file": ("bad.xlsx", b"not xlsx", "application/octet-stream")}
        r = requests.post(f"{BASE_URL}/api/decisions/{md['did']}/assessment-import",
                          files=files, headers=auth, timeout=15)
        assert r.status_code == 400
