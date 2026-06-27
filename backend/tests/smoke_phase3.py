"""Phase 3B/3C smoke test — run from /app/backend:  python tests/smoke_phase3.py
Seeds a completed decider for the test user, then exercises publish + usage credit.
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
    from routes.option_publish import record_solution_usage

    # 1) seed a COMPLETED decider for the test user
    dec_id = f"dec_smoke_{uuid.uuid4().hex[:8]}"
    f1, f2, f3 = "f_cost", "f_speed", "f_trust"
    o1, o2 = "opt_a", "opt_b"
    decision = {
        "id": dec_id, "user_id": uid, "type": "decider",
        "name": "Smoke Decider (completed)",
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
            {"id": o2, "name": "Vendor B", "assessments": [
                {"factor_id": f1, "actual_value": 1200, "percentage": 60},
                {"factor_id": f2, "actual_value": 2, "percentage": 85},
                {"factor_id": f3, "actual_value": 4.0, "percentage": 80},
            ]},
        ],
        "status": "completed", "is_complete": True,
    }
    await db.decisions.delete_many({"id": dec_id})
    await db.decisions.insert_one(dict(decision))

    # 2) source endpoint
    s = requests.get(f"{BASE}/option-publish/source/{dec_id}", headers=H).json()
    print("SOURCE is_completed:", s.get("is_completed"), "factors:", len(s.get("factors", [])), "options:", len(s.get("options", [])))

    # 3) publish gating on a NON-completed decision
    await db.decisions.update_one({"id": dec_id}, {"$set": {"current_step": 2, "status": "in_progress", "is_complete": False}})
    g = requests.post(f"{BASE}/option-publish/publish", headers=H, json={"decision_id": dec_id, "monetization": "paid"})
    print("GATING non-completed publish status:", g.status_code, "(expect 400)")
    # restore completed
    await db.decisions.update_one({"id": dec_id}, {"$set": {"current_step": 8, "status": "completed", "is_complete": True}})

    # 4) publish PAID with f3 marked qualitative
    body = {
        "decision_id": dec_id,
        "monetization": "paid",
        "solution_type": "SERVICE",
        "factor_types": {f3: "qualitative"},
        "visibility": "PRIVATE",
    }
    pr = requests.post(f"{BASE}/option-publish/publish", headers=H, json=body)
    print("PUBLISH status:", pr.status_code)
    pj = pr.json()
    print("  published_count:", pj.get("published_count"), "reward_kind:", pj.get("reward_kind"),
          "quant_ids:", pj.get("quantitative_factor_ids"), "qual_ids:", pj.get("qualitative_factor_ids"))
    sols = pj.get("solutions", [])
    assert sols, "no solutions created"
    sol_id = sols[0]["solution_id"]
    print("  solution[0]:", sols[0])

    # 5) usage crediting via helper with a synthetic beneficiary
    sol = await db.solutions_store.find_one({"solution_id": sol_id}, {"_id": 0})
    bene = "fake_beneficiary_smoke"
    # clear any prior usages/ledgers for a clean count
    await db.solution_usages.delete_many({"solution_id": sol_id})
    results = []
    for i in range(4):
        res = await record_solution_usage(sol, bene, star_rating=5, source="smoke")
        results.append((res or {}).get("kind"), )
        print(f"  use#{i+1}:", {k: (res or {}).get(k) for k in ("kind", "reward_kind", "karma", "cash_inr")})

    # 6) verify ledgers
    karma_rows = await db.karma_ledger.count_documents({"ref.solution_id": sol_id})
    earn_rows = await db.earnings_ledger.count_documents({"solution_id": sol_id})
    prof = await db.referral_profiles.find_one({"user_id": uid}, {"_id": 0, "karma_balance": 1})
    print("KARMA ledger rows for sol:", karma_rows, "| EARNINGS rows:", earn_rows,
          "| publisher karma_balance:", (prof or {}).get("karma_balance"))

    # 7) my-published
    mp = requests.get(f"{BASE}/option-publish/my-published", headers=H).json()
    mine = [x for x in mp.get("items", []) if x["solution_id"] == sol_id]
    print("MY-PUBLISHED usage_count:", mine[0].get("usage_count") if mine else "NOT FOUND")

    # cleanup
    await db.decisions.delete_many({"id": dec_id})
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
