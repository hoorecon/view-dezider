import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import certifi

load_dotenv('backend/.env')

async def main():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url, tlsCAFile=certifi.where())
    db = client[db_name]
    
    print("=== Resetting Sample Records ===")

    # 1. Clear all previous sample flags across collections
    await db.pros_cons.update_many({}, {"$unset": {"is_sample": "", "is_sample_record": ""}})
    await db.decisions.update_many({}, {"$unset": {"is_sample": "", "is_sample_record": ""}})
    await db.solution_finders.update_many({}, {"$unset": {"is_sample": "", "is_sample_record": ""}})
    print("Cleared all old sample flags.")

    # 2. Tag ONLY the 1 designated Pros & Cons sample record
    pc = await db.pros_cons.update_one(
        {"title": "Career Purpose & Direction for Divya - Sep 2026"},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "current_step": 8,
            "status": "completed"
        }}
    )
    print("Tagged ONLY ProsCons sample ('Career Purpose & Direction for Divya - Sep 2026'):", pc.matched_count, pc.modified_count)

    # 3. Tag ONLY the 1 designated My Dezider sample record
    dec = await db.decisions.update_one(
        {"title": "Business & Startup - TG Selection"},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "completed"
        }}
    )
    print("Tagged ONLY MyDezider sample ('Business & Startup - TG Selection'):", dec.matched_count, dec.modified_count)

    # 4. Tag ONLY the 1 designated Solution Finder sample record
    sf = await db.solution_finders.update_one(
        {"smart_goal": "How to close my 20L debt with interest within 30/04/2030, without selling both sites?"},
        {"$set": {
            "is_sample": True,
            "is_sample_record": True,
            "status": "completed"
        }}
    )
    print("Tagged ONLY SolutionFinder sample ('How to close my 20L debt...'):", sf.matched_count, sf.modified_count)

if __name__ == "__main__":
    asyncio.run(main())
