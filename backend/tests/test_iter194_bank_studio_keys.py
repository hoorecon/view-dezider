"""Iter 194 — Option-Bank Finder (10M scale) + AdMaker Studio + AdTaker keys/portal.

Covers:
  • finder_bank pure logic — leaf-spec mapping, prefilter compilation, scoring
  • bank ingestion — sync-template (idempotent), bulk rail, stats, clear-by-source
  • async finder job — S1 indexed prune → S2 heap Top-K → done < 60s, cache hit,
    sponsored auction against bank options
  • AdMaker Studio — dashboard access (platform admin bypass), ownership guard
    on my/bids, free-user 403 (ACM gate)
  • AdTaker — API key+secret self-serve auth (valid/invalid/rotate), org-portal gate
"""
import sys
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from core.finder_bank import (  # noqa: E402
    build_leaf_specs, compile_prefilter, score_vals,
)


def _base_url() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.strip().startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.strip().split("=", 1)[1].rstrip("/")
    raise RuntimeError("no backend url")


API = f"{_base_url()}/api"
def _resolve_bmc() -> str:
    """The live Business Model Chooser Decider App (replaced bmp-55-patterns)."""
    import requests as _rq
    r = _rq.get(f"{API}/decider-store", timeout=30)
    return next(t["template_id"] for t in r.json()["templates"]
                if t.get("title") == "Business Model Chooser")


BMP = _resolve_bmc()


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def H(s):
    r = s.post(f"{API}/auth/login",
               json={"email": "super@test.com", "password": "SuperPass2026!"}, timeout=30)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


# ═══════════════════════ pure pipeline logic ═══════════════════════
class TestBankLogic:
    TEMPLATE = {"template_id": "t1", "factors": [
        {"id": "f1", "name": "Cost", "sub_factors": [
            {"id": "s_capex", "name": "Capex"}, {"id": "s_opex", "name": "Opex"}]},
        {"id": "f2", "name": "Color", "sub_factors": [{"id": "s_color", "name": "Shade"}]},
    ]}
    DECISION = {"id": "d1", "factors": [
        {"id": "top1", "name": "Cost", "category": "primary", "rating": 5, "parent_id": None},
        {"id": "L1", "name": "Capex", "parent_id": "top1", "source_sub_id": "s_capex",
         "operator": "<=", "expected_value": "50", "weight": 60},
        {"id": "L2", "name": "Opex", "parent_id": "top1",  # no source_sub_id → name match
         "operator": "<=", "expected_value": "20", "weight": 40},
        {"id": "top2", "name": "Color", "category": "secondary", "rating": 3, "parent_id": None},
        {"id": "L3", "name": "Shade", "parent_id": "top2", "source_sub_id": "s_color",
         "operator": "equals", "expected_value": "blue", "data_type": "text", "weight": 100},
    ]}

    def test_leaf_mapping_prefers_source_sub_id_and_falls_back_to_name(self):
        specs = build_leaf_specs(self.DECISION, self.TEMPLATE)
        assert len(specs) == 2
        sids = {lf["sid"] for lf in specs[0]["leaves"]}
        assert sids == {"s_capex", "s_opex"}  # L2 resolved via name match

    def test_prefilter_compiles_numeric_and_text(self):
        specs = build_leaf_specs(self.DECISION, self.TEMPLATE)
        clauses, residual = compile_prefilter(specs, ("primary", "secondary"), "all")
        assert {"vals.s_capex.num": {"$lte": 50.0}} in clauses
        assert {"vals.s_opex.num": {"$lte": 20.0}} in clauses
        assert any("vals.s_color.txt" in c for c in clauses)
        assert residual == []
        m_only, _ = compile_prefilter(specs, ("primary",), "all")
        assert len(m_only) == 2  # text factor is secondary → excluded

    def test_score_vals_weighted_rollup(self):
        specs = build_leaf_specs(self.DECISION, self.TEMPLATE)
        vals = {"s_capex": {"num": 50.0, "txt": "50"},   # exact target → 100
                "s_opex": {"num": 40.0, "txt": "40"},    # 20/40 → 50
                "s_color": {"num": None, "txt": "blue"}}  # match → 100
        worth = score_vals(vals, specs, has_rating=True)
        # cost factor: .6*100 + .4*50 = 80 → (5*80 + 3*100) / (8*100) = 87.5
        assert worth == 87.5


