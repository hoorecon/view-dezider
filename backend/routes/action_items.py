"""
UNIVERSAL ACTION ITEM MODEL
===========================
A single, source-agnostic store for ALL action items captured across
modules so users can track them centrally:

   one-time / on-demand items → ported into CTT  (ctt_tasks)
   recurring / routine items  → ported into LifeStyle (lifestyle_routines)

Sources currently emitting action items:
   MYDEZIDER_MPPS  – decisions.mpps_improvements[].action_items[]
   PROS_CONS       – per option (added in this iteration)
   SWOT            – per chosen factor / option
   PNA             – auto-link via GEM (existing)
   CONFLICT_BREAKER, CLD, GEM, GOAL_SETTER, AALA, MANUAL

Schema (collection: `action_items`):
   action_id (uuid), user_id, org_id
   source_module, source_id, source_label, source_subref?   # e.g. option_id|factor_id
   title  (What),  description?
   who           – assignee_name (display)
   assignee_contact_id?, assignee_email?, assignee_mobile?
   by_when       – YYYY-MM-DD
   recurrence_type   – 'one_time'|'recurring'
   recurrence_frequency? – 'daily|weekly|biweekly|monthly|quarterly|yearly'
   recurrence_days?      – ['MON','WED','FRI']
   recurrence_time?      – 'HH:MM'
   recurrence_end_date?
   priority      – 'low|medium|high|urgent'
   status        – 'pending|in_progress|done|blocked|cancelled'
   progress_pct  – 0..100
   life_area?    – one of the 10 PNA life areas
   notes?
   ported_to?    – 'CTT'|'LIFESTYLE'
   ported_ref_id?, ported_at?
   created_at, updated_at
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ───── Constants ──────────────────────────────────────────────────────────

SOURCE_MODULES = {
    "MYDEZIDER_MPPS", "PROS_CONS", "SWOT", "PNA",
    "CONFLICT_BREAKER", "CLD", "GEM", "GOAL_SETTER", "AALA", "MANUAL",
    "AIM",
    # Iter 129 — universal sink hooks
    "SOLUTION_FINDER", "INSTANT_DEZIDER", "ATEX",
}
RECURRENCE_TYPES = {"one_time", "recurring"}
FREQUENCIES = {"daily", "weekly", "biweekly", "monthly", "quarterly", "yearly", "custom"}
PRIORITIES = {"low", "medium", "high", "urgent"}
from core.action_status import (
    CANONICAL_STATUSES, normalize_status, progress_for,
)
STATUSES = set(CANONICAL_STATUSES)
PORT_TARGETS = {"CTT", "LIFESTYLE"}


async def _sync_ported_status(ai_doc: Dict[str, Any]) -> None:
    """Propagate an action-item's status to every downstream record it feeds:
      • the ActionItemEditor port path  (action_item.ported_to / ported_ref_id)
      • the Solution-Finder / Matrix push path (records carrying linked_action_id)
    One-way here; the reverse hooks live in ctt_gem / lifestyle."""
    st = normalize_status(ai_doc.get("status"))
    now = _now_iso()
    action_id = ai_doc.get("action_id")
    pt = (ai_doc.get("ported_to") or "").upper()
    ref = ai_doc.get("ported_ref_id")
    if pt == "CTT" and ref:
        await db.ctt_tasks.update_one(
            {"task_id": ref}, {"$set": {"current_status": st, "updated_at": now}})
    elif pt == "LIFESTYLE" and ref:
        await db.lifestyle_routines.update_one(
            {"routine_id": ref},
            {"$set": {"status": st, "is_active": st != "cancelled", "updated_at": now}})
    if action_id:
        await db.ctt_tasks.update_many(
            {"linked_action_id": action_id},
            {"$set": {"current_status": st, "status": st, "updated_at": now}})
        await db.lifestyle_routines.update_many(
            {"linked_action_id": action_id},
            {"$set": {"status": st, "is_active": st != "cancelled", "updated_at": now}})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise(body: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Pull/clean fields from caller input. Strict on enums."""
    src = (body.get("source_module") or "MANUAL").upper()
    if src not in SOURCE_MODULES:
        raise HTTPException(400, f"source_module must be one of {sorted(SOURCE_MODULES)}")
    rec_type = (body.get("recurrence_type") or "one_time").lower()
    if rec_type not in RECURRENCE_TYPES:
        raise HTTPException(400, f"recurrence_type must be one of {sorted(RECURRENCE_TYPES)}")
    pri = (body.get("priority") or "medium").lower()
    if pri not in PRIORITIES:
        raise HTTPException(400, f"priority must be one of {sorted(PRIORITIES)}")
    status = normalize_status(body.get("status"))
    if status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")
    freq = body.get("recurrence_frequency")
    if rec_type == "recurring":
        if not freq:
            freq = "weekly"
        if freq not in FREQUENCIES:
            raise HTTPException(400, f"recurrence_frequency must be one of {sorted(FREQUENCIES)}")
    else:
        freq = None

    progress = int(body.get("progress_pct") or 0)
    progress = max(0, min(100, progress))
    # WIP / pending / done states carry a canonical %, which wins over any
    # stale client-supplied progress so the two never drift apart.
    if status in ("pending", "wip_25", "wip_50", "wip_75", "done"):
        progress = progress_for(status)

    return {
        "user_id": user.get("user_id"),
        "org_id": user.get("org_id"),
        "source_module": src,
        "source_id": body.get("source_id"),
        "source_label": body.get("source_label"),
        "source_subref": body.get("source_subref"),
        "title": (body.get("title") or "").strip(),
        "description": body.get("description") or "",
        "who": body.get("who") or "",
        "assignee_contact_id": body.get("assignee_contact_id"),
        "assignee_email": body.get("assignee_email") or "",
        "assignee_mobile": body.get("assignee_mobile") or "",
        "by_when": body.get("by_when") or None,
        "recurrence_type": rec_type,
        "recurrence_frequency": freq,
        "recurrence_days": body.get("recurrence_days") or [],
        "recurrence_time": body.get("recurrence_time") or None,
        "recurrence_end_date": body.get("recurrence_end_date") or None,
        "priority": pri,
        "status": status,
        "progress_pct": progress,
        "life_area": body.get("life_area") or None,
        "notes": body.get("notes") or "",
    }


