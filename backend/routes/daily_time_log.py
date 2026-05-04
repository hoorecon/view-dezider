"""
Daily Time Log (DTL) — backend routes + auto-rollup engine.

A DTL record is keyed by (user_id, log_date). Endpoints:

  POST /api/daily-time-log                        upsert a day log
  GET  /api/daily-time-log/{date}                 fetch a day (auto-rollup included)
  GET  /api/daily-time-log/week?start_date=       7-day overview
  GET  /api/daily-time-log/streaks                current & longest log streak
  GET  /api/daily-time-log/weekly-review          week adherence + variance
  POST /api/daily-time-log/{date}/refresh-rollup  force re-scan of source modules
  POST /api/daily-time-log/preferences            set wake_up / bed / business hrs
  GET  /api/daily-time-log/preferences            read user's 4 key timings

Auto-rollup sources:
  - CTT tasks (day_statuses.{date}.status == done)            → ctt block
  - lifestyle_eval_logs.{date}                                → lifestyle blocks
  - meditation_sessions completed on the date                 → meditation block
  - journal_entries written on the date                       → journal block

All auto blocks have `auto_sourced=True` so the frontend can flag them and
the user can edit/override.
"""
import uuid
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core.hardening import write_audit
from models.daily_time_log_models import (
    DailyKeyTimings, TimeBlock, minutes_between,
)

router = APIRouter(prefix="/daily-time-log", tags=["Daily Time Log"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class UpsertBlockBody(BaseModel):
    block_id: Optional[str] = None
    start: str
    end: str
    category: str = "other"
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    label: str = ""
    note: str = ""
    mood: Optional[int] = None
    energy: Optional[int] = None


class UpsertDayBody(BaseModel):
    log_date: str
    blocks: List[UpsertBlockBody] = []
    key_timings: Optional[DailyKeyTimings] = None
    overall_mood: Optional[int] = None
    overall_energy: Optional[int] = None
    reflection: Optional[str] = None
    run_auto_rollup: bool = True


class PreferencesBody(BaseModel):
    wake_up: Optional[str] = None
    bed_time: Optional[str] = None
    business_start: Optional[str] = None
    business_end: Optional[str] = None
    timezone: Optional[str] = None
    nudge_morning: Optional[bool] = None
    nudge_midday: Optional[bool] = None
    nudge_evening: Optional[bool] = None
    nudge_hourly: Optional[bool] = None
    nudge_event_driven: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_prefs(user_id: str) -> Dict[str, Any]:
    doc = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0}) or {}
    return {
        "wake_up": doc.get("wake_up", "06:30"),
        "bed_time": doc.get("bed_time", "22:30"),
        "business_start": doc.get("business_start", "09:30"),
        "business_end": doc.get("business_end", "18:30"),
        "timezone": doc.get("timezone", "Asia/Kolkata"),
        "nudge_morning": doc.get("nudge_morning", True),
        "nudge_midday": doc.get("nudge_midday", True),
        "nudge_evening": doc.get("nudge_evening", True),
        "nudge_hourly": doc.get("nudge_hourly", False),
        "nudge_event_driven": doc.get("nudge_event_driven", True),
    }


