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
}
RECURRENCE_TYPES = {"one_time", "recurring"}
FREQUENCIES = {"daily", "weekly", "biweekly", "monthly", "quarterly", "yearly", "custom"}
PRIORITIES = {"low", "medium", "high", "urgent"}
STATUSES = {"pending", "in_progress", "done", "blocked", "cancelled"}
PORT_TARGETS = {"CTT", "LIFESTYLE"}


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
    status = (body.get("status") or "pending").lower()
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
    if status == "done" and progress < 100:
        progress = 100

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
    norm = _normalise(merged, user)
    norm["updated_at"] = _now_iso()
    await db.action_items.update_one({"action_id": action_id}, {"$set": norm})
    out = await db.action_items.find_one({"action_id": action_id}, {"_id": 0})
    return out


@router.delete("/action-items/{action_id}")
async def delete_action_item(action_id: str, user: dict = Depends(get_current_user)):
    existing = await db.action_items.find_one(
        {"action_id": action_id, "user_id": user.get("user_id")}
    )
    if not existing:
        raise HTTPException(404, "action item not found")
    # Soft-cancel by default; if `?hard=true` and not ported, hard-delete.
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
