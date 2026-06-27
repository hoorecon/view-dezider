"""Verify "Use this solution" record-usage credits the publisher (not self).
Run:  cd /app/backend && PYTHONPATH=/app/backend python tests/verify_use_solution.py
"""
import asyncio
import uuid
import requests

BASE = "http://localhost:8001/api"


def login(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    r.raise_for_status()
    d = r.json()
    return d["session_token"], d["user_id"]


async def main():
    s_token, s_uid = login("super@test.com", "SuperPass2026!")
    a_token, a_uid = login("admin@test.com", "AdminPass2026!")
    SH = {"Authorization": f"Bearer {s_token}"}
    AH = {"Authorization": f"Bearer {a_token}"}
    from core.database import db

    # 1) seed a completed decider for super
    dec_id = f"dec_use_{uuid.uuid4().hex[:8]}"
    decision = {
        "id": dec_id, "user_id": s_uid, "type": "decider", "name": "Use-flow Decider",
        "current_step": 8, "total_steps": 8,
        "factors": [{"id": "f1", "name": "Cost", "unit": "INR", "operator": "lt"}],
        "options": [{"id": "o1", "name": "Vendor A", "assessments": [
            {"factor_id": "f1", "actual_value": 1000, "percentage": 80}]}],
        "status": "completed", "is_complete": True,
    }
    await db.decisions.delete_many({"id": dec_id})
    await db.decisions.insert_one(dict(decision))

    # 2) publish as FREE (karma) by super
    pr = requests.post(f"{BASE}/option-publish/publish", headers=SH, json={
        "decision_id": dec_id, "monetization": "free", "solution_type": "PRODUCT",
        "factor_types": {"f1": "quantitative"}, "visibility": "PRIVATE",
    })
    print("PUBLISH:", pr.status_code)
    sol_id = pr.json()["solutions"][0]["solution_id"]

    # 3) admin (different user) records usage via the SAME endpoint the button calls
    await db.solution_usages.delete_many({"solution_id": sol_id})
    ru = requests.post(f"{BASE}/option-publish/record-usage", headers=AH, json={"solution_id": sol_id})
    print("RECORD-USAGE (admin):", ru.status_code, ru.json())
    rj = ru.json()
    assert rj.get("ok") is True, "expected ok:true for cross-user usage"
    assert rj.get("reward_kind") == "karma", f"expected karma, got {rj.get('reward_kind')}"
    assert (rj.get("karma") or 0) > 0, "expected positive karma"

    # 4) super using own solution => no reward (button is hidden in UI, API is safe)
    su = requests.post(f"{BASE}/option-publish/record-usage", headers=SH, json={"solution_id": sol_id})
    print("RECORD-USAGE (self):", su.status_code, su.json())
    assert su.json().get("ok") is False, "self-use must not reward"

    # cleanup
    await db.solutions_store.delete_many({"solution_id": sol_id})
    await db.review_policies.delete_many({"solution_id": sol_id})
    await db.solution_usages.delete_many({"solution_id": sol_id})
    await db.decisions.delete_many({"id": dec_id})
    print("PASS: cross-user usage rewards publisher with Karma; self-use rewards nothing")


if __name__ == "__main__":
    asyncio.run(main())
