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


def _intake_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Initial-intake info surfaced on list cards (For / Type / Sub-area / Scenario)."""
    return {
        "acting_as_context": doc.get("acting_as_context"),
        "decision_type": doc.get("decision_type"),
        "sub_area_name": doc.get("sub_area_name") or doc.get("sub_area"),
        "scenario_title": doc.get("scenario_title") or doc.get("scenario"),
    }


# ---------- unified progress model ----------
# One consistent rule across ALL tools so the same amount of work reads the
# same way everywhere (fixes the old per-tool inconsistency):
#   • Draft        – created but real work not started (factor-tools: no factors
#                    defined yet; quick tools: only the opening field filled)
#   • In Progress  – actively being worked on, shown with a % = steps done ÷ total
#                    steps, split into <35% / 35–70% / >70%&<100%
#   • Completed    – BOTH the final step reached AND 100% of the option×factor
#                    assessment matrix filled (quick tools with no matrix complete
#                    when their final field is recorded)
#
# Bands: draft | ip_low (<35) | ip_mid (35–70) | ip_high (>70,<100) | completed
# `status` stays the coarse draft | in_progress | completed for back-compat.

def _band(pct: int, is_draft: bool, is_completed: bool):
    """Return (progress_pct, progress_band, status_coarse)."""
    if is_completed:
        return 100, "completed", "completed"
    if is_draft:
        return max(0, min(int(pct), 34)), "draft", "draft"
    pct = max(1, min(99, int(pct)))
    band = "ip_low" if pct < 35 else ("ip_mid" if pct <= 70 else "ip_high")
    return pct, band, "in_progress"


def _decider_assess_complete(doc: Dict[str, Any]) -> bool:
    factors = doc.get("factors") or []
    options = doc.get("options") or []
    if not factors or not options:
        return False
    fids = {f.get("id") for f in factors}
    for o in options:
        filled = {a.get("factor_id") for a in (o.get("assessments") or [])
                  if a.get("percentage") is not None}
        if not fids.issubset(filled):
            return False
    return True


def _proscons_assess_complete(doc: Dict[str, Any]) -> bool:
    factors = doc.get("factors") or []
    options = doc.get("options") or []
    if not factors or not options:
        return False
    a = doc.get("assessments") or {}
    fids = [f.get("id") for f in factors]
    for o in options:
        cell = a.get(o.get("id")) or {}
        if not isinstance(cell, dict):
            return False
        for fid in fids:
            v = cell.get(fid)
            if v is None:
                return False
            if isinstance(v, dict) and v.get("assessment_pct") is None and v.get("actual_value") in (None, ""):
                return False
    return True


def _progress_decider(doc: Dict[str, Any]) -> Dict[str, Any]:
    factors = doc.get("factors") or []
    options = doc.get("options") or []
    title = bool((doc.get("title") or "").strip())
    classified = any(f.get("category") for f in factors)
    rated = any(f.get("rating") is not None for f in factors)
    assess = _decider_assess_complete(doc)
    worth = any(o.get("worth_percentage") is not None for o in options)
    chosen = bool(doc.get("chosen_option_id"))
    milestones = [title, bool(factors), classified, rated, bool(options), assess, worth, chosen]
    steps_done = sum(1 for m in milestones if m)
    final_reached = chosen or (doc.get("status") == "completed")
    completed = final_reached and assess
    pct = round(steps_done / 8 * 100)
    if final_reached and not assess:
        pct = min(pct, 95)
    p, band, status = _band(pct, is_draft=not factors and not completed, is_completed=completed)
    return {"total_steps": 8, "steps_done": steps_done, "progress_pct": p,
            "progress_band": band, "status": status}


def _progress_stepwise(doc: Dict[str, Any], assess_complete) -> Dict[str, Any]:
    """8-step wizard tools that track `current_step` (Pros & Cons, SWOT)."""
    cur = int(doc.get("current_step") or 1)
    factors = doc.get("factors") or []
    converted = bool(doc.get("converted_decision_id"))
    assess = assess_complete(doc)
    final_reached = converted or cur >= 8
    completed = final_reached and assess
    steps_done = min(cur, 8)
    pct = round(steps_done / 8 * 100)
    if final_reached and not assess:
        pct = min(pct, 95)
    p, band, status = _band(pct, is_draft=not factors and not completed, is_completed=completed)
    return {"total_steps": 8, "steps_done": steps_done, "progress_pct": p,
            "progress_band": band, "status": status}


def _progress_test123(doc: Dict[str, Any]) -> Dict[str, Any]:
    situation = bool((doc.get("situation") or "").strip())
    worst = bool((doc.get("worst_case") or "").strip())
    needs = bool(doc.get("all_needs") or doc.get("important_needs"))
    final = bool((doc.get("final_decision") or "").strip())
    steps_done = sum(1 for m in (situation, worst, needs) if m)
    completed = final  # no assessment matrix → final field == completed
    is_draft = not (worst or needs or final)
    pct = round((3 if completed else steps_done) / 3 * 100)
    p, band, status = _band(pct, is_draft=is_draft and not completed, is_completed=completed)
    return {"total_steps": 3, "steps_done": 3 if completed else steps_done,
            "progress_pct": p, "progress_band": band, "status": status}


def _progress_solution_finder(doc: Dict[str, Any]) -> Dict[str, Any]:
    goal = bool((doc.get("smart_goal") or "").strip())
    concerns = bool(doc.get("q1_all_concerns"))
    sols = bool(doc.get("q3_solutions"))
    miles = bool(doc.get("milestones"))
    acts = bool(doc.get("action_items"))
    steps_done = sum(1 for m in (goal, concerns, sols, miles, acts) if m)
    completed = acts
    is_draft = goal and not (concerns or sols or miles or acts)
    if not goal:
        is_draft = True
    pct = round(steps_done / 5 * 100)
    p, band, status = _band(pct, is_draft=is_draft and not completed, is_completed=completed)
    return {"total_steps": 5, "steps_done": steps_done, "progress_pct": p,
            "progress_band": band, "status": status}


def _norm_solution_finder(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a `solution_finders` doc into the Solution Box shape."""
    goal = (doc.get("smart_goal") or "").strip()
    title = (goal[:60] + ("…" if len(goal) > 60 else "")) if goal else "Solution Finder"
    item = {
        "id": doc.get("entry_id"),
        "type": "solution_finder",
        "title": title,
        "context": goal,
        "life_area": doc.get("area_of_life"),
        "current_step": None,
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": f"/tools/solution-finder?id={doc.get('entry_id')}",
        "linked_from_decision_id": None,
        "options_count": len(doc.get("action_items") or []),
    }
    item.update(_progress_solution_finder(doc))
    item.update(_intake_fields(doc))
    return item


