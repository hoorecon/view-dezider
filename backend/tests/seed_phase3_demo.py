"""Seed a persistent COMPLETED decider for Phase 3 publish demo/testing."""
import asyncio


async def main():
    from core.database import db
    user = await db.users.find_one({"email": "super@test.com"}, {"_id": 0, "user_id": 1})
    uid = user["user_id"]
    dec_id = "dec_phase3_publish_demo"
    f1, f2, f3 = "f_price", "f_quality", "f_support"
    doc = {
        "id": dec_id, "user_id": uid, "type": "decider",
        "name": "Phase3 Publish Demo (Completed)",
        "current_step": 8, "total_steps": 8,
        "factors": [
            {"id": f1, "name": "Price", "unit": "INR", "operator": "lt"},
            {"id": f2, "name": "Quality", "unit": "score", "operator": "gt"},
            {"id": f3, "name": "Support Experience", "unit": "score", "operator": "gt"},
        ],
        "options": [
            {"id": "o_alpha", "name": "Alpha Plan", "assessments": [
                {"factor_id": f1, "actual_value": 999, "percentage": 75},
                {"factor_id": f2, "actual_value": 8.5, "percentage": 85},
                {"factor_id": f3, "actual_value": 9.0, "percentage": 90},
            ]},
            {"id": "o_beta", "name": "Beta Plan", "assessments": [
                {"factor_id": f1, "actual_value": 1299, "percentage": 60},
                {"factor_id": f2, "actual_value": 9.0, "percentage": 90},
                {"factor_id": f3, "actual_value": 8.0, "percentage": 80},
            ]},
        ],
        "status": "completed", "is_complete": True,
    }
    await db.decisions.update_one({"id": dec_id}, {"$set": doc}, upsert=True)
    print("seeded completed decider:", dec_id, "for", uid)


if __name__ == "__main__":
    asyncio.run(main())
