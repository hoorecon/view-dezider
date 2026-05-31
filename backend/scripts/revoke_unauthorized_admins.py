"""
revoke_unauthorized_admins.py
=============================

SECURITY REMEDIATION SCRIPT.

Demotes EVERY user whose role is `admin`, `co_admin` or `super_admin` back to
`user`, EXCEPT the single designated root super-admin email. The root account is
forced/ensured to `super_admin`.

Usage
-----
Local (dev) DB — uses backend/.env MONGO_URL + DB_NAME automatically:
    cd /app/backend && python scripts/revoke_unauthorized_admins.py

Dry run (report only, no writes):
    python scripts/revoke_unauthorized_admins.py --dry-run

Production DB — point it at prod by overriding env vars (NEVER hard-code creds):
    MONGO_URL="mongodb+srv://USER:PASS@cluster/..." DB_NAME="prod_db" \
        python scripts/revoke_unauthorized_admins.py

Override the protected email if ever needed:
    ROOT_SUPER_ADMIN_EMAIL="someone@x.com" python scripts/revoke_unauthorized_admins.py
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (one dir up from scripts/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

ADMIN_ROLES = ["admin", "co_admin", "super_admin"]
ROOT_EMAIL = os.environ.get(
    "ROOT_SUPER_ADMIN_EMAIL", "veales.vedic.decisions@gmail.com"
).strip().lower()


async def main(dry_run: bool = False) -> None:
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    print(f"→ Connecting to {mongo_url}  (db={db_name})")
    print(f"→ Protected root super-admin: {ROOT_EMAIL}")
    print(f"→ Mode: {'DRY RUN (no writes)' if dry_run else 'APPLY CHANGES'}")
    print("-" * 60)

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # 1) Report current privileged accounts
    cursor = db.users.find(
        {"role": {"$in": ADMIN_ROLES}}, {"_id": 0, "email": 1, "role": 1, "name": 1}
    )
    privileged = await cursor.to_list(length=1000)
    print(f"Found {len(privileged)} privileged account(s):")
    for u in privileged:
        print(f"   - {u.get('email'):<45} role={u.get('role')}")
    print("-" * 60)

    # 2) Demote everyone who is privileged but NOT the root email
    demote_filter = {
        "email": {"$ne": ROOT_EMAIL},
        "role": {"$in": ADMIN_ROLES},
    }
    to_demote = await db.users.count_documents(demote_filter)

    if dry_run:
        print(f"[DRY RUN] Would demote {to_demote} account(s) to 'user'.")
    else:
        res = await db.users.update_many(demote_filter, {"$set": {"role": "user"}})
        print(f"✓ Demoted {res.modified_count} account(s) to 'user'.")

    # 3) Ensure the root account (if present) is super_admin
    root = await db.users.find_one({"email": ROOT_EMAIL}, {"_id": 0, "email": 1, "role": 1})
    if root:
        if root.get("role") != "super_admin":
            if dry_run:
                print(f"[DRY RUN] Would promote root {ROOT_EMAIL} -> super_admin.")
            else:
                await db.users.update_one(
                    {"email": ROOT_EMAIL}, {"$set": {"role": "super_admin"}}
                )
                print(f"✓ Ensured root {ROOT_EMAIL} is super_admin.")
        else:
            print(f"✓ Root {ROOT_EMAIL} already super_admin.")
    else:
        print(f"! Root email {ROOT_EMAIL} not found in this DB (no action).")

    # 4) Final verification
    print("-" * 60)
    remaining = await db.users.find(
        {"role": {"$in": ADMIN_ROLES}}, {"_id": 0, "email": 1, "role": 1}
    ).to_list(length=1000)
    print(f"Remaining privileged account(s) after run: {len(remaining)}")
    for u in remaining:
        print(f"   - {u.get('email'):<45} role={u.get('role')}")

    client.close()
    print("Done.")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry))
