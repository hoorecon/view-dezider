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
    # SWOT-converted Decisions (source_module == "swot") should be grouped
    # under the SWOT filter in the Solution Box, not under Decider — even
    # though the data now lives in db.decisions and the UI is /prr/[id].
    # User UX feedback: keep it under the SWOT bucket end-to-end.
    is_swot_sourced = (doc.get("source_module") == "swot")
    sb_type = "swot" if is_swot_sourced else "decider"

    return {
        "id": doc.get("id"),
        "type": sb_type,
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
    # Unified Pros & Cons — the simple two-column flavour was retired
    # (user request: keep only the 8-Step wizard, rename to "Pros & Cons").
    # All items — including legacy `pros`/`cons`-only docs — now open in
    # the 8-Step wizard which handles empty state gracefully.
    route = f"/tools/pros-cons-wizard?id={doc.get('id')}&module=pros-cons"
    return {
        "id": doc.get("id"),
        "type": "pros_cons",
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

    # --- Decider (excluding SWOT-converted) + SWOT-converted under swot filter ---
    # SWOT-converted decisions live in db.decisions but report type="swot"
    # via _norm_decider. We split the iteration so each chip shows the right
    # items: "decider" filter excludes SWOT-converted, "swot" filter pulls
    # them in alongside db.swot rows.
    decider_iter_needed = type_filter in (None, "decider")
    swot_via_decisions_needed = type_filter in (None, "swot")
    if decider_iter_needed or swot_via_decisions_needed:
        # Mongo filter — when ONLY swot-from-decisions is wanted, narrow at
        # the DB layer; otherwise pull all and filter in Python (we still
        # need to bucket each doc by its source_module).
        mongo_q: Dict[str, Any] = {"user_id": uid}
        if not decider_iter_needed and swot_via_decisions_needed:
            mongo_q["source_module"] = "swot"
        cursor = db.decisions.find(mongo_q, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_decider(doc)
            # Skip docs that don't match the requested chip
            if type_filter == "decider" and item["type"] != "decider":
                continue
            if type_filter == "swot" and item["type"] != "swot":
                continue
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if status_filter and item["status"] != status_filter:
                continue
            results.append(item)

    # --- Pros & Cons (unified — 8-step is the only flavour now) ---
    # Legacy "pros_cons_8step" filter still accepted so older URLs / clients
    # continue to work; all items now report type="pros_cons".
    if type_filter in (None, "pros_cons", "pros_cons_8step"):
        cursor = db.pros_cons.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_pros_cons(doc)
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
    by_type: Dict[str, int] = {"decider": 0, "pros_cons": 0, "swot": 0}
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
