"""
Time Allocation — LDC + AALA aware allocator on top of the existing Time Dezider.

This module DOES NOT replace the existing /api/time-dezider/* routes — it
adds a thin LDC-and-AALA-aware layer that:

  • Reads user's PNA goals, GEM projects, CTT tasks, lifestyle routines
  • Reads user's LDC freedom weights (with this-week pin → 1.5x multiplier)
  • Reads user's AALA cell feasibility (which TEPFI/level resources are depleted)
  • Returns a ranked list of recommendations with explicit "why" reasoning
  • Computes Drift Report: ideal LDC % vs actual time-spent % from Daily Tracker

  GET /api/time-allocation/suggestions
        ?days=7        — look-ahead window (default 7)
        ?limit=20      — max results
        ?include_routines=true

  GET /api/time-allocation/drift
        ?days=7        — actuals window (default 7)

Both endpoints degrade gracefully when sources are sparse.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user
from models.aala_models import TEPFI, LEVELS

router = APIRouter(prefix="/time-allocation", tags=["Time Allocation — LDC × AALA"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_aware(dt) -> Optional[datetime]:
    if dt is None:
        return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# LDC weight resolver (with pin multiplier)
# ---------------------------------------------------------------------------
async def _ldc_weights_map(user_id: str) -> Tuple[Dict[str, float], int]:
    """Return {freedom_key: weight} dict + influence_pct (0..100)."""
    doc = await db.ldc.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return {}, 30
    weights: Dict[str, float] = {}
    for f in sorted(doc.get("freedoms", []), key=lambda x: x.get("rank", 999)):
        rank = max(1, int(f.get("rank", 1)))
        w = max(1.0, 11.0 - rank)
        if f.get("pinned_this_week"):
            pu = _coerce_aware(f.get("pinned_until"))
            if pu and pu > _now():
                w *= 1.5
        weights[f["key"]] = round(w, 2)
    return weights, int(doc.get("influence_pct", 30))


async def _aala_feasibility_map(user_id: str) -> Dict[Tuple[str, str], float]:
    """{(factor, level): 0..1 score}."""
    doc = await db.aala.find_one({"user_id": user_id}, {"_id": 0})
    if not doc:
        return {}
    out: Dict[Tuple[str, str], float] = {}
    for c in doc.get("cells", []):
        score = float(c.get("balance_score", 0.0))
        out[(c.get("factor"), c.get("level"))] = max(0.0, min(1.0, (score + 10.0) / 20.0))
    return out


# ---------------------------------------------------------------------------
# Score one item
# ---------------------------------------------------------------------------
def _score_item(
    item: Dict[str, Any],
    ldc_weights: Dict[str, float],
    ldc_influence_pct: int,
    aala_map: Dict[Tuple[str, str], float],
) -> Dict[str, Any]:
    """Compute a 0..100 composite score for a task/routine.

    Score = (1 - ldc_inf%)*urgency_factor + ldc_inf%*ldc_score
            with ldc_score scaled by AALA feasibility of any TEPFI/level the
            item draws on (so depleted resources can't be over-allocated).
    """
    # 1. LDC alignment: sum of weights of linked freedoms / max possible (10)
    linked = item.get("linked_freedoms") or []
    if linked and ldc_weights:
        ldc_score = sum(ldc_weights.get(k, 0.0) for k in linked) / max(1, len(linked))
        ldc_score = min(1.0, ldc_score / 10.0)  # normalise to 0..1
    else:
        ldc_score = 0.5  # neutral if untagged

    # 2. AALA feasibility: average over linked TEPFI/level cells
    constraints = item.get("linked_aala_cells") or []   # [{"factor":"time","level":"self"}, …]
    if constraints and aala_map:
        feas = sum(aala_map.get((c.get("factor"), c.get("level")), 0.5) for c in constraints) / len(constraints)
    else:
        feas = 0.6  # mildly optimistic neutral

    # 3. Urgency: simple — overdue → 1.0, due-soon → 0.7, no-due → 0.4
    due = _coerce_aware(item.get("due_date") or item.get("ends_at"))
    n = _now()
    if due:
        days_to_due = (due - n).total_seconds() / 86400.0
        urgency = 1.0 if days_to_due < 0 else (
                  0.85 if days_to_due < 1 else (
                  0.7 if days_to_due < 7 else 0.5))
    else:
        urgency = 0.4

    inf = max(0, min(100, ldc_influence_pct)) / 100.0
    composite = (1 - inf) * urgency + inf * ldc_score * feas
    composite_pct = round(composite * 100, 1)

    return {
        "score": composite_pct,
        "breakdown": {
            "ldc_alignment": round(ldc_score, 3),
            "aala_feasibility": round(feas, 3),
            "urgency": round(urgency, 3),
            "ldc_influence_pct": ldc_influence_pct,
        },
        "reasoning": _reason_for(linked, ldc_weights, feas, urgency, ldc_score),
    }


def _reason_for(linked: List[str], weights: Dict[str, float], feas: float, urg: float, ldc: float) -> str:
    parts = []
    if linked:
        top_freedom = max(linked, key=lambda k: weights.get(k, 0.0))
        parts.append(f"Serves {top_freedom.title()} (weight {weights.get(top_freedom, 0):.1f})")
    if urg >= 0.85:
        parts.append("⏰ urgent")
    if feas <= 0.3:
        parts.append("⚠️ depleted resource — defer if possible")
    elif feas >= 0.75:
        parts.append("✅ resource available")
    return " · ".join(parts) or "neutral baseline"


# ---------------------------------------------------------------------------
# Suggestions endpoint
# ---------------------------------------------------------------------------
@router.get("/suggestions")
async def suggestions(
    user: dict = Depends(get_current_user),
    days: int = 7,
    limit: int = 20,
    include_routines: bool = True,
):
    uid = user["user_id"]
    ldc_w, ldc_inf = await _ldc_weights_map(uid)
    aala = await _aala_feasibility_map(uid)

    horizon = _now() + timedelta(days=max(1, min(days, 60)))
    candidates: List[Dict[str, Any]] = []

    # CTT tasks
    async for t in db.ctt_tasks.find({"user_id": uid, "status": {"$nin": ["done", "archived"]}}, {"_id": 0}).limit(200):
        candidates.append({
            "kind": "ctt_task",
            "id": t.get("task_id") or t.get("id"),
            "title": t.get("title") or t.get("description", "Task"),
            "linked_freedoms": t.get("linked_freedoms") or [],
            "linked_aala_cells": t.get("linked_aala_cells") or [],
            "due_date": t.get("due_date") or t.get("deadline"),
            "estimated_minutes": t.get("estimated_minutes"),
        })

    # Lifestyle routines
    if include_routines:
        async for r in db.lifestyle_routines.find({"user_id": uid, "active": {"$ne": False}}, {"_id": 0}).limit(100):
            candidates.append({
                "kind": "routine",
                "id": r.get("routine_id") or r.get("id"),
                "title": r.get("title") or r.get("name", "Routine"),
                "linked_freedoms": r.get("linked_freedoms") or [],
                "linked_aala_cells": r.get("linked_aala_cells") or [],
                "due_date": None,
                "estimated_minutes": r.get("estimated_minutes") or r.get("duration_minutes"),
            })

    # PNA goals (treated as long-horizon items)
    async for g in db.pna_goals.find({"user_id": uid, "status": {"$nin": ["done", "archived"]}}, {"_id": 0}).limit(50):
        candidates.append({
            "kind": "pna_goal",
            "id": g.get("goal_id") or g.get("id"),
            "title": g.get("title") or "Goal",
            "linked_freedoms": g.get("linked_freedoms") or [],
            "linked_aala_cells": g.get("linked_aala_cells") or [],
            "due_date": g.get("target_date"),
        })

    scored = []
    for c in candidates:
        meta = _score_item(c, ldc_w, ldc_inf, aala)
        scored.append({**c, **meta})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "ok": True,
        "ldc_influence_pct": ldc_inf,
        "ldc_weights": ldc_w,
        "items": scored[:max(1, min(limit, 100))],
        "candidate_count": len(scored),
    }


# ---------------------------------------------------------------------------
# Drift Report
# ---------------------------------------------------------------------------
@router.get("/drift")
async def drift_report(user: dict = Depends(get_current_user), days: int = 7):
    """LDC-ideal % vs daily-tracker actual %.

    For each freedom in user's LDC list:
      ideal_pct = weight_i / sum(weights)
      actual_pct = minutes_logged_for(linked_freedoms = freedom) / total_minutes
      drift = actual_pct - ideal_pct          (- = under-investing, + = over)
    """
    uid = user["user_id"]
    ldc_doc = await db.ldc.find_one({"user_id": uid}, {"_id": 0})
    if not ldc_doc:
        return {"ok": True, "drifts": [], "message": "Set up your LDC first."}

    weights: Dict[str, float] = {}
    for f in sorted(ldc_doc.get("freedoms", []), key=lambda x: x.get("rank", 999)):
        rank = max(1, int(f.get("rank", 1)))
        weights[f["key"]] = max(1.0, 11.0 - rank)
    total_w = sum(weights.values()) or 1.0

    since = _now() - timedelta(days=max(1, min(days, 90)))
    actual_minutes_per_freedom: Dict[str, int] = {k: 0 for k in weights}
    total_minutes = 0
    untagged_minutes = 0

    async for d in db.daily_entries.find(
        {"user_id": uid, "started_at": {"$gte": since}}, {"_id": 0}
    ):
        m = int(d.get("minutes") or 0)
        total_minutes += m
        linked = d.get("linked_freedoms") or []
        if not linked:
            untagged_minutes += m
            continue
        # Each freedom gets the entry's minutes (we don't split — over-allocation
        # is the honest signal here)
        for fr in linked:
            if fr in actual_minutes_per_freedom:
                actual_minutes_per_freedom[fr] += m

    drifts = []
    for key, w in sorted(weights.items(), key=lambda x: -x[1]):
        ideal_pct = round(100 * w / total_w, 1)
        actual_pct = round(100 * actual_minutes_per_freedom.get(key, 0) / max(1, total_minutes), 1) if total_minutes > 0 else 0.0
        drift_pct = round(actual_pct - ideal_pct, 1)
        # Suggested correction in hours/week (positive = invest more)
        suggested_min_change = round((ideal_pct - actual_pct) / 100.0 * total_minutes)
        drifts.append({
            "freedom": key,
            "weight": w,
            "ideal_pct": ideal_pct,
            "actual_pct": actual_pct,
            "drift_pct": drift_pct,
            "actual_minutes": actual_minutes_per_freedom.get(key, 0),
            "suggested_correction_minutes": suggested_min_change,
            "status": ("over" if drift_pct > 5 else ("under" if drift_pct < -5 else "aligned")),
        })

    return {
        "ok": True,
        "window_days": days,
        "total_minutes": total_minutes,
        "untagged_minutes": untagged_minutes,
        "drifts": drifts,
    }