# ═══════════════════════ bank ingestion API ═══════════════════════
class TestBankIngestion:
    def test_sync_template_idempotent(self, s, H):
        r1 = s.post(f"{API}/decider-store/{BMP}/bank/sync-template", headers=H, timeout=60)
        assert r1.status_code == 200
        r2 = s.post(f"{API}/decider-store/{BMP}/bank/sync-template", headers=H, timeout=60)
        assert r2.status_code == 200 and r2.json()["inserted"] == 0  # idempotent
        st = s.get(f"{API}/decider-store/{BMP}/bank", headers=H, timeout=30).json()
        assert st["by_source"].get("template", 0) >= 50

    def test_bulk_rail_and_clear_by_source(self, s, H):
        items = [{"name": f"Iter194 Bulk {i}", "values": {"x": str(10 * i)}} for i in range(3)]
        r = s.post(f"{API}/decider-store/{BMP}/bank/ingest/bulk",
                   json={"items": items, "source": "deep_import"}, headers=H, timeout=30)
        assert r.status_code == 200 and r.json()["inserted"] == 3
        d = s.delete(f"{API}/decider-store/{BMP}/bank?source=deep_import", headers=H, timeout=30)
        assert d.json()["deleted"] == 3

    def test_partner_rail_validation(self, s, H):
        r = s.post(f"{API}/decider-store/{BMP}/bank/ingest/partner",
                   json={"api_url": "ftp://nope", "value_map": {"a": "b"}}, headers=H, timeout=30)
        assert r.status_code == 400
        r = s.post(f"{API}/decider-store/{BMP}/bank/ingest/partner",
                   json={"api_url": "https://example.org/x", "value_map": {}}, headers=H, timeout=30)
        assert r.status_code == 400


# ═══════════════════════ async finder job (scale) ═══════════════════════
class TestFinderJob:
    @pytest.fixture(scope="class")
    def decision(self, s, H):
        r = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "full"}, headers=H, timeout=60)
        assert r.status_code == 200
        did = r.json()["decision_id"]
        # Set a strict mandatory expectation on the first top factor so S1 prunes.
        d = s.get(f"{API}/decisions/{did}", headers=H, timeout=30).json()
        factors = d["factors"]
        tops = [f for f in factors if not f.get("parent_id")]
        t0 = tops[0]
        t0["category"], t0["rating"] = "primary", 5
        for f in factors:
            if f.get("parent_id") == t0["id"]:
                f["operator"], f["expected_value"] = ">=", "90"
        for t in tops[1:]:
            t["category"], t["rating"] = "secondary", 3
        assert s.put(f"{API}/decisions/{did}", json={"factors": factors},
                     headers=H, timeout=30).status_code == 200
        yield did
        s.delete(f"{API}/decisions/{did}", headers=H, timeout=30)

    def _poll(self, s, H, job_id, timeout_s=90):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            j = s.get(f"{API}/finder/jobs/{job_id}", headers=H, timeout=30).json()
            if j["status"] in ("done", "error"):
                return j
            time.sleep(1.0)
        raise AssertionError("job did not finish in time")

    def test_config_exposes_bank_count(self, s, H, decision):
        c = s.get(f"{API}/decisions/{decision}/finder/config", headers=H, timeout=30).json()
        assert c["bank_options"] >= 54  # real BMC bank (200K synthetic bank retired with bmp-55)

    def test_job_prunes_and_finishes_under_sla(self, s, H, decision):
        r = s.post(f"{API}/decisions/{decision}/finder/jobs",
                   json={"top_n": 5}, headers=H, timeout=30)
        assert r.status_code == 200
        job = self._poll(s, H, r.json()["job_id"])
        assert job["status"] == "done", job.get("error")
        res = job["result"]
        assert res["engine"] == "bank"
        assert res["total_options"] >= 54
        assert res["candidates"] < res["total_options"]      # S1 actually pruned
        assert len(res["top"]) == 5
        assert res["duration_ms"] < 60000                    # ≤ 60s SLA
        assert res["top"][0]["worth_percentage"] >= res["top"][4]["worth_percentage"]
        # cache hit on identical spec
        r2 = s.post(f"{API}/decisions/{decision}/finder/jobs",
                    json={"top_n": 5}, headers=H, timeout=30)
        assert r2.json()["cached"] is True

    def test_sponsored_auction_on_bank_results(self, s, H, decision):
        r = s.post(f"{API}/decisions/{decision}/finder/jobs",
                   json={"top_n": 5, "force": True}, headers=H, timeout=30)
        job = self._poll(s, H, r.json()["job_id"])
        target = job["result"]["top"][0]
        rb = s.post(f"{API}/admaker/bids", json={
            "template_id": BMP, "option_name": target["name"],
            "advertiser_name": "Iter194 Ads", "bid_paise": 900}, headers=H, timeout=30)
        assert rb.status_code == 200
        bid_id = rb.json()["bid_id"]
        try:
            r2 = s.post(f"{API}/decisions/{decision}/finder/jobs",
                        json={"top_n": 5, "force": True}, headers=H, timeout=30)
            job2 = self._poll(s, H, r2.json()["job_id"])
            spon = job2["result"]["sponsored"]
            assert len(spon) == 1 and spon[0]["bid_id"] == bid_id
            assert "bid_paise" not in spon[0]
        finally:
            s.delete(f"{API}/admaker/bids/{bid_id}", headers=H, timeout=30)


