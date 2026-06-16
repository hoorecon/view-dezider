"""Standalone migration: delete all existing Conflict Breaker sessions before
introducing the multi-party schema. Per explicit user request in v3.23 plan —
existing data is non-critical user-test data and adopting the new schema cleanly
is simpler than backfilling `parties[]` and rewrapping every response.

Run on EC2:
    cd /opt/dezider/backend && MONGO_URL='mongodb://...' python3 scripts/migrate_cb_multi_party.py
"""
import asyncio
import os
import sys

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    mongo_url = os.getenv("MONGO_URL")
    if not mongo_url:
        print("ERROR: MONGO_URL is not set.", file=sys.stderr)
        sys.exit(1)
    db_name = os.getenv("DB_NAME") or "veales_db"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    collections = [
        "conflict_breaker_sessions",
        "conflict_breaker_responses",
        "conflict_audio_files",
    ]
    for c in collections:
        try:
            res = await db[c].delete_many({})
            print(f"  - {c}: deleted {res.deleted_count}")
        except Exception as e:
            print(f"  - {c}: ERROR {e}")

    print("Done.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