# ───── CRUD ───────────────────────────────────────────────────────────────

@router.post("/action-items")
async def create_action_item(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    norm = _normalise(body, user)
    if not norm["title"]:
        raise HTTPException(400, "title (What) is required")
    doc = {
        "action_id": str(uuid.uuid4()),
        **norm,
        "ported_to": None,
        "ported_ref_id": None,
        "ported_at": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.action_items.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/action-items")
async def list_action_items(request: Request, user: dict = Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user.get("user_id")}
    p = dict(request.query_params)
    for fld in ("source_module", "source_id", "source_subref", "status",
                "priority", "ported_to", "life_area", "recurrence_type"):
        if p.get(fld):
            q[fld] = p[fld]
    if p.get("not_ported"):
        q["ported_to"] = None
    docs = await db.action_items.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return docs


@router.get("/action-items/{action_id}")
async def get_action_item(action_id: str, user: dict = Depends(get_current_user)):
    doc = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "action item not found")
    return doc


@router.put("/action-items/{action_id}")
async def update_action_item(action_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    existing = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}
    )
    if not existing:
        raise HTTPException(404, "action item not found")

    # Allow partial — only validate supplied enum fields
    merged = {**existing, **body}
    # Module-sourced items: the action NAME is owned by the source module and
    # must be edited there, not from the Action Center.
    if (existing.get("source_module") or "MANUAL").upper() != "MANUAL":
        merged["title"] = existing.get("title")
    norm = _normalise(merged, user)
    norm["updated_at"] = _now_iso()
    await db.action_items.update_one({"action_id": action_id}, {"$set": norm})
    out = await db.action_items.find_one({"action_id": action_id}, {"_id": 0})
    # Bi-directional status sync: push status onto the ported CTT/Lifestyle record.
    if out:
        await _sync_ported_status(out)
    return out


