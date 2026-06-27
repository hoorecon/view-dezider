"""Remove smoke-test artifacts created by smoke_phase3.py."""
import asyncio


async def main():
    from core.database import db
    sols = await db.solutions_store.find(
        {"published_from_option": True, "source.decision_id": {"$regex": "^dec_smoke_"}},
        {"_id": 0, "solution_id": 1, "created_by": 1},
    ).to_list(100)
    sol_ids = [s["solution_id"] for s in sols]
    # how much karma to subtract from the publisher
    karma_total = 0
    if sol_ids:
        async for k in db.karma_ledger.find({"ref.solution_id": {"$in": sol_ids}}, {"_id": 0, "points": 1, "user_id": 1}):
            karma_total += int(k.get("points") or 0)
    publisher = sols[0]["created_by"] if sols else None
    res = {
        "solutions": await db.solutions_store.delete_many({"solution_id": {"$in": sol_ids}}) if sol_ids else None,
        "policies": await db.review_policies.delete_many({"solution_id": {"$in": sol_ids}}) if sol_ids else None,
        "usages": await db.solution_usages.delete_many({"solution_id": {"$in": sol_ids}}) if sol_ids else None,
        "earnings": await db.earnings_ledger.delete_many({"solution_id": {"$in": sol_ids}}) if sol_ids else None,
        "karma": await db.karma_ledger.delete_many({"ref.solution_id": {"$in": sol_ids}}) if sol_ids else None,
    }
    if publisher and karma_total:
        await db.referral_profiles.update_one({"user_id": publisher}, {"$inc": {"karma_balance": -karma_total}})
    await db.decisions.delete_many({"id": {"$regex": "^dec_smoke_"}})
    print("cleaned sol_ids:", len(sol_ids), "karma_reverted:", karma_total)


if __name__ == "__main__":
    asyncio.run(main())