def _norm_test123(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a `test123_sessions` doc into the Solution Box shape."""
    situation = (doc.get("situation") or "").strip()
    title = (situation[:60] + ("…" if len(situation) > 60 else "")) if situation else "Quick Decision (Test123)"
    item = {
        "id": doc.get("id"),
        "type": "test123",
        "title": title,
        "context": situation,
        "life_area": doc.get("life_area"),
        "current_step": int(doc.get("current_step") or 1),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": f"/test123/{doc.get('id')}",
        "linked_from_decision_id": None,
        "options_count": len(doc.get("all_needs") or []),
    }
    item.update(_progress_test123(doc))
    return item



def _norm_decider(doc: Dict[str, Any]) -> Dict[str, Any]:
    # SWOT-converted Decisions (source_module == "swot") should be grouped
    # under the SWOT filter in the Solution Box, not under Decider — even
    # though the data now lives in db.decisions and the UI is /prr/[id].
    # User UX feedback: keep it under the SWOT bucket end-to-end.
    is_swot_sourced = (doc.get("source_module") == "swot")
    sb_type = "swot" if is_swot_sourced else "decider"

    item = {
        "id": doc.get("id"),
        "type": sb_type,
        # Collection hint so the Solution Box delete path picks the right
        # endpoint: SWOT-converted decisions live in db.decisions even
        # though they report type="swot". Without this, DELETE /swot/<id>
        # would 404 and the UI would show "Delete Failed".
        "_collection": "decisions",
        "title": doc.get("title") or "Untitled decision",
        "context": doc.get("context") or "",
        "life_area": doc.get("folder") or doc.get("life_area"),
        "current_step": None,
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        # SWOT-converted Deciders must open on Step 2 so the user can rename
        # the AI-prefilled factors via the inline pencil edit. Plain Deciders
        # open at their default landing step (the wizard auto-jumps).
        "route": (
            f"/prr/{doc.get('id')}?step=2" if is_swot_sourced
            else f"/prr/{doc.get('id')}"
        ),
        "linked_from_decision_id": doc.get("linked_from_decision_id"),
        "options_count": len(doc.get("options") or []),
    }
    item.update(_progress_decider(doc))
    return item


def _norm_pros_cons(doc: Dict[str, Any]) -> Dict[str, Any]:
    # Unified Pros & Cons — the simple two-column flavour was retired
    # (user request: keep only the 8-Step wizard, rename to "Pros & Cons").
    # All items — including legacy `pros`/`cons`-only docs — now open in
    # the 8-Step wizard which handles empty state gracefully.
    route = f"/tools/pros-cons-wizard?id={doc.get('id')}&module=pros-cons"
    item = {
        "id": doc.get("id"),
        "type": "pros_cons",
        "title": doc.get("title") or "Untitled analysis",
        "context": doc.get("context") or "",
        "life_area": doc.get("life_area"),
        "current_step": int(doc.get("current_step") or 1),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": route,
        "linked_from_decision_id": doc.get("converted_decision_id"),
        "options_count": len(doc.get("options") or []),
    }
    item.update(_progress_stepwise(doc, _proscons_assess_complete))
    return item


def _norm_swot(doc: Dict[str, Any]) -> Dict[str, Any]:
    item = {
        "id": doc.get("id"),
        "type": "swot",
        "title": doc.get("title") or "Untitled SWOT",
        "context": doc.get("context") or "",
        "life_area": doc.get("life_area"),
        "current_step": int(doc.get("current_step") or 1),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at") or doc.get("created_at")),
        "route": f"/tools/swot?id={doc.get('id')}",
        "linked_from_decision_id": doc.get("converted_decision_id"),
        "options_count": len(doc.get("options") or []),
    }
    item.update(_progress_stepwise(doc, _proscons_assess_complete))
    return item


# ---------- routes ----------

def _match_status(item: Dict[str, Any], f: Optional[str]) -> bool:
    """Accepts coarse status (draft|in_progress|completed) OR a fine band
    (ip_low|ip_mid|ip_high). `in_progress` matches any in-progress band."""
    if not f:
        return True
    return item.get("status") == f or item.get("progress_band") == f


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
            item.update(_intake_fields(doc))
            # Skip docs that don't match the requested chip
            if type_filter == "decider" and item["type"] != "decider":
                continue
            if type_filter == "swot" and item["type"] != "swot":
                continue
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if not _match_status(item, status_filter):
                continue
            results.append(item)

    # --- Pros & Cons (unified — 8-step is the only flavour now) ---
    # Legacy "pros_cons_8step" filter still accepted so older URLs / clients
    # continue to work; all items now report type="pros_cons".
    if type_filter in (None, "pros_cons", "pros_cons_8step"):
        cursor = db.pros_cons.find({"user_id": uid, "contribution_clone": {"$exists": False}}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_pros_cons(doc)
            item.update(_intake_fields(doc))
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if not _match_status(item, status_filter):
                continue
            results.append(item)

    # --- SWOT ---
    if type_filter in (None, "swot"):
        cursor = db.swot.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_swot(doc)
            item.update(_intake_fields(doc))
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if not _match_status(item, status_filter):
                continue
            results.append(item)

    # --- Test123 (3-step quick-decision) ---
    if type_filter in (None, "test123"):
        cursor = db.test123_sessions.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_test123(doc)
            item.update(_intake_fields(doc))
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if not _match_status(item, status_filter):
                continue
            results.append(item)

    # --- Solution Finder (5-step worksheet) ---
    if type_filter in (None, "solution_finder"):
        cursor = db.solution_finders.find({"user_id": uid, "contribution_clone": {"$exists": False}}, {"_id": 0}).sort("updated_at", -1)
        async for doc in cursor:
            item = _norm_solution_finder(doc)
            if life_area_filter and item["life_area"] != life_area_filter:
                continue
            if not _match_status(item, status_filter):
                continue
            results.append(item)

    # Sort merged results by updated_at desc (None last)
    results.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return results


@router.get("/counts")
async def solution_box_counts(user: dict = Depends(get_current_user)):
    """Aggregate counts by type / life_area / status — for dashboard cards & filter badges."""
    uid = user["user_id"]
    by_type: Dict[str, int] = {"decider": 0, "pros_cons": 0, "swot": 0, "test123": 0, "solution_finder": 0}
    by_life_area: Dict[str, int] = {}
    by_status: Dict[str, int] = {"draft": 0, "in_progress": 0, "completed": 0}
    by_band: Dict[str, int] = {"draft": 0, "ip_low": 0, "ip_mid": 0, "ip_high": 0, "completed": 0}

    async def _bump(item: Dict[str, Any]):
        by_type[item["type"]] = by_type.get(item["type"], 0) + 1
        if item.get("life_area"):
            by_life_area[item["life_area"]] = by_life_area.get(item["life_area"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        b = item.get("progress_band")
        if b:
            by_band[b] = by_band.get(b, 0) + 1

    async for doc in db.decisions.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_decider(doc))
    async for doc in db.pros_cons.find({"user_id": uid, "contribution_clone": {"$exists": False}}, {"_id": 0}):
        await _bump(_norm_pros_cons(doc))
    async for doc in db.swot.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_swot(doc))
    async for doc in db.test123_sessions.find({"user_id": uid}, {"_id": 0}):
        await _bump(_norm_test123(doc))
    async for doc in db.solution_finders.find({"user_id": uid, "contribution_clone": {"$exists": False}}, {"_id": 0}):
        await _bump(_norm_solution_finder(doc))

    total = sum(by_type.values())
    return {
        "total": total,
        "by_type": by_type,
        "by_life_area": by_life_area,
        "by_status": by_status,
    }
