"""Decision Journal routes — entries, reminders, linkable items."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import (
    JournalEntry, JournalEntryCreate, JournalEntryUpdate,
    VALID_LINKED_MODULES, VALID_ENTRY_TYPES,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Decisions"])


async def verify_journal_access(user: dict):
    """Ensure user is on a Subscription plan (Basic, Pro, Premium, Enterprise, Starter, Paid, Admin, or Tester).

    Restricts Free AND On-Demand plan users from accessing Learning Journal.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    role = str(user.get("role") or "").lower()
    if role in {"super_admin", "admin", "co_admin"} or user.get("is_admin"):
        return True

    user_id = user.get("user_id")

    # 1. Global payment skip check
    s = await db.app_settings.find_one({"_key": "payment_settings"}, {"_id": 0})
    if s and s.get("skip_payment_all_flows"):
        return True

    # 2. Refresh user doc from DB
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1, "user_type": 1, "subscription_plan": 1, "is_admin": 1}) or {}
    role = str(user_doc.get("role") or user.get("role") or "").lower()
    if role in {"super_admin", "admin", "co_admin"} or user_doc.get("is_admin"):
        return True

    utype = str(user_doc.get("user_type") or user.get("user_type") or "").lower().strip()
    splan = str(user_doc.get("subscription_plan") or user.get("subscription_plan") or "").lower().strip()

    # Testers override
    if utype in {"admin", "super_admin", "co_admin", "alpha", "beta", "unit_tester", "integration_tester"}:
        return True

    # 3. Explicit check for on_demand / free
    if utype.startswith("on_demand") or splan.startswith("on_demand") or utype == "free" or splan in {"free", "none", ""}:
        raise HTTPException(
            status_code=403,
            detail="Learning Journal is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access Learning Journal."
        )

    # 4. Check credit wallet subscription status
    wallet = await db.credit_wallets.find_one(
        {"user_id": user_id}, {"_id": 0, "subscription_status": 1, "current_plan": 1}
    )
    if wallet:
        st = str(wallet.get("subscription_status") or "").lower().strip()
        cp = str(wallet.get("current_plan") or "").lower().strip()
        if st in {"active", "manual", "pending"} and cp and cp not in {"none", "free"} and not cp.startswith("on_demand"):
            return True

    # 5. Check active subscription plan on user doc
    if splan and splan not in {"none", "free", ""} and not splan.startswith("on_demand"):
        return True

    if utype == "paid":
        return True

    # 6. Block Free and On-Demand users
    raise HTTPException(
        status_code=403,
        detail="Learning Journal is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access Learning Journal."
    )


