"""Soft-delete / Trash with 7-day auto-purge.

Deleted documents are MOVED to a dedicated `trash` collection. This means they
disappear from every existing list/read path automatically (no query changes
needed anywhere), and can be restored or permanently purged. Items older than
TRASH_RETENTION_DAYS are purged opportunistically (on any trash access or new
delete).
"""
import uuid
from datetime import datetime, timezone, timedelta

from core.database import db

TRASH_RETENTION_DAYS = 7

# module key -> (collection, id_field, owner_field, [title fields], label, route)
TRASH_MODULES = {
    "decision":        ("decisions",         "id",       "user_id", ["title"],                  "Decision",        "/prr"),
    "pros_cons":       ("pros_cons",         "id",       "user_id", ["title", "decision_title"], "Pros & Cons",     "/tools/pros-cons-list"),
    "swot":            ("swot_analyses",     "id",       "user_id", ["title"],                  "SWOT",            "/tools/swot"),
    "solution_finder": ("solution_finders",  "entry_id", "user_id", ["smart_goal", "title"],    "Solution Finder", "/tools/solution-finder-list"),
    "solution_matrix": ("solution_matrices", "entry_id", "user_id", ["smart_goal", "title"],    "Solution Matrix", "/tools/solution-matrix-list"),
}


def _title_of(doc: dict, fields: list) -> str:
    for f in fields:
        v = doc.get(f)
        if v:
            return str(v)
    return "Untitled"


async def move_to_trash(module: str, id_value: str, user_id: str) -> bool:
    """Move a document from its module collection into `trash`. Returns False if
    the document was not found (so callers can still return 404)."""
    if module not in TRASH_MODULES:
        raise ValueError(f"Unknown trash module: {module}")
    coll, idf, ownerf, title_fields, label, route = TRASH_MODULES[module]
    doc = await db[coll].find_one({idf: id_value, ownerf: user_id})
    if not doc:
        return False
    doc.pop("_id", None)
    await db.trash.insert_one({
        "trash_id": str(uuid.uuid4()),
        "module": module,
        "collection": coll,
        "id_field": idf,
        "owner_field": ownerf,
        "original_id": id_value,
        "user_id": user_id,
        "title": _title_of(doc, title_fields),
        "label": label,
        "route": route,
        "deleted_at": datetime.now(timezone.utc),
        "document": doc,
    })
    await db[coll].delete_one({idf: id_value, ownerf: user_id})
    await purge_expired()
    return True


async def purge_expired() -> int:
    """Permanently remove trash items older than the retention window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    res = await db.trash.delete_many({"deleted_at": {"$lt": cutoff}})
    return res.deleted_count
