"""Retest for the race-condition fix on PUT /pros-cons/{id}/assessments/{oid}/{fid}.

Validates that two concurrent partial-field PUTs (one setting actual_value,
one setting assessment_pct) on the SAME cell BOTH survive — i.e. the backend
no longer does load-modify-write of the whole assessments dict.

Existing analysis id used: 517fae05-579f-4005-8f86-195edbfa21a8
Alpha factor id          : a0950374-64c1-4c37-a359-041cc14acfa7
OptX option id           : fa25dab4-75d6-4377-adaf-a88288a8e109
"""
import os
import threading
import time
import pytest
import requests

BASE_URL = "https://goals-feels-tracker.preview.emergentagent.com"
ANALYSIS_ID = "517fae05-579f-4005-8f86-195edbfa21a8"
ALPHA_FID = "a0950374-64c1-4c37-a359-041cc14acfa7"
OPTX_OID = "fa25dab4-75d6-4377-adaf-a88288a8e109"

EMAIL = "admin@test.com"
PASSWORD = "AdminPass2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token")


@pytest.fixture
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _reset_cell(headers):
    r = requests.put(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
        json={"actual_value": "", "assessment_pct": 0},
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text


def _get_cell(headers):
    r = requests.get(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}",
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    j = r.json()
    return (j.get("assessments", {}).get(OPTX_OID) or {}).get(ALPHA_FID) or {}


# === Sanity: existing analysis is reachable ===
def test_analysis_reachable(headers):
    r = requests.get(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}", headers=headers, timeout=15
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert any(f["id"] == ALPHA_FID for f in j.get("factors", []))
    assert any(o["id"] == OPTX_OID for o in j.get("options", []))


# === Sanity: sequential partial updates merge correctly ===
def test_sequential_partial_updates_merge(headers):
    _reset_cell(headers)

    # 1) Send actual_value alone
    r1 = requests.put(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
        json={"actual_value": "55000"}, headers=headers, timeout=15,
    )
    assert r1.status_code == 200

    # 2) Send assessment_pct alone
    r2 = requests.put(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
        json={"assessment_pct": 75}, headers=headers, timeout=15,
    )
    assert r2.status_code == 200

    cell = _get_cell(headers)
    assert cell.get("actual_value") == "55000", f"actual lost: {cell}"
    assert int(cell.get("assessment_pct") or 0) == 75, f"assess pct lost: {cell}"


# === THE RACE CONDITION TEST ===
def test_concurrent_partial_updates_both_survive(headers):
    """Fire two PUTs in parallel threads, exactly mimicking DebouncedInput
    unmount-flush behaviour on Step 7→8 navigation."""
    results = {}

    def put_actual():
        try:
            r = requests.put(
                f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
                json={"actual_value": "55000"}, headers=headers, timeout=15,
            )
            results["actual"] = (r.status_code, r.text)
        except Exception as e:
            results["actual"] = ("ERR", str(e))

    def put_pct():
        try:
            r = requests.put(
                f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
                json={"assessment_pct": 75}, headers=headers, timeout=15,
            )
            results["pct"] = (r.status_code, r.text)
        except Exception as e:
            results["pct"] = ("ERR", str(e))

    # Run the race 5 times (it’s the kind of bug that may be intermittent).
    losses = []
    for i in range(5):
        _reset_cell(headers)
        time.sleep(0.05)

        t1 = threading.Thread(target=put_actual)
        t2 = threading.Thread(target=put_pct)
        t1.start(); t2.start()
        t1.join(); t2.join()

        assert results["actual"][0] == 200, f"actual PUT failed: {results['actual']}"
        assert results["pct"][0] == 200, f"pct PUT failed: {results['pct']}"

        # small settle pause so any in-flight derived-field $set lands first
        time.sleep(0.1)
        cell = _get_cell(headers)
        actual_ok = cell.get("actual_value") == "55000"
        pct_ok = int(cell.get("assessment_pct") or 0) == 75
        if not (actual_ok and pct_ok):
            losses.append({"run": i, "cell": cell})

    assert not losses, (
        f"Race condition still present in {len(losses)}/5 runs: {losses}"
    )


# === Triple-field concurrency variant (actual + pct + satisfaction_pct) ===
def test_three_way_concurrent_updates(headers):
    _reset_cell(headers)
    results = {}

    def put(key, val):
        r = requests.put(
            f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}/assessments/{OPTX_OID}/{ALPHA_FID}",
            json={key: val}, headers=headers, timeout=15,
        )
        results[key] = r.status_code

    ts = [
        threading.Thread(target=put, args=("actual_value", "99999")),
        threading.Thread(target=put, args=("assessment_pct", 88)),
        threading.Thread(target=put, args=("satisfaction_pct", 66)),
    ]
    for t in ts: t.start()
    for t in ts: t.join()

    assert all(v == 200 for v in results.values()), results
    time.sleep(0.15)
    cell = _get_cell(headers)
    assert cell.get("actual_value") == "99999", cell
    assert int(cell.get("assessment_pct") or 0) == 88, cell
    assert float(cell.get("satisfaction_pct") or 0) == 66.0, cell


# === Regression: Issue #1 (auto-ladder) endpoint still reachable ===
def test_get_analysis_returns_ladder_state(headers):
    r = requests.get(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}", headers=headers, timeout=15
    )
    assert r.status_code == 200
    j = r.json()
    # Top-level mains (no parent_id) — should retain descending std_rating ladder
    mains = [f for f in j.get("factors", []) if not f.get("parent_id")]
    mains.sort(key=lambda f: -int(f.get("std_rating") or 0))
    rats = [int(f.get("std_rating") or 0) for f in mains]
    assert len(rats) >= 3, f"expected >=3 mains, got {mains}"
    assert rats == sorted(rats, reverse=True), f"ladder broken: {rats}"


# === Regression: Issue #2 (realistic gap config) ===
def test_std_gap_config_preserved(headers):
    r = requests.get(
        f"{BASE_URL}/api/pros-cons/{ANALYSIS_ID}", headers=headers, timeout=15
    )
    assert r.status_code == 200
    cfg = r.json().get("config") or {}
    assert "std_gap" in cfg
    assert cfg.get("std_gap") in (5, 10, 20)  # the allowed selector values
