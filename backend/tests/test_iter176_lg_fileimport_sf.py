"""ITER 176 backend tests:
  • Life Goals: meta, timeline+tree create/validation, list/tree/get/put/delete cascade, gem linkage.
  • Import-from-File: success on tiny CSV/TXT, validation errors (.zip / bad b64 / tiny text).
  • Solution Finder: decision_type persists across PUT + GET.
"""
import base64
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "super@test.com", "password": "SuperPass2026!"}


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


# ───────────────────────────── LIFE GOALS ─────────────────────────────
class TestLifeGoalsMeta:
    def test_meta_shape_and_subtype_order(self, session):
        r = session.get(f"{API}/life-goals/meta", timeout=20)
        assert r.status_code == 200, r.text
        meta = r.json()
        # sub-types in exact order
        st_labels = [s["name"] for s in meta.get("sub_types", [])]
        assert st_labels == ["Present Problem", "Need", "Future Risk", "Aspiration"], st_labels
        # 7 levels
        assert len(meta.get("levels", [])) == 7
        # 5 horizons
        horizon_ids = [h["id"] for h in meta.get("horizons", [])]
        assert horizon_ids == ["quarter", "1yr", "3yr", "5yr", "10yr"], horizon_ids
        # life_areas non-empty
        assert isinstance(meta.get("life_areas"), list) and len(meta["life_areas"]) > 0


_CREATED_LG = []  # cleanup


class TestLifeGoalsTimeline:
    def test_create_timeline_success(self, session):
        body = {
            "mode": "timeline",
            "title": "TEST_iter176 timeline goal",
            "horizon": "1yr",
            "life_area": "Career",
        }
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["lg_mode"] == "timeline"
        assert d["horizon"] == "1yr"
        assert d["life_area"] == "Career"
        assert d["title"] == body["title"]
        _CREATED_LG.append(d["goal_id"])

    def test_timeline_requires_horizon(self, session):
        r = session.post(f"{API}/life-goals", json={"mode": "timeline", "title": "x", "life_area": "Career"}, timeout=20)
        assert r.status_code == 400

    def test_timeline_bad_horizon(self, session):
        r = session.post(f"{API}/life-goals", json={"mode": "timeline", "title": "x", "horizon": "weekly", "life_area": "Career"}, timeout=20)
        assert r.status_code == 400

    def test_timeline_requires_life_area(self, session):
        r = session.post(f"{API}/life-goals", json={"mode": "timeline", "title": "x", "horizon": "1yr"}, timeout=20)
        assert r.status_code == 400

    def test_timeline_requires_title(self, session):
        r = session.post(f"{API}/life-goals", json={"mode": "timeline", "title": "", "horizon": "1yr", "life_area": "Career"}, timeout=20)
        assert r.status_code == 400


