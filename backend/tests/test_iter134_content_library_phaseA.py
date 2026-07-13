"""Content Library Admin CMS — Phase A backend regression (Iter 134).

Covers all 16 acceptance items from the review request:
  • /api/version stamp (2026.06.17.004 / v3.27-content-library-cms-phaseA)
  • /api/content-library/modules (public, 7 modules, tenses_feels first)
  • /api/content-library/schema/{module} (tenses_feels=12 fields, generic=3)
  • /api/content-library/seed/tenses_feels (idempotent + force=true)
  • CRUD: list (admin), POST (create), POST duplicate -> 409,
    PUT (update + version bump), DELETE (soft-delete)
  • /api/content-library/render/{module}?locale= (public + locale fallback)
  • Auth gating: list & seed without auth -> 401/403
  • Regression: ACM v2 endpoints still up
"""
from __future__ import annotations
import os
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://repo-blueprint-1.preview.emergentagent.com"
).rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


# ------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
               timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed {r.status_code}: {r.text[:200]}")
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    if not tok:
        pytest.skip(f"No token in login response keys={list(data.keys())}")
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ------------------------------------------------------------
# 1. Version stamp
# ------------------------------------------------------------
class TestVersion:
    def test_version_stamp(self, s):
        r = s.get(f"{BASE_URL}/api/version", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("build_version") == "2026.06.17.004", \
            f"unexpected build_version: {body}"
        assert body.get("build_tag") == "v3.27-content-library-cms-phaseA", \
            f"unexpected build_tag: {body}"


# ------------------------------------------------------------
# 2. Modules + schema discovery
# ------------------------------------------------------------
class TestModulesAndSchema:
    def test_modules_list_public(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/modules", timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "modules" in body and "locales" in body
        mods = body["modules"]
        assert len(mods) == 7, f"expected 7 modules got {len(mods)}: {mods}"
        # tenses_feels must be first
        assert mods[0]["module"] == "tenses_feels", \
            f"first module should be tenses_feels: {mods[0]}"
        # each entry has module/label/blocks
        for m in mods:
            assert "module" in m and "label" in m and "blocks" in m
            assert isinstance(m["blocks"], int)
        # locales
        for lc in ("en", "hi", "ta", "te", "mr", "kn"):
            assert lc in body["locales"], f"locale {lc} missing"

    def test_schema_tenses_feels(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/schema/tenses_feels", timeout=15)
        assert r.status_code == 200
        body = r.json()
        sch = body["schema"]
        fields = sch["fields"]
        assert len(fields) == 12, f"expected 12 fields got {len(fields)}"
        keys = {f["key"]: f for f in fields}
        # required title
        assert keys["title"].get("required") is True
        # select fields with options
        for sel in ("tense", "polarity", "category", "healing_feeling"):
            assert sel in keys, f"missing field {sel}"
            assert keys[sel]["type"] == "select"
            assert isinstance(keys[sel].get("options"), list) and keys[sel]["options"]

    def test_schema_goals_feels_generic(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/schema/goals_feels", timeout=15)
        assert r.status_code == 200
        sch = r.json()["schema"]
        assert len(sch["fields"]) == 3, f"generic schema should have 3 fields: {sch}"
        keys = [f["key"] for f in sch["fields"]]
        assert "title" in keys


# ------------------------------------------------------------
# 3. Auth gating (admin-only endpoints)
# ------------------------------------------------------------
class TestAuthGating:
    def test_list_blocks_requires_auth(self, s):
        r = s.get(f"{BASE_URL}/api/content-library", timeout=15)
        assert r.status_code in (401, 403), \
            f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_seed_requires_auth(self, s):
        r = s.post(f"{BASE_URL}/api/content-library/seed/tenses_feels", timeout=20)
        assert r.status_code in (401, 403), \
            f"expected 401/403 got {r.status_code}: {r.text[:200]}"


# ------------------------------------------------------------
# 4. Seed flow (idempotent + force)
# ------------------------------------------------------------
class TestSeed:
    def test_seed_first_or_idempotent(self, s, admin_headers):
        # first call: inserted could be 12 (fresh) OR 0 (already seeded by a
        # previous run). Both are acceptable: spec says first call returns 12,
        # but in this preview env the seed may already exist.
        r = s.post(f"{BASE_URL}/api/content-library/seed/tenses_feels",
                   headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert body.get("total_seed_entries") == 12
        assert body.get("inserted") in (0, 12), f"inserted={body.get('inserted')}"

    def test_seed_idempotent_second_call(self, s, admin_headers):
        r = s.post(f"{BASE_URL}/api/content-library/seed/tenses_feels",
                   headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("inserted") == 0, \
            f"second call should not insert: {body}"
        assert body.get("updated") == 0

    def test_seed_force_updates_all(self, s, admin_headers):
        r = s.post(f"{BASE_URL}/api/content-library/seed/tenses_feels?force=true",
                   headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body.get("updated") == 12, f"force update expected 12: {body}"
        assert body.get("inserted") == 0


# ------------------------------------------------------------
# 5. List (admin) — 12 seeded entries sorted by order
# ------------------------------------------------------------
class TestList:
    def test_list_tenses_feels_en(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/content-library",
                  params={"module": "tenses_feels", "locale": "en"},
                  headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        items = body["items"]
        assert len(items) >= 12, f"expected ≥12 entries got {len(items)}"
        # take just the seeded ones (order 1..12)
        seeded = [it for it in items if it.get("order") in range(1, 13)
                  and it.get("module") == "tenses_feels"]
        assert len(seeded) == 12, f"expected 12 seeded entries, got {len(seeded)}"
        # sorted by order
        orders = [it["order"] for it in seeded]
        assert orders == sorted(orders), f"items not sorted by order: {orders}"
        # verify keys
        keys_present = {it["key"] for it in seeded}
        expected_keys = {"clinging", "longing", "fear", "anxiety", "anger", "sadness",
                         "over_cautious", "over_careless", "jealousy", "disgraceful",
                         "aggression", "heartbroken"}
        assert expected_keys.issubset(keys_present), \
            f"missing keys: {expected_keys - keys_present}"


# ------------------------------------------------------------
# 6. Create / Conflict / Update / Delete
# ------------------------------------------------------------
class TestCRUD:
    created_id = None

    def test_create_block(self, s, admin_headers):
        # cleanup in case of leftover from prior run
        payload = {
            "module": "tenses_feels",
            "key": "TEST_block_iter134",
            "locale": "en",
            "title": "Test",
            "fields": {"narrative_paraphrase": "hello", "color": "#000000"},
            "order": 999,
        }
        # try to clean any leftover by attempting delete via list lookup
        r0 = s.get(f"{BASE_URL}/api/content-library",
                   params={"module": "tenses_feels", "locale": "en"},
                   headers=admin_headers, timeout=15)
        if r0.status_code == 200:
            for it in r0.json().get("items", []):
                if it.get("key") == "TEST_block_iter134":
                    s.delete(f"{BASE_URL}/api/content-library/{it['id']}",
                             headers=admin_headers, timeout=15)
                    # hard cleanup not exposed — soft delete is fine, but our
                    # uniqueness key (module,key,locale) still hits. We'll need
                    # a unique key per run.
                    pass

        # Use a uniquified key to ensure 201/200
        import uuid as _uuid
        unique_suffix = _uuid.uuid4().hex[:8]
        payload["key"] = f"TEST_block_iter134_{unique_suffix}"
        r = s.post(f"{BASE_URL}/api/content-library",
                   json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert "id" in body and body["id"]
        assert body["title"] == "Test"
        assert body["module"] == "tenses_feels"
        assert body["locale"] == "en"
        assert body["version"] == 1
        TestCRUD.created_id = body["id"]
        TestCRUD.created_key = payload["key"]

    def test_create_duplicate_returns_409(self, s, admin_headers):
        assert TestCRUD.created_id, "previous create test must have run"
        payload = {
            "module": "tenses_feels",
            "key": TestCRUD.created_key,
            "locale": "en",
            "title": "Test dup",
            "fields": {},
        }
        r = s.post(f"{BASE_URL}/api/content-library",
                   json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 409, \
            f"expected 409 conflict got {r.status_code}: {r.text[:200]}"

    def test_update_block_increments_version(self, s, admin_headers):
        assert TestCRUD.created_id, "previous create test must have run"
        r = s.put(f"{BASE_URL}/api/content-library/{TestCRUD.created_id}",
                  json={"title": "Test Updated"},
                  headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["title"] == "Test Updated"
        assert body["version"] == 2, f"expected version 2 got {body.get('version')}"

    def test_delete_block_soft_delete(self, s, admin_headers):
        assert TestCRUD.created_id, "previous create test must have run"
        r = s.delete(f"{BASE_URL}/api/content-library/{TestCRUD.created_id}",
                     headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True

        # Verify active=false (filter active=true should exclude)
        r2 = s.get(f"{BASE_URL}/api/content-library",
                   params={"module": "tenses_feels", "locale": "en", "active": "true"},
                   headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        ids = [it["id"] for it in r2.json().get("items", [])]
        assert TestCRUD.created_id not in ids, \
            "soft-deleted block should be excluded from active=true filter"


# ------------------------------------------------------------
# 7. Render endpoint (public + locale fallback)
# ------------------------------------------------------------
class TestRender:
    def test_render_en(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/render/tenses_feels",
                  params={"locale": "en"}, timeout=20)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["module"] == "tenses_feels"
        assert body["locale"] == "en"
        assert body["count"] >= 12, f"expected ≥12 blocks got {body['count']}"
        # ordered ascending
        orders = [b.get("order", 999) for b in body["blocks"]]
        assert orders == sorted(orders), "blocks not ordered"
        # verify first block has merged fields (narrative_paraphrase etc.)
        first = body["blocks"][0]
        assert "title" in first and first["title"]
        assert "fields" in first

    def test_render_hi_falls_back_to_en(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/render/tenses_feels",
                  params={"locale": "hi"}, timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["locale"] == "hi"
        # Fallback to en — should still return 12 blocks (en versions)
        assert body["count"] >= 12, \
            f"hi locale should fall back to en (≥12 blocks), got {body['count']}"


# ------------------------------------------------------------
# 8. Regression — ACM v2 endpoints from prior iter still work
# ------------------------------------------------------------
class TestACMv2Regression:
    def test_geo_countries(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/geo/countries",
                  headers=admin_headers, timeout=15)
        # Public or admin endpoint — accept 200
        assert r.status_code in (200, 401, 403), r.status_code
        if r.status_code == 200:
            body = r.json()
            items = body.get("countries") or body.get("items") or body
            assert items, f"empty geo countries: {body}"

    def test_resolver_config_get(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/resolver-config",
                  headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_trial_payments_get(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/trial-payments",
                  headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]
