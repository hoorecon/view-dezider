"""
Seed an 8-step Pros & Cons analysis with hierarchical factors so the
wizard test for Steps 6/7/8 has predictable data:
  MainA  ↳  MainB (sub via parent_id)
  MainC  ↳  MainC-sub
Options: OptX
current_step is set to 5 so the UI lands on Step 5 first.

Also calls /aggregate to verify backend filters scoring_factors to mains only.
"""
import os
import sys
import requests

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
EMAIL = "admin@test.com"
PASSWORD = "AdminPass2026!"


def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("session_token") or data.get("token") or data.get("access_token")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def seed():
    tok = login()
    h = hdr(tok)
    # Create analysis
    r = requests.post(f"{BASE}/api/pros-cons", headers=h, json={
        "title": "Step6-8 hierarchy test",
        "context": "Testing only-mains rendering on Steps 6/7/8",
        "life_area": "career",
        "decision_type": "career",
    }, timeout=20)
    r.raise_for_status()
    aid = r.json()["id"]
    print(f"analysis_id={aid}")

    # Add factors
    def add_factor(name, parent_id=None):
        r = requests.post(f"{BASE}/api/pros-cons/{aid}/factors", headers=h,
                          json={"name": name, "parent_id": parent_id}, timeout=20)
        r.raise_for_status()
        return r.json()["id"]

    a = add_factor("MainA")
    b = add_factor("MainB")
    c = add_factor("MainC")
    csub = add_factor("MainC-sub", parent_id=c)

    # Nest MainB under MainA (simulate Step 4 picker "Move existing under MainA")
    requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{b}", headers=h,
                 json={"parent_id": a}, timeout=20).raise_for_status()

    # Add option OptX
    r = requests.post(f"{BASE}/api/pros-cons/{aid}/options", headers=h,
                      json={"name": "OptX"}, timeout=20)
    r.raise_for_status()
    optx = r.json().get("id") or r.json().get("option", {}).get("id")
    if not optx:
        # try fetch
        r2 = requests.get(f"{BASE}/api/pros-cons/{aid}", headers=h, timeout=20)
        optx = r2.json()["options"][0]["id"]
    print(f"option_id={optx}")

    # Move to step 5
    requests.post(f"{BASE}/api/pros-cons/{aid}/step", headers=h, json={"current_step": 5}, timeout=20)

    # Verify aggregate behaviour BEFORE assessments → joint=0 but main factors only
    r = requests.get(f"{BASE}/api/pros-cons/{aid}/aggregate", headers=h, timeout=20)
    r.raise_for_status()
    agg = r.json()
    print("aggregate.rollups=", agg["rollups"])

    # Now SET ratings + assessments to validate scoring uses mains only
    # MainA std_rating=80, MainC std_rating=60
    requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{a}", headers=h, json={"std_rating": 80}).raise_for_status()
    requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{c}", headers=h, json={"std_rating": 60}).raise_for_status()
    # Sub-factors get fake ratings — must NOT contribute
    requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{b}", headers=h, json={"std_rating": 99}).raise_for_status()
    requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{csub}", headers=h, json={"std_rating": 99}).raise_for_status()

    # OptX × MainA assess_pct=70 → cell = 70 * 80 / 100 = 56
    # OptX × MainC assess_pct=50 → cell = 50 * 60 / 100 = 30
    requests.put(f"{BASE}/api/pros-cons/{aid}/assessments/{optx}/{a}", headers=h,
                 json={"assessment_pct": 70}).raise_for_status()
    requests.put(f"{BASE}/api/pros-cons/{aid}/assessments/{optx}/{c}", headers=h,
                 json={"assessment_pct": 50}).raise_for_status()
    # Sub-factor assessments — should NOT contribute to joint
    requests.put(f"{BASE}/api/pros-cons/{aid}/assessments/{optx}/{b}", headers=h,
                 json={"assessment_pct": 100}).raise_for_status()
    requests.put(f"{BASE}/api/pros-cons/{aid}/assessments/{optx}/{csub}", headers=h,
                 json={"assessment_pct": 100}).raise_for_status()

    r = requests.get(f"{BASE}/api/pros-cons/{aid}/aggregate", headers=h, timeout=20)
    r.raise_for_status()
    agg = r.json()
    rollup = agg["rollups"][0]
    print("AFTER ASSESSMENTS rollups=", rollup)
    expected_joint = 56 + 30  # mains only = 86
    actual_joint = rollup["joint_score"]
    print(f"expected_joint={expected_joint}, actual_joint={actual_joint}")
    assert abs(actual_joint - expected_joint) < 0.5, (
        f"BACKEND BUG — joint_score={actual_joint} should be {expected_joint} (mains only). "
        f"Sub-factors apparently contribute."
    )
    print("[PASS] Backend aggregate excludes sub-factors from joint_score")

    print(f"\nWIZARD_URL={BASE}/tools/pros-cons-wizard?id={aid}&module=pros-cons")
    print(f"ANALYSIS_ID={aid}")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
