"""E2E: owner Review → AI Auto-Merge → Apply → post-merge review (decision module).

Run: python tests/verify_review_merge.py
"""
import requests

BASE = "http://localhost:8001/api"
OWNER = {"email": "super@test.com", "password": "SuperPass2026!"}
CONTRIB = {"email": "admin@test.com", "password": "AdminPass2026!"}


def login(creds):
    r = requests.post(f"{BASE}/auth/login", json=creds)
    r.raise_for_status()
    return r.json()["session_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    owner = login(OWNER)
    contrib = login(CONTRIB)

    # 1. Create a fresh decision owned by super, with 1 factor + 1 option.
    dec = requests.post(f"{BASE}/decisions", headers=H(owner), json={
        "title": "TEST review-merge decision", "context": "verify",
    }).json()
    did = dec["id"]
    # add a factor + option via update
    factors = [{"id": "f1", "name": "Cost", "category": "primary", "order": 1}]
    options = [{"id": "o1", "name": "Option A", "assessments": [
        {"factor_id": "f1", "percentage": 40, "assessment_mode": "custom", "unit_value": ""}]}]
    requests.put(f"{BASE}/decisions/{did}", headers=H(owner),
                 json={"factors": factors, "options": options})

    # 2. Share step 7 with admin (equal mode).
    sh = requests.post(f"{BASE}/decisions/{did}/share-step", headers=H(owner), json={
        "decision_id": did, "step_number": 7, "recipient_emails": ["admin@test.com"],
        "merge_mode": "equal", "message": "please assess",
    })
    assert sh.status_code == 200, sh.text
    share_id = sh.json()["id"]
    print("shared:", share_id)

    # 3. Contributor opens + contributes an assessment (higher value 80).
    requests.post(f"{BASE}/shared-steps/{share_id}/open", headers=H(contrib))
    c = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=H(contrib), json={
        "assessments": {"o1_f1": 80}, "note": "I think cost is fine"})
    assert c.status_code == 200, c.text
    print("contributed OK")

    # 4. Owner review BEFORE merge.
    rv = requests.get(f"{BASE}/shared-steps/{share_id}/review", headers=H(owner))
    assert rv.status_code == 200, rv.text
    rvj = rv.json()
    assert len(rvj["contributions"]) == 1, rvj
    print("review pre-merge: contributions =", len(rvj["contributions"]),
          "| owner present:", bool(rvj.get("owner")))

    # 5. AI Auto-Merge (advisory).
    am = requests.post(f"{BASE}/shared-steps/{share_id}/ai-merge", headers=H(owner), json={})
    print("ai-merge status:", am.status_code)
    if am.status_code == 200:
        amj = am.json()
        print("  rationale:", (amj.get("rationale") or "")[:120])
        print("  charged:", amj.get("charged"), "provider:", amj.get("provider"))
    else:
        print("  ai-merge body:", am.text[:200])

    # 6. Manual merge (weighted) via legacy /merge for decision step 7.
    mg = requests.post(f"{BASE}/shared-steps/{share_id}/merge", headers=H(owner),
                       json={"merge_mode": "equal"})
    assert mg.status_code == 200, mg.text
    print("merged OK, weights:", mg.json().get("weights"))

    # 7. Owner review AFTER merge — contributions MUST still be visible.
    rv2 = requests.get(f"{BASE}/shared-steps/{share_id}/review", headers=H(owner))
    assert rv2.status_code == 200, rv2.text
    assert len(rv2.json()["contributions"]) == 1, "contributions lost after merge!"
    print("review post-merge: contributions =", len(rv2.json()["contributions"]),
          "status =", rv2.json().get("status"))

    # cleanup
    requests.delete(f"{BASE}/decisions/{did}", headers=H(owner))
    print("\nALL PASS ✅")


if __name__ == "__main__":
    main()
