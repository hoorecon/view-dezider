"""
Iter 171 — Epic Phase 3B/3C — Option Publish backend tests.

Covers:
  • GET  /api/option-publish/source/{decision_id} — completed seed demo decider
  • POST /api/option-publish/publish — gating, validation, success, persistence
  • POST /api/option-publish/record-usage — chain (karma -> cash), self-use
  • GET  /api/option-publish/my-published — list with stats fields
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "super@test.com"
SUPER_PWD = "SuperPass2026!"
DEC_ID = "dec_phase3_publish_demo"


# ── shared session / auth ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PWD}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    body = r.json()
    token = body.get("session_token") or body.get("token")
    uid = body.get("user_id") or (body.get("user") or {}).get("user_id")
    assert token, f"no session_token in login response: {body}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    s.user_id = uid  # type: ignore[attr-defined]
    return s


@pytest.fixture(scope="module")
def source_data(session):
    r = session.get(f"{API}/option-publish/source/{DEC_ID}", timeout=20)
    assert r.status_code == 200, f"source endpoint: {r.status_code} {r.text[:200]}"
    return r.json()


# ── 1) GET /source ─────────────────────────────────────────────────────────
class TestSource:
    def test_source_is_completed(self, source_data):
        assert source_data.get("is_completed") is True, source_data

    def test_source_has_three_factors_with_default_quant(self, source_data):
        factors = source_data.get("factors") or []
        assert len(factors) == 3, factors
        names = sorted(f.get("name") for f in factors)
        assert names == sorted(["Price", "Quality", "Support Experience"]), names
        for f in factors:
            assert f.get("default_kind") == "quantitative", f

    def test_source_has_two_options(self, source_data):
        opts = source_data.get("options") or []
        names = sorted(o.get("name") for o in opts)
        assert names == sorted(["Alpha Plan", "Beta Plan"]), names


# ── 2) gating on a non-completed decider ───────────────────────────────────
class TestPublishGating:
    @pytest.fixture(scope="class")
    def temp_decision_id(self, session):
        """Create a non-completed decider directly in MongoDB owned by super@test.com."""
        import asyncio, sys
        sys.path.insert(0, "/app/backend")
        from core.database import db  # type: ignore

        dec_id = f"dec_test_iter171_{uuid.uuid4().hex[:8]}"
        doc = {
            "id": dec_id,
            "user_id": getattr(session, "user_id", None),
            "type": "decider",
            "name": "Iter171 In-Progress Decider",
            "current_step": 2,
            "total_steps": 8,
            "factors": [{"id": "f_x", "name": "X", "unit": "INR", "operator": "lt"}],
            "options": [{"id": "o_x", "name": "Option X", "assessments": []}],
            "status": "in_progress",
            "is_complete": False,
        }
        assert doc["user_id"], "missing user_id from login"
        asyncio.get_event_loop().run_until_complete(db.decisions.insert_one(dict(doc)))
        yield dec_id
        try:
            asyncio.get_event_loop().run_until_complete(db.decisions.delete_many({"id": dec_id}))
        except Exception:
            pass

    def test_publish_non_completed_returns_400(self, session, temp_decision_id):
        r = session.post(
            f"{API}/option-publish/publish",
            json={"decision_id": temp_decision_id, "monetization": "paid"},
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"
        assert "completed" in r.text.lower()


# ── 3) validations on the completed decider ────────────────────────────────
class TestPublishValidation:
    def test_all_qualitative_rejected(self, session, source_data):
        ftypes = {f["id"]: "qualitative" for f in source_data["factors"]}
        r = session.post(
            f"{API}/option-publish/publish",
            json={"decision_id": DEC_ID, "factor_types": ftypes, "monetization": "free"},
            timeout=20,
        )
        assert r.status_code == 400, r.text[:200]
        assert "quantitative" in r.text.lower()

    def test_unknown_solution_type_rejected(self, session):
        r = session.post(
            f"{API}/option-publish/publish",
            json={"decision_id": DEC_ID, "solution_type": "FOO_BAR", "monetization": "free"},
            timeout=20,
        )
        assert r.status_code == 400, r.text[:200]


# ── 4) successful publish + persistence ────────────────────────────────────
class TestPublishHappyPath:
    @pytest.fixture(scope="class")
    def published(self, session, source_data):
        # mark Support Experience as qualitative
        support_id = next(f["id"] for f in source_data["factors"] if f["name"] == "Support Experience")
        body = {
            "decision_id": DEC_ID,
            "monetization": "paid",
            "solution_type": "SERVICE",
            "factor_types": {support_id: "qualitative"},
        }
        r = session.post(f"{API}/option-publish/publish", json=body, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        yield {"support_id": support_id, "resp": data}
        # cleanup created solutions
        try:
            for sol in data.get("solutions", []) or []:
                session.delete(f"{API}/solutions-store/{sol['solution_id']}", timeout=10)
        except Exception:
            pass

    def test_published_count_and_reward_kind(self, published):
        d = published["resp"]
        assert d.get("published_count") == 2, d
        assert d.get("reward_kind") == "cash", d
        assert d.get("monetization") == "paid", d

    def test_factor_partition(self, published, source_data):
        d = published["resp"]
        assert len(d.get("quantitative_factor_ids") or []) == 2
        assert len(d.get("qualitative_factor_ids") or []) == 1
        assert published["support_id"] in (d.get("qualitative_factor_ids") or [])

    def test_my_published_lists_solutions(self, session, published):
        r = session.get(f"{API}/option-publish/my-published", timeout=20)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        items = data.get("items") or []
        published_ids = {s["solution_id"] for s in (published["resp"]["solutions"] or [])}
        mine_ids = {it["solution_id"] for it in items}
        assert published_ids.issubset(mine_ids), (published_ids, mine_ids)
        # verify stat fields present
        for it in items:
            if it["solution_id"] in published_ids:
                assert "review_avg" in it
                assert "review_count" in it
                assert "usage_count" in it

    # ── 5) record-usage chain — basic non-500 sanity ──
    def test_record_usage_self_use_returns_ok_false(self, session, published):
        sol_id = published["resp"]["solutions"][0]["solution_id"]
        r = session.post(
            f"{API}/option-publish/record-usage",
            json={"solution_id": sol_id, "star_rating": 5},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        # publisher == current user => no reward
        assert body.get("ok") is False, body

    def test_record_usage_unknown_solution_404(self, session):
        r = session.post(
            f"{API}/option-publish/record-usage",
            json={"solution_id": "sol_does_not_exist"},
            timeout=20,
        )
        assert r.status_code == 404, r.text[:200]
