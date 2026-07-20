"""Iter 190 — Decider Store Bridge tests (STRATEGY, push/sync/from-solutions, auto-push).

Runs against the public preview URL derived from frontend/.env (EXPO_PUBLIC_BACKEND_URL).
"""
import os
import pytest
import requests


def _base_url() -> str:
    env_path = "/app/frontend/.env"
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")


BASE_URL = _base_url()
API = f"{BASE_URL}/api"
TID = "bmp-55-patterns"

ADMIN_EMAIL = "super@test.com"
ADMIN_PASS = "SuperPass2026!"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_headers(s):
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


# ── STRATEGY solution type ─────────────────────────────────────────────
class TestStrategyType:
    _sid = None

    def test_create_strategy_solution(self, s, admin_headers):
        r = s.post(
            f"{API}/solutions-store/solutions",
            json={"type": "STRATEGY", "name": "TEST_iter190_strategy", "visibility": "PRIVATE"},
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        j = r.json()
        assert j.get("type") == "STRATEGY", f"expected STRATEGY got {j.get('type')}"
        assert j.get("name") == "TEST_iter190_strategy"
        sid = j.get("id") or j.get("solution_id")
        assert sid, f"no id/solution_id in response: {list(j.keys())}"
        TestStrategyType._sid = sid

    def test_get_strategy_persisted(self, s, admin_headers):
        sid = TestStrategyType._sid
        assert sid
        r = s.get(f"{API}/solutions-store/solutions/{sid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("type") == "STRATEGY"

    def test_cleanup_strategy(self, s, admin_headers):
        sid = TestStrategyType._sid
        if not sid:
            pytest.skip("no sid")
        # try delete; ignore failure since it's cleanup
        try:
            s.delete(f"{API}/solutions-store/solutions/{sid}", headers=admin_headers, timeout=30)
        except Exception:
            pass


# ── PUSH / SYNC / FROM-SOLUTIONS (positive + negative) ─────────────────
class TestBridge:
    def test_push_to_stores(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/{TID}/push-to-stores", headers=admin_headers, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("solutions") == 54, f"expected 54 solutions got {j.get('solutions')}"
        assert j.get("reviews") == 54, f"expected 54 reviews got {j.get('reviews')}"

    def test_option_carries_linked_solution_id(self, s, admin_headers):
        r = s.get(f"{API}/decider-store/{TID}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        t = r.json()
        opts = t.get("options", [])
        assert opts, "no options in template"
        linked = [o for o in opts if o.get("linked_solution_id")]
        assert len(linked) == 54, f"expected 54 linked options, got {len(linked)}"
        # keep first two ids for downstream test
        TestBridge._sids = [o["linked_solution_id"] for o in linked[:3]]

    def test_linked_solution_is_strategy_with_decider_ref(self, s, admin_headers):
        sids = getattr(TestBridge, "_sids", [])
        assert sids
        r = s.get(f"{API}/solutions-store/solutions/{sids[0]}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j.get("type") == "STRATEGY", f"got {j.get('type')}"
        assert j.get("decider_template_id") == TID

    def test_reviewnet_baseline_created(self, s, admin_headers):
        sids = getattr(TestBridge, "_sids", [])
        assert sids
        r = s.get(f"{API}/review-net/reviews", params={"solution_id": sids[0]}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        items = r.json().get("items", []) or r.json().get("reviews", [])
        base = [i for i in items if i.get("is_baseline")]
        assert base, f"no baseline review found for {sids[0]}; items={len(items)}"
        b = base[0]
        fr = b.get("factor_ratings") or {}
        assert fr, "empty factor_ratings"
        # all values within 1..5
        for k, v in fr.items():
            try:
                fv = float(v)
            except Exception:
                fv = float(v.get("rating", 0)) if isinstance(v, dict) else 0
            assert 1 <= fv <= 5, f"factor rating {k}={v} out of 1..5"
        bp = b.get("baseline_profile")
        assert isinstance(bp, dict) and bp, "baseline_profile missing/empty"

    def test_sync_from_stores(self, s, admin_headers):
        r = s.post(f"{API}/decider-store/{TID}/sync-from-stores", headers=admin_headers, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("options") == 54, f"expected options=54 got {j.get('options')}"

    def test_from_solutions_build_template(self, s, admin_headers):
        sids = getattr(TestBridge, "_sids", [])[:2]
        assert len(sids) == 2
        r = s.post(
            f"{API}/decider-store/from-solutions",
            json={"solution_ids": sids, "title": "TEST_iter190_from_solutions"},
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        new_tid = j.get("template_id")
        assert new_tid
        # Fetch and validate
        r2 = s.get(f"{API}/decider-store/{new_tid}", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        tpl = r2.json()
        assert len(tpl.get("options", [])) == 2
        assert len(tpl.get("factors", [])) > 0
        # cleanup
        s.delete(f"{API}/decider-store/{new_tid}", headers=admin_headers, timeout=30)

    # ── Negative auth ───────────────────────────────────────────────
    def test_push_requires_admin(self):
        r = requests.post(f"{API}/decider-store/{TID}/push-to-stores", timeout=30)
        assert r.status_code in (401, 403)

    def test_sync_requires_admin(self):
        r = requests.post(f"{API}/decider-store/{TID}/sync-from-stores", timeout=30)
        assert r.status_code in (401, 403)

    def test_from_solutions_requires_admin(self):
        r = requests.post(f"{API}/decider-store/from-solutions",
                          json={"solution_ids": ["x"], "title": "x"}, timeout=30)
        assert r.status_code in (401, 403)


# ── AUTO-PUSH ON AUTHORIZE ─────────────────────────────────────────────
class TestAutoPush:
    def test_auto_push_on_authorize(self, s, admin_headers):
        # Build a tiny template with auto_push_on_authorize=true and status='draft'
        body = {
            "title": "TEST_iter190_autopush",
            "subtitle": "",
            "description": "",
            "category": "Business",
            "decision_type": "aspiration",
            "pricing_type": "free",
            "allowed_clone_modes": ["full", "values_only"],
            "auto_push_on_authorize": True,
            "status": "draft",
            "is_public": False,
            "factors": [
                {"name": "Cost", "factor_type": "quantitative", "unit_type": "currency",
                 "values": [{"label": "Low", "score": 5}, {"label": "High", "score": 1}]},
                {"name": "Fit", "factor_type": "qualitative",
                 "values": [{"label": "Good", "score": 5}, {"label": "Bad", "score": 1}]},
            ],
            "options": [
                {"name": "TEST_iter190_optA", "assessments": [
                    {"factor_name": "Cost", "unit_value": "Low"},
                    {"factor_name": "Fit", "unit_value": "Good"},
                ]},
                {"name": "TEST_iter190_optB", "assessments": [
                    {"factor_name": "Cost", "unit_value": "High"},
                    {"factor_name": "Fit", "unit_value": "Bad"},
                ]},
            ],
        }
        r = s.post(f"{API}/decider-store", json=body, headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        created = r.json()
        tid = created["template_id"]
        try:
            # If server auto-authorized on create (common), the auto_pushed may be in the create response.
            ap = created.get("auto_pushed")
            if ap is None:
                # Explicit authorize
                r2 = s.post(f"{API}/decider-store/{tid}/authorize", headers=admin_headers, timeout=60)
                assert r2.status_code == 200, f"{r2.status_code} {r2.text[:300]}"
                jj = r2.json()
                ap = jj.get("auto_pushed")
            assert ap is not None, "auto_pushed field missing from authorize response"
            assert isinstance(ap, dict)
            # expect solution count >=1 (reviews may be 0 if template lacks qualitative assessments)
            assert ap.get("solutions", 0) >= 1, f"auto_pushed solutions=0 in {ap}"
            assert "reviews" in ap, f"auto_pushed missing 'reviews' key: {ap}"
        finally:
            s.delete(f"{API}/decider-store/{tid}", headers=admin_headers, timeout=30)
