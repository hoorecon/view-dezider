"""Full async collaboration E2E: contribute (participant) + merge (owner).
Run: cd /app/backend && PYTHONPATH=/app/backend python tests/verify_collab_async.py
Leaves a completed demo session 'collab_async_demo' for screenshots.
"""
import asyncio
import requests
from datetime import datetime, timezone

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

    dec_id = "dec_collab_async_demo"
    sid = "collab_async_demo"
    now = datetime.now(timezone.utc).isoformat()

    await db.decisions.delete_many({"id": dec_id})
    await db.decisions.insert_one({
        "id": dec_id, "user_id": s_uid, "type": "decider", "title": "Hire Agency A or B?",
        "current_step": 8, "total_steps": 8, "status": "completed", "is_complete": True,
        "factors": [{"id": "f1", "name": "Cost"}, {"id": "f2", "name": "Quality"}],
        "options": [
            {"id": "o1", "name": "Agency A", "assessments": [
                {"factor_id": "f1", "percentage": 60}, {"factor_id": "f2", "percentage": 80}]},
            {"id": "o2", "name": "Agency B", "assessments": [
                {"factor_id": "f1", "percentage": 70}, {"factor_id": "f2", "percentage": 50}]},
        ],
    })

    await db.collaboration_sessions.delete_many({"id": sid})
    await db.collaboration_sessions.insert_one({
        "id": sid, "owner_id": s_uid, "owner_name": "Super", "module_type": "decision",
        "module_id": dec_id, "title": "Hire Agency A or B?", "decision_mode_id": "equal",
        "decision_mode": {"id": "equal", "name": "Equal Weightage", "config": {}},
        "session_mode": "async",
        "participants": [{
            "contact_id": "c_admin", "name": "Admin Reviewer", "email": "admin@test.com",
            "linked_user_id": a_uid, "status": "invited", "auth_verified": False,
            "auth_methods_completed": [], "contribution": None, "vote": None, "accepted": None,
        }],
        "auth_requirements": {"methods_required": 0, "verify_each_time": False, "enabled_methods": []},
        "status": "active", "created_at": now, "updated_at": now, "result": None,
    })

    # 1) participant (admin) contributes
    c = requests.post(f"{BASE}/collaboration/sessions/{sid}/contribute", headers=AH,
                      json={"contribution": {"notes": "Agency A has better quality for the cost."}})
    print("CONTRIBUTE:", c.status_code, c.json())
    assert c.status_code == 200

    sess = requests.get(f"{BASE}/collaboration/sessions/{sid}", headers=AH).json()
    pstat = sess["participants"][0]["status"]
    print("  participant status:", pstat)
    assert pstat == "contributed"

    # 2) owner (super) merges
    m = requests.post(f"{BASE}/collaboration/sessions/{sid}/merge", headers=SH, json={})
    print("MERGE:", m.status_code, m.json().get("status"), "weights:", m.json().get("weights"))
    assert m.status_code == 200 and m.json().get("status") == "merged"

    sess2 = requests.get(f"{BASE}/collaboration/sessions/{sid}", headers=SH).json()
    print("  session status:", sess2["status"], "| has result:", bool(sess2.get("result")))
    assert sess2["status"] == "completed" and sess2.get("result")
    print("PASS: async contribute + merge works end-to-end. Demo session kept for screenshots.")


if __name__ == "__main__":
    asyncio.run(main())
