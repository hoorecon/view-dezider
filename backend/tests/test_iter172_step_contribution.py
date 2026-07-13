"""Iter172 — Multi-module step-share contribution (decision | pros_cons | solution_finder).

Covers:
  - POST /api/shared-steps/create (module-aware)
  - GET  /api/shared-steps/{id}/decision (decision-only owner doc for recipient)
  - POST /api/shared-steps/{id}/open  → returns target_id (decision: same id; PC/SF: NEW clone id)
  - POST /api/shared-steps/{id}/contribute (snapshot for clone modules)
  - DELETE /api/shared-steps/{id}/contribution
  - Clone docs are hidden from contributor's lists (/api/pros-cons, /api/solution-finders, /api/solution-box)

Run: cd /app/backend && PYTHONPATH=/app/backend pytest tests/test_iter172_step_contribution.py -v
"""
import os
import pytest
import requests

BASE = (os.environ.get("EXPO_BACKEND_URL") or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/") + "/api"


def _login(email: str, pwd: str):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    d = r.json()
    return d["session_token"], d["user_id"]


@pytest.fixture(scope="module")
def owner_ctx():
    tok, uid = _login("super@test.com", "SuperPass2026!")
    return {"token": tok, "uid": uid, "h": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def contrib_ctx():
    tok, uid = _login("admin@test.com", "AdminPass2026!")
    return {"token": tok, "uid": uid, "h": {"Authorization": f"Bearer {tok}"}}


# ──────────────────────────── DECISION ────────────────────────────
class TestDecisionShareContribute:
    def test_create_decision_share_and_full_flow(self, owner_ctx, contrib_ctx):
        # 1) owner creates a decision via module-aware /shared-steps/create requires existing decision
        # Use the well-known seeded share path: list owner's decisions
        decs = requests.get(f"{BASE}/decisions", headers=owner_ctx["h"], timeout=30)
        assert decs.status_code == 200
        if not decs.json():
            pytest.skip("Owner has no decisions to share")
        dec = decs.json()[0]
        dec_id = dec["id"]

        # Create share via module-aware endpoint
        sr = requests.post(f"{BASE}/shared-steps/create", headers=owner_ctx["h"], json={
            "module": "decision", "module_id": dec_id, "step_number": 7,
            "recipient_emails": ["admin@test.com"],
            "merge_mode": "equal", "message": "iter172 test", "step_access": "readonly",
        }, timeout=30)
        assert sr.status_code == 200, sr.text
        share_id = sr.json()["id"]
        assert sr.json()["shared_count"] >= 1

        try:
            # 2) GET /shared-steps/{id}/decision returns owner decision
            dr = requests.get(f"{BASE}/shared-steps/{share_id}/decision", headers=contrib_ctx["h"], timeout=30)
            assert dr.status_code == 200, dr.text
            body = dr.json()
            assert body["decision"]["id"] == dec_id
            assert body["share"]["step_access"] == "readonly"

            # 3) /open returns same decision_id as target_id
            op = requests.post(f"{BASE}/shared-steps/{share_id}/open", headers=contrib_ctx["h"], timeout=30)
            assert op.status_code == 200
            assert op.json()["module"] == "decision"
            assert op.json()["target_id"] == dec_id  # for decisions, target == owner doc

            # 4) contribute
            cb = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=contrib_ctx["h"], json={
                "assessments": {"x_y": 50}, "note": "iter172"
            }, timeout=30)
            assert cb.status_code == 200, cb.text

            # 5) withdraw
            wr = requests.delete(f"{BASE}/shared-steps/{share_id}/contribution", headers=contrib_ctx["h"], timeout=30)
            assert wr.status_code == 200, wr.text
            assert wr.json().get("ok") is True
        finally:
            # cleanup share
            requests.delete(f"{BASE}/shared-steps/{share_id}", headers=owner_ctx["h"], timeout=15)


# ──────────────────────────── PROS & CONS ────────────────────────────
class TestProsConsShareContribute:
    def test_pc_clone_flow_and_list_exclusion(self, owner_ctx, contrib_ctx):
        # 1) Owner creates a P&C
        cr = requests.post(f"{BASE}/pros-cons", headers=owner_ctx["h"], json={
            "title": "TEST_iter172 PC Demo", "context": "ctx",
            "life_area": "career", "decision_type": "strategic",
        }, timeout=30)
        assert cr.status_code == 200, cr.text
        pc_id = cr.json()["id"]

        # Snapshot contributor's list counts BEFORE clone exists
        list_before = requests.get(f"{BASE}/pros-cons", headers=contrib_ctx["h"], timeout=30).json()
        ids_before = {x["id"] for x in list_before}
        sb_before = requests.get(f"{BASE}/solution-box", headers=contrib_ctx["h"], timeout=30)
        sb_ids_before = set()
        if sb_before.status_code == 200:
            for it in sb_before.json() if isinstance(sb_before.json(), list) else sb_before.json().get("items", []):
                sb_ids_before.add(it.get("id"))

        # 2) Share PC step 3 to admin
        sr = requests.post(f"{BASE}/shared-steps/create", headers=owner_ctx["h"], json={
            "module": "pros_cons", "module_id": pc_id, "step_number": 3,
            "recipient_emails": ["admin@test.com"], "merge_mode": "equal",
            "step_access": "hidden",
        }, timeout=30)
        assert sr.status_code == 200, sr.text
        share_id = sr.json()["id"]

        clone_id = None
        try:
            # 3) Admin opens → returns NEW clone id
            op = requests.post(f"{BASE}/shared-steps/{share_id}/open", headers=contrib_ctx["h"], timeout=30)
            assert op.status_code == 200, op.text
            assert op.json()["module"] == "pros_cons"
            clone_id = op.json()["target_id"]
            assert clone_id and clone_id != pc_id

            # 4) Admin can load the clone via normal endpoint
            gc = requests.get(f"{BASE}/pros-cons/{clone_id}", headers=contrib_ctx["h"], timeout=30)
            assert gc.status_code == 200
            assert gc.json()["title"] == "TEST_iter172 PC Demo"

            # 4b) Clone must NOT be in contributor's normal P&C list
            list_after = requests.get(f"{BASE}/pros-cons", headers=contrib_ctx["h"], timeout=30).json()
            ids_after = {x["id"] for x in list_after}
            assert clone_id not in ids_after, "Clone leaked into /api/pros-cons list!"
            # Also: list count must not grow due to clone
            assert ids_after == ids_before, f"Unexpected list churn. Diff: {ids_after ^ ids_before}"

            # 4c) Clone must NOT be in solution-box aggregator either
            sb_after = requests.get(f"{BASE}/solution-box", headers=contrib_ctx["h"], timeout=30)
            if sb_after.status_code == 200:
                items = sb_after.json() if isinstance(sb_after.json(), list) else sb_after.json().get("items", [])
                sb_ids_after = {it.get("id") for it in items}
                assert clone_id not in sb_ids_after, "Clone leaked into /api/solution-box!"

            # 5) Contribute → snapshot saved on owner share doc
            cb = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=contrib_ctx["h"], json={
                "note": "iter172 pc submit"
            }, timeout=30)
            assert cb.status_code == 200, cb.text

            # 6) Withdraw works
            wr = requests.delete(f"{BASE}/shared-steps/{share_id}/contribution", headers=contrib_ctx["h"], timeout=30)
            assert wr.status_code == 200
        finally:
            requests.delete(f"{BASE}/pros-cons/{pc_id}", headers=owner_ctx["h"], timeout=15)
            if clone_id:
                requests.delete(f"{BASE}/pros-cons/{clone_id}", headers=contrib_ctx["h"], timeout=15)
            requests.delete(f"{BASE}/shared-steps/{share_id}", headers=owner_ctx["h"], timeout=15)


