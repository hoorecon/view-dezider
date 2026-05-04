"""
Time Dezider — Raja Guru rule-based guidance engine.

Mission: from wake-up to sleep, guide the user to maximise time-on-purpose
across all life areas. Pure rule-based for v1 (LLM layer is in the backlog
as an overlay once the budget resets).

Endpoints:

  GET  /api/time-dezider/day-plan                  morning intent-setter
  GET  /api/time-dezider/midday-check              mid-day recalibration
  GET  /api/time-dezider/evening-retro             evening retrospective
  GET  /api/time-dezider/next-action               event-driven "what now?"
  GET  /api/time-dezider/preferences               read nudge cadence prefs
  POST /api/time-dezider/preferences               update nudge cadence
  POST /api/time-dezider/feedback                  user's accept/defer/skip on a nudge

Scoring model (every candidate action):
  score =  urgency * W_urg
         + importance * W_imp
         + energy_match * W_energy
         + time_window_match * W_window
         + streak_risk * W_streak
         + cld_leverage * W_cld

All weights env-tunable; sane defaults embedded. Results cap at top-N per
slot. Copy templates convey a "Raja Guru" tone — confident, compassionate,
crisp — but are deterministic for reproducibility.
"""
import uuid
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core.hardening import write_audit

router = APIRouter(prefix="/raja-guru", tags=["Time Dezider — Raja Guru"])

W = {
    "urgency": 3.0,
    "importance": 4.0,
    "energy_match": 1.5,
    "time_window": 2.5,
    "streak_risk": 2.0,
    "cld_leverage": 1.5,
}

RAJA_COPY = {
    "morning_intro": "Good morning, Raja. Here is today's high-conviction plan. Choose what to accept.",
    "midday_intro": "Raja, half the day is done. Here is what still matters — recalibrate, don't regret.",
    "evening_intro": "Raja, the sun sets with grace. Close the day with honesty and gentle review.",
    "event_intro": "One action at a time, Raja. This is the next highest-leverage move.",
    "no_plan": "No plan is still a plan — but a weaker one. Add a routine and we'll guide sharper.",
}


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------
class NudgeFeedback(BaseModel):
    nudge_id: str
    action_ref_id: Optional[str] = None
    action_ref_type: Optional[str] = None
    decision: str      # "accept" | "defer" | "skip"
    defer_to: Optional[str] = None    # ISO timestamp
    note: Optional[str] = None


class PreferencesBody(BaseModel):
    nudge_morning: Optional[bool] = None
    nudge_midday: Optional[bool] = None
    nudge_evening: Optional[bool] = None
    nudge_hourly: Optional[bool] = None
    nudge_event_driven: Optional[bool] = None


# ---------------------------------------------------------------------------
# Situation fetchers
# ---------------------------------------------------------------------------
async def _user_key_timings(uid: str) -> Dict[str, str]:
    doc = await db.user_preferences.find_one({"user_id": uid}, {"_id": 0}) or {}
    return {
        "wake_up": doc.get("wake_up", "06:30"),
        "bed_time": doc.get("bed_time", "22:30"),
        "business_start": doc.get("business_start", "09:30"),
        "business_end": doc.get("business_end", "18:30"),
    }


async def _user_ctt_tasks(uid: str, today: str) -> List[Dict[str, Any]]:
    """Live CTT tasks visible to the user for today."""
    q = {
        "user_id": uid,
        "$or": [
            {f"day_statuses.{today}": {"$exists": True}},
            {"status": {"$in": ["active", "in_progress", "pending"]}},
            {"scheduled_date": today},
        ],
    }
    cursor = db.ctt_tasks.find(q, {"_id": 0}).limit(50)
    return await cursor.to_list(50)


async def _user_lifestyle_plan(uid: str) -> Dict[str, Any]:
    doc = await db.lifestyle_designs.find_one(
        {"user_id": uid}, {"_id": 0},
        sort=[("created_at", -1)],
    )
    return doc or {}


async def _user_active_matrix(uid: str) -> Optional[Dict[str, Any]]:
    """Most recent in-progress Solution Matrix — reveals situational roles."""
    return await db.solution_matrices.find_one(
        {"user_id": uid, "status": {"$in": ["in_progress", "completed"]}},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )


async def _latest_cld(uid: str) -> Optional[Dict[str, Any]]:
    return await db.clds.find_one(
        {"user_id": uid}, {"_id": 0},
        sort=[("created_at", -1)],
    )


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------
def _parse_hhmm(s: str) -> int:
    try:
        h, m = map(int, s.split(":")); return h * 60 + m
    except Exception:
        return 0


def _now_minutes() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