@router.delete("/action-items/{action_id}")
async def delete_action_item(action_id: str, request: Request, user: dict = Depends(get_current_user)):
    existing = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}
    )
    if not existing:
        raise HTTPException(404, "action item not found")
    hard = (request.query_params.get("hard") or "").lower() in ("1", "true", "yes")
    is_manual = (existing.get("source_module") or "MANUAL").upper() == "MANUAL"
    # Only manually-created, un-ported items may be hard-deleted from here.
    if hard and is_manual and not existing.get("ported_to"):
        await db.action_items.delete_one({"action_id": action_id})
        return {"deleted": True, "action_id": action_id}
    # Otherwise soft-cancel.
    await db.action_items.update_one(
        {"action_id": action_id},
        {"$set": {"status": "cancelled", "updated_at": _now_iso()}},
    )
    return {"status": "cancelled", "action_id": action_id}


# ───── PORTING to CTT / LifeStyle ─────────────────────────────────────────

def _ctt_doc_from_action(ai: Dict[str, Any], user: dict) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "task_id": str(uuid.uuid4()),
        "user_id": user.get("user_id"),
        "org_id": user.get("org_id"),
        "task": ai.get("title"),
        "sub_task": "",
        "task_logged_by": user.get("name") or "",
        "task_owners": [ai.get("who")] if ai.get("who") else [],
        "deadline": ai.get("by_when"),
        "internal_dependency": "",
        "external_dependency": "",
        "internal_help": "",
        "external_help": "",
        "task_duration": "",
        "from_time": None,
        "to_time": None,
        "life_area": ai.get("life_area") or "",
        "decision_type": ai.get("source_module"),
        "goal_id": None,
        "is_routine": False,
        "frequency": None,
        "day_status": {},
        "source_type": "ACTION_ITEM",
        "source_id": ai.get("action_id"),
        "linked_freedoms": [],
        "linked_aala_cells": [],
        "priority": ai.get("priority"),
        "status": ai.get("status"),
        "notes": ai.get("notes"),
        "created_at": now,
        "updated_at": now,
    }


def _routine_doc_from_action(ai: Dict[str, Any], user: dict) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "routine_id": str(uuid.uuid4()),
        "user_id": user.get("user_id"),
        "org_id": user.get("org_id"),
        "name": ai.get("title"),
        "description": ai.get("description") or ai.get("notes") or "",
        "life_area": ai.get("life_area") or "",
        "frequency": ai.get("recurrence_frequency") or "daily",
        "recurrence_days": ai.get("recurrence_days") or [],
        "time_slot": ai.get("recurrence_time"),
        "end_date": ai.get("recurrence_end_date"),
        "owner": ai.get("who"),
        "priority": ai.get("priority"),
        "status": ai.get("status"),
        "source_type": "ACTION_ITEM",
        "source_id": ai.get("action_id"),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }


@router.post("/action-items/{action_id}/port-to-ctt")
async def port_to_ctt(action_id: str, user: dict = Depends(get_current_user)):
    ai = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}, {"_id": 0}
    )
    if not ai:
        raise HTTPException(404, "action item not found")
    if ai.get("ported_to"):
        raise HTTPException(409, f"Already ported to {ai['ported_to']} (ref {ai.get('ported_ref_id')})")

    task = _ctt_doc_from_action(ai, user)
    await db.ctt_tasks.insert_one(task)
    await db.action_items.update_one(
        {"action_id": action_id},
        {"$set": {
            "ported_to": "CTT",
            "ported_ref_id": task["task_id"],
            "ported_at": _now_iso(),
            "updated_at": _now_iso(),
        }},
    )
    out = await db.action_items.find_one({"action_id": action_id}, {"_id": 0})
    task.pop("_id", None)
    return {"action_item": out, "ctt_task": task}


