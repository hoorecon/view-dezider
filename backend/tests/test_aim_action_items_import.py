"""
Tests for AIM → Action Items Planner import flow.

Covers POST /api/action-items/import-from-aim/{session_id} end-to-end:
- grouping (commitments → one_time, addictions → corrective+routine, irritations → weekly routine)
- priority bucketing
- by_when timing (today / +7 / +30)
- idempotency on re-import
- listing via source_module=AIM
- porting one_time → CTT and recurring → LifeStyle
- edge cases: empty AIM (no addictions / no irritations), no breakthrough report,
  permission boundary (another user cannot import).
"""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ───── Helpers / fixtures ────────────────────────────────────────────────

def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN_EMAIL, ADMIN_PASS)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def other_user_headers():
    """Throwaway user for permission boundary test."""
    import time
    email = f"aim_other_{int(time.time())}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "OtherPass2026!", "name": "AIM Other"},
        timeout=30,
    )
    if r.status_code in (200, 201):
        tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    else:
        # already exists — try login
        tok = _login(email, "OtherPass2026!")
    assert tok
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _mk_session(headers, title="TEST_AIM_Import"):
    r = requests.post(
        f"{API}/emotional-gatekeeper/sessions",
        headers=headers,
        json={"session_type": "aim", "title": title},
        timeout=30,
    )
    assert r.status_code == 200, f"create session failed: {r.status_code} {r.text}"
    return r.json()["id"]


def _save_aim(headers, sid, addictions, irritations):
    r = requests.post(
        f"{API}/emotional-gatekeeper/aim/{sid}/save",
        headers=headers,
        json={"addictions": addictions, "irritations": irritations},
        timeout=30,
    )
    assert r.status_code == 200, f"aim save failed: {r.status_code} {r.text}"
    return r.json()


def _add_commit(headers, sid, ctype, text, due=None):
    payload = {"commitment_type": ctype, "commitment_text": text, "reminder_enabled": False}
    if due:
        payload["due_date"] = due
    r = requests.post(
        f"{API}/emotional-gatekeeper/sessions/{sid}/commitments",
        headers=headers,
        json=payload,
        timeout=30,
    )
    assert r.status_code == 200, f"add commit failed: {r.status_code} {r.text}"
    return r.json()


# ───── Tests ──────────────────────────────────────────────────────────────

