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

    from core.posthog_client import track as ph_track
    ph_track(user["user_id"], "eg_session_completed", {"final_step": "outlet"})

    doc.pop("_id", None)
    return doc


async def verify_aim_access(user: dict):
    """Ensure user is on an active Subscription plan or Admin/Tester role.

    Restricts Free plan and On-Demand plan users from accessing AIM Manager.
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

    # Testers and paid user_type override
    if utype in {"admin", "super_admin", "co_admin", "alpha", "beta", "unit_tester", "integration_tester", "paid"}:
        return True

    # 3. Check credit wallet subscription status
    wallet = await db.credit_wallets.find_one(
        {"user_id": user_id}, {"_id": 0, "subscription_status": 1, "current_plan": 1}
    )
    if wallet:
        st = str(wallet.get("subscription_status") or "").lower().strip()
        cp = str(wallet.get("current_plan") or "").lower().strip()
        if st in {"active", "manual", "pending"} and cp and cp not in {"none", "free"} and not cp.startswith("on_demand"):
            return True

    # 4. Check active subscription plan on user doc
    if splan and splan not in {"none", "free", ""} and not splan.startswith("on_demand"):
        return True

    # 5. Block Free and On-Demand users
    raise HTTPException(
        status_code=403,
        detail="AIM Manager (Addictions & Irritations) is not available for Free or On-Demand plans. Please upgrade to a subscription plan (Basic, Pro, Premium) to access AIM Manager."
    )


# ============ AIM (Addictions & Irritations Manager) ============

@router.get("/aim/options")
async def get_aim_options(user: dict = Depends(get_current_user)):
    """Get life areas and occurrence options for AIM."""
    await verify_aim_access(user)
    return {
        "life_areas": [{"id": la, "name": LIFE_AREA_LABELS.get(la, la)} for la in LIFE_AREAS],
        "occurrences": AIM_OCCURRENCE_OPTIONS,
    }


@router.post("/aim/{session_id}/save")
async def aim_save(session_id: str, data: AIMSaveRequest, user: dict = Depends(get_current_user)):
    """Save addictions and irritations data."""
    await verify_aim_access(user)
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
    await verify_aim_access(user)
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

    from core.posthog_client import track as ph_track
    ph_track(user["user_id"], "eg_session_completed", {"final_step": "aim"})

    return {"session_id": session_id, "analysis": analysis}