class TestLifeGoalsTree:
    """Build L1..L7 chain, verify validation rules, cascade delete."""

    chain = {}  # level -> goal_id

    def test_create_l1_overall(self, session):
        body = {"mode": "tree", "level": 1, "title": "TEST_iter176 overall L1"}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["lg_mode"] == "tree" and d["lg_level"] == 1 and d["parent_id"] is None
        TestLifeGoalsTree.chain[1] = d["goal_id"]
        _CREATED_LG.append(d["goal_id"])

    def test_l1_with_parent_400(self, session):
        body = {"mode": "tree", "level": 1, "title": "bad", "parent_id": TestLifeGoalsTree.chain[1]}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 400

    def test_l2_requires_parent_id(self, session):
        r = session.post(f"{API}/life-goals", json={"mode": "tree", "level": 2, "title": "x"}, timeout=20)
        assert r.status_code == 400

    def test_l2_wrong_level_parent(self, session):
        # Try to use L1 as parent for L3 (should fail; parent must be exactly level-1 of new)
        r = session.post(f"{API}/life-goals", json={"mode": "tree", "level": 3, "title": "x", "parent_id": TestLifeGoalsTree.chain[1]}, timeout=20)
        assert r.status_code == 400

    def test_create_l2_l3_l4(self, session):
        for lvl in (2, 3, 4):
            body = {"mode": "tree", "level": lvl, "title": f"TEST_iter176 L{lvl}", "parent_id": TestLifeGoalsTree.chain[lvl - 1]}
            r = session.post(f"{API}/life-goals", json=body, timeout=20)
            assert r.status_code == 200, f"L{lvl}: {r.text}"
            d = r.json()
            assert d["lg_level"] == lvl and d["parent_id"] == TestLifeGoalsTree.chain[lvl - 1]
            TestLifeGoalsTree.chain[lvl] = d["goal_id"]
            _CREATED_LG.append(d["goal_id"])

    def test_l5_requires_life_area(self, session):
        body = {"mode": "tree", "level": 5, "title": "L5 no life area", "parent_id": TestLifeGoalsTree.chain[4]}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 400

    def test_create_l5_with_life_area(self, session):
        body = {"mode": "tree", "level": 5, "title": "TEST_iter176 L5", "parent_id": TestLifeGoalsTree.chain[4], "life_area": "Career"}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 200, r.text
        TestLifeGoalsTree.chain[5] = r.json()["goal_id"]
        _CREATED_LG.append(r.json()["goal_id"])

    def test_l6_requires_sub_type(self, session):
        body = {"mode": "tree", "level": 6, "title": "L6 no sub", "parent_id": TestLifeGoalsTree.chain[5]}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 400

    def test_l6_invalid_sub_type(self, session):
        body = {"mode": "tree", "level": 6, "title": "L6 bad sub", "parent_id": TestLifeGoalsTree.chain[5], "sub_type": "random"}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 400

    def test_create_l6_with_sub_type(self, session):
        body = {"mode": "tree", "level": 6, "title": "TEST_iter176 L6", "parent_id": TestLifeGoalsTree.chain[5], "sub_type": "need"}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sub_type"] == "need" and d["lg_level"] == 6
        TestLifeGoalsTree.chain[6] = d["goal_id"]
        _CREATED_LG.append(d["goal_id"])

    def test_create_l7(self, session):
        body = {"mode": "tree", "level": 7, "title": "TEST_iter176 L7", "parent_id": TestLifeGoalsTree.chain[6]}
        r = session.post(f"{API}/life-goals", json=body, timeout=20)
        assert r.status_code == 200, r.text
        TestLifeGoalsTree.chain[7] = r.json()["goal_id"]
        _CREATED_LG.append(r.json()["goal_id"])

    def test_list_filters(self, session):
        # mode=tree
        r = session.get(f"{API}/life-goals?mode=tree", timeout=20)
        assert r.status_code == 200
        items = r.json()
        ids = {g["goal_id"] for g in items}
        for lvl in (1, 2, 3, 4, 5, 6, 7):
            assert TestLifeGoalsTree.chain[lvl] in ids
        # level filter
        r2 = session.get(f"{API}/life-goals?mode=tree&level=5", timeout=20)
        assert r2.status_code == 200
        assert all(g["lg_level"] == 5 for g in r2.json())
        # parent_id filter
        r3 = session.get(f"{API}/life-goals?parent_id={TestLifeGoalsTree.chain[1]}", timeout=20)
        assert r3.status_code == 200
        ids3 = {g["goal_id"] for g in r3.json()}
        assert TestLifeGoalsTree.chain[2] in ids3

    def test_get_tree(self, session):
        r = session.get(f"{API}/life-goals/tree", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "levels" in data and len(data["levels"]) == 7
        ids = {g["goal_id"] for g in data["goals"]}
        for lvl in (1, 2, 3, 4, 5, 6, 7):
            assert TestLifeGoalsTree.chain[lvl] in ids

    def test_put_update_title(self, session):
        gid = TestLifeGoalsTree.chain[5]
        r = session.put(f"{API}/life-goals/{gid}", json={"title": "TEST_iter176 L5 UPDATED"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["title"] == "TEST_iter176 L5 UPDATED"

    def test_gem_goals_linkage(self, session):
        """Life Goals must also appear in /gem/goals with lg_mode set."""
        r = session.get(f"{API}/gem/goals", timeout=20)
        assert r.status_code == 200, r.text
        items = r.json() if isinstance(r.json(), list) else r.json().get("goals", [])
        index = {g["goal_id"]: g for g in items if "goal_id" in g}
        for lvl in (1, 5, 6):
            gid = TestLifeGoalsTree.chain[lvl]
            assert gid in index, f"L{lvl} {gid} missing in /gem/goals (saw {len(index)})"
            assert index[gid].get("lg_mode") == "tree"

    def test_delete_cascades_l1(self, session):
        """Deleting L1 must cascade L2..L7."""
        gid = TestLifeGoalsTree.chain[1]
        r = session.delete(f"{API}/life-goals/{gid}", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        # 7 descendants total (L1..L7)
        assert d["deleted"] >= 7
        # confirm gone
        r2 = session.get(f"{API}/life-goals/{TestLifeGoalsTree.chain[7]}", timeout=20)
        assert r2.status_code == 404


# ───────────────────────────── IMPORT-FROM-FILE ─────────────────────────────

_CSV_VC = (
    "name,stage,sector,ticket_size_usd\n"
    "Sequoia,Seed-Series A,Tech/Consumer,1M-10M\n"
    "Accel,Seed-Series B,SaaS/Fintech,500K-15M\n"
    "Lightspeed,Series A-C,Consumer/Enterprise,2M-25M\n"
    "Matrix,Seed-Series B,SaaS/Health,250K-5M\n"
)


@pytest.fixture(scope="module")
def decision_id(session):
    body = {"title": f"TEST_iter176 file-import decision {uuid.uuid4().hex[:6]}", "decision_type": "need", "context": "iter176 backend test seed"}
    r = session.post(f"{API}/decisions", json=body, timeout=20)
    assert r.status_code in (200, 201), r.text
    did = r.json().get("id") or r.json().get("decision_id")
    assert did, r.json()
    yield did


class TestFileImport:
    def test_success_small_csv(self, session, decision_id):
        b64 = base64.b64encode(_CSV_VC.encode("utf-8")).decode("ascii")
        body = {
            "filename": "vcs.csv",
            "file_b64": b64,
            "ai_tier": "fast",
            "crawl_web": False,
            "context": "Pick a VC for our seed round",
        }
        r = session.post(f"{API}/file-import/decision/{decision_id}", json=body, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("file_type") == "csv"
        assert "factors_added" in d and "options_added" in d
        assert isinstance(d.get("factors"), list) and isinstance(d.get("options"), list)
        # AI is real — at least something should come back
        assert (d["factors_added"] + d["options_added"]) > 0, d

        # Decision should reflect grown factors/options
        r2 = session.get(f"{API}/decisions/{decision_id}", timeout=20)
        assert r2.status_code == 200
        dec = r2.json()
        # factors/options counts > 0
        fcount = len(dec.get("factors") or [])
        ocount = len(dec.get("candidates") or dec.get("options") or [])
        assert fcount > 0 or ocount > 0, f"decision factors/options not grown: f={fcount} o={ocount}"

    def test_unsupported_extension_zip(self, session, decision_id):
        b64 = base64.b64encode(b"PK\x03\x04 dummy zip content").decode("ascii")
        body = {"filename": "bundle.zip", "file_b64": b64, "ai_tier": "fast", "crawl_web": False}
        r = session.post(f"{API}/file-import/decision/{decision_id}", json=body, timeout=30)
        assert r.status_code == 400, r.text

    def test_empty_garbage_b64(self, session, decision_id):
        # empty b64 string → backend treats as empty file → 400
        body = {"filename": "n.csv", "file_b64": "", "ai_tier": "fast", "crawl_web": False}
        r = session.post(f"{API}/file-import/decision/{decision_id}", json=body, timeout=30)
        assert r.status_code == 400, r.text

    def test_tiny_text_under_20_chars(self, session, decision_id):
        b64 = base64.b64encode(b"hello").decode("ascii")
        body = {"filename": "tiny.txt", "file_b64": b64, "ai_tier": "fast", "crawl_web": False}
        r = session.post(f"{API}/file-import/decision/{decision_id}", json=body, timeout=30)
        assert r.status_code == 422, r.text


# ─────────────────────── SOLUTION FINDER decision_type ───────────────────────
class TestSolutionFinderDecisionType:
    def test_create_then_put_decision_type_persists(self, session):
        # Create
        r = session.post(f"{API}/solution-finders", json={"smart_goal": "TEST_iter176 SF dt", "area_of_life": "Career"}, timeout=20)
        assert r.status_code == 200, r.text
        eid = r.json().get("entry_id")
        assert eid
        # PUT decision_type='risk'
        r2 = session.put(f"{API}/solution-finders/{eid}", json={"decision_type": "risk"}, timeout=20)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("decision_type") == "risk"
        # GET
        r3 = session.get(f"{API}/solution-finders/{eid}", timeout=20)
        assert r3.status_code == 200
        assert r3.json().get("decision_type") == "risk"
        # cleanup (trash)
        session.delete(f"{API}/solution-finders/{eid}", timeout=20)
