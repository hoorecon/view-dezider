"""Iter196 — Finder ANY-semantics on Business Model Chooser clone (v2 checkbox).

Scenario:
  1. Clone the live 'Business Model Chooser' Decider App (full mode).
  2. Set the child value factor 'Solo' → operator '>=' / expected 60 (numeric).
     Run POST /decisions/{id}/finder/jobs, poll GET /finder/jobs/{job_id}
     until status='done'. Expect ~11 candidates.
  3. Additionally set 'Startup' → '>=' 50 (numeric). Re-run finder.
     Expect candidates ≈ 23 (union grows — NOT intersection).

All calls use EXPO_PUBLIC_BACKEND_URL from /app/frontend/.env.
"""
import time
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
ADMIN_EMAIL = "super@test.com"
ADMIN_PASS = "SuperPass2026!"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.fixture(scope="module")
def admin_headers(s):
    r = s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def bmc_id(s):
    r = s.get(f"{API}/decider-store", timeout=30)
    assert r.status_code == 200
    t = next((t for t in r.json().get("templates", [])
              if t.get("title") == "Business Model Chooser"), None)
    assert t is not None, "Business Model Chooser template not in public list"
    return t["template_id"]


@pytest.fixture(scope="module")
def cloned_decision(s, admin_headers, bmc_id):
    r = s.post(f"{API}/decider-store/{bmc_id}/clone",
               json={"mode": "full"}, headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    did = r.json()["decision_id"]
    yield did
    # cleanup
    s.delete(f"{API}/decisions/{did}", headers=admin_headers, timeout=30)


def _poll_job(s, headers, job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = s.get(f"{API}/finder/jobs/{job_id}", headers=headers, timeout=30)
        assert r.status_code == 200, r.text[:200]
        j = r.json()
        if j.get("status") in ("done", "error", "failed"):
            return j
        time.sleep(1.0)
    raise AssertionError(f"finder job {job_id} did not finish in {timeout}s")


def _set_expectation(s, headers, did, factor_name, operator, expected):
    """PUT the entire factors[] array with our target factor updated."""
    r = s.get(f"{API}/decisions/{did}", headers=headers, timeout=30)
    assert r.status_code == 200
    dec = r.json()
    factors = dec["factors"]
    found = False
    for f in factors:
        if f.get("name") == factor_name and f.get("parent_id"):
            f["operator"] = operator
            f["expected_value"] = expected
            f["data_type"] = "numeric"
            found = True
            break
    assert found, f"child factor {factor_name!r} not found"
    r = s.put(f"{API}/decisions/{did}",
              json={"factors": factors}, headers=headers, timeout=30)
    assert r.status_code == 200, r.text[:300]


class TestFinderAnySemantics:
    def test_solo_ge_60_yields_candidates(self, s, admin_headers, cloned_decision):
        did = cloned_decision
        _set_expectation(s, admin_headers, did, "Solo", ">=", 60)
        r = s.post(f"{API}/decisions/{did}/finder/jobs",
                   json={"force": True}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        job_id = r.json()["job_id"]
        job = _poll_job(s, admin_headers, job_id, timeout=90)
        assert job["status"] == "done", f"job errored: {job}"
        result = job.get("result") or {}
        cands = result.get("candidates")
        if cands is None:
            # engines may return items/matches — fall back to any list-like key
            for k in ("items", "matches", "options", "top", "survivors"):
                if isinstance(result.get(k), list):
                    cands = result[k]
                    break
        assert isinstance(cands, (int, list)), f"no candidates in result: {result}"
        count = cands if isinstance(cands, int) else len(cands)
        # main-agent measured ~11; assert a small window
        assert 5 <= count <= 20, f"Solo>=60 candidates {count} outside 5..20 window"
        # stash for next test
        pytest.solo_only_count = count  # type: ignore[attr-defined]

    def test_add_startup_ge_50_union_grows(self, s, admin_headers, cloned_decision):
        did = cloned_decision
        # Keep Solo already set, and add Startup >=50
        _set_expectation(s, admin_headers, did, "Startup", ">=", 50)
        r = s.post(f"{API}/decisions/{did}/finder/jobs",
                   json={"force": True}, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        job_id = r.json()["job_id"]
        job = _poll_job(s, admin_headers, job_id, timeout=90)
        assert job["status"] == "done", f"job errored: {job}"
        result = job.get("result") or {}
        cands = result.get("candidates")
        if cands is None:
            for k in ("items", "matches", "options", "top", "survivors"):
                if isinstance(result.get(k), list):
                    cands = result[k]
                    break
        assert isinstance(cands, (int, list)), f"no candidates in result: {result}"
        count = cands if isinstance(cands, int) else len(cands)
        prior = getattr(pytest, "solo_only_count", 0)
        # main-agent measured ~23 — assert reasonable window AND union grows
        assert count > prior, (
            f"union should grow: Solo-only={prior} vs Solo+Startup={count}")
        assert 15 <= count <= 40, f"Solo+Startup candidates {count} outside 15..40 window"
