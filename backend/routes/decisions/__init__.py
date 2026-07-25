"""Decisions module — aggregates all decision-related sub-routers into a single
`router` so the public import contract (`from routes.decisions import router`)
remains unchanged after the refactor.

Sub-modules:
  crud             — PRR decision CRUD + clone
  assessment       — XLS / Google Sheet export-import + per-cell AI assess
  templates        — save-as-template, list, use, import, update, delete
  admin            — setup, promote/demote, admin users, template authorization
  test123          — quick-decision sessions
  assessment_modes — decision-mode self assessment
  journal          — decision journal, reminders, linkable items
  dashboard        — stats + folders
  sharing          — step sharing / contribute / merge
  mpps             — MPPS action-plan CSV/PDF downloads

Shared business logic lives in `services.py`.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .assessment import router as assessment_router
from .templates import router as templates_router
from .admin import router as admin_router
from .test123 import router as test123_router
from .assessment_modes import router as assessment_modes_router
from .journal import router as journal_router
from .dashboard import router as dashboard_router
from .sharing import router as sharing_router
from .mpps import router as mpps_router
from .links import router as links_router
from .formulas import router as formulas_router

router = APIRouter(tags=["Decisions"])

for _sub in (
    crud_router,
    assessment_router,
    templates_router,
    admin_router,
    test123_router,
    assessment_modes_router,
    journal_router,
    dashboard_router,
    sharing_router,
    mpps_router,
    links_router,
    formulas_router,
):
    router.include_router(_sub)

__all__ = ["router"]
