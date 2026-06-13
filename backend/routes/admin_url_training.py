"""
Admin URL-Training Console — REST routes.

GET    /api/admin/url-training/examples              — list curated examples
POST   /api/admin/url-training/examples              — create or upsert
PUT    /api/admin/url-training/examples/{id}         — update
DELETE /api/admin/url-training/examples/{id}         — remove
POST   /api/admin/url-training/examples/{id}/run     — run ONE example now
POST   /api/admin/url-training/run-suite             — run ALL pinned regression examples now
GET    /api/admin/url-training/runs                  — list run history (optional ?example_id=)
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import require_super_admin
from core import url_training

router = APIRouter(prefix="/admin/url-training", tags=["admin-url-training"])


@router.get("/examples")
async def list_examples(_admin: dict = Depends(require_super_admin)):
    rows = await url_training.list_examples()
    pinned_count = sum(1 for r in rows if r.get("is_regression_pinned"))
    return {"items": rows,
            "pinned_count": pinned_count,
            "pin_limit": url_training.REGRESSION_MAX_PINS}


@router.post("/examples")
async def create_example(body: Dict[str, Any],
                         admin: dict = Depends(require_super_admin)):
    try:
        return await url_training.upsert_example(body, admin["user_id"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.put("/examples/{example_id}")
async def update_example(example_id: str, body: Dict[str, Any],
                         admin: dict = Depends(require_super_admin)):
    body["id"] = example_id
    try:
        return await url_training.upsert_example(body, admin["user_id"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/examples/{example_id}")
async def delete_example(example_id: str,
                         _admin: dict = Depends(require_super_admin)):
    ok = await url_training.delete_example(example_id)
    if not ok:
        raise HTTPException(404, "Training example not found")
    return {"deleted": True}


@router.post("/examples/{example_id}/run")
async def run_example(example_id: str,
                      admin: dict = Depends(require_super_admin)):
    try:
        return await url_training.run_single(
            example_id, admin["user_id"], trigger="manual_single")
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/run-suite")
async def run_regression_suite(admin: dict = Depends(require_super_admin)):
    return await url_training.run_suite(admin["user_id"], trigger="manual")


@router.get("/runs")
async def list_runs(example_id: Optional[str] = Query(default=None),
                    limit: int = Query(default=100, ge=1, le=500),
                    _admin: dict = Depends(require_super_admin)):
    rows = await url_training.list_runs(example_id=example_id, limit=limit)
    return {"items": rows}
