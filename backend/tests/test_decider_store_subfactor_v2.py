"""Iter (new sub-factor model) — The Decider Store: sub-factor architecture tests.

Verifies:
  - GET /api/decider-store/import-template.xlsx returns 2-sheet XLSX
  - POST /api/decider-store/import/excel with the downloaded template parses
    to factors with sub_factors[] and options with values keyed by sub-factor id
  - GET /api/decider-store/bmp-55-patterns returns 10 factors each with
    sub_factors[] and 54 options
  - POST /clone {full} creates a MyDezider decision with ~28 factors
    (one per sub-factor) and assessments carrying unit_value + num_value
  - POST /clone {values_only} works and strips classification
  - POST /push-to-stores returns solutions>0 & reviews>0
  - POST /sync-from-stores returns options synced without error
  - OLD collapsed-string format upload raises a clean 400 (not a crash)
"""
import base64
import io
import openpyxl
import pytest
import requests


def _base_url() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")


BASE_URL = _base_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "super@test.com"
ADMIN_PASS = "SuperPass2026!"


# ── Fixtures ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_headers(s):
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


# ══════════════════════════════════════════════════════════════════════════
# 1) Downloadable template (2 sheets)
# ══════════════════════════════════════════════════════════════════════════
class TestImportTemplate:
    def test_template_two_sheets_no_auth(self, s):
        r = s.get(f"{API}/decider-store/import-template.xlsx", timeout=30)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "").lower()
        assert "spreadsheetml" in ct
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        assert set(wb.sheetnames) == {"Template Data", "Instructions"}, \
            f"expected 2 sheets Template Data + Instructions, got {wb.sheetnames}"
        # Template Data sheet must contain Main Factor + Sub-Factor labels in col A
        ws = wb["Template Data"]
        colA = [str(ws.cell(r, 1).value or "").strip().lower() for r in range(1, 15)]
        assert any(x.startswith("main factor") for x in colA)
        assert any(x.startswith("sub-factor") or x.startswith("sub factor") for x in colA)


