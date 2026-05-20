"""Admin-only Regression Suite endpoints."""
from __future__ import annotations

import io
import json
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.database import db
from core.regression import registry, runner
from routes.admin import ADMIN_ROLES, get_current_user, get_user_role

router = APIRouter()


@router.get("/admin/regression/suites")
async def list_suites(user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    suites = [s.to_meta() for s in registry.list_suites()]
    # Group by feature for the UI
    features: dict = {}
    for s in suites:
        features.setdefault(s["feature"], []).append(s)
    # Sort: user-app + admin features first (alphabetical), then "ACM Coverage" suites last.
    def _sort_key(feature_name: str) -> tuple:
        # 0 = top priority, 1 = ACM coverage at bottom
        is_acm = feature_name.startswith("ACM Coverage")
        return (1 if is_acm else 0, feature_name)
    ordered = sorted(features.items(), key=lambda kv: _sort_key(kv[0]))
    latest = await runner.latest_per_suite()
    return {
        "features": [{"feature": f, "suites": items} for f, items in ordered],
        "total_suites": len(suites),
        "total_cases": sum(s["case_count"] for s in suites),
        "latest_per_suite": latest,
    }


class RunRequest(BaseModel):
    level: str = "smoke"        # smoke | functional | both
    kind: str = "api"           # api | ui | both
    suite_ids: Optional[List[str]] = None  # None or [] = all matching


class RerunRequest(BaseModel):
    """Re-run only the failed cases from a previous run, optionally applying
    auto-remediation steps first."""
    source_run_id: str
    fix: bool = False             # if True, apply auto-fix steps before re-running
    case_ids: Optional[List[str]] = None   # subset of failed cases (None = all failed)


@router.post("/admin/regression/run")
async def trigger_run(payload: RunRequest, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    if payload.level not in ("smoke", "functional", "both"):
        raise HTTPException(400, "level must be smoke|functional|both")
    if payload.kind not in ("api", "ui", "both"):
        raise HTTPException(400, "kind must be api|ui|both")
    result = await runner.run(
        level=payload.level,
        kind=payload.kind,
        suite_ids=payload.suite_ids or None,
        triggered_by="manual",
        triggered_by_user=user.get("email") or user.get("id"),
    )
    return result.to_dict()


@router.post("/admin/regression/rerun-failed")
async def rerun_failed(payload: RerunRequest, user: dict = Depends(get_current_user)):
    """Re-run only the failed cases from a prior run. If `fix=true`, apply
    safe auto-remediation steps before re-running (refresh ACM cache, re-seed
    admin data with the existing seed marker, drop stale unique indexes that
    fail the seed). Returns a new RunResult covering only those cases.
    """
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    source = await db.regression_runs.find_one({"run_id": payload.source_run_id}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Source run not found")

    # Collect failed (suite_id, case_id) pairs from the source run
    failed_pairs: list[tuple[str, str]] = []
    for sr in source.get("suites", []):
        for cr in sr.get("cases", []):
            if cr.get("status") == "failed":
                if payload.case_ids and cr.get("case_id") not in payload.case_ids:
                    continue
                failed_pairs.append((sr.get("suite_id"), cr.get("case_id")))

    if not failed_pairs:
        raise HTTPException(400, "No failed cases to re-run in the source run")

    fix_actions: list[str] = []
    if payload.fix:
        # ── Auto-fix step 1: refresh ACM cache (resolves stale role/quota maps)
        try:
            from core.acm_engine import refresh_acm_cache
            await refresh_acm_cache()
            fix_actions.append("acm_cache_refreshed")
        except Exception as e:
            fix_actions.append(f"acm_refresh_failed:{type(e).__name__}")
        # ── Auto-fix step 2: ensure admin seed marker exists (drops stale
        # unique indexes that crashed the seed previously)
        try:
            from core.admin_data_seed import seed_admin_data
            res = await seed_admin_data(force=False)
            fix_actions.append(f"seed_status:{res.get('seed_version','?')}")
        except Exception as e:
            fix_actions.append(f"seed_failed:{type(e).__name__}")
        # ── Auto-fix step 3: ensure tier_matrix is properly seeded
        try:
            from core.database import db as _db
            cnt = await _db.tier_matrix.count_documents({})
            if cnt < 100:
                from routes.tier_matrix import _smart_seed as _tm_smart_seed
                await _db.tier_matrix.delete_many({})
                await _tm_smart_seed()
                fix_actions.append("tier_matrix_reseeded")
        except Exception as e:
            fix_actions.append(f"tm_reseed_failed:{type(e).__name__}")

    # Run only the suites that have failed cases. The runner re-runs *all*
    # cases in a suite (it doesn't filter by case_id), so we may include
    # passing cases — that's intentional, it verifies they still pass.
    failed_suite_ids = sorted({sid for sid, _ in failed_pairs})
    result = await runner.run(
        level=source.get("level_filter", "smoke"),
        kind=source.get("kind_filter", "api"),
        suite_ids=failed_suite_ids,
        triggered_by=f"rerun_failed{'_fix' if payload.fix else ''}",
        triggered_by_user=user.get("email") or user.get("id"),
    )
    out = result.to_dict()
    out["source_run_id"] = payload.source_run_id
    out["fix_applied"] = payload.fix
    out["fix_actions"] = fix_actions
    out["rerun_case_count"] = len(failed_pairs)
    return out



async def list_runs(limit: int = Query(20, le=100),
                    user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    cur = db.regression_runs.find({}, {"_id": 0, "suites": 0}).sort("triggered_at", -1).limit(limit)
    return {"runs": await cur.to_list(limit)}


@router.get("/admin/regression/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    doc = await db.regression_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    return doc


@router.get("/admin/regression/latest")
async def latest(user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    return {"latest_per_suite": await runner.latest_per_suite()}


# ─────────────────────────────────────────────────────────────────────────────
# Download / Delete — manual result management
# ─────────────────────────────────────────────────────────────────────────────
def _build_zip_for_runs(run_docs: list) -> bytes:
    """Build a ZIP in-memory containing run JSON + HTML summary."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Per-run JSON
        for doc in run_docs:
            run_id = doc.get("run_id", "unknown")
            zf.writestr(f"runs/{run_id}.json", json.dumps(doc, indent=2, default=str))
        # Top-level index
        index = {
            "exported_at": run_docs[0].get("triggered_at") if run_docs else None,
            "run_count": len(run_docs),
            "runs": [
                {
                    "run_id": d.get("run_id"),
                    "triggered_at": d.get("triggered_at"),
                    "triggered_by": d.get("triggered_by"),
                    "overall_status": d.get("overall_status"),
                    "totals": d.get("totals"),
                    "duration_ms": d.get("duration_ms"),
                }
                for d in run_docs
            ],
        }
        zf.writestr("index.json", json.dumps(index, indent=2, default=str))
        # Simple HTML summary
        html_rows = []
        for d in run_docs:
            t = d.get("totals", {})
            html_rows.append(
                f"<tr><td>{d.get('run_id', '')}</td>"
                f"<td>{d.get('triggered_at', '')}</td>"
                f"<td>{d.get('triggered_by', '')}</td>"
                f"<td><b>{d.get('overall_status', '')}</b></td>"
                f"<td>{t.get('passed', 0)}</td>"
                f"<td>{t.get('failed', 0)}</td>"
                f"<td>{t.get('skipped', 0)}</td>"
                f"<td>{t.get('manual_pending', 0)}</td>"
                f"<td>{d.get('duration_ms', 0)} ms</td></tr>"
            )
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Regression Runs Export</title>"
            "<style>body{font-family:system-ui;padding:24px;background:#f9fafb}"
            "table{border-collapse:collapse;width:100%;background:#fff}"
            "th,td{padding:8px 12px;border:1px solid #e5e7eb;text-align:left;font-size:13px}"
            "th{background:#f3f4f6}</style></head><body>"
            f"<h1>Regression Runs — {len(run_docs)} run(s)</h1>"
            "<table><thead><tr><th>Run ID</th><th>Triggered At</th><th>By</th>"
            "<th>Status</th><th>Passed</th><th>Failed</th><th>Skipped</th>"
            "<th>Manual</th><th>Duration</th></tr></thead><tbody>"
            f"{''.join(html_rows)}</tbody></table></body></html>"
        )
        zf.writestr("summary.html", html)
    buf.seek(0)
    return buf.getvalue()


@router.get("/admin/regression/runs/{run_id}/download")
async def download_single(run_id: str, user: dict = Depends(get_current_user)):
    """Download a single run as a ZIP (JSON detail + HTML summary)."""
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    doc = await db.regression_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    zip_bytes = _build_zip_for_runs([doc])
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="regression_{run_id}.zip"'},
    )


class BulkRunsRequest(BaseModel):
    run_ids: List[str]


@router.post("/admin/regression/runs/download-bulk")
async def download_bulk(payload: BulkRunsRequest, user: dict = Depends(get_current_user)):
    """Download multiple runs (selected) as a single ZIP."""
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    if not payload.run_ids:
        raise HTTPException(400, "run_ids cannot be empty")
    docs = await db.regression_runs.find(
        {"run_id": {"$in": payload.run_ids}}, {"_id": 0},
    ).to_list(len(payload.run_ids))
    if not docs:
        raise HTTPException(404, "No matching runs")
    zip_bytes = _build_zip_for_runs(docs)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="regression_bulk_{len(docs)}.zip"'},
    )


@router.delete("/admin/regression/runs/{run_id}")
async def delete_single(run_id: str, user: dict = Depends(get_current_user)):
    """Delete a single run."""
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    res = await db.regression_runs.delete_one({"run_id": run_id})
    if not res.deleted_count:
        raise HTTPException(404, "Run not found")
    return {"deleted": 1, "run_id": run_id}


@router.post("/admin/regression/runs/delete-bulk")
async def delete_bulk(payload: BulkRunsRequest, user: dict = Depends(get_current_user)):
    """Delete multiple runs by id list."""
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    if not payload.run_ids:
        raise HTTPException(400, "run_ids cannot be empty")
    res = await db.regression_runs.delete_many({"run_id": {"$in": payload.run_ids}})
    return {"deleted": res.deleted_count, "requested": len(payload.run_ids)}
