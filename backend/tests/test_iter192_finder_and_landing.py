"""Iter 192 — DeciderApp / Finder + Landing + clone-as-hierarchy tests.

Covers:
  • POST /decider-store/bmp-55-patterns/clone (mode=full & values_only) — hierarchy
  • GET  /decisions/{id}/finder/config
  • POST /decisions/{id}/finder/run (deterministic, funnel effect, body override)
  • GET/PUT /admin/ai-wallet/config (finder_* keys) reflect in finder/config
  • GET  /decider-store/landing (public), PUT /decider-store/landing (admin),
    GET /decider-store/landing.html
  • GET  /decider-store?kind=app / kind=template segmentation
  • PUT  /decider-store/{id} kind toggle (template<->app)
"""
import os
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
BMP = "bmp-55-patterns"

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _login(s, email, password):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def super_headers(s):
    return _login(s, SUPER_EMAIL, SUPER_PASS)


# ══════════════════════ CLONE → NATIVE HIERARCHY ══════════════════════
class TestCloneHierarchy:
    _full_did = None
    _values_only_did = None

    def test_clone_full_hierarchy(self, s, super_headers):
        r = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "full"},
                   headers=super_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        did = r.json()["decision_id"]
        TestCloneHierarchy._full_did = did

        # Fetch decision
        r2 = s.get(f"{API}/decisions/{did}", headers=super_headers, timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("decider_kind") == "app", f"expected decider_kind=app got {d.get('decider_kind')}"
        factors = d.get("factors") or []
        tops = [f for f in factors if not f.get("parent_id")]
        kids = [f for f in factors if f.get("parent_id")]
        assert len(tops) == 10, f"expected ~10 top-level, got {len(tops)}"
        assert len(kids) >= 20, f"expected >=20 children, got {len(kids)}"
        # Children must reference a valid parent + have weight
        top_ids = {f["id"] for f in tops}
        for k in kids:
            assert k["parent_id"] in top_ids, f"orphan child {k.get('name')}"
            assert isinstance(k.get("weight"), (int, float)), f"child {k.get('name')} missing weight"
        # full mode → category populated on top (primary|secondary)
        for t in tops:
            assert t.get("category") in ("primary", "secondary"), \
                f"factor {t.get('name')} category={t.get('category')}"

    def test_clone_values_only_no_classification(self, s, super_headers):
        r = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "values_only"},
                   headers=super_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        did = r.json()["decision_id"]
        TestCloneHierarchy._values_only_did = did

        r2 = s.get(f"{API}/decisions/{did}", headers=super_headers, timeout=30)
        assert r2.status_code == 200
        d = r2.json()
        factors = d.get("factors") or []
        tops = [f for f in factors if not f.get("parent_id")]
        assert tops, "no top-level factors"
        for t in tops:
            assert t.get("category") in ("", None), \
                f"values_only mode should leave category blank, got {t.get('category')} on {t.get('name')}"
            assert int(t.get("rating") or 0) == 0, \
                f"values_only mode should leave rating=0, got {t.get('rating')} on {t.get('name')}"


