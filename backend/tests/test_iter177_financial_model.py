"""ITER 177 backend tests — Financial Model (Phase 1):
  • GET  /api/financial-models/meta      (default_assumptions, units, currencies, historical_stages)
  • POST /api/financial-models/compute   (stateless 3-statement + valuation; BS ties out; edge case w/ growth)
  • POST /api/financial-models           (CRUD with ownership check via user_org)
  • GET  /api/financial-models?user_org_id=...
  • GET  /api/financial-models/{id}      (model + computed)
  • PUT  /api/financial-models/{id}      (recompute reflects assumption changes)
  • DELETE /api/financial-models/{id}
  • Non-owned org rejection
"""
import os
import uuid

import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "super@test.com", "password": "SuperPass2026!"}


# ───────────────────────────── Fixtures ─────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=OWNER, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("access_token") or j.get("token") or j.get("session_token")
    assert tok, f"No token in login: {j}"
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def owned_org(session):
    """Create a Custom Org owned by super@test.com (POST /api/seven-seven/orgs)."""
    body = {
        "name": f"TEST_iter177 FinModel Co {uuid.uuid4().hex[:6]}",
        "org_type": "BUSINESS",
        "life_area": "finance",
        "sub_area": "",
        "description": "iter177 financial model owner org",
        "icon": "business",
        "color": "#4338CA",
    }
    r = session.post(f"{API}/seven-seven/orgs", json=body, timeout=30)
    assert r.status_code == 200, f"Org create failed: {r.status_code} {r.text}"
    j = r.json()
    org = j.get("user_org") or j
    assert org.get("id"), f"No org id: {j}"
    yield org
    # cleanup (soft-delete)
    try:
        session.delete(f"{API}/seven-seven/orgs/{org['id']}", timeout=20)
    except Exception:
        pass