@router.post("/journal", response_model=dict)
async def create_journal_entry(entry: JournalEntryCreate, user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    if entry.linked_module and entry.linked_module not in VALID_LINKED_MODULES:
        raise HTTPException(status_code=400, detail=f"Invalid linked_module. Must be one of: {VALID_LINKED_MODULES}")
    if entry.entry_type and entry.entry_type not in VALID_ENTRY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type. Must be one of: {VALID_ENTRY_TYPES}")
    linked_title = entry.linked_title
    if entry.linked_module and entry.linked_id and not linked_title:
        collection_map = {
            "decision": ("decisions", "title"), "solution_finder": ("solution_finders", "title"),
            "solution_matrix": ("solution_matrices", "smart_goal"), "gem": ("gem_goals", "title"),
            "ctt": ("ctt_tasks", "task"), "lifestyle": ("lifestyle_routines", "name"),
        }
        if entry.linked_module in collection_map:
            coll, field = collection_map[entry.linked_module]
            doc = await db[coll].find_one({"id": entry.linked_id}, {field: 1})
            linked_title = doc.get(field) if doc else None
    journal_entry = JournalEntry(
        user_id=user["user_id"], decision_title=entry.decision_title,
        decision_description=entry.decision_description, linked_module=entry.linked_module,
        linked_id=entry.linked_id, linked_title=linked_title or entry.linked_title,
        entry_type=entry.entry_type, decision_date=entry.decision_date or datetime.now(timezone.utc)
    )
    await db.journal.insert_one(journal_entry.dict())
    return {"id": journal_entry.id, "message": "Journal entry created"}


@router.get("/journal", response_model=List[dict])
async def get_journal_entries(user: dict = Depends(get_current_user),
                              linked_module: Optional[str] = None, linked_id: Optional[str] = None,
                              entry_type: Optional[str] = None):
    await verify_journal_access(user)
    query = {"user_id": user["user_id"]}
    if linked_module:
        query["linked_module"] = linked_module
    if linked_id:
        query["linked_id"] = linked_id
    if entry_type:
        query["entry_type"] = entry_type
    entries = await db.journal.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries


@router.get("/journal/reminders", response_model=List[dict])
async def get_journal_reminders(user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    now = datetime.now(timezone.utc)
    decisions = await db.decisions.find({
        "user_id": user["user_id"],
        "implementation_review_date": {"$lte": now, "$ne": None},
        "decision_type": {"$in": ["problem", "need"]},
    }, {"_id": 0}).sort("implementation_review_date", 1).to_list(50)
    reminders = []
    for dec in decisions:
        existing_journal = await db.journal.find_one({"user_id": user["user_id"], "linked_module": "decision", "linked_id": dec["id"]})
        if not existing_journal:
            priority_label = "P0" if dec.get("decision_type") == "problem" else "P1"
            reminders.append({
                "decision_id": dec["id"], "title": dec.get("title", ""),
                "decision_type": dec.get("decision_type", ""), "life_area": dec.get("life_area", ""),
                "priority_label": priority_label,
                "implementation_review_date": dec.get("implementation_review_date"),
                "status": dec.get("status", ""), "created_at": dec.get("created_at"),
            })
    return reminders


@router.get("/journal/linkable-items", response_model=dict)
async def get_linkable_items(user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    user_id = user["user_id"]

    async def _fetch(coll, title_field: str, extra_field: str | None = None):
        """Resilient per-collection fetch — a bad doc in one module must never
        wipe out the whole response (this was making My Dezider show empty)."""
        try:
            projection = {"_id": 0, "id": 1, title_field: 1}
            if extra_field:
                projection[extra_field] = 1
            docs = await coll.find({"user_id": user_id}, projection).sort("created_at", -1).to_list(50)
            out = []
            for d in docs:
                if not d.get("id"):
                    continue
                out.append({
                    "id": d["id"],
                    "title": d.get(title_field) or "(untitled)",
                    "extra": (d.get(extra_field) or "") if extra_field else "",
                })
            return out
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("linkable-items fetch failed for %s: %s", title_field, e)
            return []

    return {
        "decision": await _fetch(db.decisions, "title", "decision_type"),
        "pros_cons": await _fetch(db.pros_cons, "title", "decision_type"),
        "swot": await _fetch(db.swot_analyses, "title", "decision_type"),
        "solution_finder": await _fetch(db.solution_finders, "title"),
        "gem": await _fetch(db.gem_goals, "title", "goal_type"),
        "ctt": await _fetch(db.ctt_tasks, "task", "status"),
        "lifestyle": await _fetch(db.lifestyle_routines, "name", "frequency"),
    }


@router.get("/journal/{entry_id}")
async def get_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    entry = await db.journal.find_one({"id": entry_id, "user_id": user["user_id"]}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.put("/journal/{entry_id}")
async def update_journal_entry(entry_id: str, update_data: JournalEntryUpdate, user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    existing = await db.journal.find_one({"id": entry_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.journal.update_one({"id": entry_id}, {"$set": update_dict})
    return {"message": "Entry updated successfully"}


@router.delete("/journal/{entry_id}")
async def delete_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    await verify_journal_access(user)
    result = await db.journal.delete_one({"id": entry_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted successfully"}
