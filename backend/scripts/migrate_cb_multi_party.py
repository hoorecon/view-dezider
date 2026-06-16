"""Standalone migration: delete all existing Conflict Breaker sessions before
introducing the multi-party schema. Per explicit user request in v3.23 plan —
existing data is non-critical user-test data and adopting the new schema cleanly
is simpler than backfilling `parties[]` and rewrapping every response.

Run on EC2:
    cd /opt/dezider/backend && python3 scripts/migrate_cb_multi_party.py
The script reads `MONGO_URL` (and optionally `DB_NAME`) from the local
`backend/.env` automatically — no env vars need to be exported.
"""
import asyncio
import os
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


def _load_env() -> None:
    """Best-effort .env loader (no python-dotenv dependency).

    Looks for `.env` in:
      1. the directory of this script's parent (e.g. /opt/dezider/backend/.env)
      2. the current working directory
    so it works both when the operator `cd`s into backend/ first AND when they
    run it from anywhere else.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",  # backend/.env
        Path.cwd() / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        try:
            for raw in env_path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                # Don't clobber explicit shell exports.
                os.environ.setdefault(key, val)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: failed reading {env_path}: {e}", file=sys.stderr)


async def main():
    _load_env()
    mongo_url = os.getenv("MONGO_URL")
    if not mongo_url:
        print(
            "ERROR: MONGO_URL is not set.\n"
            "  Looked for it in env vars and in backend/.env — neither had it.\n"
            "  Either export MONGO_URL or add it to backend/.env then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)
    db_name = os.getenv("DB_NAME") or "veales_db"
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    print(f"Connected to {db_name} via {mongo_url[:32]}...")

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
