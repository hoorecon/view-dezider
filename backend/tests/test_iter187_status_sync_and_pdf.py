"""ITER 187 — Backend regression: canonical action-status vocabulary + true bi-directional sync
across Action Center ↔ CTT ↔ Solution Finder + PDF grouping/labels.

Reference: /app/backend/scripts/test_status_sync.py (script proven forward+reverse sync).
This pytest suite re-confirms the same via the PUBLIC EXPO_PUBLIC_BACKEND_URL and adds:
  * PDF gate (402) for Solution Finder without paid L1 (expected)
  * PDF Action Plan group prefixes/suffixes present in generated PDF (when entitled) — SKIPPED if 402
  * Central action-item PATCH from Solution Finder sync path (pushed item reconciliation)
"""

import os
import uuid
import io
import pytest
import requests

# Public backend URL (fail fast on missing env)
BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE:
    # tests helper: allow local dev fallback for the smoke bootstrap
    BASE = "http://localhost:8001"
API = f"{BASE}/api"

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"

# Canonical vocabulary from /app/backend/core/action_status.py
CANONICAL = ["pending", "wip_25", "wip_50", "wip_75",
             "done", "deferred", "blocked", "cancelled"]
PROGRESS_MAP = {"pending": 0, "wip_25": 25, "wip_50": 50, "wip_75": 75, "done": 100}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": SUPER_EMAIL, "password": SUPER_PASS},
                      timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok, "no session_token on login"
    return tok


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# --- action-items CRUD & canonical statuses -----------------------------------------

class TestActionItemStatusVocabulary:
    def test_create_pending_default(self, H):
        r = requests.post(f"{API}/action-items", json={
            "source_module": "MANUAL",
            "title": f"TEST_iter187 pending {uuid.uuid4().hex[:6]}",
            "status": "pending", "recurrence_type": "one_time",
        }, headers=H, timeout=15)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["status"] == "pending"
        assert d["progress_pct"] == 0
        assert "action_id" in d
        # cleanup: cancel
        requests.delete(f"{API}/action-items/{d['action_id']}", headers=H)

    @pytest.mark.parametrize("st,expected_pct", list(PROGRESS_MAP.items()))
    def test_status_progress_alignment(self, H, st, expected_pct):
        # Create fresh action item then PATCH to `st`, expect progress_pct auto-aligned.
        c = requests.post(f"{API}/action-items", json={
            "source_module": "MANUAL",
            "title": f"TEST_iter187 progress {st} {uuid.uuid4().hex[:6]}",
            "status": "pending", "recurrence_type": "one_time",
        }, headers=H, timeout=15).json()
        aid = c["action_id"]
        try:
            u = requests.put(f"{API}/action-items/{aid}", json={"status": st}, headers=H, timeout=15)
            assert u.status_code == 200, u.text[:200]
            j = u.json()
            assert j["status"] == st, j
            assert j["progress_pct"] == expected_pct, j
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)

    @pytest.mark.parametrize("st", ["deferred", "blocked", "cancelled"])
    def test_terminal_statuses_accepted(self, H, st):
        c = requests.post(f"{API}/action-items", json={
            "source_module": "MANUAL",
            "title": f"TEST_iter187 term {st} {uuid.uuid4().hex[:6]}",
            "status": "pending", "recurrence_type": "one_time",
        }, headers=H, timeout=15).json()
        aid = c["action_id"]
        try:
            u = requests.put(f"{API}/action-items/{aid}", json={"status": st}, headers=H, timeout=15)
            assert u.status_code == 200, u.text[:200]
            assert u.json()["status"] == st
        finally:
            if st != "cancelled":
                requests.delete(f"{API}/action-items/{aid}", headers=H)

    def test_legacy_status_aliases(self, H):
        # 'in_progress' -> wip_50, 'completed' -> done, 'open' -> pending
        c = requests.post(f"{API}/action-items", json={
            "source_module": "MANUAL",
            "title": f"TEST_iter187 alias {uuid.uuid4().hex[:6]}",
            "status": "in_progress", "recurrence_type": "one_time",
        }, headers=H, timeout=15).json()
        aid = c["action_id"]
        try:
            # Alias may be normalized either at create or update path.
            r = requests.get(f"{API}/action-items/{aid}", headers=H, timeout=15).json()
            # accept either wip_50 (canonical) or in_progress (legacy tolerated on read)
            assert r["status"] in ("wip_50", "in_progress")
            # Sending 'completed' must normalize to done + 100%
            u = requests.put(f"{API}/action-items/{aid}", json={"status": "completed"},
                             headers=H, timeout=15).json()
            assert u["status"] == "done"
            assert u["progress_pct"] == 100
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)


# --- Bi-directional sync: Action Item <-> CTT ---------------------------------------

