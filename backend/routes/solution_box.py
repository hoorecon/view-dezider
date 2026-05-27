"""
Solution Box — Unified Aggregator
=================================

Single endpoint that consolidates the user's flows across:
- Decider (db.decisions)
- Pros & Cons + Pros & Cons 8-Step (db.pros_cons — same collection, distinguished
  by current_step / pros_cons_items presence)
- SWOT (db.swot)

Returns a normalized list so the Solution Box tab can render everything
with consistent type chips, status pills, life-area badges and deep-link
routes — without changing the underlying collections.

This module is purely *additive*; existing list endpoints for each module
remain unchanged.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query

from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/solution-box", tags=["Solution Box"])


# ---------- helpers ----------

def _iso(v: Any) -> Optional[str]:
    if not v:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()
    return str(v)


def _decider_status(doc: Dict[str, Any]) -> str:
    """Pass-through with safe default for legacy rows."""
    s = (doc.get("status") or "").lower()
    if s in ("draft", "in_progress", "completed"):
        return s
    # Heuristic for very old rows that omit status
    if doc.get("chosen_option_id"):
        return "completed"
    if doc.get("options"):
        return "in_progress"
    return "draft"


def _pros_cons_flavor(doc: Dict[str, Any]) -> str:
    """
    Distinguish the lightweight Pros & Cons mode from the 8-Step framework.
    Heuristic: if `options` array is populated (8-step seeds 0 options initially,
    user adds them in Step 2) OR `current_step > 1`, treat as 8-step.
    Otherwise treat as normal (legacy `pros`/`cons` flat lists).
    """
    cur_step = int(doc.get("current_step") or 1)
    has_options = bool(doc.get("options"))
    has_factors = bool(doc.get("factors"))
    if cur_step > 1 or has_options or has_factors:
        return "pros_cons_8step"
    return "pros_cons"


def _pros_cons_status(doc: Dict[str, Any]) -> str:
    if doc.get("converted_decision_id"):
        return "completed"
    cur_step = int(doc.get("current_step") or 1)
    has_any_content = bool(
        doc.get("options") or doc.get("factors")
        or doc.get("pros") or doc.get("cons")
    )
    if cur_step >= 8:
        return "completed"
    if cur_step > 1 or has_any_content:
        return "in_progress"
    return "draft"


def _swot_status(doc: Dict[str, Any]) -> str:
    if doc.get("converted_decision_id"):
        return "completed"
    cur_step = int(doc.get("current_step") or 1)
    quadrants = doc.get("quadrants") or {}
    has_any = any(
        bool(quadrants.get(k))
        for k in ("strengths", "weaknesses", "opportunities", "threats")
    )
    has_any = has_any or bool(doc.get("options") or doc.get("factors"))
    if cur_step >= 8:
        return "completed"
    if cur_step > 1 or has_any:
        return "in_progress"
    return "draft"


def _norm_decider(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "type": "decider",
        "title": doc.get("title") or "Untitled decision",
        "context": doc.get("context") or "",
        "life_area": doc.get("folder") or doc.get("life_area"),
        "status": _decider_status(doc),
        "current_step": None,
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": f"/prr/{doc.get('id')}",
        "linked_from_decision_id": doc.get("linked_from_decision_id"),
        "options_count": len(doc.get("options") or []),
    }


def _norm_pros_cons(doc: Dict[str, Any]) -> Dict[str, Any]:
    flavor = _pros_cons_flavor(doc)
    if flavor == "pros_cons_8step":
        route = f"/tools/pros-cons-wizard?id={doc.get('id')}&module=pros-cons"
    else:
        route = f"/tools/pros-cons?id={doc.get('id')}"
    return {
        "id": doc.get("id"),
        "type": flavor,  # "pros_cons" | "pros_cons_8step"
        "title": doc.get("title") or "Untitled analysis",
        "context": doc.get("context") or "",
        "life_area": doc.get("life_area"),
        "status": _pros_cons_status(doc),
        "current_step": int(doc.get("current_step") or 1),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": route,
        "linked_from_decision_id": doc.get("converted_decision_id"),
        "options_count": len(doc.get("options") or []),
    }


def _norm_swot(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "type": "swot",
        "title": doc.get("title") or "Untitled SWOT",
        "context": doc.get("context") or "",
        "life_area": doc.get("life_area"),
        "status": _swot_status(doc),
        "current_step": int(doc.get("current_step") or 1),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": f"/tools/swot?id={doc.get('id')}",
        "linked_from_decision_id": doc.get("converted_decision_id"),
        "options_count": len(doc.get("options") or []),
    }


# ---------- routes ----------

@router.get("")
async def list_solution_box(
    user: dict = Depends(get_current_user),
    type: Optional[str] = Query(
        None,
        description="Filter by flow type: decider | pros_cons | pros_cons_8step | swot. Omit for all.",
    ),
    life_area: Optional[str] = Query(None, description="Filter by life area id"),
    status: Optional[str] = Query(None, description="Filter by status: draft | in_progress | completed"),
):
    """Unified list of all flows owned by the user, sorted by updated_at desc."""
    uid = user["user_id"]
    type_filter = (type or "").strip().lower() or None
    life_area_filter = (life_area or "").strip() or None
    status_filter = (status or "").strip().lower() or None

    results: List[Dict[str, Any]] = []

    # --- Decider ---
    if type_filter in (None, "decider"):
        cursor = db.decisions.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_decider(doc)
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            results.append(item)

    # --- Pros & Cons (covers both normal + 8-step) ---
    if type_filter in (None, "pros_cons", "pros_cons_8step"):
        cursor = db.pros_cons.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_pros_cons(doc)
            if type_filter and item["type"] != type_filter:
                continue
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            results.append(item)

    # --- SWOT ---
    if type_filter in (None, "swot"):
        cursor = db.swot.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_swot(doc)
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            results.append(item)

    # Sort merged results by updated_at desc (None last)
    results.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return results


@router.get("/counts")
async def solution_box_counts(user: dict = Depends(get_current_user)):
    """Aggregate counts by type / life_area / status — for dashboard cards & filter badges."""
    uid = user["user_id"]
    by_type: Dict[str, int] = {"decider": 0, "pros_cons": 0, "pros_cons_8step": 0, "swot": 0}
    by_life_area: Dict[str, int] = {}
    by_status: Dict[str, int] = {"draft": 0, "in_progress": 0, "completed": 0}

    async def _bump(item: Dict[str, Any]):
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1
        if item.get("life_area"):
            by_life_area[item["life_area"]] = by_life_area.get(item["life_area"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    async for doc in db.decisions.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_decider(doc))
    async for doc in db.pros_cons.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_pros_cons(doc))
    async for doc in db.swot.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_swot(doc))

    total = sum(by_type.values())
    return {
        "total": total,
        "by_type": by_type,
        "by_life_area": by_life_area,
        "by_status": by_status,
    }
