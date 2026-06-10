"""Emotional Gatekeeper — Emotional Outlet Analyzer & AIM Routes"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from routes.auth_routes import get_current_user

from .models import OutletAnalysisRequest, AIMSaveRequest
from .constants import COPING_STRATEGIES, OUTLET_FREQUENCIES, OUTLET_NATURES, LIFE_AREAS, LIFE_AREA_LABELS, AIM_OCCURRENCE_OPTIONS
from .ai_engine import analyze_outlets, analyze_aim, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


# ============ OUTLET ANALYZER ============

@router.get("/outlet/strategies")
async def get_strategies(user: dict = Depends(get_current_user)):
    """Get the list of coping strategies and frequency options."""
    return {
        "strategies": COPING_STRATEGIES,
        "frequencies": OUTLET_FREQUENCIES,
        "natures": OUTLET_NATURES,
    }


@router.post("/outlet/{session_id}/analyze")
async def outlet_analyze(session_id: str, data: OutletAnalysisRequest, user: dict = Depends(get_current_user)):
    """Analyze emotional outlets and get AI recommendations."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    # Build entries with full names + group + healthy/unhealthy flag
    strategy_map = {s["id"]: s for s in COPING_STRATEGIES}
    entries = []
    for entry in data.entries:
        strat = strategy_map.get(entry.strategy_id, {})
        entries.append({
            "strategy_id": entry.strategy_id,
            "name": entry.custom_name or strat.get("name", entry.strategy_id),
            "nature": entry.nature_override or strat.get("nature", "other"),
            "default_constructive": strat.get("default_constructive"),
            "frequency": entry.frequency,
            "is_compulsive": entry.is_compulsive,
            "side_effects": entry.side_effects,
        })

    # Frequency-weighted Outlet-Group breakdown (deterministic)
    freq_weight = {f["id"]: f["value"] for f in OUTLET_FREQUENCIES}
    weights = {"physical": 0, "mental": 0, "emotional": 0, "energy": 0}
    for e in entries:
        nat = e["nature"]
        if nat not in weights:
            continue
        w = freq_weight.get(e["frequency"], 0)
        if w > 0:
            weights[nat] += w
    total_w = sum(weights.values()) or 1
    group_breakdown = {k: round(v / total_w * 100) for k, v in weights.items()}
    ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    primary_mode = ranked[0][0] if ranked[0][1] > 0 else ""
    secondary_mode = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else ""

    try:
        ai = await analyze_outlets(
            entries, group_breakdown, primary_mode, secondary_mode,
            user_id=user["user_id"], session_id=session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outlet analysis failed: {e}")
        raise HTTPException(502, detail={"code": "ai_error", "message": "AI analysis failed. Please try again."})

    # Merge deterministic metrics into the stored analysis so resume renders them.
    analysis = {
        "group_breakdown": group_breakdown,
        "primary_mode": primary_mode,
        "secondary_mode": secondary_mode,
        **ai,
    }

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": f"OA-{uuid.uuid4().hex[:8].upper()}",
        "session_id": session_id,
        "user_id": user["user_id"],
        "entries": entries,
        "ai_analysis": analysis,
        "created_at": now,
        "updated_at": now,
    }

    await db.outlet_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc}, upsert=True,
    )

    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "completed", "updated_at": now}}
    )

    doc.pop("_id", None)
    return doc


# ============ AIM (Addictions & Irritations Manager) ============

@router.get("/aim/options")
async def get_aim_options(user: dict = Depends(get_current_user)):
    """Get life areas and occurrence options for AIM."""
    return {
        "life_areas": [{"id": la, "name": LIFE_AREA_LABELS.get(la, la)} for la in LIFE_AREAS],
        "occurrences": AIM_OCCURRENCE_OPTIONS,
    }


@router.post("/aim/{session_id}/save")
async def aim_save(session_id: str, data: AIMSaveRequest, user: dict = Depends(get_current_user)):
    """Save addictions and irritations data."""
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user["user_id"]})
    if not session:
        raise HTTPException(404, "Session not found")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": f"AIM-{uuid.uuid4().hex[:8].upper()}",
        "session_id": session_id,
        "user_id": user["user_id"],
        "addictions": [a.model_dump() for a in data.addictions],
        "irritations": [i.model_dump() for i in data.irritations],
        "ai_analysis": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.aim_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc}, upsert=True,
    )

    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "in_progress", "updated_at": now}}
    )

    doc.pop("_id", None)
    return doc


@router.post("/aim/{session_id}/analyze")
async def aim_analyze(session_id: str, user: dict = Depends(get_current_user)):
    """AI analyzes addictions and irritations, suggests corrective actions."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured")

    aim = await db.aim_reflections.find_one({"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not aim:
        raise HTTPException(404, "AIM data not found. Save addictions/irritations first.")

    try:
        analysis = await analyze_aim(aim.get("addictions", []), aim.get("irritations", []), user_id=user["user_id"], session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AIM analysis failed: {e}")
        raise HTTPException(502, detail={"code": "ai_error", "message": "AI analysis failed. Please try again."})

    now = datetime.now(timezone.utc).isoformat()
    await db.aim_reflections.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": {"ai_analysis": analysis, "updated_at": now}}
    )

    await db.breakthrough_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "completed", "updated_at": now}}
    )

    return {"session_id": session_id, "analysis": analysis}