class TestAimImportFull:
    """End-to-end: addictions + irritations + commitments → import → list → port."""

    @pytest.fixture(scope="class")
    def context(self, admin_headers):
        sid = _mk_session(admin_headers, title="TEST_AIM_Full")
        _save_aim(
            admin_headers,
            sid,
            addictions=[
                {
                    "area_of_life": "health",
                    "addiction": "TEST_late_night_snacking",
                    "negative_impact_pct": 80,
                    "corrective_actions": "TEST stop after 9pm; brush teeth early",
                    "triggering_situations": "stress",
                    "negative_impact": "weight gain",
                    "task_owner_timeline": "Me / 2 weeks",
                },
                {
                    "area_of_life": "career",
                    "addiction": "TEST_doomscrolling",
                    "negative_impact_pct": 40,
                    # NO corrective_actions on this one — should only generate routine
                },
            ],
            irritations=[
                {
                    "area_of_life": "relationships",
                    "irritation": "TEST_messy_kitchen",
                    "irritation_pct": 65,
                    "probable_reaction": "snap at spouse",
                    "negative_impact": "tense evenings",
                },
            ],
        )
        _add_commit(admin_headers, sid, "immediate", "TEST do the kitchen sweep tonight")
        _add_commit(admin_headers, sid, "7_day", "TEST cook 3 dinners this week")
        _add_commit(admin_headers, sid, "30_day", "TEST hit gym 3x/week")
        return {"sid": sid}

    def test_import_first_call_creates_items(self, admin_headers, context):
        sid = context["sid"]
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        # 3 commitments + 1 corrective (addiction #1 only) = 4 one_time
        # 2 addictions × 1 daily routine + 1 irritation × 1 weekly routine = 3 recurring
        assert body["imported_count"] == 7, body
        assert body["ctt_count"] == 4, body
        assert body["lifestyle_count"] == 3, body
        # remember imported for assertions in next steps
        context["imported"] = body["imported"]

    def test_grouping_and_priorities(self, context):
        imported = context["imported"]
        # Find by title hints
        by_title = {it["title"]: it for it in imported}

        # 1) high-impact addiction (80%) corrective → priority=urgent, one_time
        addiction_act = [it for it in imported if "Addiction · Action" in it["title"]]
        assert len(addiction_act) == 1
        assert addiction_act[0]["priority"] == "urgent"
        assert addiction_act[0]["recurrence_type"] == "one_time"

        # 2) Both addictions have daily routine
        daily_routines = [it for it in imported if "Addiction · Routine" in it["title"]]
        assert len(daily_routines) == 2
        for r_ in daily_routines:
            assert r_["recurrence_type"] == "recurring"
            assert r_["recurrence_frequency"] == "daily"

        # 3) Irritation → weekly recurring
        irr = [it for it in imported if "Irritation · Routine" in it["title"]]
        assert len(irr) == 1
        assert irr[0]["recurrence_type"] == "recurring"
        assert irr[0]["recurrence_frequency"] == "weekly"
        # 65% → high
        assert irr[0]["priority"] == "high"

        # 4) Commitments with by_when bucketing
        today = date.today()
        immed = [it for it in imported if "Commitment · immediate" in it["title"]]
        d7    = [it for it in imported if "Commitment · 7-day" in it["title"]]
        d30   = [it for it in imported if "Commitment · 30-day" in it["title"]]
        assert len(immed) == len(d7) == len(d30) == 1
        assert immed[0]["priority"] == "urgent"
        assert immed[0]["by_when"] == today.isoformat()
        assert d7[0]["priority"] == "high"
        # +7 days (allow ±1d for boundary)
        d7_target = (today + timedelta(days=7)).isoformat()
        assert d7[0]["by_when"] == d7_target
        assert d30[0]["priority"] == "medium"
        d30_target = (today + timedelta(days=30)).isoformat()
        assert d30[0]["by_when"] == d30_target

    def test_idempotent_second_import(self, admin_headers, context):
        sid = context["sid"]
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["imported_count"] == 0, body
        assert body["ctt_count"] == 0
        assert body["lifestyle_count"] == 0

    def test_list_filtered_by_aim_source(self, admin_headers, context):
        r = requests.get(
            f"{API}/action-items?source_module=AIM",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        items = r.json()
        # may include older AIM items from other test runs; we just confirm OUR 7 are there
        sid = context["sid"]
        ours = [it for it in items if it.get("source_id") == sid]
        assert len(ours) == 7, f"expected 7 for {sid}, got {len(ours)}"
        # Save for next test
        context["items"] = ours

    def test_port_one_time_to_ctt(self, admin_headers, context):
        one_time = [it for it in context["items"] if it["recurrence_type"] == "one_time"]
        assert one_time, "need at least one one_time item"
        target = one_time[0]
        r = requests.post(
            f"{API}/action-items/{target['action_id']}/port-to-ctt",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action_item"]["ported_to"] == "CTT"
        assert body["action_item"]["ported_ref_id"] == body["ctt_task"]["task_id"]

    def test_port_recurring_to_lifestyle(self, admin_headers, context):
        rec = [it for it in context["items"] if it["recurrence_type"] == "recurring"]
        assert rec, "need at least one recurring item"
        target = rec[0]
        r = requests.post(
            f"{API}/action-items/{target['action_id']}/port-to-lifestyle",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["action_item"]["ported_to"] == "LIFESTYLE"
        assert body["action_item"]["ported_ref_id"] == body["lifestyle_routine"]["routine_id"]


class TestAimImportEdges:
    """Edge cases: empty AIM, no report, permission boundary."""

    def test_no_aim_no_commitments_returns_zero(self, admin_headers):
        sid = _mk_session(admin_headers, title="TEST_AIM_Empty")
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["imported_count"] == 0
        assert body["ctt_count"] == 0
        assert body["lifestyle_count"] == 0

    def test_only_irritation_no_addictions(self, admin_headers):
        sid = _mk_session(admin_headers, title="TEST_AIM_OnlyIrr")
        _save_aim(
            admin_headers, sid,
            addictions=[],
            irritations=[
                {"area_of_life": "health", "irritation": "TEST_traffic_noise",
                 "irritation_pct": 30, "probable_reaction": "frustrated"}
            ],
        )
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["imported_count"] == 1, body
        assert body["lifestyle_count"] == 1
        assert body["ctt_count"] == 0
        # 30% → medium
        assert body["imported"][0]["priority"] == "medium"
        assert body["imported"][0]["recurrence_frequency"] == "weekly"

    def test_addiction_without_corrective_only_creates_routine(self, admin_headers):
        sid = _mk_session(admin_headers, title="TEST_AIM_NoCorrective")
        _save_aim(
            admin_headers, sid,
            addictions=[{
                "area_of_life": "career", "addiction": "TEST_no_corrective_item",
                "negative_impact_pct": 55,
            }],
            irritations=[],
        )
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=admin_headers, timeout=30,
        )
        body = r.json()
        assert body["imported_count"] == 1
        assert body["ctt_count"] == 0
        assert body["lifestyle_count"] == 1
        assert body["imported"][0]["priority"] == "high"  # 55%

    def test_permission_boundary_other_user_404(self, admin_headers, other_user_headers):
        # admin creates the session
        sid = _mk_session(admin_headers, title="TEST_AIM_PermBoundary")
        # the OTHER user must NOT be able to import — should 404
        r = requests.post(
            f"{API}/action-items/import-from-aim/{sid}",
            headers=other_user_headers, timeout=30,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text}"

    def test_unknown_session_returns_404(self, admin_headers):
        r = requests.post(
            f"{API}/action-items/import-from-aim/EG-DOESNOTEXIST",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 404
