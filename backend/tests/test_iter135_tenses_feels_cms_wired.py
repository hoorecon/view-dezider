"""Iter 135 — Phase B: /tools/tenses-feels wired to Content Library CMS.

Acceptance items (review_request):
  1. GET /api/version returns build 2026.06.17.005 / tag v3.28-tenses-feels-cms-wired
  2. GET /api/content-library/render/tenses_feels returns 12 blocks
  3. Each rendered block has all required emotion fields populated:
       title, key, fields.tense, fields.polarity, fields.category, fields.color,
       fields.narrative_paraphrase, fields.power_statement,
       fields.instruction_for_user, fields.resolution_quote, fields.healing_feeling
  4. PUT one block via /api/content-library/{id} to change power_statement;
     refetch render endpoint — change is reflected
  5. GET /api/content-library/render/tenses_feels?locale=hi falls back to en (12 blocks)
  6. Regression: ACM v2 + content-library endpoints from iter133 + iter134 still pass
"""
from __future__ import annotations
import os
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "https://modal-responsive-fix.preview.emergentagent.com"
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
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
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
# 1. Version stamp (Phase B build)
# ------------------------------------------------------------
class TestVersion:
    def test_version_stamp_phase_b(self, s):
        r = s.get(f"{BASE_URL}/api/version", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("build_version") == "2026.06.17.005", \
            f"unexpected build_version: {body}"
        assert body.get("build_tag") == "v3.28-tenses-feels-cms-wired", \
            f"unexpected build_tag: {body}"


# ------------------------------------------------------------
# 2 + 3. Render endpoint — 12 blocks with all required emotion fields
# ------------------------------------------------------------
REQUIRED_FIELD_KEYS = (
    "tense", "polarity", "category", "color",
    "narrative_paraphrase", "power_statement",
    "instruction_for_user", "resolution_quote", "healing_feeling",
)
EXPECTED_KEYS = {
    "clinging", "longing", "fear", "anxiety",
    "anger", "sadness", "over_cautious", "over_careless",
    "jealousy", "disgraceful", "aggression", "heartbroken",
}


class TestRenderTensesFeels:
    def test_render_returns_12_blocks_with_all_fields(self, s):
        r = s.get(
            f"{BASE_URL}/api/content-library/render/tenses_feels",
            params={"locale": "en"}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["module"] == "tenses_feels"
        assert body["locale"] == "en"
        blocks = body.get("blocks", [])
        assert body.get("count") == len(blocks)
        assert len(blocks) == 12, f"expected exactly 12 blocks got {len(blocks)}"

        # All emotion keys present
        keys_present = {b.get("key") for b in blocks}
        missing_keys = EXPECTED_KEYS - keys_present
        assert not missing_keys, f"missing emotion keys: {missing_keys}"

        # Each block populated with required emotion fields
        for b in blocks:
            assert b.get("key"), f"block missing key: {b}"
            assert b.get("title"), f"block missing title: {b.get('key')}"
            fields = b.get("fields") or {}
            for fk in REQUIRED_FIELD_KEYS:
                val = fields.get(fk)
                assert val not in (None, ""), \
                    f"block {b.get('key')}.fields.{fk} is empty: {fields}"

            # Sanity-check enum values
            assert fields["tense"] in ("past", "future", "present"), \
                f"invalid tense in {b['key']}: {fields['tense']}"
            assert fields["polarity"] in ("negative", "positive"), \
                f"invalid polarity in {b['key']}: {fields['polarity']}"
            assert fields["category"] in (
                "self_emotional", "self_mental",
                "others_yours", "others_theirs", "none",
            ), f"invalid category in {b['key']}: {fields['category']}"
            assert fields["healing_feeling"] in (
                "gratefulness", "faith", "happily_active",
            ), f"invalid healing_feeling in {b['key']}: {fields['healing_feeling']}"

        # Ordered ascending by order
        orders = [b.get("order", 999) for b in blocks]
        assert orders == sorted(orders), f"blocks not sorted by order: {orders}"

    def test_render_hi_falls_back_to_en_with_12_blocks(self, s):
        r = s.get(
            f"{BASE_URL}/api/content-library/render/tenses_feels",
            params={"locale": "hi"}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["locale"] == "hi"
        blocks = body.get("blocks", [])
        assert len(blocks) == 12, \
            f"hi fallback should return 12 en blocks, got {len(blocks)}"
        # Fallback rows are still the en ones (have english power_statement text)
        sample = blocks[0]
        assert sample.get("fields", {}).get("power_statement"), \
            "fallback block missing power_statement"


# ------------------------------------------------------------
# 4. PUT power_statement -> refetch render shows the change
# ------------------------------------------------------------
class TestWriteThroughToRender:
    """Edit one block's power_statement via admin PUT, then verify the
    public /render endpoint reflects the new value (cache invalidation OK).
    """

    @pytest.fixture(autouse=True, scope="class")
    def restore_after(self, request, s):
        # Captured in test body; we restore in teardown.
        request.cls._restore = None

        def _teardown():
            payload = getattr(request.cls, "_restore", None)
            tok = getattr(request.cls, "_token", None)
            if payload and tok:
                hdr = {"Authorization": f"Bearer {tok}",
                       "Content-Type": "application/json"}
                bid = payload["id"]
                fields = payload["fields"]
                try:
                    s.put(f"{BASE_URL}/api/content-library/{bid}",
                          json={"fields": fields},
                          headers=hdr, timeout=15)
                except Exception:
                    pass

        request.addfinalizer(_teardown)

    def test_put_power_statement_reflects_in_render(
            self, s, admin_headers, admin_token, request):
        # cache admin token for teardown
        request.cls._token = admin_token

        # 1. List admin blocks to find the 'clinging' tenses_feels en row
        r = s.get(
            f"{BASE_URL}/api/content-library",
            params={"module": "tenses_feels", "locale": "en", "active": "true"},
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        items = r.json().get("items", [])
        clinging = next(
            (it for it in items if it.get("key") == "clinging"
             and it.get("module") == "tenses_feels"),
            None,
        )
        assert clinging is not None, "could not find 'clinging' block to edit"
        bid = clinging["id"]
        original_fields = dict(clinging.get("fields") or {})
        request.cls._restore = {"id": bid, "fields": original_fields}

        # 2. PUT a new power_statement (must include all current fields so we
        #    don't lose them — endpoint replaces fields on update if present).
        new_power = "ITER135 TEST power_statement — write-through verification"
        new_fields = dict(original_fields)
        new_fields["power_statement"] = new_power

        r2 = s.put(
            f"{BASE_URL}/api/content-library/{bid}",
            json={"fields": new_fields},
            headers=admin_headers, timeout=20,
        )
        assert r2.status_code == 200, r2.text[:300]
        upd = r2.json()
        assert upd["fields"]["power_statement"] == new_power
        assert upd["version"] >= (clinging.get("version") or 1) + 1, \
            f"version not bumped: was {clinging.get('version')} now {upd.get('version')}"

        # 3. Public render endpoint should reflect the change immediately
        r3 = s.get(
            f"{BASE_URL}/api/content-library/render/tenses_feels",
            params={"locale": "en"}, timeout=20,
        )
        assert r3.status_code == 200
        blocks = r3.json().get("blocks", [])
        clinging_rendered = next(
            (b for b in blocks if b.get("key") == "clinging"), None,
        )
        assert clinging_rendered is not None, "clinging missing from render"
        assert (clinging_rendered.get("fields") or {}).get("power_statement") \
            == new_power, \
            "render endpoint did not reflect PUT update (cache not invalidated?)"

        # 4. Other required fields preserved (no data loss)
        for fk in REQUIRED_FIELD_KEYS:
            if fk == "power_statement":
                continue
            assert clinging_rendered["fields"].get(fk) == original_fields.get(fk), \
                f"field {fk} changed unexpectedly after PUT"


# ------------------------------------------------------------
# 5. Regression — content-library + ACM v2 still healthy
# ------------------------------------------------------------
class TestRegression:
    def test_modules_list_still_returns_7(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/modules", timeout=15)
        assert r.status_code == 200
        mods = r.json().get("modules", [])
        assert len(mods) == 7
        assert mods[0]["module"] == "tenses_feels"
        tf = next((m for m in mods if m["module"] == "tenses_feels"), None)
        assert tf and tf["blocks"] >= 12, \
            f"tenses_feels should have ≥12 active blocks: {tf}"

    def test_schema_endpoint_still_works(self, s):
        r = s.get(f"{BASE_URL}/api/content-library/schema/tenses_feels", timeout=15)
        assert r.status_code == 200
        sch = r.json()["schema"]
        assert len(sch["fields"]) == 12

    def test_list_blocks_requires_auth(self):
        # Use a brand-new session so cookies from the admin login fixture
        # don't leak into this unauthenticated assertion.
        fresh = requests.Session()
        r = fresh.get(f"{BASE_URL}/api/content-library", timeout=15)
        assert r.status_code in (401, 403), \
            f"expected 401/403 got {r.status_code}: {r.text[:200]}"

    def test_acm_v2_resolver_config(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/resolver-config",
                  headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_acm_v2_trial_payments(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/acm-v2/trial-payments",
                  headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_geo_countries(self, s, admin_headers):
        r = s.get(f"{BASE_URL}/api/geo/countries",
                  headers=admin_headers, timeout=15)
        assert r.status_code in (200, 401, 403)