def _score_ctt(task: Dict[str, Any], now_min: int, kt: Dict[str, str]) -> float:
    # urgency from due date
    urg = 0.0
    due = task.get("due_date") or task.get("deadline")
    try:
        if due:
            d = datetime.fromisoformat(str(due).replace("Z", "+00:00"))
            days = (d.date() - datetime.now(timezone.utc).date()).days
            urg = max(0.0, 5.0 - min(days, 5))
    except Exception:
        pass
    # importance from priority field
    prio = task.get("priority") or task.get("importance") or "medium"
    imp_map = {"critical": 5, "high": 4, "medium": 3, "low": 2, "someday": 1}
    imp = float(imp_map.get(str(prio).lower(), 3))
    # time-window: prefer business hours for work-category
    tw = 0.0
    biz_s = _parse_hhmm(kt["business_start"]); biz_e = _parse_hhmm(kt["business_end"])
    if biz_s <= now_min <= biz_e:
        tw = 2.0 if (task.get("category") == "work" or task.get("task_type") == "work") else 1.0
    # energy-match: rough heuristic — complex tasks preferred early
    e_est = float(task.get("difficulty") or task.get("complexity") or 3)
    em = max(0.0, 5.0 - abs(e_est - (5 if now_min < biz_s + 120 else 3)))
    # streak risk: task pending > 7 days
    sr = 0.0
    try:
        created = task.get("created_at")
        if created:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(created).replace("Z", "+00:00"))).days
            sr = min(3.0, age / 7.0)
    except Exception:
        pass
    score = (urg * W["urgency"] + imp * W["importance"]
             + em * W["energy_match"] + tw * W["time_window"]
             + sr * W["streak_risk"])
    return score


def _score_lifestyle_area(area: Dict[str, Any], now_min: int, kt: Dict[str, str]) -> float:
    hpd = float(area.get("hours_per_day") or (area.get("hours_per_week", 0) / 7.0))
    imp = min(5.0, hpd * 1.5)                # more hours = more important
    tw = 0.0
    t = (area.get("preferred_time") or "").lower()
    wake = _parse_hhmm(kt["wake_up"]); bed = _parse_hhmm(kt["bed_time"])
    biz_s = _parse_hhmm(kt["business_start"]); biz_e = _parse_hhmm(kt["business_end"])
    if "morning" in t and abs(now_min - wake) < 120: tw = 3.0
    elif "evening" in t and abs(now_min - bed) < 180: tw = 3.0
    elif "noon" in t or "afternoon" in t:
        if biz_s <= now_min <= biz_e: tw = 2.5
    return imp * W["importance"] + tw * W["time_window"]


def _cld_leverage_bonus(cld: Optional[Dict[str, Any]], ref_id: Optional[str]) -> float:
    if not cld or not ref_id:
        return 0.0
    # Pure count-based leverage: how many nodes does this item touch?
    nodes = cld.get("nodes") or []
    edges = cld.get("edges") or []
    node_ids = {n.get("node_id") for n in nodes if str(ref_id).lower() in (n.get("label", "").lower(), n.get("node_id", ""))}
    if not node_ids:
        return 0.0
    return min(3.0, sum(1 for e in edges if e.get("from") in node_ids or e.get("to") in node_ids) * 0.5)


