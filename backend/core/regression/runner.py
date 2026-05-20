"""Async regression-suite runner. Executes registered suites, persists results."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from core.database import db
from core.regression import registry
from core.regression.models import (
    CaseResult,
    RunResult,
    Suite,
    SuiteResult,
    TestContext,
)

logger = logging.getLogger(__name__)

# Internal base URL (calls go to the local API, bypassing nginx/cloudflare)
DEFAULT_BASE_URL = os.getenv("REGRESSION_BASE_URL", "http://localhost:8001")
HISTORY_RETENTION_DAYS = int(os.getenv("REGRESSION_RETENTION_DAYS", "7"))

# Default service account creds for the runner. Override via env in prod.
ADMIN_EMAIL = os.getenv("REGRESSION_ADMIN_EMAIL", "admin@test.com")
ADMIN_PASSWORD = os.getenv("REGRESSION_ADMIN_PASSWORD", "AdminPass2026!")
USER_EMAIL = os.getenv("REGRESSION_USER_EMAIL", "harden_1777921741@example.com")
USER_PASSWORD = os.getenv("REGRESSION_USER_PASSWORD", "HardenPass2026!")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _login(http: httpx.AsyncClient, email: str, password: str) -> Optional[str]:
    try:
        r = await http.post("/api/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            return None
        data = r.json()
        # Try common token keys across auth implementations
        return (
            data.get("session_token")
            or data.get("access_token")
            or data.get("token")
        )
    except Exception as e:
        logger.warning(f"Login failed for {email}: {e}")
        return None


async def _build_context(base_url: str) -> TestContext:
    client = httpx.AsyncClient(base_url=base_url, timeout=20.0)
    admin_token = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    user_token = await _login(client, USER_EMAIL, USER_PASSWORD)
    return TestContext(http=client, base_url=base_url, admin_token=admin_token, user_token=user_token)


async def _run_case(ctx: TestContext, case) -> CaseResult:
    started = _now_iso()
    t0 = time.monotonic()
    try:
        out = await asyncio.wait_for(case.body(ctx), timeout=30)
        latency = int((time.monotonic() - t0) * 1000)
        passed = bool(out.get("passed", False))
        return CaseResult(
            case_id=case.id, name=case.name, level=case.level,
            status="passed" if passed else "failed",
            message=out.get("message", "OK" if passed else "Assertion failed"),
            latency_ms=latency,
            traceback=out.get("traceback"),
            started_at=started, finished_at=_now_iso(),
        )
    except asyncio.TimeoutError:
        return CaseResult(
            case_id=case.id, name=case.name, level=case.level,
            status="failed", message="Timeout after 30s",
            latency_ms=int((time.monotonic() - t0) * 1000),
            started_at=started, finished_at=_now_iso(),
        )
    except Exception as e:
        return CaseResult(
            case_id=case.id, name=case.name, level=case.level,
            status="failed", message=f"{type(e).__name__}: {e}",
            traceback=traceback.format_exc(),
            latency_ms=int((time.monotonic() - t0) * 1000),
            started_at=started, finished_at=_now_iso(),
        )


def _suite_matches(s: Suite, kind_filter: str, suite_ids: Optional[List[str]]) -> bool:
    if suite_ids and s.id not in suite_ids:
        return False
    if kind_filter != "both" and s.kind != kind_filter:
        return False
    return True


async def run(
    *,
    level: str = "smoke",
    kind: str = "api",
    suite_ids: Optional[List[str]] = None,
    triggered_by: str = "manual",
    triggered_by_user: Optional[str] = None,
) -> RunResult:
    """Execute regression suites and persist result to db.regression_runs.

    level: "smoke" | "functional" | "both"
    kind:  "api" | "ui" | "both"
    suite_ids: subset filter (None or empty = all matching suites)
    """
    t_start = time.monotonic()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    suites_to_run = [s for s in registry.list_suites() if _suite_matches(s, kind, suite_ids)]

    ctx = await _build_context(DEFAULT_BASE_URL)
    suite_results: List[SuiteResult] = []

    try:
        for suite in suites_to_run:
            cases_to_run = [
                c for c in suite.cases
                if level == "both" or c.level == level or (level == "functional" and c.level == "smoke")
            ]
            sr = SuiteResult(
                suite_id=suite.id, feature=suite.feature, module=suite.module,
                kind=suite.kind, title=suite.title,
            )
            if suite.kind == "ui":
                # UI suites are declarative-only in core; mark as manual_pending.
                # When the Playwright sidecar is wired in Phase B.2, the
                # runner can dispatch to it via HTTP and capture real results.
                for case in cases_to_run:
                    sr.cases.append(CaseResult(
                        case_id=case.id, name=case.name, level=case.level,
                        status="manual_pending",
                        message=f"UI spec at {suite.ui_spec_path or '/docs/regression/ui/'} — pending Playwright sidecar runner.",
                        started_at=_now_iso(), finished_at=_now_iso(),
                    ))
            else:
                for case in cases_to_run:
                    sr.cases.append(await _run_case(ctx, case))
            suite_results.append(sr)
    finally:
        await ctx.http.aclose()

    result = RunResult(
        run_id=run_id,
        triggered_at=_now_iso(),
        triggered_by=triggered_by,
        triggered_by_user=triggered_by_user,
        level_filter=level,
        kind_filter=kind,
        suite_ids=suite_ids or [],
        suites=suite_results,
        duration_ms=int((time.monotonic() - t_start) * 1000),
        finished_at=_now_iso(),
    )

    # Persist + prune
    try:
        await db.regression_runs.insert_one({**result.to_dict(), "_id": run_id})
        await _prune_old_runs()
    except Exception as e:
        logger.error(f"Failed to persist regression run: {e}", exc_info=True)

    return result


async def _prune_old_runs() -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)).isoformat()
    res = await db.regression_runs.delete_many({"triggered_at": {"$lt": cutoff}})
    if res.deleted_count:
        logger.info(f"Pruned {res.deleted_count} regression runs older than {HISTORY_RETENTION_DAYS}d")


async def latest_per_suite() -> dict:
    """Returns {suite_id: latest CaseResult-style summary} across all stored runs."""
    out = {}
    async for run_doc in db.regression_runs.find({}, {"_id": 0}).sort("triggered_at", -1):
        for s in run_doc.get("suites", []):
            if s["suite_id"] not in out:
                out[s["suite_id"]] = {
                    "run_id": run_doc["run_id"],
                    "triggered_at": run_doc["triggered_at"],
                    "triggered_by": run_doc["triggered_by"],
                    "status": s["status"],
                    "passed": s["passed"],
                    "failed": s["failed"],
                    "skipped": s["skipped"],
                    "manual_pending": s.get("manual_pending", 0),
                }
    return out
