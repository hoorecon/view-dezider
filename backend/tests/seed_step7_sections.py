"""
Seed an 8-step Pros & Cons analysis for testing Step 7's
Mandatory (A) / Optional (B) sectioned layout.

Creates:
  - title: "Step7 sectioned"
  - 5 main factors: Zeta, Alpha, Mango, Banana, Echo
  - 1 option: OptX
  - notation: Alpha & Mango => mandatory; Zeta, Banana, Echo => optional
  - current_step set to 7
"""
import os
import sys
import requests

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://voice-browse-epic.preview.emergentagent.com").rstrip("/")
EMAIL = "admin@test.com"
PASSWORD = "AdminPass2026!"


def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    r.raise_for_status()
    d = r.json()
    return d.get("session_token") or d.get("token") or d.get("access_token")


def hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def seed():
    tok = login()
    h = hdr(tok)
    r = requests.post(f"{BASE}/api/pros-cons", headers=h, json={
        "title": "Step7 sectioned",
        "context": "Testing Step 7 split A/B sections",
        "life_area": "career",
        "decision_type": "career",
    }, timeout=20)
    r.raise_for_status()
    aid = r.json()["id"]
    print(f"analysis_id={aid}")

    def add_factor(name):
        r = requests.post(f"{BASE}/api/pros-cons/{aid}/factors", headers=h,
                          json={"name": name}, timeout=20)
        r.raise_for_status()
        return r.json()["id"]

    ids = {}
    for name in ["Zeta", "Alpha", "Mango", "Banana", "Echo"]:
        ids[name] = add_factor(name)
    print("factor_ids=", ids)

    # Add option
    r = requests.post(f"{BASE}/api/pros-cons/{aid}/options", headers=h, json={"name": "OptX"}, timeout=20)
    r.raise_for_status()
    optx = r.json().get("id") or r.json().get("option", {}).get("id")
    if not optx:
        r2 = requests.get(f"{BASE}/api/pros-cons/{aid}", headers=h, timeout=20)
        optx = r2.json()["options"][0]["id"]
    print(f"option_id={optx}")

    # Notation: mandatory for Alpha & Mango, optional for the rest
    for name in ["Alpha", "Mango"]:
        requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{ids[name]}", headers=h,
                     json={"notation": "mandatory"}, timeout=20).raise_for_status()
    for name in ["Zeta", "Banana", "Echo"]:
        requests.put(f"{BASE}/api/pros-cons/{aid}/factors/{ids[name]}", headers=h,
                     json={"notation": "optional"}, timeout=20).raise_for_status()

    # Jump to step 7 (API expects {"step": N})
    requests.post(f"{BASE}/api/pros-cons/{aid}/step", headers=h, json={"step": 7}, timeout=20)

    # Verify state
    r = requests.get(f"{BASE}/api/pros-cons/{aid}", headers=h, timeout=20)
    r.raise_for_status()
    a = r.json()
    print("current_step=", a.get("current_step"))
    print("factors:")
    for f in a["factors"]:
        print(f"  {f['name']:8s} rank={f['priority_rank']:2}  notation={f['notation']}")

    print(f"\nWIZARD_URL={BASE}/tools/pros-cons-wizard?id={aid}&module=pros-cons")
    print(f"ANALYSIS_ID={aid}")
    return aid


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