@router.post("/action-items/{action_id}/port-to-lifestyle")
async def port_to_lifestyle(action_id: str, user: dict = Depends(get_current_user)):
    ai = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}, {"_id": 0}
    )
    if not ai:
        raise HTTPException(404, "action item not found")
    if ai.get("ported_to"):
        raise HTTPException(409, f"Already ported to {ai['ported_to']} (ref {ai.get('ported_ref_id')})")
    # Heuristic: if user calls this on a one_time item, auto-upgrade it to recurring.
    if ai.get("recurrence_type") != "recurring":
        await db.action_items.update_one(
            {"action_id": action_id},
            {"$set": {"recurrence_type": "recurring",
                      "recurrence_frequency": ai.get("recurrence_frequency") or "daily"}},
        )
        ai["recurrence_type"] = "recurring"
        ai["recurrence_frequency"] = ai.get("recurrence_frequency") or "daily"

    routine = _routine_doc_from_action(ai, user)
    await db.lifestyle_routines.insert_one(routine)
    await db.action_items.update_one(
        {"action_id": action_id},
        {"$set": {
            "ported_to": "LIFESTYLE",
            "ported_ref_id": routine["routine_id"],
            "ported_at": _now_iso(),
            "updated_at": _now_iso(),
        }},
    )
    out = await db.action_items.find_one({"action_id": action_id}, {"_id": 0})
    routine.pop("_id", None)
    return {"action_item": out, "lifestyle_routine": routine}


@router.post("/action-items/{action_id}/unport")
async def unport_action(action_id: str, user: dict = Depends(get_current_user)):
    """Detach the CTT/Lifestyle link (does not delete the downstream record)."""
    ai = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}
    )
    if not ai:
        raise HTTPException(404, "action item not found")
    await db.action_items.update_one(
        {"action_id": action_id},
        {"$set": {"ported_to": None, "ported_ref_id": None, "ported_at": None, "updated_at": _now_iso()}},
    )
    return {"status": "unported", "action_id": action_id}


# ───── BULK INGEST from MPPS / Pros&Cons / SWOT ───────────────────────────