# ══════════════════════════════════════════════════════════════════════════
# 2) Admin import/excel — round-trip parses downloaded template
# ══════════════════════════════════════════════════════════════════════════
class TestImportExcelParse:
    def test_upload_downloaded_template_parses_new_model(self, s, admin_headers):
        # Download the freshly generated template …
        r = s.get(f"{API}/decider-store/import-template.xlsx", timeout=30)
        assert r.status_code == 200
        b64 = base64.b64encode(r.content).decode()
        # … then upload it as base64
        r = s.post(f"{API}/decider-store/import/excel",
                   json={"file_b64": b64}, headers=admin_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        data = r.json()
        factors = data["factors"]
        options = data["options"]
        # 3 sample factors: Org Type / Solution Category / Affordability
        assert len(factors) == 3, f"expected 3 factors got {len(factors)}"
        assert factors[0]["name"] == "Org Type"
        assert factors[0]["category"] == "mandatory"
        assert factors[0]["priority"] == 1
        assert factors[0]["factor_type"] == "qualitative"
        subs = factors[0]["sub_factors"]
        assert [s["name"] for s in subs] == ["Solo %", "Startup %", "SME %", "Corporate %"]
        # data_type / ui_object / split_pct
        assert subs[0]["data_type"] == "%"
        assert subs[0]["ui_object"] == "Input Box"
        assert sum(s["split_pct"] for s in subs) == 100
        # each option's values are keyed by sub-factor id AND every value is {raw,num}
        assert len(options) == 2
        opt = options[0]
        assert opt["name"] == "AFFILIATION"
        sub_ids = {s["id"] for f in factors for s in f["sub_factors"]}
        for sid, cell in opt["values"].items():
            assert sid in sub_ids
            assert set(cell.keys()) >= {"raw", "num"}
        # AFFILIATION → Solo=100
        solo_id = next(s["id"] for s in factors[0]["sub_factors"] if s["name"] == "Solo %")
        assert opt["values"][solo_id]["num"] == 100.0

    def test_old_collapsed_format_returns_400(self, s, admin_headers):
        """OLD format sheet (single 'Values (with suitability%)' row) must NOT
        crash — a clear 400 is expected."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Factor", "Values (with suitability%)"])
        ws.append(["Org Type", "Solo, Startup (40%)"])
        buf = io.BytesIO()
        wb.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        r = s.post(f"{API}/decider-store/import/excel",
                   json={"file_b64": b64}, headers=admin_headers, timeout=30)
        assert r.status_code == 400, f"expected 400 for old format got {r.status_code}"
        # Message must be human — mention Main-Factor / Sub-Factor
        msg = (r.json() or {}).get("detail") or ""
        assert "Main-Factor" in msg or "Sub-Factor" in msg or "template" in msg.lower()


# ══════════════════════════════════════════════════════════════════════════
# 3) Seeded BMP template — new sub-factor model
# ══════════════════════════════════════════════════════════════════════════
class TestBmpSeed:
    def test_bmp_has_sub_factors(self, s):
        r = s.get(f"{API}/decider-store/bmp-55-patterns", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["factors"]) == 10
        assert len(d["options"]) == 54
        # every factor MUST have sub_factors[] non-empty
        subs_total = 0
        for f in d["factors"]:
            subs = f.get("sub_factors") or []
            assert len(subs) >= 1, f"factor {f.get('name')!r} has no sub_factors"
            subs_total += len(subs)
            for sf in subs:
                assert sf.get("id")
                assert sf.get("name")
                assert "split_pct" in sf
        assert subs_total >= 20, f"expected ~28 sub-factors got {subs_total}"
        # Org Type breakdown matches the new spec
        org = next(f for f in d["factors"] if f["name"] == "Org Type")
        names = [s["name"] for s in org["sub_factors"]]
        assert names == ["Solo %", "Startup %", "SME %", "Corporate %"]
        # options[0].values keyed by sub-factor id
        opt = d["options"][0]
        vals = opt["values"]
        assert vals
        sub_ids = {sf["id"] for f in d["factors"] for sf in f["sub_factors"]}
        for sid, cell in vals.items():
            assert sid in sub_ids
            assert isinstance(cell, dict) and "raw" in cell and "num" in cell


# ══════════════════════════════════════════════════════════════════════════
# 4) Clone — one MyDezider factor per sub-factor (~28)
# ══════════════════════════════════════════════════════════════════════════
class TestClone:
    def test_clone_full_expands_sub_factors(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/clone",
                   json={"mode": "full"}, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text[:400]
        info = r.json()
        did = info["decision_id"]
        # ~28 factors (10 main × sub-factors)
        assert info["factors"] >= 20, f"expected ~28 got {info['factors']}"
        assert info["options"] == 54

        # Fetch decision & validate
        r = s.get(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        dec = r.json()
        assert len(dec["factors"]) == info["factors"]
        # display name: "Org Type — Solo %"
        by_name = {f["name"]: f for f in dec["factors"]}
        assert any(name.startswith("Org Type") and "Solo" in name for name in by_name)
        f0 = dec["factors"][0]
        assert f0["category"] in ("primary", "mandatory", "optional")
        # option assessments carry unit_value + num_value; percentage=None
        opt0 = dec["options"][0]
        assert len(opt0["assessments"]) > 0
        a0 = opt0["assessments"][0]
        assert a0.get("percentage") is None
        assert isinstance(a0.get("unit_value"), str)
        # at least one assessment should have a numeric num_value
        assert any(isinstance(a.get("num_value"), (int, float))
                   for a in opt0["assessments"]), "no num_value found"
        # cleanup
        s.delete(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)

    def test_clone_values_only_strips_classification(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/clone",
                   json={"mode": "values_only"}, headers=admin_headers, timeout=60)
        assert r.status_code == 200
        did = r.json()["decision_id"]
        r = s.get(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        dec = r.json()
        f0 = dec["factors"][0]
        assert f0["category"] == ""
        assert f0["rating"] == 0
        s.delete(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)


# ══════════════════════════════════════════════════════════════════════════
# 5) Push / Sync bridges
# ══════════════════════════════════════════════════════════════════════════
class TestBridges:
    def test_push_to_stores(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/push-to-stores",
                   headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("solutions", 0) > 0
        assert d.get("reviews", 0) > 0

    def test_sync_from_stores(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/bmp-55-patterns/sync-from-stores",
                   headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert "options" in d
        assert isinstance(d["options"], int)

    def test_push_requires_admin(self):
        r = requests.post(f"{API}/decider-store/bmp-55-patterns/push-to-stores", timeout=30)
        assert r.status_code in (401, 403)

    def test_sync_requires_admin(self):
        r = requests.post(f"{API}/decider-store/bmp-55-patterns/sync-from-stores", timeout=30)
        assert r.status_code in (401, 403)
