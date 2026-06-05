"""Iter 58 — Sub-factor weightage + assessment rollup tests.

Validates:
  (1) PUT /api/pros-cons/{id}/factors/{factor_id} accepts and persists `weight`.
  (2) compute_option_rollups (via /aggregate) derives main factor's effective
      Assess % from sub-factor cells when sub-factors are assessed:
      - weighted average if subs carry weights
      - equal average if subs have no weights
      - parent's own cell when no sub is assessed
  (3) joint_score & overall_satisfaction_pct reflect the rolled-up value.
"""

import os
import time
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "https://dashboard-rewire.preview.emergentagent.com"
).rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def analysis(headers):
    """Create a pros_cons analysis with one option, one main factor + 2 subs."""
    title = f"TEST_iter58_weightage_{int(time.time())}"
    r = requests.post(
        f"{BASE_URL}/api/pros-cons",
        headers=headers,
        json={"title": title, "context": "iter58 weightage rollup"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    aid = r.json()["id"]

    # Option
    r = requests.post(
        f"{BASE_URL}/api/pros-cons/{aid}/options",
        headers=headers,
        json={"name": "Option A"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    opt_id = r.json()["id"]

    # Main factor
    r = requests.post(
        f"{BASE_URL}/api/pros-cons/{aid}/factors",
        headers=headers,
        json={"name": "TEST_main"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    main_id = r.json()["id"]

    # Two sub-factors
    sub_ids = []
    for sname in ("TEST_sub1", "TEST_sub2"):
        r = requests.post(
            f"{BASE_URL}/api/pros-cons/{aid}/factors",
            headers=headers,
            json={"name": sname, "parent_id": main_id},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        sub_ids.append(r.json()["id"])

    # Give main factor a std_rating so cell_value > 0. Reorder to anchor.
    requests.post(
        f"{BASE_URL}/api/pros-cons/{aid}/factors/reorder",
        headers=headers,
        json={"ordered_ids": [main_id, sub_ids[0], sub_ids[1]]},
        timeout=20,
    )

    yield {
        "id": aid,
        "option_id": opt_id,
        "main_id": main_id,
        "sub_ids": sub_ids,
    }

    # Cleanup
    requests.delete(f"{BASE_URL}/api/pros-cons/{aid}", headers=headers, timeout=20)


# ---------- (1) PUT weight persists ----------

def test_put_factor_weight_persists(analysis, headers):
    aid = analysis["id"]
    s1 = analysis["sub_ids"][0]
    r = requests.put(
        f"{BASE_URL}/api/pros-cons/{aid}/factors/{s1}",
        headers=headers,
        json={"weight": 80},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json()["factor"]["weight"] == 80

    # Re-fetch and verify
    r = requests.get(f"{BASE_URL}/api/pros-cons/{aid}", headers=headers, timeout=20)
    assert r.status_code == 200
    factors = {f["id"]: f for f in r.json()["factors"]}
    assert factors[s1]["weight"] == 80


# ---------- (2a) Weighted rollup ----------

def test_weighted_rollup_main_from_subs(analysis, headers):
    aid, opt_id, main_id, sub_ids = analysis["id"], analysis["option_id"], analysis["main_id"], analysis["sub_ids"]
    # weights 80/20; pcts 70 / 40 → weighted avg = 64
    for sid, w in zip(sub_ids, (80, 20)):
        r = requests.put(f"{BASE_URL}/api/pros-cons/{aid}/factors/{sid}", headers=headers, json={"weight": w}, timeout=20)
        assert r.status_code == 200
    for sid, pct in zip(sub_ids, (70, 40)):
        r = requests.put(
            f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{sid}",
            headers=headers,
            json={"assessment_pct": pct},
            timeout=20,
        )
        assert r.status_code == 200, r.text

    r = requests.get(f"{BASE_URL}/api/pros-cons/{aid}/aggregate", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    rollup = next(rr for rr in data["rollups"] if rr["option_id"] == opt_id)
    main = next(f for f in data["factors"] if f["id"] == main_id)
    std_rating = main.get("std_rating") or 0
    # weighted: (70*80 + 40*20)/100 = 64
    expected_cell = round(64 * std_rating / 100.0, 2)
    assert rollup["joint_score"] == pytest.approx(expected_cell, abs=0.5), (
        f"expected joint_score≈{expected_cell} got {rollup['joint_score']} std_rating={std_rating}"
    )
    assert std_rating > 0, "main factor should have std_rating > 0 after reorder anchor"


# ---------- (2b) Equal-average rollup (weights cleared) ----------

def test_equal_rollup_when_no_weights(analysis, headers):
    aid, opt_id, main_id, sub_ids = analysis["id"], analysis["option_id"], analysis["main_id"], analysis["sub_ids"]
    # Clear weights → 0
    for sid in sub_ids:
        r = requests.put(f"{BASE_URL}/api/pros-cons/{aid}/factors/{sid}", headers=headers, json={"weight": 0}, timeout=20)
        assert r.status_code == 200
    # Pcts 100 / 50 → mean = 75
    for sid, pct in zip(sub_ids, (100, 50)):
        r = requests.put(
            f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{sid}",
            headers=headers,
            json={"assessment_pct": pct},
            timeout=20,
        )
        assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/pros-cons/{aid}/aggregate", headers=headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    rollup = next(rr for rr in data["rollups"] if rr["option_id"] == opt_id)
    main = next(f for f in data["factors"] if f["id"] == main_id)
    std_rating = main.get("std_rating") or 0
    expected_cell = round(75 * std_rating / 100.0, 2)
    assert rollup["joint_score"] == pytest.approx(expected_cell, abs=0.5)


# ---------- (2c) Parent fallback when no sub assessed ----------

def test_parent_fallback_when_no_sub_assessed(analysis, headers):
    aid, opt_id, main_id, sub_ids = analysis["id"], analysis["option_id"], analysis["main_id"], analysis["sub_ids"]
    # Zero out sub assessments
    for sid in sub_ids:
        r = requests.put(
            f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{sid}",
            headers=headers,
            json={"assessment_pct": 0},
            timeout=20,
        )
        assert r.status_code == 200
    # Set parent's own assessment
    r = requests.put(
        f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{main_id}",
        headers=headers,
        json={"assessment_pct": 55},
        timeout=20,
    )
    assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/pros-cons/{aid}/aggregate", headers=headers, timeout=20)
    assert r.status_code == 200
    data = r.json()
    rollup = next(rr for rr in data["rollups"] if rr["option_id"] == opt_id)
    main = next(f for f in data["factors"] if f["id"] == main_id)
    std_rating = main.get("std_rating") or 0
    expected_cell = round(55 * std_rating / 100.0, 2)
    assert rollup["joint_score"] == pytest.approx(expected_cell, abs=0.5), (
        f"expected fallback cell≈{expected_cell} got {rollup['joint_score']}"
    )


# ---------- (3) Mandatory threshold disqualification reflects rolled-up pct ----------

def test_knockout_uses_rolled_up_pct(analysis, headers):
    aid, opt_id, main_id, sub_ids = analysis["id"], analysis["option_id"], analysis["main_id"], analysis["sub_ids"]
    # Make main mandatory; threshold 60
    r = requests.put(
        f"{BASE_URL}/api/pros-cons/{aid}/factors/{main_id}",
        headers=headers,
        json={"notation": "mandatory"},
        timeout=20,
    )
    assert r.status_code == 200
    r = requests.put(
        f"{BASE_URL}/api/pros-cons/{aid}/config",
        headers=headers,
        json={"mandatory_threshold_pct": 60},
        timeout=20,
    )
    assert r.status_code == 200

    # Subs equal-mean = (50+30)/2 = 40 (< 60 → DQ)
    for sid in sub_ids:
        r = requests.put(f"{BASE_URL}/api/pros-cons/{aid}/factors/{sid}", headers=headers, json={"weight": 0}, timeout=20)
        assert r.status_code == 200
    for sid, pct in zip(sub_ids, (50, 30)):
        r = requests.put(
            f"{BASE_URL}/api/pros-cons/{aid}/assessments/{opt_id}/{sid}",
            headers=headers,
            json={"assessment_pct": pct},
            timeout=20,
        )
        assert r.status_code == 200

    r = requests.get(f"{BASE_URL}/api/pros-cons/{aid}/aggregate", headers=headers, timeout=20)
    assert r.status_code == 200
    rollup = next(rr for rr in r.json()["rollups"] if rr["option_id"] == opt_id)
    assert rollup["disqualified"] is True
    assert main_id in rollup["disqualifying_factor_ids"]