@router.post("/action-items/import-from-mpps/{decision_id}")
async def import_from_mpps(decision_id: str, user: dict = Depends(get_current_user)):
    """
    Pull the legacy MPPS action items (decisions.mpps_improvements[].action_items[])
    into the universal store. Idempotent — skips items already linked.
    """
    dec = await db.decisions.find_one(
        {"id": decision_id, "user_id": user.get("user_id")}
    )
    if not dec:
        raise HTTPException(404, "decision not found")
    label = f"My Dezider · MPPS · {dec.get('title','Untitled')}"
    life_area = dec.get("folder") or dec.get("life_area") or None
    factors = {f.get("id"): f for f in (dec.get("factors") or [])}

    def _num(v) -> str:
        try:
            fv = float(v)
            return str(int(fv)) if fv == int(fv) else str(fv)
        except Exception:
            return str(v)

    def _improve_delta(imp) -> Optional[float]:
        """Improvement gain %, preferring explicit delta_percentage else projected-original."""
        delta = imp.get("delta_percentage")
        if delta in (None, ""):
            orig = imp.get("original_percentage")
            proj = imp.get("projected_percentage")
            if orig is not None and proj is not None:
                try:
                    delta = float(proj) - float(orig)
                except Exception:
                    delta = None
        try:
            return float(delta) if delta not in (None, "") else None
        except Exception:
            return None

    def _fmt_delta(imp) -> str:
        d = _improve_delta(imp)
        if d in (None, 0):
            return ""
        return f"[{'+' if d >= 0 else ''}{_num(d)}%]"

    def _realistic_rating(imp):
        """Realistic rating = MPPS projected (realistic) % after improvement;
        falls back to a SWOT/Pros&Cons factor's realistic/std rating."""
        rating = imp.get("projected_percentage")
        if rating is None:
            f = factors.get(imp.get("factor_id")) or {}
            rating = f.get("realistic_rating")
            if rating is None:
                rating = f.get("std_rating")
            if rating is None:
                rating = f.get("rating")
        return rating

    def _fmt_title(imp, action_text) -> str:
        f = factors.get(imp.get("factor_id")) or {}
        fname = f.get("name") or "Factor"
        rating = _realistic_rating(imp)
        head = f"[{fname} - {_num(rating)}]" if rating is not None else f"[{fname}]"
        parts = [head, (action_text or "").strip()]
        dstr = _fmt_delta(imp)
        if dstr:
            parts.append(dstr)
        return " · ".join([p for p in parts if p])

    inserted: List[Dict[str, Any]] = []
    for imp in dec.get("mpps_improvements") or []:
        factor_id = imp.get("factor_id")
        action_list = imp.get("action_items") or []
        if not action_list:
            # Push every improvement even when no explicit action was typed.
            fname = (factors.get(factor_id) or {}).get("name") or "this factor"
            base = (imp.get("improvement_plan") or "").strip() or f"Improve {fname}"
            action_list = [{"task": base}]
        for ai in action_list:
            raw_task = (ai.get("task") or imp.get("improvement_plan") or "").strip()
            if not raw_task:
                continue
            mpps_key = f"{factor_id}|{raw_task}|{ai.get('deadline') or ''}"
            new_title = _fmt_title(imp, raw_task)
            # Idempotent on a stable key (survives title-format changes).
            existing = await db.action_items.find_one({
                "user_id": user.get("user_id"),
                "source_module": "MYDEZIDER_MPPS",
                "source_id": decision_id,
                "mpps_key": mpps_key,
            })
            if existing:
                # Self-heal: keep the visible title in sync with the latest format
                # (e.g. when the user revises the projected % / delta).
                if new_title and existing.get("title") != new_title:
                    await db.action_items.update_one(
                        {"action_id": existing["action_id"]},
                        {"$set": {"title": new_title, "updated_at": _now_iso()}},
                    )
                continue
            norm = _normalise({
                "source_module": "MYDEZIDER_MPPS",
                "source_id": decision_id,
                "source_label": label,
                "source_subref": factor_id,
                "title": new_title,
                "who": ai.get("assignee_name") or "",
                "assignee_email": ai.get("assignee_email") or "",
                "assignee_mobile": ai.get("assignee_mobile") or "",
                "by_when": ai.get("deadline"),
                "life_area": life_area,
            }, user)
            if not norm["title"]:
                continue
            doc = {
                "action_id": str(uuid.uuid4()),
                **norm,
                "is_mpps": True,
                "mpps_key": mpps_key,
                "ported_to": None, "ported_ref_id": None, "ported_at": None,
                "created_at": _now_iso(), "updated_at": _now_iso(),
            }
            await db.action_items.insert_one(doc)
            doc.pop("_id", None)
            inserted.append(doc)
    return {"imported_count": len(inserted), "imported": inserted}


