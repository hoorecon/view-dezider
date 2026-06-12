"""Admin routes — Import-URL Analytics (Super-Admin).

The learning & enhancement loop for the Import-from-URL feature: every run is
recorded by core/url_telemetry.py (user inputs URL + the 4 accuracy hints +
AI engine + classified page type + route taken + extraction outcome + the
EXACT prompt/raw LLM response + 👍/👎 user feedback). These endpoints power the
/admin/import-analytics dashboard.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_super_admin
from core import url_telemetry
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