def _normalise_blocks(raw_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalised: List[Dict[str, Any]] = []
    for b in raw_blocks:
        if not isinstance(b, dict):
            continue
        start = str(b.get("start") or "00:00")
        end = str(b.get("end") or "00:00")
        cat = str(b.get("category") or "other").lower()
        normalised.append({
            "block_id": str(b.get("block_id") or uuid.uuid4()),
            "start": start,
            "end": end,
            "category": cat,
            "ref_type": b.get("ref_type"),
            "ref_id": b.get("ref_id"),
            "label": str(b.get("label") or ""),
            "note": str(b.get("note") or ""),
            "mood": b.get("mood"),
            "energy": b.get("energy"),
            "auto_sourced": bool(b.get("auto_sourced", False)),
            "minutes": minutes_between(start, end),
        })
    return normalised


async def _build_auto_blocks(user_id: str, log_date: str) -> List[Dict[str, Any]]:
    """Synthesise auto-sourced blocks from CTT + Lifestyle Eval + Meditation + Journal."""
    auto: List[Dict[str, Any]] = []

    # 1) CTT tasks marked done today
    ctt_cursor = db.ctt_tasks.find(
        {"user_id": user_id, f"day_statuses.{log_date}.status": "done"},
        {"_id": 0, "task_id": 1, "title": 1, "day_statuses": 1,
         "estimated_minutes": 1, "duration_estimate": 1},
    ).limit(200)
    async for t in ctt_cursor:
        mins = int(
            t.get("estimated_minutes") or t.get("duration_estimate") or 30
        )
        auto.append({
            "block_id": f"auto_ctt_{t.get('task_id')}",
            "start": "", "end": "",  # unanchored — user positions later
            "category": "ctt",
            "ref_type": "ctt_task",
            "ref_id": t.get("task_id"),
            "label": str(t.get("title") or "CTT task")[:120],
            "note": "Auto-imported — tap to position on timeline",
            "auto_sourced": True,
            "minutes": mins,
        })

    # 2) Lifestyle Eval logs
    le = await db.lifestyle_eval_logs.find_one(
        {"user_id": user_id, "log_date": log_date},
        {"_id": 0},
    )
    if le:
        for entry in (le.get("entries") or []):
            area = entry.get("area") or entry.get("area_id") or "lifestyle"
            dur = int(entry.get("actual_minutes") or entry.get("duration_min") or 0)
            if dur <= 0:
                continue
            auto.append({
                "block_id": f"auto_le_{uuid.uuid4().hex[:8]}",
                "start": entry.get("start_time") or "",
                "end": entry.get("end_time") or "",
                "category": "lifestyle",
                "ref_type": "lifestyle_area",
                "ref_id": area,
                "label": entry.get("label") or f"Lifestyle: {area}",
                "note": entry.get("note", ""),
                "auto_sourced": True,
                "minutes": dur,
            })

    # 3) Meditation sessions
    day_start = datetime.fromisoformat(log_date + "T00:00:00+00:00")
    day_end = day_start + timedelta(days=1)
    med_cursor = db.meditation_sessions.find(
        {
            "user_id": user_id,
            "completed_at": {"$gte": day_start, "$lt": day_end},
        },
        {"_id": 0, "session_id": 1, "duration_minutes": 1, "session_type": 1, "completed_at": 1},
    ).limit(20)
    async for m in med_cursor:
        dur = int(m.get("duration_minutes") or 10)
        auto.append({
            "block_id": f"auto_med_{m.get('session_id') or uuid.uuid4().hex[:8]}",
            "start": "", "end": "",
            "category": "meditation",
            "ref_type": "meditation_session",
            "ref_id": m.get("session_id"),
            "label": f"Meditation: {m.get('session_type', 'general')}",
            "auto_sourced": True,
            "minutes": dur,
        })

    # 4) Journal entries
    j_cursor = db.journal_entries.find(
        {
            "user_id": user_id,
            "$or": [
                {"entry_date": log_date},
                {"created_at": {"$gte": day_start, "$lt": day_end}},
            ],
        },
        {"_id": 0, "entry_id": 1, "title": 1, "created_at": 1, "duration_minutes": 1},
    ).limit(20)
    async for j in j_cursor:
        dur = int(j.get("duration_minutes") or 10)
        auto.append({
            "block_id": f"auto_j_{j.get('entry_id') or uuid.uuid4().hex[:8]}",
            "start": "", "end": "",
            "category": "journal",
            "ref_type": "journal_entry",
            "ref_id": j.get("entry_id"),
            "label": (j.get("title") or "Journal")[:120],
            "auto_sourced": True,
            "minutes": dur,
        })

    return auto


async def _update_streak(user_id: str, log_date: str, total_minutes: int):
    """Advance or break the daily_time_log streak."""
    if total_minutes < 15:
        return  # don't count empty / near-empty days
    doc = await db.user_streaks.find_one({"user_id": user_id, "streak_key": "daily_time_log"}, {"_id": 0}) or {}
    last = doc.get("last_log_date")
    current = int(doc.get("current") or 0)
    longest = int(doc.get("longest") or 0)
    today_dt = date_cls.fromisoformat(log_date)
    if last:
        last_dt = date_cls.fromisoformat(last)
        diff = (today_dt - last_dt).days
        if diff == 0:
            pass  # already counted
        elif diff == 1:
            current += 1
        else:
            current = 1
    else:
        current = 1
    longest = max(longest, current)
    await db.user_streaks.update_one(
        {"user_id": user_id, "streak_key": "daily_time_log"},
        {"$set": {
            "current": current,
            "longest": longest,
            "last_log_date": log_date,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


async def _rollup_planned_vs_actual(user_id: str, log_date: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll blocks up into category totals + lifestyle plan comparison."""
    per_category: Dict[str, int] = {}
    per_lifestyle_area: Dict[str, int] = {}
    per_ctt_task: Dict[str, int] = {}
    for b in blocks:
        cat = b.get("category") or "other"
        per_category[cat] = per_category.get(cat, 0) + int(b.get("minutes") or 0)
        if cat == "lifestyle" and b.get("ref_id"):
            per_lifestyle_area[b["ref_id"]] = per_lifestyle_area.get(b["ref_id"], 0) + int(b.get("minutes") or 0)
        if cat == "ctt" and b.get("ref_id"):
            per_ctt_task[b["ref_id"]] = per_ctt_task.get(b["ref_id"], 0) + int(b.get("minutes") or 0)
    return {
        "per_category_minutes": per_category,
        "per_lifestyle_area_minutes": per_lifestyle_area,
        "per_ctt_task_minutes": per_ctt_task,
    }


# ---------------------------------------------------------------------------
# Preferences (4 key timings + nudge cadence)
# ---------------------------------------------------------------------------
@router.get("/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    return await _get_prefs(user["user_id"])


@router.post("/preferences")
async def set_preferences(body: PreferencesBody, user: dict = Depends(get_current_user)):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "No fields to update")
    payload["user_id"] = user["user_id"]
    payload["updated_at"] = datetime.now(timezone.utc)
    await db.user_preferences.update_one(
        {"user_id": user["user_id"]}, {"$set": payload}, upsert=True,
    )
    return await _get_prefs(user["user_id"])


# ---------------------------------------------------------------------------
# Week / Streaks / Weekly review  — MUST be before /{log_date} catch-all
# ---------------------------------------------------------------------------
@router.get("/week")
async def week_view(start_date: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not start_date:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=today.weekday())     # Monday
    else:
        start = date_cls.fromisoformat(start_date)
    days = [str(start + timedelta(days=i)) for i in range(7)]
    docs = await db.daily_time_logs.find(
        {"user_id": user["user_id"], "log_date": {"$in": days}},
        {"_id": 0},
    ).to_list(7)
    by_date = {d.get("log_date"): d for d in docs}
    out = []
    for d in days:
        doc = by_date.get(d) or {"log_date": d, "blocks": [], "total_logged_minutes": 0}
        out.append({
            "log_date": d,
            "total_logged_minutes": int(doc.get("total_logged_minutes") or 0),
            "per_category_minutes": (doc.get("planned_vs_actual") or {}).get("per_category_minutes", {}),
            "overall_mood": doc.get("overall_mood"),
            "overall_energy": doc.get("overall_energy"),
            "has_log": bool(doc.get("blocks")),
        })
    return {"start_date": str(start), "days": out}


@router.get("/streaks")
async def streaks(user: dict = Depends(get_current_user)):
    doc = await db.user_streaks.find_one(
        {"user_id": user["user_id"], "streak_key": "daily_time_log"}, {"_id": 0},
    ) or {}
    return {
        "current": int(doc.get("current") or 0),
        "longest": int(doc.get("longest") or 0),
        "last_log_date": doc.get("last_log_date"),
    }


@router.get("/weekly-review")
async def weekly_review(start_date: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not start_date:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=today.weekday())
    else:
        start = date_cls.fromisoformat(start_date)
    days = [str(start + timedelta(days=i)) for i in range(7)]
    docs = await db.daily_time_logs.find(
        {"user_id": user["user_id"], "log_date": {"$in": days}},
        {"_id": 0},
    ).to_list(7)

    actual_totals: Dict[str, int] = {}
    ctt_minutes = 0; lifestyle_minutes = 0; meditation_minutes = 0; journal_minutes = 0
    for d in docs:
        for cat, mins in (d.get("planned_vs_actual") or {}).get("per_category_minutes", {}).items():
            actual_totals[cat] = actual_totals.get(cat, 0) + int(mins)
            if cat == "ctt": ctt_minutes += int(mins)
            elif cat == "lifestyle": lifestyle_minutes += int(mins)
            elif cat == "meditation": meditation_minutes += int(mins)
            elif cat == "journal": journal_minutes += int(mins)
    total_actual = sum(actual_totals.values())

    design = await db.lifestyle_designs.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "areas": 1, "day_types": 1},
        sort=[("created_at", -1)],
    ) or {}
    planned_lifestyle_week_hours = 0.0
    if design.get("areas"):
        for area in design["areas"]:
            hrs = float(area.get("hours_per_day") or area.get("hours_per_week", 0) / 7 or 0)
            planned_lifestyle_week_hours += hrs * 7

    adherence_pct = None
    if planned_lifestyle_week_hours > 0:
        adherence_pct = round(
            (lifestyle_minutes / 60.0) / planned_lifestyle_week_hours * 100, 1,
        )

    streak_doc = await db.user_streaks.find_one(
        {"user_id": user["user_id"], "streak_key": "daily_time_log"}, {"_id": 0},
    ) or {}

    return {
        "start_date": str(start),
        "days_with_logs": sum(1 for d in docs if d.get("blocks")),
        "total_logged_minutes": total_actual,
        "actual_category_minutes": actual_totals,
        "planned_lifestyle_hours_week": round(planned_lifestyle_week_hours, 1),
        "actual_lifestyle_minutes_week": lifestyle_minutes,
        "adherence_pct": adherence_pct,
        "ctt_minutes": ctt_minutes,
        "meditation_minutes": meditation_minutes,
        "journal_minutes": journal_minutes,
        "current_streak": int(streak_doc.get("current") or 0),
        "longest_streak": int(streak_doc.get("longest") or 0),
        "variance_notes": _variance_notes(
            lifestyle_minutes, planned_lifestyle_week_hours * 60, ctt_minutes,
        ),
    }


def _variance_notes(actual_lifestyle_min: int, planned_lifestyle_min: float,
                    ctt_min: int) -> List[str]:
    notes: List[str] = []
    if planned_lifestyle_min > 0:
        gap = actual_lifestyle_min - planned_lifestyle_min
        if gap < -planned_lifestyle_min * 0.2:
            notes.append("Lifestyle adherence below 80% — consider dropping a commitment.")
        elif gap > planned_lifestyle_min * 0.1:
            notes.append("You're over-delivering on lifestyle routines — healthy buffer.")
        else:
            notes.append("Lifestyle adherence within ±10% of plan. Nice consistency.")
    if ctt_min < 30:
        notes.append("Less than 30 min of CTT tasks logged this week — are tasks stuck?")
    return notes


# ---------------------------------------------------------------------------
# Day CRUD
# ---------------------------------------------------------------------------
@router.get("/{log_date}")
async def get_day(log_date: str, user: dict = Depends(get_current_user), auto_rollup: bool = True):
    existing = await db.daily_time_logs.find_one(
        {"user_id": user["user_id"], "log_date": log_date}, {"_id": 0},
    ) or {}
    prefs = await _get_prefs(user["user_id"])
    if "key_timings" not in existing:
        existing["key_timings"] = {
            "wake_up": prefs["wake_up"], "bed_time": prefs["bed_time"],
            "business_start": prefs["business_start"], "business_end": prefs["business_end"],
        }
    existing["timezone"] = existing.get("timezone", prefs["timezone"])
    existing["blocks"] = existing.get("blocks") or []

    if auto_rollup:
        auto = await _build_auto_blocks(user["user_id"], log_date)
        # Merge auto + manual — user-edited blocks win on same block_id
        by_id = {b["block_id"]: b for b in existing["blocks"]}
        for b in auto:
            by_id.setdefault(b["block_id"], b)
        existing["blocks"] = list(by_id.values())
    existing["total_logged_minutes"] = sum(int(b.get("minutes") or 0) for b in existing["blocks"])
    existing["planned_vs_actual"] = await _rollup_planned_vs_actual(
        user["user_id"], log_date, existing["blocks"],
    )
    existing["user_id"] = user["user_id"]
    existing["log_date"] = log_date
    return existing


@router.post("")
async def upsert_day(body: UpsertDayBody, request: Request, user: dict = Depends(get_current_user)):
    prefs = await _get_prefs(user["user_id"])
    kt = (body.key_timings or DailyKeyTimings(
        wake_up=prefs["wake_up"], bed_time=prefs["bed_time"],
        business_start=prefs["business_start"], business_end=prefs["business_end"],
    )).model_dump()

    blocks = _normalise_blocks([b.model_dump() for b in body.blocks])
    if body.run_auto_rollup:
        existing_ids = {b["block_id"] for b in blocks}
        auto = await _build_auto_blocks(user["user_id"], body.log_date)
        for b in auto:
            if b["block_id"] not in existing_ids:
                blocks.append(b)

    pva = await _rollup_planned_vs_actual(user["user_id"], body.log_date, blocks)
    total = sum(int(b.get("minutes") or 0) for b in blocks)

    doc = {
        "user_id": user["user_id"],
        "log_date": body.log_date,
        "timezone": prefs["timezone"],
        "key_timings": kt,
        "blocks": blocks,
        "overall_mood": body.overall_mood,
        "overall_energy": body.overall_energy,
        "reflection": body.reflection or "",
        "total_logged_minutes": total,
        "planned_vs_actual": pva,
        "auto_rollup_run_at": datetime.now(timezone.utc).isoformat() if body.run_auto_rollup else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.daily_time_logs.update_one(
        {"user_id": user["user_id"], "log_date": body.log_date},
        {"$set": doc},
        upsert=True,
    )
    await _update_streak(user["user_id"], body.log_date, total)
    await write_audit(db, action="dtl.upsert", actor_id=user["user_id"],
                      actor_email=user.get("email"), request=request,
                      metadata={"log_date": body.log_date, "blocks": len(blocks), "minutes": total})
    return doc


@router.post("/{log_date}/refresh-rollup")
async def refresh_rollup(log_date: str, user: dict = Depends(get_current_user)):
    existing = await db.daily_time_logs.find_one(
        {"user_id": user["user_id"], "log_date": log_date}, {"_id": 0},
    ) or {"blocks": []}
    manual = [b for b in existing.get("blocks", []) if not b.get("auto_sourced")]
    auto = await _build_auto_blocks(user["user_id"], log_date)
    merged = _normalise_blocks(manual + auto)
    total = sum(int(b.get("minutes") or 0) for b in merged)
    pva = await _rollup_planned_vs_actual(user["user_id"], log_date, merged)
    await db.daily_time_logs.update_one(
        {"user_id": user["user_id"], "log_date": log_date},
        {"$set": {
            "blocks": merged,
            "total_logged_minutes": total,
            "planned_vs_actual": pva,
            "auto_rollup_run_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "blocks": merged, "total_logged_minutes": total,
            "planned_vs_actual": pva}

