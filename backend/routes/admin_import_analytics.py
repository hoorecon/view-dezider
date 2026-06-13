"""Admin routes — Import-URL Analytics (Super-Admin).

The learning & enhancement loop for the Import-from-URL feature: every run is
recorded by core/url_telemetry.py (user inputs URL + the 4 accuracy hints +
AI engine + classified page type + route taken + extraction outcome + the
EXACT prompt/raw LLM response + 👍/👎 user feedback). These endpoints power the
/admin/import-analytics dashboard.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_super_admin
from core import url_telemetry
from core import url_prompt_tuning
from core import engine_recos
from core.url_pagetype import PAGE_TYPES

router = APIRouter(prefix="/admin/import-analytics", tags=["admin-import-analytics"])

ROUTES = ("deterministic_hier", "deterministic_flat", "ai_extraction",
          "deterministic_fallback", "llm_flat_fallback")


@router.get("/summary")
async def import_analytics_summary(days: int = 30,
                                   admin: dict = Depends(require_super_admin)):
    """KPIs + breakdowns by page type / AI provider / pipeline route."""
    return await url_telemetry.summary(days=max(1, min(days, 365)))


@router.get("/runs")
async def import_analytics_runs(days: int = 30, page_type: Optional[str] = None,
                                route: Optional[str] = None, status: Optional[str] = None,
                                feedback: Optional[str] = None,
                                limit: int = 50, skip: int = 0,
                                admin: dict = Depends(require_super_admin)):
    """Run list (no prompt bodies — drill into a run for those)."""
    if page_type and page_type not in PAGE_TYPES:
        raise HTTPException(400, f"page_type must be one of {PAGE_TYPES}")
    if route and route not in ROUTES:
        raise HTTPException(400, f"route must be one of {ROUTES}")
    return await url_telemetry.list_runs(days=max(1, min(days, 365)),
                                         page_type=page_type, route=route,
                                         status=status, feedback=feedback,
                                         limit=limit, skip=max(0, skip))


@router.get("/runs/{run_id}")
async def import_analytics_run_detail(run_id: str,
                                      admin: dict = Depends(require_super_admin)):
    """Full run detail incl. exact prompt + raw LLM response (prompt-tuning)."""
    run = await url_telemetry.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


# ── AI Auto-Tune: AI reads failing runs per page type → proposes prompt edits
# → admin approves → override goes LIVE for all subsequent extractions. ──
@router.post("/tuning/generate")
async def tuning_generate(days: int = 30, page_type: Optional[str] = None,
                          admin: dict = Depends(require_super_admin)):
    """Run the AI prompt-tuning analysis (precise tier, metered to the admin).
    Covers page types AND deep-import stages. Also runs automatically every
    24h. Skips keys with no failing runs or a suggestion already pending."""
    if page_type and page_type not in url_prompt_tuning.TUNE_KEYS:
        raise HTTPException(400, f"page_type must be one of {url_prompt_tuning.TUNE_KEYS}")
    return await url_prompt_tuning.generate_suggestions(
        admin["user_id"], days=max(1, min(days, 365)), page_type=page_type)


@router.get("/tuning")
async def tuning_list(admin: dict = Depends(require_super_admin)):
    """Suggestions (newest first) + the currently ACTIVE prompt overrides."""
    return {"suggestions": await url_prompt_tuning.list_suggestions(),
            "active_overrides": await url_prompt_tuning.list_overrides()}


@router.post("/tuning/{suggestion_id}/approve")
async def tuning_approve(suggestion_id: str, admin: dict = Depends(require_super_admin)):
    """Approve → the proposed guidance becomes the LIVE extraction prompt block."""
    try:
        return await url_prompt_tuning.decide(suggestion_id, admin["user_id"], approve=True)
    except KeyError:
        raise HTTPException(404, "Suggestion not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/tuning/{suggestion_id}/reject")
async def tuning_reject(suggestion_id: str, admin: dict = Depends(require_super_admin)):
    try:
        return await url_prompt_tuning.decide(suggestion_id, admin["user_id"], approve=False)
    except KeyError:
        raise HTTPException(404, "Suggestion not found")
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.delete("/tuning/override/{page_type}")
async def tuning_revert(page_type: str, admin: dict = Depends(require_super_admin)):
    """Revert a tunable key (page type / deep-import stage) to its built-in default."""
    if page_type not in url_prompt_tuning.TUNE_KEYS:
        raise HTTPException(400, f"page_type must be one of {url_prompt_tuning.TUNE_KEYS}")
    if not await url_prompt_tuning.revert_override(page_type, admin["user_id"]):
        raise HTTPException(404, "No active override for this page type")
    return {"page_type": page_type, "reverted": True}


# ── Auto-Approve config + actions ───────────────────────────────────────────
@router.get("/tuning/autoapprove")
async def autoapprove_get(_admin: dict = Depends(require_super_admin)):
    return await url_prompt_tuning.get_auto_approve_config()


@router.put("/tuning/autoapprove")
async def autoapprove_set(body: Dict[str, Any],
                          admin: dict = Depends(require_super_admin)):
    try:
        return await url_prompt_tuning.set_auto_approve_config(body, admin["user_id"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tuning/autoapprove/run")
async def autoapprove_run_now(_admin: dict = Depends(require_super_admin)):
    """Run the auto-approve pass on demand (admin tap on the dashboard)."""
    return await url_prompt_tuning.auto_approve_pass()


@router.post("/tuning/bulk")
async def tuning_bulk(body: Dict[str, Any],
                      admin: dict = Depends(require_super_admin)):
    """One-click bulk approve / reject of all pending suggestions.
    Dedupes per page-type before applying so only the latest survives.
    Body: { action: 'approve' | 'reject' }."""
    action = (body or {}).get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action must be 'approve' or 'reject'")
    return await url_prompt_tuning.bulk_decide(admin["user_id"], approve=(action == "approve"))


# ── Engine tiering (margin protection) ──────────────────────────────────────
@router.get("/quality-floor")
async def get_quality_floor(admin: dict = Depends(require_super_admin)):
    """Read the current import quality floor — the min factor count below
    which a run is stamped `partial` instead of `success`."""
    return {"min_factors": await engine_recos.get_quality_floor(),
            "default": engine_recos.DEFAULT_QUALITY_FLOOR}


@router.put("/quality-floor")
async def set_quality_floor(body: Dict[str, Any],
                            admin: dict = Depends(require_super_admin)):
    """Tune the import quality floor. Body: { min_factors: int 1..50 }."""
    try:
        mf = int(body.get("min_factors") or 0)
        val = await engine_recos.set_quality_floor(mf, admin["user_id"])
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return {"min_factors": val}


@router.get("/engine-recos")
async def engine_recommendations(days: int = 30,
                                 admin: dict = Depends(require_super_admin)):
    """Per-deep-import-stage engine stats (success % + avg credits per tier,
    from the AI call trace) + a conservative tier recommendation."""
    return await engine_recos.compute_recos(days=max(1, min(days, 365)))


@router.put("/engine-tiers")
async def set_engine_tier(body: Dict[str, Any],
                          admin: dict = Depends(require_super_admin)):
    """Set a deep-import stage's AI tier. Body: { stage, tier } where tier is
    fast | precise | job ('job' = follow the tier the user picked)."""
    try:
        tiers = await engine_recos.set_stage_tier(
            str(body.get("stage") or ""), str(body.get("tier") or ""), admin["user_id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"tiers": tiers}
