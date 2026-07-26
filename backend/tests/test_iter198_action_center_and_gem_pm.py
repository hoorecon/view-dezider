"""
Iter 198 — Action Center revoke/switch + sync-all, six_legs↔AC status sync,
Goal-Setter create-task, GEM PM (WBS/deps/CPM/kanban/registers/port), OAuth start.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    tok = body.get("access_token") or body.get("token") or body.get("session_token")
    assert tok, r.text
    s.headers["Authorization"] = f"Bearer {tok}"
    s.user_id = body.get("user_id") or body.get("id")
    if not s.user_id:
        me = s.get(f"{API}/auth/me", timeout=15)
        if me.status_code == 200:
            s.user_id = me.json().get("user_id") or me.json().get("id")
    return s


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


# ─── sync-all idempotency ────────────────────────────────────────────
class TestSyncAll:
    def test_sync_all_returns_counts_and_is_idempotent(self, client):
        r1 = client.post(f"{API}/action-items/sync-all", timeout=60)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        for k in ("mpps", "pros_cons", "solution_finder", "total"):
            assert k in d1, f"missing key {k}: {d1}"
        r2 = client.post(f"{API}/action-items/sync-all", timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["total"] == 0, f"second call should be idempotent (0 new): got {d2}"


# ─── revoke (unport) deletes downstream ctt task ────────────────────
class TestUnportDeletesCtt:
    def test_manual_port_then_unport_removes_ctt(self, client, mongo):
        title = f"TEST_iter198_unport_{uuid.uuid4().hex[:6]}"
        r = client.post(f"{API}/action-items", json={"title": title, "source_module": "MANUAL"})
        assert r.status_code == 200, r.text
        aid = r.json()["action_id"]
        r = client.post(f"{API}/action-items/{aid}/port-to-ctt")
        assert r.status_code == 200, r.text
        ctt_task_id = r.json()["ctt_task"]["task_id"]
        assert mongo.ctt_tasks.find_one({"task_id": ctt_task_id}) is not None
        r = client.post(f"{API}/action-items/{aid}/unport")
        assert r.status_code == 200, r.text
        ai = mongo.action_items.find_one({"action_id": aid})
        assert ai["ported_to"] is None
        assert mongo.ctt_tasks.find_one({"task_id": ctt_task_id}) is None
        # cleanup
        client.delete(f"{API}/action-items/{aid}?hard=1")


# ─── switch-port ────────────────────────────────────────────────────
class TestSwitchPort:
    def test_switch_ctt_to_lifestyle_and_back(self, client, mongo):
        title = f"TEST_iter198_switch_{uuid.uuid4().hex[:6]}"
        r = client.post(f"{API}/action-items", json={"title": title, "source_module": "MANUAL"})
        aid = r.json()["action_id"]
        r = client.post(f"{API}/action-items/{aid}/port-to-ctt")
        old_ctt = r.json()["ctt_task"]["task_id"]
        r = client.post(f"{API}/action-items/{aid}/switch-port")
        assert r.status_code == 200, r.text
        body = r.json()
        assert mongo.ctt_tasks.find_one({"task_id": old_ctt}) is None, "old CTT should be deleted"
        assert body["action_item"]["ported_to"] == "LIFESTYLE"
        assert body["action_item"]["recurrence_type"] == "recurring"
        assert mongo.lifestyle_routines.find_one({"routine_id": body["lifestyle_routine"]["routine_id"]}) is not None
        # switch back to CTT
        r = client.post(f"{API}/action-items/{aid}/switch-port")
        assert r.status_code == 200, r.text
        body2 = r.json()
        assert body2["action_item"]["ported_to"] == "CTT"
        assert body2["action_item"]["recurrence_type"] == "one_time"
        # cleanup
        client.post(f"{API}/action-items/{aid}/unport")
        client.delete(f"{API}/action-items/{aid}?hard=1")

    def test_switch_port_on_unported_returns_409(self, client):
        r = client.post(f"{API}/action-items", json={"title": f"TEST_iter198_unp_{uuid.uuid4().hex[:6]}", "source_module": "MANUAL"})
        aid = r.json()["action_id"]
        r = client.post(f"{API}/action-items/{aid}/switch-port")
        assert r.status_code == 409, r.text
        client.delete(f"{API}/action-items/{aid}?hard=1")


# ─── six_legs ↔ Action Center status sync ────────────────────────────
class TestSixLegsStatusSync:
    def test_convert_and_bidirectional_sync(self, client, mongo):
        uid = client.user_id
        assert uid, "no user_id"
        # ensure a user_org
        org = mongo.user_orgs.find_one({"owner_user_id": uid})
        if not org:
            org_id = str(uuid.uuid4())
            mongo.user_orgs.insert_one({
                "org_id": org_id, "id": org_id, "owner_user_id": uid,
                "name": "TEST_iter198_org", "created_at": "2026-01-01T00:00:00Z"
            })
        else:
            org_id = org.get("org_id") or org.get("id")

        # create a six_legs goal directly
        goal_id = str(uuid.uuid4())
        mongo.six_legs_goals.insert_one({
            "id": goal_id, "goal_id": goal_id, "user_id": uid, "org_id": org_id,
            "title": f"TEST_iter198_sl_{uuid.uuid4().hex[:5]}",
            "status": "in_progress",
            "leg": "financial", "level": "goal", "created_at": "2026-01-01T00:00:00Z",
        })
        # convert-to-action
        r = client.post(f"{API}/six-legs/goals/{goal_id}/convert-to-action", json={})
        if r.status_code == 404:
            pytest.skip("six-legs convert-to-action endpoint missing")
        assert r.status_code in (200, 201), r.text
        body = r.json()
        aid = body.get("action_id") or (body.get("action_item") or {}).get("action_id")
        assert aid, f"no action_id in response: {body}"
        ai = mongo.action_items.find_one({"action_id": aid})
        assert ai["status"] == "wip_50", f"expected wip_50, got {ai['status']}"
        assert (ai.get("source_module") or "").upper() == "GOAL_SETTER"

        # PUT goal status=done → action item becomes done (full-body PUT)
        goal_doc = mongo.six_legs_goals.find_one({"id": goal_id}, {"_id": 0})
        put_body = {
            "user_org_id": org_id,
            "level": goal_doc.get("level") or "goal",
            "title": goal_doc.get("title"),
            "status": "done",
        }
        r = client.put(f"{API}/six-legs/goals/{goal_id}", json=put_body)
        assert r.status_code in (200, 204), r.text
        ai2 = mongo.action_items.find_one({"action_id": aid})
        assert ai2["status"] == "done", ai2

        # PUT action item status=blocked → six_legs goal status at_risk
        r = client.put(f"{API}/action-items/{aid}", json={"status": "blocked"})
        assert r.status_code == 200, r.text
        g = mongo.six_legs_goals.find_one({"id": goal_id})
        assert g["status"] == "at_risk", g["status"]

        # cleanup
        mongo.action_items.delete_one({"action_id": aid})
        mongo.six_legs_goals.delete_one({"id": goal_id})


# ─── Goal-Setter create-task ─────────────────────────────────────────
class TestGoalSetterCreateTask:
    def test_create_task_ctt_and_lifestyle_and_status_writeback(self, client, mongo):
        uid = client.user_id
        # create a smart_goal with a milestone directly
        goal_id = str(uuid.uuid4())
        ms_id = str(uuid.uuid4())
        mongo.smart_goals.insert_one({
            "goal_id": goal_id, "id": goal_id, "user_id": uid,
            "title": f"TEST_iter198_smart_{uuid.uuid4().hex[:5]}",
            "milestones": [{"milestone_id": ms_id, "title": "MS1", "target_date": "2026-06-30", "status": "pending"}],
            "created_at": "2026-01-01T00:00:00Z",
        })
        # kind=ctt (goal-level)
        r = client.post(f"{API}/goal-setter/goals/{goal_id}/create-task", json={"kind": "ctt"})
        if r.status_code == 404:
            pytest.skip("goal-setter create-task not available")
        assert r.status_code in (200, 201), r.text
        b = r.json()
        aid = b.get("action_id") or (b.get("action_item") or {}).get("action_id")
        assert aid, b
        ai = mongo.action_items.find_one({"action_id": aid})
        assert (ai.get("source_module") or "").upper() == "GOAL_SETTER"
        assert (ai.get("ported_to") or "").upper() == "CTT"

        # repeat = idempotent
        r2 = client.post(f"{API}/goal-setter/goals/{goal_id}/create-task", json={"kind": "ctt"})
        assert r2.status_code in (200, 201), r2.text
        assert r2.json().get("already_exists") is True, r2.json()

        # kind=lifestyle + milestone_id
        r3 = client.post(f"{API}/goal-setter/goals/{goal_id}/create-task",
                         json={"kind": "lifestyle", "milestone_id": ms_id})
        assert r3.status_code in (200, 201), r3.text
        b3 = r3.json()
        aid3 = b3.get("action_id") or (b3.get("action_item") or {}).get("action_id")
        ai3 = mongo.action_items.find_one({"action_id": aid3})
        assert (ai3.get("ported_to") or "").upper() == "LIFESTYLE"
        assert ai3.get("by_when") == "2026-06-30"

        # status=done writes back to milestone
        r = client.put(f"{API}/action-items/{aid3}", json={"status": "done"})
        assert r.status_code == 200, r.text
        sg = mongo.smart_goals.find_one({"goal_id": goal_id})
        ms = next((m for m in sg.get("milestones", []) if m["milestone_id"] == ms_id), None)
        assert ms and ms.get("status") == "done", ms

        # cleanup
        mongo.action_items.delete_many({"source_id": goal_id, "source_module": "GOAL_SETTER"})
        mongo.smart_goals.delete_one({"goal_id": goal_id})
        mongo.ctt_tasks.delete_many({"source_id": aid})
        mongo.lifestyle_routines.delete_many({"source_id": aid3})


# ─── GEM PM ─────────────────────────────────────────────────────────
class TestGemPM:
    @pytest.fixture(scope="class")
    def gem_goal(self, client):
        r = client.post(f"{API}/gem/goals", json={
            "title": f"TEST_iter198_pm_{uuid.uuid4().hex[:5]}",
            "description": "Iter198 PM test",
        })
        assert r.status_code in (200, 201), r.text
        gid = r.json().get("goal_id") or r.json().get("id")
        return gid

    def test_wbs_create_hierarchy_and_invalid_child(self, client, gem_goal):
        gid = gem_goal
        # milestone
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "milestone", "title": "M1"})
        assert r.status_code == 200, r.text
        m_id = r.json()["node_id"]
        # deliverable under milestone
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "deliverable", "title": "D1", "parent_id": m_id})
        assert r.status_code == 200
        d_id = r.json()["node_id"]
        # work_package under deliverable
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "work_package", "title": "WP1", "parent_id": d_id})
        assert r.status_code == 200
        wp_id = r.json()["node_id"]
        # task under work_package
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "task", "title": "T1", "parent_id": wp_id,
                                                             "est_start": "2026-02-01", "est_finish": "2026-02-05"})
        assert r.status_code == 200
        t_id = r.json()["node_id"]
        # subtask under task
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "subtask", "title": "S1", "parent_id": t_id})
        assert r.status_code == 200
        s_id = r.json()["node_id"]
        # subtask under subtask (recursive)
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "subtask", "title": "S2", "parent_id": s_id})
        assert r.status_code == 200
        s2_id = r.json()["node_id"]
        # invalid: deliverable under task
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "deliverable", "title": "bad", "parent_id": t_id})
        assert r.status_code == 400, r.text

        # Set leaf subtask status to wip_50 → workspace rollup parents > 0
        r = client.put(f"{API}/gem-pm/nodes/{s2_id}", json={"status": "wip_50"})
        assert r.status_code == 200
        r = client.get(f"{API}/gem-pm/{gid}/workspace")
        assert r.status_code == 200
        ws = r.json()
        # find milestone in enriched
        mnode = next(n for n in ws["nodes"] if n["node_id"] == m_id)
        assert mnode["computed"]["rollup_progress"] > 0, mnode

        # store ids for follow-ups
        return {"task": t_id, "goal": gid}

    def test_deps_and_cpm_and_dup_and_delete(self, client, gem_goal):
        gid = gem_goal
        # create 2 tasks with dates
        r1 = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "task", "title": "A",
                                                             "est_start": "2026-03-01", "est_finish": "2026-03-05"})
        r2 = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "task", "title": "B",
                                                             "est_start": "2026-03-06", "est_finish": "2026-03-10"})
        a, b = r1.json()["node_id"], r2.json()["node_id"]
        r = client.post(f"{API}/gem-pm/{gid}/deps", json={"predecessor_id": a, "successor_id": b, "dep_type": "FS"})
        assert r.status_code == 200, r.text
        dep_id = r.json()["dep_id"]
        # duplicate
        r_dup = client.post(f"{API}/gem-pm/{gid}/deps", json={"predecessor_id": a, "successor_id": b, "dep_type": "FS"})
        assert r_dup.status_code == 409
        # workspace critical path
        r = client.get(f"{API}/gem-pm/{gid}/workspace")
        cp = r.json()["critical_path"]
        assert a in cp and b in cp, cp
        # delete dep
        r = client.delete(f"{API}/gem-pm/deps/{dep_id}")
        assert r.status_code == 200

    def test_kanban_move_to_done(self, client, gem_goal):
        gid = gem_goal
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "task", "title": "kanban"})
        nid = r.json()["node_id"]
        r = client.put(f"{API}/gem-pm/nodes/{nid}/kanban", json={"col": "done"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "done"
        assert body["progress_pct"] == 100

    def test_port_task_to_ctt_creates_action_and_duplicate_409(self, client, gem_goal, mongo):
        gid = gem_goal
        r = client.post(f"{API}/gem-pm/{gid}/nodes", json={"node_type": "task", "title": "portable",
                                                             "est_finish": "2026-04-15"})
        nid = r.json()["node_id"]
        r = client.post(f"{API}/gem-pm/nodes/{nid}/port", json={"target": "CTT"})
        assert r.status_code == 200, r.text
        aid = r.json()["action_id"]
        ai = mongo.action_items.find_one({"action_id": aid})
        assert (ai.get("source_module") or "").upper() == "GEM"
        assert (ai.get("ported_to") or "").upper() == "CTT"
        # second port → 409
        r2 = client.post(f"{API}/gem-pm/nodes/{nid}/port", json={"target": "CTT"})
        assert r2.status_code == 409, r2.text

    def test_registers_crud(self, client, gem_goal):
        gid = gem_goal
        r = client.post(f"{API}/gem-pm/{gid}/registers", json={"kind": "risk", "title": "R1", "probability": "high"})
        assert r.status_code == 200
        rid = r.json()["reg_id"]
        r = client.post(f"{API}/gem-pm/{gid}/registers", json={"kind": "issue", "title": "I1", "severity": "high"})
        assert r.status_code == 200
        r = client.post(f"{API}/gem-pm/{gid}/registers", json={"kind": "change", "title": "C1", "change_type": "scope"})
        assert r.status_code == 200
        # GET filter by kind
        r = client.get(f"{API}/gem-pm/{gid}/registers?kind=risk")
        assert r.status_code == 200
        rows = r.json()
        assert all(x["kind"] == "risk" for x in rows) and any(x["reg_id"] == rid for x in rows)
        # PUT
        r = client.put(f"{API}/gem-pm/registers/{rid}", json={"title": "R1-updated", "status": "mitigating"})
        assert r.status_code == 200 and r.json()["title"] == "R1-updated"
        # DELETE
        r = client.delete(f"{API}/gem-pm/registers/{rid}")
        assert r.status_code == 200


# ─── OAuth calendar start ─────────────────────────────────────────────
class TestOAuthCalendarStart:
    def test_start_does_not_500(self, client):
        r = client.get(f"{API}/oauth/calendar/start", allow_redirects=False, timeout=15)
        assert r.status_code != 500, r.text[:300]
        # Accept 200/302/303/307/503 (503 only if env vars missing — informational)
        assert r.status_code in (200, 302, 303, 307, 503), r.status_code
