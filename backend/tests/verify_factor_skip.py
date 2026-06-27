"""Verify factor skip: publishing with a subset of factor_ids excludes the rest.
Run from /app/backend:  python tests/verify_factor_skip.py
"""
import asyncio
import uuid
import requests

BASE = "http://localhost:8001/api"
EMAIL, PWD = "super@test.com", "SuperPass2026!"


def login():
    r = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PWD})
    r.raise_for_status()
    d = r.json()
    return d["session_token"], d["user_id"]


async def main():
    token, uid = login()
    H = {"Authorization": f"Bearer {token}"}
    from core.database import db

    dec_id = f"dec_fskip_{uuid.uuid4().hex[:8]}"
    f1, f2, f3 = "f_cost", "f_speed", "f_trust"
    o1 = "opt_a"
    decision = {
        "id": dec_id, "user_id": uid, "type": "decider",
        "name": "Factor Skip Decider",
        "current_step": 8, "total_steps": 8,
        "factors": [
            {"id": f1, "name": "Cost", "unit": "INR", "operator": "lt"},
            {"id": f2, "name": "Speed", "unit": "days", "operator": "lt"},
            {"id": f3, "name": "Trust", "unit": "score", "operator": "gt"},
        ],
        "options": [
            {"id": o1, "name": "Vendor A", "assessments": [
                {"factor_id": f1, "actual_value": 1000, "percentage": 80},
                {"factor_id": f2, "actual_value": 3, "percentage": 70},
                {"factor_id": f3, "actual_value": 4.5, "percentage": 90},
            ]},
        ],
        "status": "completed", "is_complete": True,
    }
    await db.decisions.delete_many({"id": dec_id})
    await db.decisions.insert_one(dict(decision))

    # Publish keeping ONLY f1 (Cost) and f3 (Trust as qualitative). f2 (Speed) is SKIPPED.
    body = {
        "decision_id": dec_id,
        "monetization": "free",
        "solution_type": "PRODUCT",
        "factor_ids": [f1, f3],
        "factor_types": {f1: "quantitative", f3: "qualitative"},
        "visibility": "PRIVATE",
    }
    pr = requests.post(f"{BASE}/option-publish/publish", headers=H, json=body)
    print("PUBLISH status:", pr.status_code)
    pj = pr.json()
    print("  quant_ids:", pj.get("quantitative_factor_ids"), "qual_ids:", pj.get("qualitative_factor_ids"))
    sol_id = pj["solutions"][0]["solution_id"]
    sol = await db.solutions_store.find_one({"solution_id": sol_id}, {"_id": 0})

    quant_fids = {q["factor_id"] for q in sol.get("quantitative_factors", [])}
    qual_fids = {q["factor_id"] for q in sol.get("qualitative_factors", [])}
    print("  stored quant:", quant_fids, "stored qual:", qual_fids)

    assert f2 not in quant_fids and f2 not in qual_fids, "FAIL: skipped factor f2 leaked into solution"
    assert quant_fids == {f1}, f"FAIL: expected quant {{f1}}, got {quant_fids}"
    assert qual_fids == {f3}, f"FAIL: expected qual {{f3}}, got {qual_fids}"
    print("PASS: skipped factor f2 excluded; quant/qual partition correct")

    await db.solutions_store.delete_many({"solution_id": sol_id})
    await db.review_policies.delete_many({"solution_id": sol_id})
    await db.decisions.delete_many({"id": dec_id})
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
