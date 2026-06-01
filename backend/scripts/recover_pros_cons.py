"""
Production recovery / forensic search for a deleted Pros & Cons (or any module) entry.

WHAT IT DOES (READ-ONLY by default):
  1. Searches the LIVE `pros_cons` collection for the entry (in case it was a
     soft-delete or only partially removed).
  2. Searches the `trash` collection (soft-delete safety net) for the entry.
  3. Optionally does a broad scan across the main user-content collections.
  4. With --restore-trash <trash_id> it restores a soft-deleted doc from trash
     back into its original collection.

IMPORTANT: This script connects to whatever MONGO_URL / DB_NAME you give it.
To run it against PRODUCTION, point those env vars at your Atlas cluster.

USAGE (on your EC2 box, in the backend dir, venv active):
  python3.12 -m pip install motor python-dotenv      # if not already installed

  # 1) Search for the entry (default term: "Praveen"):
  MONGO_URL="<atlas-uri>" DB_NAME="<prod-db>" python3.12 -m scripts.recover_pros_cons

  # 2) Search for a custom term:
  MONGO_URL="..." DB_NAME="..." python3.12 -m scripts.recover_pros_cons --term "Praveen Raj"

  # 3) Restore a soft-deleted item found in trash:
  MONGO_URL="..." DB_NAME="..." python3.12 -m scripts.recover_pros_cons --restore-trash <trash_id>

If the entry is NOT found in either pros_cons or trash, it was HARD-DELETED on a
deploy that did not yet have the Trash feature. In that case the ONLY recovery is
a MongoDB Atlas Backup / Point-in-Time Restore from the Atlas dashboard.
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load backend/.env if present (local), but env vars passed inline always win.
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

# Collections that hold user-authored content worth scanning in a broad search.
CONTENT_COLLECTIONS = [
    "pros_cons", "decisions", "swot_analyses",
    "solution_finders", "solution_matrices",
]


def _short(doc: dict) -> dict:
    """Pick the human-meaningful fields for printing."""
    return {
        "id": doc.get("id") or doc.get("entry_id") or doc.get("_id"),
        "title": doc.get("title") or doc.get("decision_title") or doc.get("smart_goal"),
        "user_id": doc.get("user_id"),
        "created_at": str(doc.get("created_at") or doc.get("createdAt") or ""),
        "updated_at": str(doc.get("updated_at") or doc.get("updatedAt") or ""),
    }


async def search(db, term: str):
    rx = {"$regex": term, "$options": "i"}
    print(f"\n=== LIVE `pros_cons` matches for '{term}' ===")
    found_live = 0
    cur = db.pros_cons.find({"$or": [{"title": rx}, {"decision_title": rx}]})
    async for d in cur:
        found_live += 1
        print("  •", _short(d))
    if not found_live:
        print("  (none — not present in the live pros_cons collection)")

    print(f"\n=== `trash` matches for '{term}' ===")
    found_trash = 0
    cur = db.trash.find({"title": rx})
    async for t in cur:
        found_trash += 1
        print("  • trash_id=", t.get("trash_id"),
              "| module=", t.get("module"),
              "| title=", t.get("title"),
              "| user_id=", t.get("user_id"),
              "| deleted_at=", str(t.get("deleted_at")))
    if not found_trash:
        print("  (none — not present in the trash collection)")

    print(f"\n=== BROAD scan across {CONTENT_COLLECTIONS} for '{term}' ===")
    broad = 0
    for coll in CONTENT_COLLECTIONS:
        try:
            cur = db[coll].find({"$or": [
                {"title": rx}, {"decision_title": rx}, {"smart_goal": rx},
            ]})
            async for d in cur:
                broad += 1
                print(f"  • [{coll}]", _short(d))
        except Exception as e:
            print(f"  ! {coll}: {e}")
    if not broad:
        print("  (no matches in any content collection)")

    print("\n----------------------------------------------------------------")
    if found_trash:
        print("RESULT: Found in TRASH. Restore with:")
        print('  --restore-trash <trash_id>')
    elif found_live:
        print("RESULT: Still present in the LIVE collection — it was NOT deleted.")
    else:
        print("RESULT: NOT found in live data or trash.")
        print("        => Hard-deleted on a build without the Trash feature.")
        print("        => Recover via MongoDB Atlas Backup / Point-in-Time Restore")
        print("           (Atlas dashboard → your cluster → Backup → Restore to a")
        print("            timestamp just BEFORE the delete).")
    print("----------------------------------------------------------------\n")


async def restore_trash(db, trash_id: str):
    t = await db.trash.find_one({"trash_id": trash_id})
    if not t:
        print(f"No trash item with trash_id={trash_id}")
        return
    doc = t.get("document") or {}
    doc.pop("_id", None)
    coll = t["collection"]
    idf = t["id_field"]
    existing = await db[coll].find_one({idf: t["original_id"]}, {"_id": 1})
    if existing:
        print(f"An item with {idf}={t['original_id']} already exists in {coll}; not overwriting.")
    else:
        await db[coll].insert_one(doc)
        print(f"Restored '{t.get('title')}' into {coll} (route {t.get('route')}).")
    await db.trash.delete_one({"trash_id": trash_id})
    print("Removed item from trash.")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--term", default="Praveen", help="Search term (case-insensitive)")
    ap.add_argument("--restore-trash", dest="restore_trash", default=None,
                    help="trash_id to restore from the trash collection")
    args = ap.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: set MONGO_URL and DB_NAME env vars (point them at PRODUCTION Atlas).")
        sys.exit(1)

    print(f"Connecting to DB '{db_name}' ...")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=8000)
    db = client[db_name]
    # Fail fast if unreachable
    await db.command("ping")
    print("Connected.")

    if args.restore_trash:
        await restore_trash(db, args.restore_trash)
    else:
        await search(db, args.term)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