# ══════════════════════ FINDER CONFIG + RUN ══════════════════════
class TestFinder:
    def test_finder_config(self, s, super_headers):
        did = TestCloneHierarchy._full_did
        assert did
        r = s.get(f"{API}/decisions/{did}/finder/config", headers=super_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        j = r.json()
        assert j.get("is_app") is True
        assert isinstance(j.get("total_options"), int) and j["total_options"] > 0
        cfg = j.get("config") or {}
        for k in ("min_options", "max_options", "top_n", "match_rule", "engine"):
            assert k in cfg, f"missing {k} in config"
        assert cfg["match_rule"] in ("all", "any")
        assert cfg["engine"] in ("deterministic", "llm")

    def test_finder_run_deterministic_default(self, s, super_headers):
        did = TestCloneHierarchy._full_did
        assert did
        r = s.post(f"{API}/decisions/{did}/finder/run", json={}, headers=super_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        for k in ("stage", "total_options", "survivors", "top", "top_ids", "ranked"):
            assert k in j, f"missing {k} in finder result"
        assert isinstance(j["top"], list) and isinstance(j["ranked"], list)
        TestFinder._baseline_survivors = j["survivors"]
        TestFinder._baseline_top_ids = j["top_ids"]

    def test_finder_run_body_override(self, s, super_headers):
        did = TestCloneHierarchy._full_did
        assert did
        body = {"min_options": 2, "max_options": 5, "top_n": 3, "match_rule": "any"}
        r = s.post(f"{API}/decisions/{did}/finder/run", json=body, headers=super_headers, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        j = r.json()
        assert j.get("match_rule") == "any"
        assert j.get("top_n") == 3
        assert len(j["top"]) <= 3

    def test_finder_run_funnel_with_mandatory(self, s, super_headers):
        """Setting expected_value + primary category on a factor should filter survivors."""
        did = TestCloneHierarchy._full_did
        assert did
        # Load decision
        r = s.get(f"{API}/decisions/{did}", headers=super_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        factors = d.get("factors") or []
        tops = [f for f in factors if not f.get("parent_id")]
        # Pick first top with children
        target_top = None
        for t in tops:
            children = [f for f in factors if f.get("parent_id") == t["id"]]
            if children:
                target_top = t
                break
        assert target_top, "no factor with children"
        # Mark this top as primary + rating=5
        for t in tops:
            t["category"] = "primary" if t["id"] == target_top["id"] else "secondary"
        for t in tops:
            if t["id"] == target_top["id"]:
                t["rating"] = 5
        # Set a leaf child's expected value to something restrictive
        target_child = None
        for f in factors:
            if f.get("parent_id") == target_top["id"]:
                target_child = f
                break
        assert target_child
        # Force a rare/exact match: use "= 100" numeric — reduces to options that have that leaf==100
        target_child["expected_value"] = "100"
        target_child["operator"] = "="
        target_child["data_type"] = "numeric"

        # PUT the updated decision
        r2 = s.put(f"{API}/decisions/{did}", json={"factors": factors},
                   headers=super_headers, timeout=30)
        assert r2.status_code in (200, 204), f"{r2.status_code} {r2.text[:200]}"

        r3 = s.post(f"{API}/decisions/{did}/finder/run", json={"match_rule": "all"},
                    headers=super_headers, timeout=60)
        assert r3.status_code == 200
        j = r3.json()
        baseline = getattr(TestFinder, "_baseline_survivors", None)
        # Survivors should not exceed baseline; usually strictly less. Allow equal if 100 matches all.
        assert j["survivors"] <= (baseline or j["total_options"]) , \
            f"funnel should not increase survivors: {j['survivors']} vs baseline {baseline}"


# ══════════════════════ ADMIN FINDER DEFAULTS ══════════════════════
class TestAdminFinderDefaults:
    _restore = None

    def test_admin_config_reflect_in_finder(self, s, super_headers):
        # Fetch current wallet config
        r = s.get(f"{API}/admin/ai-wallet/config", headers=super_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        cur = r.json()
        TestAdminFinderDefaults._restore = {
            k: cur.get(k) for k in ("finder_min_options", "finder_max_options",
                                    "finder_top_n", "finder_match_rule", "finder_engine")
        }
        # Push distinctive values
        patch = {
            "finder_min_options": 4,
            "finder_max_options": 12,
            "finder_top_n": 7,
            "finder_match_rule": "any",
            "finder_engine": "deterministic",
        }
        r2 = s.put(f"{API}/admin/ai-wallet/config", json=patch, headers=super_headers, timeout=30)
        assert r2.status_code == 200, f"{r2.status_code} {r2.text[:200]}"

        # Verify persistence
        r3 = s.get(f"{API}/admin/ai-wallet/config", headers=super_headers, timeout=30)
        assert r3.status_code == 200
        got = r3.json()
        for k, v in patch.items():
            assert got.get(k) == v, f"{k} not persisted: {got.get(k)} vs {v}"

        # Verify reflection in finder/config on a NEW clone (older clones cache their own finder_config)
        r4 = s.post(f"{API}/decider-store/{BMP}/clone", json={"mode": "values_only"},
                    headers=super_headers, timeout=60)
        assert r4.status_code == 200
        did = r4.json()["decision_id"]
        r5 = s.get(f"{API}/decisions/{did}/finder/config", headers=super_headers, timeout=30)
        assert r5.status_code == 200
        cfg = r5.json()["config"]
        # finder_settings on the template can override — but bmp doesn't set these, so admin defaults win
        assert cfg["min_options"] == 4, f"admin min_options not reflected: {cfg}"
        assert cfg["max_options"] == 12, f"admin max_options not reflected: {cfg}"
        assert cfg["top_n"] == 7, f"admin top_n not reflected: {cfg}"
        assert cfg["match_rule"] == "any", f"admin match_rule not reflected: {cfg}"

    def test_restore_admin_defaults(self, s, super_headers):
        restore = TestAdminFinderDefaults._restore
        if not restore:
            pytest.skip("no snapshot")
        # Restore (send only non-null values that we snapshotted)
        clean = {k: v for k, v in restore.items() if v is not None}
        if clean:
            r = s.put(f"{API}/admin/ai-wallet/config", json=clean, headers=super_headers, timeout=30)
            assert r.status_code == 200


# ══════════════════════ STOREFRONT KIND FILTER + TOGGLE ══════════════════════
class TestStorefrontKind:
    _prev_kind = None

    def test_list_kind_app_includes_bmp(self, s):
        r = s.get(f"{API}/decider-store", params={"kind": "app"}, timeout=30)
        assert r.status_code == 200
        tpls = r.json().get("templates", [])
        ids = [t.get("template_id") for t in tpls]
        assert BMP in ids, f"BMP not returned in kind=app list; got {ids[:5]}"
        for t in tpls:
            assert t.get("kind") == "app", f"non-app in kind=app: {t.get('template_id')} kind={t.get('kind')}"

    def test_list_kind_template_excludes_bmp(self, s):
        r = s.get(f"{API}/decider-store", params={"kind": "template"}, timeout=30)
        assert r.status_code == 200
        tpls = r.json().get("templates", [])
        ids = [t.get("template_id") for t in tpls]
        assert BMP not in ids, f"BMP should NOT be in kind=template list; ids={ids[:5]}"

    def test_admin_kind_toggle(self, s, super_headers):
        # Toggle BMP to template then back to app
        r0 = s.get(f"{API}/decider-store/{BMP}", timeout=30)
        assert r0.status_code == 200
        TestStorefrontKind._prev_kind = r0.json().get("kind")

        r = s.put(f"{API}/decider-store/{BMP}", json={"kind": "template"},
                  headers=super_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        r2 = s.get(f"{API}/decider-store/{BMP}", timeout=30)
        assert r2.json().get("kind") == "template"

        # Restore
        r3 = s.put(f"{API}/decider-store/{BMP}", json={"kind": "app"},
                   headers=super_headers, timeout=30)
        assert r3.status_code == 200
        r4 = s.get(f"{API}/decider-store/{BMP}", timeout=30)
        assert r4.json().get("kind") == "app"


# ══════════════════════ LANDING ══════════════════════
class TestLanding:
    _snapshot = None

    def test_public_landing_defaults(self, s):
        r = s.get(f"{API}/decider-store/landing", timeout=30)
        assert r.status_code == 200
        j = r.json()
        for k in ("title", "subtitle", "hero", "cta_label", "cta_target"):
            assert j.get(k), f"landing missing {k}: {j}"
        TestLanding._snapshot = j

    def test_admin_landing_update(self, s, super_headers):
        patch = {
            "title": "TEST_iter192_title",
            "subtitle": "TEST_iter192_sub",
            "hero": "TEST_iter192_hero",
            "cta_label": "TEST_iter192_cta",
            "cta_target": "https://example.com/iter192",
        }
        r = s.put(f"{API}/decider-store/landing", json=patch,
                  headers=super_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        got = r.json()
        for k, v in patch.items():
            assert got.get(k) == v, f"landing {k} not persisted: {got.get(k)} vs {v}"

    def test_landing_html_contains_cta(self, s):
        r = s.get(f"{API}/decider-store/landing.html", timeout=30)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "html" in ct.lower(), f"expected HTML got {ct}"
        assert "TEST_iter192_cta" in r.text, "cta_label not in landing.html body"

    def test_restore_landing(self, s, super_headers):
        snap = TestLanding._snapshot
        if not snap:
            pytest.skip("no snapshot")
        # Only send the known editable keys
        patch = {k: snap.get(k) for k in ("title", "subtitle", "hero", "cta_label", "cta_target")
                 if snap.get(k)}
        r = s.put(f"{API}/decider-store/landing", json=patch,
                  headers=super_headers, timeout=30)
        assert r.status_code == 200

    def test_landing_public_no_auth(self):
        r = requests.get(f"{API}/decider-store/landing", timeout=30)
        assert r.status_code == 200

    def test_landing_update_requires_admin(self):
        r = requests.put(f"{API}/decider-store/landing",
                         json={"title": "hack"}, timeout=30)
        assert r.status_code in (401, 403)