# ═══════════════════════ AdMaker Studio ═══════════════════════
class TestAdMakerStudio:
    def test_admin_dashboard_and_ownership_guard(self, s, H):
        d = s.get(f"{API}/admaker/my/dashboard", headers=H, timeout=30)
        assert d.status_code == 200 and "totals" in d.json()
        e = s.get(f"{API}/admaker/my/eligible-options?template_id={BMP}", headers=H, timeout=30)
        assert e.status_code == 200
        # ownership guard: an option NOT linked to caller's solutions → 403
        r = s.post(f"{API}/admaker/my/bids", json={
            "template_id": BMP, "option_name": "Definitely Not Owned Option",
            "advertiser_name": "x", "bid_paise": 100}, headers=H, timeout=30)
        assert r.status_code == 403

    def test_free_user_is_acm_locked(self, s):
        email = f"iter194_{uuid.uuid4().hex[:8]}@test.com"
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "Passw0rd!194", "name": "Iter194"},
                          timeout=30)
        assert r.status_code in (200, 201)
        tok = r.json().get("session_token") or requests.post(
            f"{API}/auth/login", json={"email": email, "password": "Passw0rd!194"},
            timeout=30).json()["session_token"]
        h = {"Authorization": f"Bearer {tok}"}
        d = requests.get(f"{API}/admaker/my/dashboard", headers=h, timeout=30)
        assert d.status_code == 403


# ═══════════════════════ AdTaker keys + portal ═══════════════════════
class TestAdTakerKeys:
    @pytest.fixture(scope="class")
    def pub(self, s, H):
        r = s.post(f"{API}/adtaker/publishers",
                   json={"name": f"Iter194 Pub {uuid.uuid4().hex[:4]}"}, headers=H, timeout=30)
        assert r.status_code == 200
        p = r.json()
        assert p["api_key"].startswith("dzk_") and p["api_secret"].startswith("dzs_")
        yield p
        s.delete(f"{API}/adtaker/publishers/{p['publisher_id']}", headers=H, timeout=30)

    def test_self_serve_auth_and_snippets(self, s, pub):
        good = {"X-Adtaker-Key": pub["api_key"], "X-Adtaker-Secret": pub["api_secret"]}
        prof = requests.get(f"{API}/adtaker/self/profile", headers=good, timeout=30)
        assert prof.status_code == 200
        assert "api_secret_hash" not in prof.json()
        assert requests.get(f"{API}/adtaker/self/profile",
                            headers={**good, "X-Adtaker-Secret": "dzs_wrong"},
                            timeout=30).status_code == 401
        apps = requests.get(f"{API}/adtaker/self/apps", headers=good, timeout=30).json()
        assert any(a["template_id"] == BMP for a in apps["apps"])
        assert pub["tracker_id"] in apps["apps"][0]["embed_snippet"]
        st = requests.get(f"{API}/adtaker/self/stats?days=7", headers=good, timeout=30)
        assert st.status_code == 200 and "earnings_estimate_paise" in st.json()

    def test_rotate_invalidates_old_secret(self, s, H, pub):
        rot = s.post(f"{API}/adtaker/publishers/{pub['publisher_id']}/rotate-keys",
                     headers=H, timeout=30).json()
        old = {"X-Adtaker-Key": pub["api_key"], "X-Adtaker-Secret": pub["api_secret"]}
        assert requests.get(f"{API}/adtaker/self/profile", headers=old, timeout=30).status_code == 401
        new = {"X-Adtaker-Key": rot["api_key"], "X-Adtaker-Secret": rot["api_secret"]}
        assert requests.get(f"{API}/adtaker/self/profile", headers=new, timeout=30).status_code == 200

    def test_org_portal_requires_org_identity(self, s, H):
        r = s.get(f"{API}/adtaker/portal/me", headers=H, timeout=30)
        assert r.status_code in (403, 404)  # super admin has no org_id