# ──────────────────────────── SOLUTION FINDER ────────────────────────────
class TestSolutionFinderShareContribute:
    def test_sf_clone_flow_and_list_exclusion(self, owner_ctx, contrib_ctx):
        # 1) Owner creates a SF
        cr = requests.post(f"{BASE}/solution-finders", headers=owner_ctx["h"], json={
            "title": "TEST_iter172 SF Demo",
            "context": "iter172 sf demo",
            "life_area": "career",
        }, timeout=30)
        assert cr.status_code in (200, 201), cr.text
        sf = cr.json()
        sf_id = sf.get("id") or sf.get("entry_id")
        assert sf_id, f"no id in SF create response: {sf}"

        # Snapshot contributor SF list + solution-box before
        before = requests.get(f"{BASE}/solution-finders", headers=contrib_ctx["h"], timeout=30).json()
        ids_before = {x.get("id") or x.get("entry_id") for x in before}
        sb_before = requests.get(f"{BASE}/solution-box", headers=contrib_ctx["h"], timeout=30)
        sb_ids_before = set()
        if sb_before.status_code == 200:
            items = sb_before.json() if isinstance(sb_before.json(), list) else sb_before.json().get("items", [])
            sb_ids_before = {it.get("id") for it in items}

        # 2) Share SF (SF steps are 0-indexed → use 2)
        sr = requests.post(f"{BASE}/shared-steps/create", headers=owner_ctx["h"], json={
            "module": "solution_finder", "module_id": sf_id, "step_number": 2,
            "recipient_emails": ["admin@test.com"], "merge_mode": "equal",
            "step_access": "hidden",
        }, timeout=30)
        assert sr.status_code == 200, sr.text
        share_id = sr.json()["id"]

        clone_id = None
        try:
            # 3) admin opens → NEW clone id
            op = requests.post(f"{BASE}/shared-steps/{share_id}/open", headers=contrib_ctx["h"], timeout=30)
            assert op.status_code == 200, op.text
            assert op.json()["module"] == "solution_finder"
            clone_id = op.json()["target_id"]
            assert clone_id and clone_id != sf_id
            assert op.json()["step_number"] == 2

            # 4) admin can load the clone
            gc = requests.get(f"{BASE}/solution-finders/{clone_id}", headers=contrib_ctx["h"], timeout=30)
            assert gc.status_code == 200, gc.text

            # 4b) clone not in contributor's SF list
            after = requests.get(f"{BASE}/solution-finders", headers=contrib_ctx["h"], timeout=30).json()
            ids_after = {x.get("id") or x.get("entry_id") for x in after}
            assert clone_id not in ids_after, "SF clone leaked into /api/solution-finders!"
            assert ids_after == ids_before

            # 4c) clone not in solution-box
            sb_after = requests.get(f"{BASE}/solution-box", headers=contrib_ctx["h"], timeout=30)
            if sb_after.status_code == 200:
                items = sb_after.json() if isinstance(sb_after.json(), list) else sb_after.json().get("items", [])
                sb_ids_after = {it.get("id") for it in items}
                assert clone_id not in sb_ids_after, "SF clone leaked into /api/solution-box!"

            # 5) contribute
            cb = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=contrib_ctx["h"], json={
                "note": "iter172 sf submit"
            }, timeout=30)
            assert cb.status_code == 200, cb.text

            # 6) withdraw
            wr = requests.delete(f"{BASE}/shared-steps/{share_id}/contribution", headers=contrib_ctx["h"], timeout=30)
            assert wr.status_code == 200
        finally:
            requests.delete(f"{BASE}/solution-finders/{sf_id}", headers=owner_ctx["h"], timeout=15)
            if clone_id:
                requests.delete(f"{BASE}/solution-finders/{clone_id}", headers=contrib_ctx["h"], timeout=15)
            requests.delete(f"{BASE}/shared-steps/{share_id}", headers=owner_ctx["h"], timeout=15)
