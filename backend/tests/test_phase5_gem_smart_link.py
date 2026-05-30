"""
Phase 5 backend tests — GEM ↔ SMART Goal linkage + milestones + contacts (Self/SME/resources).
Covers:
  - POST /api/goal-setter/goals with metrics/achievable_skills/realistic_resources/milestones
  - POST /api/goal-setter/goals/{gid}/milestones
  - PUT  /api/goal-setter/goals/{gid}/milestones/{mid}/status  (lightweight updater)
  - PUT/GET /api/gem/goals/{gid} with linked_smart_goal_id
  - POST /api/contacts/ensure-self (idempotency)
  - POST /api/contacts with is_sme/skillset/resources/social_links/time_bandwidth
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"No token returned: {data}"
    return tok


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return s


# ─────────────────────────────────────────────────────────────
# Section A — SMART Goal create with full enrichment
# ─────────────────────────────────────────────────────────────
class TestSmartGoalCreate:
    goal_id = None
    milestone_id = None

    def test_create_goal_with_metrics_skills_resources_milestones(self, client):
        payload = {
            "title": f"TEST_SMART_{uuid.uuid4().hex[:6]}",
            "life_area": "career",
            "specific": "Launch product",
            "measurable": "MRR target",
            "metrics": [
                {"name": "MRR", "unit": "INR", "type": "currency",
                 "operator": ">=", "target_value": 1000000, "set_by": "self", "owner_role": "founder"}
            ],
            "achievable": "Yes with team",
            "achievable_skills": [{"skill": "Coding", "contact_id": "c1", "contact_name": "Self"}],
            "realistic": "Yes market timing good",
            "realistic_resources": [
                {"resource_type": "finance", "contact_id": "c1", "amount": 500000, "currency": "INR"}
            ],
            "timebound": "12 months",
            "milestones": [
                {"title": "MVP", "specific": "Build MVP", "measurable": "1 release",
                 "achievable": "Y", "realistic": "Y", "timebound": "3mo",
                 "target_date": "2026-04-30", "status": "pending", "progress_pct": 0,
                 "metrics": [{"name": "Releases", "type": "count", "operator": ">=", "target_value": 1}]}
            ],
            "priority": "high",
            "status": "active",
        }
        r = client.post(f"{API}/goal-setter/goals", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["goal_id"].startswith("GOAL-")
        assert data["title"] == payload["title"]
        assert isinstance(data["metrics"], list) and data["metrics"][0]["name"] == "MRR"
        assert data["achievable_skills"][0]["skill"] == "Coding"
        assert data["realistic_resources"][0]["resource_type"] == "finance"
        assert len(data["milestones"]) == 1
        assert data["milestones"][0]["title"] == "MVP"
        assert data["milestones"][0]["status"] == "pending"
        TestSmartGoalCreate.goal_id = data["goal_id"]
        # NOTE: Inline milestones at create time are stored verbatim and do NOT
        # get an auto-assigned milestone_id from _make_milestone(). Frontend
        # works around this by promoting "draft_" milestones via POST
        # /goals/{gid}/milestones after create, so the GEM read-only flow keeps
        # working. Flagged as a minor backend issue in the test report.
        TestSmartGoalCreate.milestone_id = data["milestones"][0].get("milestone_id")

    def test_get_persists(self, client):
        assert TestSmartGoalCreate.goal_id
        r = client.get(f"{API}/goal-setter/goals/{TestSmartGoalCreate.goal_id}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["metrics"][0]["target_value"] == 1000000
        assert len(d["milestones"]) == 1


# ─────────────────────────────────────────────────────────────
# Section B — Milestones add + status updater
# ─────────────────────────────────────────────────────────────
class TestMilestones:
    extra_mid = None

    def test_add_milestone_with_smart_fields(self, client):
        gid = TestSmartGoalCreate.goal_id
        assert gid
        body = {
            "title": "Phase 2 Beta",
            "specific": "Beta launch", "measurable": "10 users",
            "achievable": "Y", "realistic": "Y", "timebound": "6mo",
            "metrics": [{"name": "Users", "type": "count", "operator": ">=", "target_value": 10}],
            "target_date": "2026-07-31",
        }
        r = client.post(f"{API}/goal-setter/goals/{gid}/milestones", json=body, timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["title"] == "Phase 2 Beta"
        assert m["status"] == "pending"
        assert m["progress_pct"] == 0
        assert m["milestone_id"].startswith("ms_")
        TestMilestones.extra_mid = m["milestone_id"]

    def test_status_in_progress(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"status": "in_progress", "progress_pct": 35},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["status"] == "in_progress"
        assert m["progress_pct"] == 35

    def test_status_done_auto_sets_100(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"status": "done"},
            timeout=15,
        )
        assert r.status_code == 200
        m = r.json()
        assert m["status"] == "done"
        assert m["progress_pct"] == 100

    def test_progress_pct_clamps_above_100(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"status": "in_progress", "progress_pct": 250},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["progress_pct"] == 100

    def test_progress_pct_clamps_below_0(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"progress_pct": -50},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["progress_pct"] == 0

    def test_invalid_status_rejected(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"status": "bogus_status"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_blocked_status(self, client):
        gid, mid = TestSmartGoalCreate.goal_id, TestMilestones.extra_mid
        r = client.put(
            f"{API}/goal-setter/goals/{gid}/milestones/{mid}/status",
            json={"status": "blocked"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "blocked"


# ─────────────────────────────────────────────────────────────
# Section C — GEM goal linked_smart_goal_id
# ─────────────────────────────────────────────────────────────
class TestGemSmartLink:
    gem_goal_id = None

    def test_create_gem_goal(self, client):
        r = client.post(
            f"{API}/gem/goals",
            json={
                "title": f"TEST_GEM_{uuid.uuid4().hex[:6]}",
                "life_area": "career",
                "goal_type": "aspiration",
                "smart_goal": "Launch SaaS product",
                "priority": "high",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("goal_id")
        assert d.get("linked_smart_goal_id") is None
        TestGemSmartLink.gem_goal_id = d["goal_id"]

    def test_put_linked_smart_goal_id(self, client):
        smart_gid = TestSmartGoalCreate.goal_id
        gem_gid = TestGemSmartLink.gem_goal_id
        assert smart_gid and gem_gid
        r = client.put(
            f"{API}/gem/goals/{gem_gid}",
            json={"linked_smart_goal_id": smart_gid},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["linked_smart_goal_id"] == smart_gid

    def test_get_returns_linked_id(self, client):
        gem_gid = TestGemSmartLink.gem_goal_id
        r = client.get(f"{API}/gem/goals/{gem_gid}", timeout=15)
        assert r.status_code == 200
        assert r.json()["linked_smart_goal_id"] == TestSmartGoalCreate.goal_id

    def test_unlink_persists_null(self, client):
        gem_gid = TestGemSmartLink.gem_goal_id
        r = client.put(
            f"{API}/gem/goals/{gem_gid}",
            json={"linked_smart_goal_id": None},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["linked_smart_goal_id"] is None
        # And GET reflects null too
        g = client.get(f"{API}/gem/goals/{gem_gid}", timeout=15).json()
        assert g["linked_smart_goal_id"] is None


# ─────────────────────────────────────────────────────────────
# Section D — Contacts: ensure-self idempotency + create with rich profile
# ─────────────────────────────────────────────────────────────
class TestContactsPhase1:
    self_contact_id = None
    sme_contact_id = None

    def test_ensure_self_idempotent(self, client):
        r1 = client.post(f"{API}/contacts/ensure-self", timeout=15)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["is_self"] is True
        assert d1["id"].startswith("contact_")
        TestContactsPhase1.self_contact_id = d1["id"]

        r2 = client.post(f"{API}/contacts/ensure-self", timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["id"] == d1["id"], "ensure-self must return same Self contact id"
        assert d2["is_self"] is True

    def test_create_contact_with_rich_profile(self, client):
        payload = {
            "name": f"TEST_SME_{uuid.uuid4().hex[:6]}",
            "email": f"test_sme_{uuid.uuid4().hex[:4]}@example.com",
            "is_sme": True,
            "sme_domains": ["AI", "Product"],
            "skills": ["Python", "Strategy"],
            "time_bandwidth_hours_per_month": 20,
            "resources": {
                "finance": {"amount": 250000, "currency": "USD", "note": "Angel"},
                "infrastructure": {"description": "Office 1000 sqft", "note": "Bangalore"},
                "people_connects": {"count": 50, "note": "VC network"},
            },
            "social_links": {
                "linkedin": "https://linkedin.com/in/test",
                "x": "https://x.com/test",
                "youtube": "",
            },
            "org_type": "business",
            "org_subtype": "pvt_ltd",
        }
        r = client.post(f"{API}/contacts", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        TestContactsPhase1.sme_contact_id = d["id"]
        assert d["is_sme"] is True
        assert d["sme_domains"] == ["AI", "Product"]
        assert d["time_bandwidth_hours_per_month"] == 20.0
        assert d["resources"]["finance"]["amount"] == 250000.0
        assert d["resources"]["finance"]["currency"] == "USD"
        assert d["resources"]["infrastructure"]["description"] == "Office 1000 sqft"
        assert d["resources"]["people_connects"]["count"] == 50
        assert d["social_links"]["linkedin"] == "https://linkedin.com/in/test"
        assert d["social_links"]["x"] == "https://x.com/test"
        # All social_link keys should exist (normalized)
        for k in ["gmail", "official_email", "whatsapp", "telegram",
                  "linkedin", "youtube", "instagram", "facebook", "x", "reddit"]:
            assert k in d["social_links"]

    def test_get_contact_roundtrip(self, client):
        cid = TestContactsPhase1.sme_contact_id
        assert cid
        r = client.get(f"{API}/contacts/{cid}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["resources"]["finance"]["amount"] == 250000.0
        assert d["time_bandwidth_hours_per_month"] == 20.0
        assert d["is_sme"] is True

    def test_skills_aggregate_includes_sme_skills(self, client):
        r = client.get(f"{API}/contacts/skills/aggregate", timeout=15)
        assert r.status_code == 200
        skills = [s["skill"] for s in r.json().get("skills", [])]
        assert "Python" in skills or "Strategy" in skills

    def test_self_contact_cannot_be_deleted(self, client):
        cid = TestContactsPhase1.self_contact_id
        r = client.delete(f"{API}/contacts/{cid}", timeout=15)
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────
# Section E — Cleanup
# ─────────────────────────────────────────────────────────────
class TestZCleanup:
    def test_cleanup(self, client):
        gid = TestSmartGoalCreate.goal_id
        if gid:
            client.delete(f"{API}/goal-setter/goals/{gid}", timeout=15)
        gem_gid = TestGemSmartLink.gem_goal_id
        if gem_gid:
            client.delete(f"{API}/gem/goals/{gem_gid}", timeout=15)
        sme_id = TestContactsPhase1.sme_contact_id
        if sme_id:
            client.delete(f"{API}/contacts/{sme_id}", timeout=15)