@router.post("/action-items/import-from-pros-cons/{analysis_id}")
async def import_from_pros_cons(analysis_id: str, user: dict = Depends(get_current_user)):
    """
    Seed the Action Plan from the CHOSEN option's per-factor improvement deltas
    (Pros & Cons Step 8 "Improvement %"). Mirrors the My Dezider MPPS import.
    Only positive deltas (actionable improvements) are imported. Idempotent —
    skips items already linked (keyed on option|factor|delta).
    """
    doc = await db.pros_cons.find_one(
        {"id": analysis_id, "user_id": user.get("user_id")}
    )
    if not doc:
        raise HTTPException(404, "analysis not found")

    cfg = doc.get("config") or {}
    chosen = cfg.get("final_choice_option_id")
    if not chosen:
        return {"imported_count": 0, "imported": [], "reason": "no_chosen_option"}

    factors = {f.get("id"): f for f in (doc.get("factors") or [])}
    assessments = (doc.get("assessments") or {}).get(chosen) or {}
    label = f"Pros & Cons · {doc.get('title', 'Untitled')}"
    life_area = doc.get("life_area") or None

    def _num(v) -> str:
        try:
            fv = float(v)
            return str(int(fv)) if fv == int(fv) else str(fv)
        except Exception:
            return str(v)

    inserted: List[Dict[str, Any]] = []
    for factor_id, cell in (assessments or {}).items():
        if not isinstance(cell, dict):
            continue
        try:
            delta = float(cell.get("improvement_pct") or 0)
        except Exception:
            delta = 0.0
        if delta <= 0:
            # Only actionable improvements (positive deltas) become action items.
            continue
        f = factors.get(factor_id) or {}
        fname = f.get("name") or "this factor"
        try:
            base_assess = float(cell.get("assessment_pct") or 0)
        except Exception:
            base_assess = 0.0
        effective = max(0.0, min(100.0, base_assess + delta))  # projected post-improvement %
        note = (cell.get("notes") or "").strip()
        action_text = note or f"Improve {fname}"
        title = " · ".join([
            f"[{fname} - {_num(effective)}]",
            action_text,
            f"[+{_num(delta)}%]",
        ])
        pc_key = f"{chosen}|{factor_id}|{_num(delta)}"

        existing = await db.action_items.find_one({
            "user_id": user.get("user_id"),
            "source_module": "PROS_CONS",
            "source_id": analysis_id,
            "pc_key": pc_key,
        })
        if existing:
            # Self-heal the visible title if the format/values changed.
            if title and existing.get("title") != title:
                await db.action_items.update_one(
                    {"action_id": existing["action_id"]},
                    {"$set": {"title": title, "updated_at": _now_iso()}},
                )
            continue

        norm = _normalise({
            "source_module": "PROS_CONS",
            "source_id": analysis_id,
            "source_label": label,
            "source_subref": factor_id,
            "title": title,
            "life_area": life_area,
        }, user)
        if not norm["title"]:
            continue
        doc_ai = {
            "action_id": str(uuid.uuid4()),
            **norm,
            "is_mpps": False,
            "pc_key": pc_key,
            "ported_to": None, "ported_ref_id": None, "ported_at": None,
            "created_at": _now_iso(), "updated_at": _now_iso(),
        }
        await db.action_items.insert_one(doc_ai)
        doc_ai.pop("_id", None)
        inserted.append(doc_ai)

    return {"imported_count": len(inserted), "imported": inserted}



# ───── AIM (Emotional Gatekeeper) import ─────────────────────────────────