@pytest.fixture(scope="module")
def meta(session):
    r = session.get(f"{API}/financial-models/meta", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


# ───────────────────────────── meta ─────────────────────────────
class TestMeta:
    def test_meta_shape(self, meta):
        # default_assumptions present + has revenue_by_year (list of 5)
        da = meta.get("default_assumptions")
        assert isinstance(da, dict) and da
        assert isinstance(da.get("revenue_by_year"), list) and len(da["revenue_by_year"]) == 5

    def test_units_default_absolute(self, meta):
        units = meta.get("units")
        assert isinstance(units, list) and len(units) >= 5
        assert units[0]["id"] == "absolute", f"first unit must be 'absolute', got {units[0]}"
        ids = {u["id"] for u in units}
        assert {"absolute", "thousands", "lakhs", "millions", "crores"}.issubset(ids), ids

    def test_currencies_includes_inr_and_usd(self, meta):
        ccy = meta.get("currencies") or []
        assert "INR" in ccy and "USD" in ccy

    def test_historical_stages_order(self, meta):
        stages = [h["id"] for h in (meta.get("historical_stages") or [])]
        assert stages == ["pre_revenue", "3m", "6m", "9m", "1y", "2y"], stages

    def test_max_projection_years(self, meta):
        assert int(meta.get("max_projection_years") or 0) >= 5


# ─────────────────────── stateless /compute ───────────────────────
class TestCompute:
    def test_compute_with_defaults_balances_and_valuation(self, session, meta):
        body = {"assumptions": meta["default_assumptions"], "projection_years": 5}
        r = session.post(f"{API}/financial-models/compute", json=body, timeout=30)
        assert r.status_code == 200, r.text
        comp = r.json().get("computed")
        assert comp, "no computed payload"
        # P&L / BS / CF / Ratios / Valuation sections exist
        for k in ("pnl", "balance_sheet", "cash_flow", "ratios", "valuation", "summary"):
            assert k in comp, f"missing {k}"
        # BS ties out every year
        bs = comp["balance_sheet"]
        checks = bs["balance_check"]
        assert len(checks) == 5
        for i, c in enumerate(checks):
            assert abs(c) < 1.0, f"balance_check[{i}]={c} not ~0; BS does not tie out"
        # Valuation has numeric EV / Equity / per-share
        v = comp["valuation"]
        for k in ("enterprise_value", "equity_value", "per_share"):
            assert isinstance(v.get(k), (int, float)), f"{k} not numeric: {v.get(k)}"
        # ratios.dscr is a 5-list
        dscr = comp["ratios"]["dscr"]
        assert isinstance(dscr, list) and len(dscr) == 5
        # summary
        s = comp["summary"]
        assert isinstance(s.get("revenue_cagr_pct"), (int, float))
        assert isinstance(s.get("dscr_avg"), (int, float))

    def test_compute_growth_only(self, session):
        """Edge case: empty revenue_by_year + year1_revenue + growth → still computes."""
        body = {
            "assumptions": {
                "revenue_by_year": [],
                "year1_revenue": 5_000_000,
                "revenue_growth_pct": 50,
                "gross_margin_pct": 50, "opex_pct": 30,
                "depreciation_pct": 10, "tax_rate_pct": 25,
                "interest_rate_pct": 10, "wacc_pct": 18, "terminal_growth_pct": 4,
                "shares_outstanding": 100_000,
            },
            "projection_years": 5,
        }
        r = session.post(f"{API}/financial-models/compute", json=body, timeout=30)
        assert r.status_code == 200, r.text
        comp = r.json().get("computed") or {}
        rev = comp["pnl"]["revenue"]
        assert len(rev) == 5
        # year2 should be ~year1 * 1.5
        assert rev[0] > 0 and rev[1] > rev[0]
        assert abs(rev[1] - rev[0] * 1.5) < max(1.0, rev[0] * 0.01)
        # BS still ties
        for c in comp["balance_sheet"]["balance_check"]:
            assert abs(c) < 1.0


# ────────────────────────── CRUD with ownership ──────────────────────────
_CREATED_MODEL_IDS = []


class TestCRUD:
    def test_create_model_persists_with_computed(self, session, meta, owned_org):
        body = {
            "user_org_id": owned_org["id"],
            "name": "TEST_iter177 Model A",
            "currency": "INR",
            "units": "absolute",
            "projection_years": 5,
            "assumptions": meta["default_assumptions"],
        }
        r = session.post(f"{API}/financial-models", json=body, timeout=30)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m.get("id") and m["user_org_id"] == owned_org["id"]
        assert m.get("computed"), "create response should include computed"
        # BS ties
        for c in m["computed"]["balance_sheet"]["balance_check"]:
            assert abs(c) < 1.0
        _CREATED_MODEL_IDS.append(m["id"])

    def test_create_with_fake_user_org_returns_404(self, session, meta):
        body = {
            "user_org_id": f"fake-{uuid.uuid4()}",
            "name": "TEST_iter177 Bad Org",
            "assumptions": meta["default_assumptions"],
        }
        r = session.post(f"{API}/financial-models", json=body, timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"

    def test_list_includes_created_model(self, session, owned_org):
        assert _CREATED_MODEL_IDS, "previous test must have created a model"
        r = session.get(f"{API}/financial-models", params={"user_org_id": owned_org["id"]}, timeout=20)
        assert r.status_code == 200, r.text
        rows = r.json().get("models") or []
        ids = {m["id"] for m in rows}
        assert _CREATED_MODEL_IDS[0] in ids, f"model not in list: {ids}"

    def test_get_model_returns_model_plus_computed(self, session):
        mid = _CREATED_MODEL_IDS[0]
        r = session.get(f"{API}/financial-models/{mid}", timeout=20)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["id"] == mid and m.get("assumptions")
        assert m.get("computed") and m["computed"].get("pnl")

    def test_put_recomputes(self, session):
        mid = _CREATED_MODEL_IDS[0]
        # Snapshot before
        before = session.get(f"{API}/financial-models/{mid}", timeout=20).json()
        gp_before = before["computed"]["pnl"]["gross_profit"][0]
        new_assumptions = dict(before["assumptions"])
        new_assumptions["gross_margin_pct"] = 75  # was 55
        r = session.put(f"{API}/financial-models/{mid}",
                        json={"assumptions": new_assumptions}, timeout=30)
        assert r.status_code == 200, r.text
        after = r.json()
        gp_after = after["computed"]["pnl"]["gross_profit"][0]
        assert gp_after > gp_before, f"gross_profit should rise after GM 55→75: {gp_before}→{gp_after}"
        # Verify persistence via GET
        verify = session.get(f"{API}/financial-models/{mid}", timeout=20).json()
        assert verify["assumptions"]["gross_margin_pct"] == 75

    def test_delete_then_get_404(self, session):
        mid = _CREATED_MODEL_IDS[0]
        r = session.delete(f"{API}/financial-models/{mid}", timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # second GET should 404
        r2 = session.get(f"{API}/financial-models/{mid}", timeout=20)
        assert r2.status_code == 404
        _CREATED_MODEL_IDS.remove(mid)