# ---------------------------------------------------------------------------
# Candidate builders
# ---------------------------------------------------------------------------
async def _candidates(user_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    kt = await _user_key_timings(user_id)
    today = str(date_cls.today())
    tasks = await _user_ctt_tasks(user_id, today)
    plan = await _user_lifestyle_plan(user_id)
    cld = await _latest_cld(user_id)
    now_min = _now_minutes()

    cands: List[Dict[str, Any]] = []

    # CTT tasks
    for t in tasks:
        if (t.get("day_statuses") or {}).get(today, {}).get("status") == "done":
            continue
        base = _score_ctt(t, now_min, kt)
        lev = _cld_leverage_bonus(cld, t.get("task_id") or t.get("title"))
        cands.append({
            "kind": "ctt_task",
            "ref_id": t.get("task_id"),
            "title": t.get("title") or "Untitled task",
            "estimated_minutes": int(t.get("estimated_minutes") or t.get("duration_estimate") or 30),
            "score": round(base + lev * W["cld_leverage"], 2),
            "reason": "Urgent + high importance" if base > 20 else "Keep it moving",
        })

    # Lifestyle areas
    for area in (plan.get("areas") or []):
        base = _score_lifestyle_area(area, now_min, kt)
        lev = _cld_leverage_bonus(cld, area.get("area_id") or area.get("name"))
        cands.append({
            "kind": "lifestyle_area",
            "ref_id": area.get("area_id") or area.get("name"),
            "title": area.get("name") or area.get("area_id") or "Area",
            "estimated_minutes": int(float(area.get("hours_per_day") or 0.5) * 60),
            "score": round(base + lev * W["cld_leverage"], 2),
            "reason": _lifestyle_reason(area, now_min, kt),
        })

    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands, kt


def _lifestyle_reason(area: Dict[str, Any], now_min: int, kt: Dict[str, str]) -> str:
    t = (area.get("preferred_time") or "").lower()
    wake = _parse_hhmm(kt["wake_up"])
    if "morning" in t:
        if now_min < wake + 180:
            return "Best window for this is now — morning compounds."
        return "Morning window passed; still worth completing before noon."
    if "evening" in t: return "Reserve this for after business hours."
    return "Pick any clear slot today — lifestyle compounds daily."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/preferences")
async def prefs(user: dict = Depends(get_current_user)):
    doc = await db.user_preferences.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    return {
        "nudge_morning": doc.get("nudge_morning", True),
        "nudge_midday": doc.get("nudge_midday", True),
        "nudge_evening": doc.get("nudge_evening", True),
        "nudge_hourly": doc.get("nudge_hourly", False),
        "nudge_event_driven": doc.get("nudge_event_driven", True),
        "wake_up": doc.get("wake_up", "06:30"),
        "bed_time": doc.get("bed_time", "22:30"),
        "business_start": doc.get("business_start", "09:30"),
        "business_end": doc.get("business_end", "18:30"),
    }


@router.post("/preferences")
async def set_prefs(body: PreferencesBody, user: dict = Depends(get_current_user)):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if payload:
        payload["user_id"] = user["user_id"]
        payload["updated_at"] = datetime.now(timezone.utc)
        await db.user_preferences.update_one(
            {"user_id": user["user_id"]}, {"$set": payload}, upsert=True,
        )
    return await prefs(user)  # return fresh merged


@router.get("/day-plan")
async def day_plan(user: dict = Depends(get_current_user), top_n: int = 5):
    cands, kt = await _candidates(user["user_id"])
    picks = cands[:max(1, min(top_n, 10))]
    if not picks:
        return {"intro": RAJA_COPY["no_plan"], "key_timings": kt, "picks": [], "raja_note": ""}
    total = sum(p["estimated_minutes"] for p in picks)
    return {
        "intro": RAJA_COPY["morning_intro"],
        "key_timings": kt,
        "total_planned_minutes": total,
        "picks": picks,
        "raja_note": "Accept 2-3 non-negotiables. Defer the rest with dignity.",
    }


@router.get("/midday-check")
async def midday_check(user: dict = Depends(get_current_user), top_n: int = 4):
    cands, kt = await _candidates(user["user_id"])
    today = str(date_cls.today())
    # exclude CTT tasks already marked done today
    remaining = [c for c in cands if c["kind"] != "ctt_task" or True]
    picks = remaining[:max(1, min(top_n, 8))]
    return {
        "intro": RAJA_COPY["midday_intro"],
        "key_timings": kt,
        "picks": picks,
        "raja_note": "Protect one deep-work slot. Energy is a currency.",
    }


@router.get("/evening-retro")
async def evening_retro(user: dict = Depends(get_current_user)):
    today = str(date_cls.today())
    dtl = await db.daily_time_logs.find_one(
        {"user_id": user["user_id"], "log_date": today}, {"_id": 0},
    ) or {}
    logged = int(dtl.get("total_logged_minutes") or 0)
    wins: List[str] = []
    gaps: List[str] = []
    pva = (dtl.get("planned_vs_actual") or {}).get("per_category_minutes", {})
    if pva.get("ctt", 0) > 0:
        wins.append(f"{pva['ctt']} min on tasks — momentum preserved.")
    else:
        gaps.append("No CTT task time logged. Pick ONE for tomorrow.")
    if pva.get("lifestyle", 0) >= 45:
        wins.append(f"{pva['lifestyle']} min on lifestyle — compounding.")
    else:
        gaps.append("Lifestyle under 45 min. Start tomorrow with the easiest 15 min.")
    if pva.get("meditation", 0) > 0:
        wins.append("Meditation logged — mind unhooked.")
    return {
        "intro": RAJA_COPY["evening_intro"],
        "total_logged_minutes": logged,
        "wins": wins,
        "gaps": gaps,
        "raja_note": "Sleep is the first tool of tomorrow. Close the laptop.",
    }


@router.get("/next-action")
async def next_action(user: dict = Depends(get_current_user)):
    cands, kt = await _candidates(user["user_id"])
    pick = cands[0] if cands else None
    return {
        "intro": RAJA_COPY["event_intro"],
        "key_timings": kt,
        "pick": pick,
        "raja_note": "Do it for 5 minutes. Momentum will decide the rest.",
    }


@router.post("/feedback")
async def nudge_feedback(body: NudgeFeedback, request: Request, user: dict = Depends(get_current_user)):
    if body.decision not in ("accept", "defer", "skip"):
        raise HTTPException(400, "decision must be accept/defer/skip")
    doc = {
        "feedback_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "nudge_id": body.nudge_id,
        "action_ref_id": body.action_ref_id,
        "action_ref_type": body.action_ref_type,
        "decision": body.decision,
        "defer_to": body.defer_to,
        "note": body.note,
        "created_at": datetime.now(timezone.utc),
    }
    await db.time_dezider_feedback.insert_one(doc)
    await write_audit(db, action="time_dezider.feedback", actor_id=user["user_id"],
                      actor_email=user.get("email"), request=request,
                      metadata={"decision": body.decision, "nudge_id": body.nudge_id})
    return {"ok": True, "feedback_id": doc["feedback_id"]}
