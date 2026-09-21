import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import certifi

load_dotenv('.env')

async def main():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where())
    db = client[db_name]
    
    print("=== Tagging & Updating Sample Records ===")

    # -------------------------------------------------------------
    # 1. PROS & CONS SAMPLES
    # -------------------------------------------------------------
    # Sample A: Completed
    r1 = await db.pros_cons.update_one(
        {"title": {"$regex": "Career Purpose & Direction for Divya"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "current_step": 8,
            "status": "completed",
            "context": "To be decided clearly within 12 month"
        }}
    )
    print("ProsCons Sample A (Completed):", r1.matched_count, r1.modified_count)

    # Sample B: In Progress
    r2 = await db.pros_cons.update_one(
        {"title": {"$regex": "Education Pathway for Ekanga"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "current_step": 4,
            "status": "in_progress",
            "context": "Education Pathway for Ekanga"
        }}
    )
    print("ProsCons Sample B (In Progress):", r2.matched_count, r2.modified_count)

    # Sample C: Draft
    r3 = await db.pros_cons.update_one(
        {"title": {"$regex": "Where should I invest my savings"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "current_step": 1,
            "status": "draft",
            "context": "Comparing asset classes for 2026 savings"
        }}
    )
    print("ProsCons Sample C (Draft):", r3.matched_count, r3.modified_count)

    # -------------------------------------------------------------
    # 2. MY DEZIDER SAMPLES
    # -------------------------------------------------------------
    # Sample A: Completed
    d1 = await db.decisions.update_one(
        {"title": {"$regex": "Business & Startup - TG Selection"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "completed",
            "chosen_option_id": "opt_tg_1"
        }}
    )
    print("Decisions Sample A (Completed):", d1.matched_count, d1.modified_count)

    # Sample B: In Progress
    d2 = await db.decisions.update_one(
        {"title": {"$regex": "Finance — 7 Sept 2026"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "in_progress",
            "factors": [{"id": "f1", "name": "ROI", "rating": 8}],
            "options": [{"id": "o1", "name": "Option A"}]
        }}
    )
    print("Decisions Sample B (In Progress):", d2.matched_count, d2.modified_count)

    # Sample C: Draft
    d3 = await db.decisions.update_one(
        {"title": {"$regex": "Physical, Mental & Emotional Health — 16 Sept 2026"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "draft",
            "factors": [],
            "options": []
        }}
    )
    print("Decisions Sample C (Draft):", d3.matched_count, d3.modified_count)

    # -------------------------------------------------------------
    # 3. SOLUTION FINDER SAMPLES
    # -------------------------------------------------------------
    # Sample A: Completed
    s1 = await db.solution_finders.update_one(
        {"smart_goal": {"$regex": "Success Week Planning"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "completed"
        }}
    )
    print("SolutionFinders Sample A (Completed):", s1.matched_count, s1.modified_count)

    # Sample B: In Progress
    s2 = await db.solution_finders.update_one(
        {"smart_goal": {"$regex": "Earliest and Smoothest Possible Closure"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "in_progress"
        }}
    )
    print("SolutionFinders Sample B (In Progress):", s2.matched_count, s2.modified_count)

    # Sample C: Completed (Debt closure)
    s3 = await db.solution_finders.update_one(
        {"smart_goal": {"$regex": "How to close my 20L debt"}},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "completed"
        }}
    )
    print("SolutionFinders Sample C (Completed):", s3.matched_count, s3.modified_count)

if __name__ == "__main__":
    asyncio.run(main())