@router.post("/action-items/import-from-aim/{session_id}")
async def import_from_aim(session_id: str, user: dict = Depends(get_current_user)):
    """
    Pre-fill the Action Items Planner from an AIM (Addictions/Irritations/
    Management) session with *intelligent grouping*:

      • Commitments  → one-time (CTT-bound). 'immediate'=urgent/today,
                       '7_day'=high/+7d, '30_day'=medium/+30d.
      • Addictions   → 2 items each:
                         a) one-time corrective action  (CTT)  – if user
                            captured `corrective_actions`.
                         b) recurring daily check-in    (LifeStyle).
                       Priority: -neg_pct ≥70 urgent | ≥50 high | else medium.
      • Irritations  → recurring weekly reaction-management  (LifeStyle).
      • Advised items from breakthrough_reports.advised_items → one-time (CTT).

    Idempotent — keyed on `aim_key` (session_id|kind|text|cadence).
    """
    sess = await db.breakthrough_sessions.find_one(
        {"id": session_id, "user_id": user.get("user_id")}
    )
    if not sess:
        raise HTTPException(404, "AIM session not found")

    aim = await db.aim_reflections.find_one({"session_id": session_id}) or {}
    commitments = await db.breakthrough_commitments.find(
        {"session_id": session_id, "user_id": user.get("user_id")}
    ).to_list(50)
    report = await db.breakthrough_reports.find_one({"session_id": session_id}) or {}

    label = f"AIM · {sess.get('title', 'Introspection Session')}"
    now = datetime.now(timezone.utc)

    def _today() -> str:
        return now.date().isoformat()

    def _plus_days(d: int) -> str:
        from datetime import timedelta
        return (now + timedelta(days=d)).date().isoformat()

    def _pri_from_pct(pct) -> str:
        try:
            p = int(pct or 0)
        except Exception:
            p = 0
        if p >= 70:
            return "urgent"
        if p >= 50:
            return "high"
        return "medium"

    inserted: List[Dict[str, Any]] = []

    async def _insert(payload: Dict[str, Any], aim_key: str, source_subref: str):
        existing = await db.action_items.find_one({
            "user_id": user.get("user_id"),
            "source_module": "AIM",
            "source_id": session_id,
            "aim_key": aim_key,
        })
        if existing:
            new_title = (payload.get("title") or "").strip()
            if new_title and existing.get("title") != new_title:
                await db.action_items.update_one(
                    {"action_id": existing["action_id"]},
                    {"$set": {"title": new_title, "updated_at": _now_iso()}},
                )
            return
        body = {
            "source_module": "AIM",
            "source_id": session_id,
            "source_label": label,
            "source_subref": source_subref,
            **payload,
        }
        norm = _normalise(body, user)
        if not norm["title"]:
            return
        doc = {
            "action_id": str(uuid.uuid4()),
            **norm,
            "aim_key": aim_key,
            "ported_to": None, "ported_ref_id": None, "ported_at": None,
            "created_at": _now_iso(), "updated_at": _now_iso(),
        }
        await db.action_items.insert_one(doc)
        doc.pop("_id", None)
        inserted.append(doc)

    # ── Commitments → one-time (CTT-bound)
    for c in commitments:
        c_id = c.get("id") or ""
        c_text = (c.get("commitment_text") or "").strip()
        if not c_text:
            continue
        c_type = (c.get("commitment_type") or "immediate").lower()
        if c_type == "30_day":
            pri, by = "medium", _plus_days(30)
        elif c_type == "7_day":
            pri, by = "high", _plus_days(7)
        else:
            pri, by = "urgent", (c.get("due_date") or _today())
        await _insert({
            "title": f"[Commitment · {c_type.replace('_', '-')}] {c_text}",
            "description": c_text,
            "recurrence_type": "one_time",
            "priority": pri,
            "by_when": by,
        }, aim_key=f"commit|{c_id or c_text[:40]}", source_subref=c_id)

    # ── Addictions → corrective (one_time) + daily routine (recurring)
    for a in (aim.get("addictions") or []):
        if not isinstance(a, dict):
            continue
        text = (a.get("addiction") or "").strip()
        if not text:
            continue
        area = a.get("area_of_life") or None
        neg = a.get("negative_impact_pct")
        pri = _pri_from_pct(neg)
        corrective = (a.get("corrective_actions") or "").strip()
        owner_timeline = (a.get("task_owner_timeline") or "").strip()
        # (a) one-time corrective action — only if the user captured one
        if corrective:
            await _insert({
                "title": f"[Addiction · Action] {corrective[:90]}",
                "description": (
                    f"Addiction: {text}.\nCorrective action: {corrective}."
                    + (f"\nOwner / timeline: {owner_timeline}" if owner_timeline else "")
                ),
                "recurrence_type": "one_time",
                "priority": pri,
                "life_area": area,
                "by_when": _plus_days(7),
            }, aim_key=f"add_act|{text[:60]}", source_subref=text[:60])
        # (b) daily routine — habit-breaking check-in
        await _insert({
            "title": f"[Addiction · Routine] Stay free of: {text}",
            "description": (
                f"Daily check-in to avoid the addictive pattern: {text}."
                + (f"\nTriggers: {a.get('triggering_situations') or '—'}.")
                + (f"\nNegative impact: {a.get('negative_impact') or '—'} ({neg or 0}%).")
            ),
            "recurrence_type": "recurring",
            "recurrence_frequency": "daily",
            "priority": pri,
            "life_area": area,
        }, aim_key=f"add_routine|{text[:60]}", source_subref=text[:60])

    # ── Irritations → weekly reaction-management (recurring routine)
    for ir in (aim.get("irritations") or []):
        if not isinstance(ir, dict):
            continue
        text = (ir.get("irritation") or "").strip()
        if not text:
            continue
        area = ir.get("area_of_life") or None
        pct = ir.get("irritation_pct")
        pri = _pri_from_pct(pct)
        await _insert({
            "title": f"[Irritation · Routine] Manage reaction to: {text}",
            "description": (
                f"Weekly reflection on reactions to: {text}."
                + (f"\nProbable reaction: {ir.get('probable_reaction') or '—'}.")
                + (f"\nNegative impact: {ir.get('negative_impact') or '—'} ({pct or 0}%).")
            ),
            "recurrence_type": "recurring",
            "recurrence_frequency": "weekly",
            "priority": pri,
            "life_area": area,
        }, aim_key=f"irr_routine|{text[:60]}", source_subref=text[:60])

    # ── Advised items from the AI Breakthrough Report → one_time (CTT)
    for adv in (report.get("advised_items") or []):
        if not isinstance(adv, dict):
            continue
        lbl = (adv.get("label") or "").strip()
        if not lbl:
            continue
        kind = (adv.get("kind") or "addiction").lower()
        why = (adv.get("why") or "").strip()
        area = adv.get("life_area") or None
        await _insert({
            "title": f"[AI Advised · {kind.capitalize()}] {lbl}",
            "description": (f"AI suggests focusing on: {lbl}." + (f"\nWhy: {why}" if why else "")),
            "recurrence_type": "one_time",
            "priority": "high",
            "life_area": area,
            "by_when": _plus_days(7),
        }, aim_key=f"adv|{kind}|{lbl[:60]}", source_subref=f"adv:{kind}")

    # Tally for the UI banner
    ctt_n = sum(1 for x in inserted if x.get("recurrence_type") == "one_time")
    life_n = sum(1 for x in inserted if x.get("recurrence_type") == "recurring")
    return {
        "imported_count": len(inserted),
        "ctt_count": ctt_n,
        "lifestyle_count": life_n,
        "imported": inserted,
    }



# ───── Aggregate stats (for Action Center widget) ────────────────────────

@router.get("/action-items/stats/summary")
async def action_items_summary(user: dict = Depends(get_current_user)):
    q = {"user_id": user.get("user_id")}
    pipeline = [
        {"$match": q},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    rows = await db.action_items.aggregate(pipeline).to_list(50)
    status_counts = {r["_id"]: r["count"] for r in rows}
    src_rows = await db.action_items.aggregate([
        {"$match": q},
        {"$group": {"_id": "$source_module", "count": {"$sum": 1}}},
    ]).to_list(50)
    ported_rows = await db.action_items.aggregate([
        {"$match": q},
        {"$group": {"_id": "$ported_to", "count": {"$sum": 1}}},
    ]).to_list(10)
    total = await db.action_items.count_documents(q)
    return {
        "total": total,
        "by_status": status_counts,
        "by_source": {r["_id"]: r["count"] for r in src_rows},
        "by_ported": {(r["_id"] or "NOT_PORTED"): r["count"] for r in ported_rows},
    }
