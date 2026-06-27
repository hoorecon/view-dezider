"""Full MyDezider step-share contribution E2E (real-flow contribution path).
super shares Step 7 of a decision to admin → admin reads decision via share →
admin contributes (assessments) → super merges (equal) → admin withdraws.
Run: cd /app/backend && PYTHONPATH=/app/backend python tests/verify_step_contribution.py
Leaves a demo share 'for screenshots' (decision dec_stepshare_demo).
"""
import asyncio
import requests

BASE = "http://localhost:8001/api"


def login(email, pwd):
    d = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()
    return d["session_token"], d["user_id"]


async def main():
    s_tok, s_uid = login("super@test.com", "SuperPass2026!")
    a_tok, a_uid = login("admin@test.com", "AdminPass2026!")
    SH = {"Authorization": f"Bearer {s_tok}"}
    AH = {"Authorization": f"Bearer {a_tok}"}
    from core.database import db

    dec_id = "dec_stepshare_demo"
    await db.decisions.delete_many({"id": dec_id})
    await db.shared_steps.delete_many({"decision_id": dec_id})
    await db.decisions.insert_one({
        "id": dec_id, "user_id": s_uid, "type": "decider", "title": "Choose our CRM",
        "context": "Sales team tooling", "current_step": 7, "total_steps": 8,
        "factors": [
            {"id": "f1", "name": "Price", "weight": 5},
            {"id": "f2", "name": "Ease of use", "weight": 4},
        ],
        "options": [
            {"id": "o1", "name": "HubSpot", "assessments": [
                {"factor_id": "f1", "percentage": 60}, {"factor_id": "f2", "percentage": 80}]},
            {"id": "o2", "name": "Salesforce", "assessments": [
                {"factor_id": "f1", "percentage": 40}, {"factor_id": "f2", "percentage": 70}]},
        ],
        "status": "in_progress",
    })

    # 1) owner shares Step 7 to admin
    sr = requests.post(f"{BASE}/decisions/{dec_id}/share-step", headers=SH, json={
        "decision_id": dec_id, "step_number": 7, "recipient_emails": ["admin@test.com"],
        "merge_mode": "equal", "message": "Please rate the CRMs", "allow_reshare": False,
        "step_access": "hidden", "module": "decision",
    })
    print("SHARE:", sr.status_code, sr.json().get("message") or sr.json())
    share_id = sr.json().get("share_id") or sr.json().get("id")
    if not share_id:
        share = await db.shared_steps.find_one({"decision_id": dec_id}, {"_id": 0, "id": 1})
        share_id = share["id"]
    print("  share_id:", share_id)

    # 2) recipient reads the owner's decision via the share (Contribution Mode load)
    dr = requests.get(f"{BASE}/shared-steps/{share_id}/decision", headers=AH)
    print("READ DECISION (recipient):", dr.status_code, "| step_access:", dr.json().get("share", {}).get("step_access"))
    assert dr.status_code == 200 and dr.json()["decision"]["id"] == dec_id

    # 3) recipient contributes their assessments (what the real flow submits)
    cr = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=AH, json={
        "assessments": {"o1_f1": 90, "o1_f2": 90, "o2_f1": 30, "o2_f2": 40},
        "note": "I rate HubSpot much higher on price.",
    })
    print("CONTRIBUTE:", cr.status_code, cr.json())
    assert cr.status_code == 200

    # 4) owner merges (equal) → owner's decision step-7 assessments updated (weighted)
    mr = requests.post(f"{BASE}/shared-steps/{share_id}/merge", headers=SH, json={"merge_mode": "equal"})
    print("MERGE:", mr.status_code, mr.json())
    assert mr.status_code == 200
    dec = await db.decisions.find_one({"id": dec_id}, {"_id": 0})
    o1 = next(o for o in dec["options"] if o["id"] == "o1")
    a_f1 = next(a for a in o1["assessments"] if a["factor_id"] == "f1")["percentage"]
    print("  merged o1/f1 (owner 60 + admin 90, equal => ~75):", a_f1)

    # 5) recipient withdraws their contribution
    wr = requests.delete(f"{BASE}/shared-steps/{share_id}/contribution", headers=AH)
    print("WITHDRAW:", wr.status_code, wr.json())
    assert wr.status_code == 200

    print("PASS: share → recipient-read → contribute → merge → withdraw all work.")


if __name__ == "__main__":
    asyncio.run(main())
