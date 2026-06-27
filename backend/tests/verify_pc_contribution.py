"""P&C (and pattern for SF) clone-based contribution E2E.
super creates a P&C → shares step 3 to admin (module=pros_cons) → admin opens
(gets a clone) → admin edits the clone via the normal P&C API → admin submits →
super sees the snapshot. Also verifies clones are hidden from admin's P&C list.
Run: cd /app/backend && PYTHONPATH=/app/backend python tests/verify_pc_contribution.py
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

    # 0) clean up any prior demo
    await db.shared_steps.delete_many({"decision_title": "PC Contribution Demo"})
    await db.pros_cons.delete_many({"contribution_clone": {"$exists": True}})

    # 1) super creates a P&C
    cr = requests.post(f"{BASE}/pros-cons", headers=SH, json={
        "title": "PC Contribution Demo", "context": "Should we expand to EU?",
        "life_area": "career", "decision_type": "strategic",
    })
    pc_id = cr.json()["id"]
    print("CREATE P&C:", cr.status_code, pc_id)

    # admin's P&C count BEFORE clone
    before = len(requests.get(f"{BASE}/pros-cons", headers=AH).json())

    # 2) super shares step 3 to admin (module-aware create)
    sr = requests.post(f"{BASE}/shared-steps/create", headers=SH, json={
        "module": "pros_cons", "module_id": pc_id, "step_number": 3,
        "recipient_emails": ["admin@test.com"], "merge_mode": "equal",
        "message": "Add your pros & cons", "step_access": "hidden",
    })
    print("SHARE create:", sr.status_code, sr.json())
    share_id = sr.json()["id"]

    # 3) admin opens → gets a clone id
    op = requests.post(f"{BASE}/shared-steps/{share_id}/open", headers=AH)
    print("OPEN:", op.status_code, op.json())
    assert op.json()["module"] == "pros_cons"
    clone_id = op.json()["target_id"]
    assert clone_id != pc_id

    # 4) admin can load the clone via the NORMAL P&C endpoint (it's their own doc)
    gc = requests.get(f"{BASE}/pros-cons/{clone_id}", headers=AH)
    print("LOAD CLONE (admin):", gc.status_code, "| title:", gc.json().get("title"))
    assert gc.status_code == 200

    # 4b) clone must NOT appear in admin's normal P&C list (no clutter)
    after = len(requests.get(f"{BASE}/pros-cons", headers=AH).json())
    print("admin P&C list count before/after:", before, after)
    assert after == before, "clone leaked into the contributor's P&C list!"

    # 5) admin edits the clone (real flow CRUD) then submits the contribution
    requests.put(f"{BASE}/pros-cons/{clone_id}", headers=AH, json={"context": "EU expansion — admin view"})
    cb = requests.post(f"{BASE}/shared-steps/{share_id}/contribute", headers=AH, json={"note": "Done from the real flow"})
    print("CONTRIBUTE:", cb.status_code, cb.json())
    assert cb.status_code == 200

    # 6) owner sees the contributor's snapshot
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    rec = next(r for r in share["recipients"] if r["user_id"] == a_uid)
    snap = (rec.get("contribution") or {}).get("snapshot")
    print("owner sees snapshot context:", (snap or {}).get("context"), "| status:", rec.get("status"))
    assert rec["status"] == "contributed" and snap and snap.get("context") == "EU expansion — admin view"

    # cleanup
    await db.pros_cons.delete_many({"id": {"$in": [pc_id, clone_id]}})
    await db.shared_steps.delete_many({"id": share_id})
    print("PASS: P&C clone-based contribution works (open→clone→edit→submit→owner sees snapshot; no list clutter).")


if __name__ == "__main__":
    asyncio.run(main())