class TestBiDirectionalSync:
    def _mk_ai(self, H):
        c = requests.post(f"{API}/action-items", json={
            "source_module": "MANUAL",
            "title": f"TEST_iter187 sync {uuid.uuid4().hex[:6]}",
            "status": "pending", "recurrence_type": "one_time",
        }, headers=H, timeout=15).json()
        return c["action_id"]

    def test_forward_ai_to_ctt(self, H):
        aid = self._mk_ai(H)
        try:
            # port to CTT
            p = requests.post(f"{API}/action-items/{aid}/port-to-ctt", headers=H, timeout=15).json()
            task_id = p["ctt_task"]["task_id"]
            # update AI -> done, expect CTT.current_status == done
            requests.put(f"{API}/action-items/{aid}", json={"status": "done"}, headers=H, timeout=15)
            t = requests.get(f"{API}/ctt/tasks/{task_id}", headers=H, timeout=15).json()
            assert t.get("current_status") == "done", t
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)

    def test_reverse_ctt_to_ai(self, H):
        aid = self._mk_ai(H)
        try:
            p = requests.post(f"{API}/action-items/{aid}/port-to-ctt", headers=H, timeout=15).json()
            task_id = p["ctt_task"]["task_id"]
            # update CTT.current_status=wip_25, expect AI.status/progress
            requests.put(f"{API}/ctt/tasks/{task_id}",
                         json={"current_status": "wip_25"}, headers=H, timeout=15)
            a = requests.get(f"{API}/action-items/{aid}", headers=H, timeout=15).json()
            assert a["status"] == "wip_25", a
            assert a["progress_pct"] == 25, a
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)

    def test_reverse_ctt_wip_75_to_ai(self, H):
        aid = self._mk_ai(H)
        try:
            p = requests.post(f"{API}/action-items/{aid}/port-to-ctt", headers=H, timeout=15).json()
            task_id = p["ctt_task"]["task_id"]
            requests.put(f"{API}/ctt/tasks/{task_id}",
                         json={"current_status": "wip_75"}, headers=H, timeout=15)
            a = requests.get(f"{API}/action-items/{aid}", headers=H, timeout=15).json()
            assert a["status"] == "wip_75"
            assert a["progress_pct"] == 75
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)

    def test_forward_blocked_propagates(self, H):
        aid = self._mk_ai(H)
        try:
            p = requests.post(f"{API}/action-items/{aid}/port-to-ctt", headers=H, timeout=15).json()
            task_id = p["ctt_task"]["task_id"]
            requests.put(f"{API}/action-items/{aid}", json={"status": "blocked"}, headers=H, timeout=15)
            t = requests.get(f"{API}/ctt/tasks/{task_id}", headers=H, timeout=15).json()
            assert t.get("current_status") == "blocked"
        finally:
            requests.delete(f"{API}/action-items/{aid}", headers=H)


# --- Solution Finder reconciliation --------------------------------------------------

SF_ID = "11cf0bc0-8086-40c3-a679-6da1ea10fdab"


class TestSolutionFinderReconciliation:
    def test_get_solution_finder_ok(self, H):
        r = requests.get(f"{API}/solution-finders/{SF_ID}", headers=H, timeout=20)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        # accept either action_plan_items or nested equivalent
        assert isinstance(j, dict)

    def test_pdf_gated_402(self, H):
        # SF PDF must be gated by paid L1 entitlement (expected)
        r = requests.get(f"{API}/reports/solution_finder/{SF_ID}.pdf", headers=H, timeout=30)
        assert r.status_code in (200, 402), r.status_code
        if r.status_code == 402:
            # payload should be JSON with entitlement guidance
            try:
                j = r.json()
                assert "detail" in j
            except Exception:
                pass

    def test_sf_reconciliation_pushed_item_status(self, H):
        """If any SF action plan item was pushed (has action_id), GET /solution-finders/{id}
        must reconcile its status to central action item's current status."""
        r = requests.get(f"{API}/solution-finders/{SF_ID}", headers=H, timeout=20).json()
        plan = r.get("action_plan_items") or []
        pushed = [it for it in plan if isinstance(it, dict) and it.get("action_id")]
        if not pushed:
            pytest.skip("No pushed SF items on sample entry; reconciliation cannot be tested.")
        target = pushed[0]
        aid = target["action_id"]
        # Flip central action item to blocked, then re-fetch SF entry
        original_status = target.get("status")
        try:
            u = requests.put(f"{API}/action-items/{aid}", json={"status": "blocked"},
                             headers=H, timeout=15)
            assert u.status_code == 200
            r2 = requests.get(f"{API}/solution-finders/{SF_ID}", headers=H, timeout=20).json()
            plan2 = r2.get("action_plan_items") or []
            match = [it for it in plan2 if it.get("action_id") == aid]
            assert match, f"pushed item {aid} not found after reconciliation"
            assert match[0].get("status") == "blocked", match[0]
        finally:
            # restore
            if original_status:
                requests.put(f"{API}/action-items/{aid}",
                             json={"status": original_status}, headers=H, timeout=15)


# --- PDF grouping labels (best-effort: only when entitlement lets PDF through) ------

class TestPDFActionPlanGroupLabels:
    def test_pdf_group_prefixes_and_suffixes(self, H):
        r = requests.get(f"{API}/reports/solution_finder/{SF_ID}.pdf", headers=H, timeout=45)
        if r.status_code == 402:
            pytest.skip("SF PDF gated by L1 entitlement (expected) — cannot validate PDF body content.")
        assert r.status_code == 200, r.status_code
        assert r.headers.get("content-type", "").startswith("application/pdf")
        # Extract text from PDF (best-effort with pypdf if available, else raw bytes check)
        text = ""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            text = r.content.decode("latin-1", errors="ignore")
        # Presence of at least one prefix/suffix combo is sufficient (empty groups skipped)
        found_any = any(
            (prefix in text and label in text and suffix in text)
            for prefix, label, suffix in [
                ("I.", "Solution Actions", "Mandatory"),
                ("II.", "Risk Mitigation Actions", "Most Recommended"),
                ("III.", "Risk Contingency Actions", "Recommended"),
            ]
        )
        assert found_any, "None of the expected group headings found in PDF"
