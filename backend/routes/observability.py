"""
Observability + admin metrics endpoints.

Exposes:
  - GET /api/metrics           Prometheus text format (auth via METRICS_TOKEN if set)
  - GET /api/metrics/json      JSON snapshot of counters + histograms (admin only)
  - GET /api/health/live       Liveness probe (no DB)
  - GET /api/health/version    Build/version info
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response

from core.auth import require_admin
from core.hardening import metrics, METRICS_ENABLED, METRICS_TOKEN

router = APIRouter(tags=["observability"])

VERSION = os.environ.get("DEZIDER_VERSION", "alpha-2026-05-04")
COMMIT = os.environ.get("DEZIDER_COMMIT", "")


@router.get("/metrics")
async def prometheus_metrics(authorization: Optional[str] = Header(None)):
    """Prometheus scrape endpoint. If METRICS_TOKEN is set, callers must pass
    `Authorization: Bearer <METRICS_TOKEN>`. Otherwise it's open (use only
    if the endpoint is on a private VPC).
    """
    if not METRICS_ENABLED:
        raise HTTPException(404, "Metrics disabled")
    if METRICS_TOKEN:
        expected = f"Bearer {METRICS_TOKEN}"
        if (authorization or "") != expected:
            raise HTTPException(401, "Invalid metrics token")
    return Response(content=metrics.render_prometheus(),
                    media_type="text/plain; version=0.0.4")


@router.get("/metrics/json")
async def metrics_json(user: dict = Depends(require_admin)):
    """Admin-only JSON snapshot."""
    if not METRICS_ENABLED:
        raise HTTPException(404, "Metrics disabled")
    return metrics.render_json()


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/version")
async def version():
    return {
        "version": VERSION,
        "commit": COMMIT,
        "env": os.environ.get("DEZIDER_ENV", "dev"),
    }
